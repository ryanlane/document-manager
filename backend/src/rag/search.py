import argparse
import logging
from typing import List, Tuple, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text, func, literal

from src.db.session import get_db
from src.db.models import Entry, RawFile
from src.llm_client import embed_text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Search mode constants
SEARCH_MODE_VECTOR = 'vector'
SEARCH_MODE_KEYWORD = 'keyword'
SEARCH_MODE_HYBRID = 'hybrid'

def search_keyword_only(db: Session, query: str, k: int = 5, filters: dict = None) -> List[dict]:
    """
    Perform keyword-only search using PostgreSQL full-text search (BM25-like).
    Returns list of dicts with entry and rank score.
    """
    # Build the tsquery from the search query
    search_query = ' & '.join(query.split())  # Convert to AND query
    
    sql = text("""
        SELECT e.id, 
               ts_rank_cd(e.search_vector, plainto_tsquery('english', :query)) as rank
        FROM entries e
        JOIN raw_files rf ON e.file_id = rf.id
        WHERE e.search_vector @@ plainto_tsquery('english', :query)
        ORDER BY rank DESC
        LIMIT :limit
    """)
    
    results = db.execute(sql, {"query": query, "limit": k}).fetchall()
    return [{"id": r[0], "keyword_score": float(r[1])} for r in results]


def search_entries_semantic(
    db: Session, 
    query: str, 
    k: int = 5, 
    filters: dict = None,
    mode: str = SEARCH_MODE_HYBRID,
    vector_weight: float = 0.7
) -> List[dict]:
    """
    Search entries with support for vector-only, keyword-only, or hybrid modes.
    
    Args:
        db: Database session
        query: Search query string
        k: Number of results to return
        filters: Optional filters (tags, author, extension, category, date_start, date_end)
        mode: Search mode - 'vector', 'keyword', or 'hybrid'
        vector_weight: Weight for vector score in hybrid mode (0-1), keyword gets (1-vector_weight)
    
    Returns:
        List of Entry objects (for backward compatibility) or dicts with scores if mode != 'vector'
    """
    
    # Keyword-only mode
    if mode == SEARCH_MODE_KEYWORD:
        keyword_results = search_keyword_only(db, query, k * 2, filters)
        entry_ids = [r['id'] for r in keyword_results[:k]]
        entries = db.query(Entry).filter(Entry.id.in_(entry_ids)).all()
        # Sort by original keyword rank
        id_to_rank = {r['id']: i for i, r in enumerate(keyword_results)}
        entries.sort(key=lambda e: id_to_rank.get(e.id, 999))
        return entries
    
    # Get vector embedding for query
    q_emb = embed_text(query)
    if not q_emb:
        logger.error("Failed to embed query")
        # Fallback to keyword search if embedding fails
        if mode == SEARCH_MODE_HYBRID:
            logger.info("Falling back to keyword search")
            return search_entries_semantic(db, query, k, filters, SEARCH_MODE_KEYWORD)
        return []
    
    # Vector-only mode
    if mode == SEARCH_MODE_VECTOR:
        stmt = db.query(Entry).join(RawFile)
        
        # Apply Filters
        if filters:
            if filters.get('tags') and len(filters['tags']) > 0:
                stmt = stmt.filter(Entry.tags.overlap(filters['tags']))
            if filters.get('author'):
                stmt = stmt.filter(Entry.author.ilike(f"%{filters['author']}%"))
            if filters.get('extension'):
                stmt = stmt.filter(RawFile.extension == filters['extension'])
            if filters.get('category'):
                stmt = stmt.filter(Entry.category.ilike(f"%{filters['category']}%"))
            if filters.get('date_start'):
                stmt = stmt.filter(Entry.created_hint >= filters['date_start'])
            if filters.get('date_end'):
                stmt = stmt.filter(Entry.created_hint <= filters['date_end'])
        
        results = stmt.order_by(Entry.embedding.cosine_distance(q_emb)).limit(k).all()
        return results
    
    # Hybrid mode: Combine vector similarity with BM25 keyword ranking
    keyword_weight = 1.0 - vector_weight
    
    # Use raw SQL for hybrid ranking
    # This query computes both vector distance and keyword rank, then combines them
    sql = text("""
        WITH vector_scores AS (
            SELECT e.id, 
                   1.0 - (e.embedding <=> :embedding) as vector_score
            FROM entries e
            WHERE e.embedding IS NOT NULL
        ),
        keyword_scores AS (
            SELECT e.id,
                   COALESCE(ts_rank_cd(e.search_vector, plainto_tsquery('english', :query)), 0) as keyword_score
            FROM entries e
        ),
        combined AS (
            SELECT 
                v.id,
                v.vector_score,
                COALESCE(k.keyword_score, 0) as keyword_score,
                (v.vector_score * :vector_weight + COALESCE(k.keyword_score, 0) * :keyword_weight) as combined_score
            FROM vector_scores v
            LEFT JOIN keyword_scores k ON v.id = k.id
            ORDER BY combined_score DESC
            LIMIT :limit
        )
        SELECT id, vector_score, keyword_score, combined_score FROM combined
    """)
    
    results = db.execute(sql, {
        "embedding": str(q_emb),
        "query": query,
        "vector_weight": vector_weight,
        "keyword_weight": keyword_weight,
        "limit": k
    }).fetchall()
    
    # Fetch the actual Entry objects
    entry_ids = [r[0] for r in results]
    if not entry_ids:
        return []
    
    entries = db.query(Entry).filter(Entry.id.in_(entry_ids)).all()
    
    # Build a map of id to scores
    score_map = {r[0]: {'vector_score': r[1], 'keyword_score': r[2], 'combined_score': r[3]} for r in results}
    
    # Sort entries by combined score and attach scores as attributes
    entries.sort(key=lambda e: score_map.get(e.id, {}).get('combined_score', 0), reverse=True)
    
    # Attach scores to entries for transparency
    for entry in entries:
        if entry.id in score_map:
            entry._search_scores = score_map[entry.id]
    
    return entries

def main():
    parser = argparse.ArgumentParser(description="Semantic search")
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument("-k", type=int, default=5, help="Number of results")
    args = parser.parse_args()
    
    db = next(get_db())
    results = search_entries_semantic(db, args.query, args.k)
    
    print(f"Results for '{args.query}':")
    for i, entry in enumerate(results):
        print(f"{i+1}. {entry.title} (ID: {entry.id})")
        print(f"   {entry.entry_text[:100]}...")
        print()

if __name__ == "__main__":
    main()
