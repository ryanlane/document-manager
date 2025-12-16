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
SEARCH_MODE_TWO_STAGE = 'two_stage'


def search_docs_stage1(
    db: Session, 
    query: str, 
    query_embedding: List[float],
    top_n: int = 20,
    filters: dict = None
) -> List[dict]:
    """
    Stage 1: Search at document level for fast screening.
    Uses doc_embedding (vector) and doc_search_vector (FTS) for hybrid ranking.
    
    Uses Reciprocal Rank Fusion (RRF) to combine vector and keyword rankings.
    RRF formula: score = sum(1 / (k + rank_i)) where k=60 is standard.
    This is more robust than raw score combination since it normalizes 
    across different score distributions.
    
    Returns top N document IDs with scores.
    """
    # Set IVFFlat probes for better recall (default is 1)
    # Higher = better recall but slower. 10 is a good balance.
    db.execute(text("SET ivfflat.probes = 10"))
    
    # Build filter conditions
    filter_sql = ""
    params = {
        "embedding": str(query_embedding),
        "query": query,
        "limit": top_n * 3  # Get more candidates for RRF
    }
    
    if filters:
        if filters.get('author'):
            filter_sql += " AND rf.author_key ILIKE :author_filter"
            params['author_filter'] = f"%{filters['author'].lower().replace(' ', '_')}%"
        if filters.get('source'):
            filter_sql += " AND rf.source = :source_filter"
            params['source_filter'] = filters['source']
        if filters.get('extension'):
            filter_sql += " AND rf.extension = :ext_filter"
            params['ext_filter'] = filters['extension']
    
    # Use Reciprocal Rank Fusion (RRF) with k=60
    # RRF score = 1/(k + vector_rank) + 1/(k + keyword_rank)
    # This normalizes scores across different distributions
    # Limit each source to top 100 candidates for efficiency
    sql = text(f"""
        WITH doc_vector AS (
            SELECT rf.id, 
                   1.0 - (rf.doc_embedding <=> :embedding) as vector_score,
                   ROW_NUMBER() OVER (ORDER BY rf.doc_embedding <=> :embedding) as vector_rank
            FROM raw_files rf
            WHERE rf.doc_embedding IS NOT NULL
            {filter_sql}
            ORDER BY rf.doc_embedding <=> :embedding
            LIMIT 100
        ),
        doc_keyword AS (
            SELECT rf.id,
                   COALESCE(ts_rank_cd(rf.doc_search_vector, plainto_tsquery('english', :query)), 0) as keyword_score,
                   ROW_NUMBER() OVER (ORDER BY ts_rank_cd(rf.doc_search_vector, plainto_tsquery('english', :query)) DESC NULLS LAST) as keyword_rank
            FROM raw_files rf
            WHERE rf.doc_search_vector @@ plainto_tsquery('english', :query)
            {filter_sql}
            ORDER BY ts_rank_cd(rf.doc_search_vector, plainto_tsquery('english', :query)) DESC
            LIMIT 100
        ),
        rrf_scores AS (
            SELECT 
                COALESCE(v.id, k.id) as doc_id,
                COALESCE(v.vector_score, 0) as vector_score,
                COALESCE(k.keyword_score, 0) as keyword_score,
                COALESCE(v.vector_rank, 99999) as vector_rank,
                COALESCE(k.keyword_rank, 99999) as keyword_rank,
                -- RRF with k=60, weight vector 0.7, keyword 0.3
                (0.7 / (60.0 + COALESCE(v.vector_rank, 99999))) + 
                (0.3 / (60.0 + COALESCE(k.keyword_rank, 99999))) as rrf_score
            FROM doc_vector v
            FULL OUTER JOIN doc_keyword k ON v.id = k.id
        )
        SELECT doc_id, vector_score, keyword_score, rrf_score
        FROM rrf_scores
        ORDER BY rrf_score DESC
        LIMIT :limit
    """)
    
    params['limit'] = top_n  # Final limit
    results = db.execute(sql, params).fetchall()
    return [{"doc_id": r[0], "vector_score": r[1], "keyword_score": r[2], "combined_score": r[3]} for r in results]


def search_chunks_stage2(
    db: Session,
    query: str,
    query_embedding: List[float],
    doc_ids: List[int],
    k: int = 10
) -> List[Entry]:
    """
    Stage 2: Search chunks only within the specified document IDs.
    Much faster than global search since we're limiting to a small doc set.
    Uses RRF (Reciprocal Rank Fusion) for combining vector and keyword scores.
    Falls back to keyword search if chunks don't have embeddings.
    """
    if not doc_ids:
        return []
    
    # Use RRF for hybrid ranking within the filtered doc set
    sql = text("""
        WITH vector_ranked AS (
            SELECT e.id,
                   1.0 - (e.embedding <=> :embedding) as vector_score,
                   ROW_NUMBER() OVER (ORDER BY e.embedding <=> :embedding) as vector_rank
            FROM entries e
            WHERE e.file_id = ANY(:doc_ids)
              AND e.embedding IS NOT NULL
        ),
        keyword_ranked AS (
            SELECT e.id,
                   COALESCE(ts_rank_cd(e.search_vector, plainto_tsquery('english', :query)), 0) as keyword_score,
                   ROW_NUMBER() OVER (ORDER BY ts_rank_cd(e.search_vector, plainto_tsquery('english', :query)) DESC NULLS LAST) as keyword_rank
            FROM entries e
            WHERE e.file_id = ANY(:doc_ids)
        ),
        rrf_combined AS (
            SELECT 
                COALESCE(v.id, k.id) as id,
                COALESCE(v.vector_score, 0) as vector_score,
                COALESCE(k.keyword_score, 0) as keyword_score,
                -- RRF with k=60, weight vector 0.7, keyword 0.3
                (0.7 / (60.0 + COALESCE(v.vector_rank, 99999))) + 
                (0.3 / (60.0 + COALESCE(k.keyword_rank, 99999))) as rrf_score
            FROM vector_ranked v
            FULL OUTER JOIN keyword_ranked k ON v.id = k.id
        )
        SELECT id, vector_score, keyword_score, rrf_score
        FROM rrf_combined
        ORDER BY rrf_score DESC
        LIMIT :limit
    """)
    
    results = db.execute(sql, {
        "embedding": str(query_embedding),
        "query": query,
        "doc_ids": doc_ids,
        "limit": k
    }).fetchall()
    
    # If no embedded chunks, fall back to keyword-only search within docs
    if not results:
        logger.info(f"No embedded chunks in {len(doc_ids)} docs, falling back to keyword search")
        sql_fallback = text("""
            SELECT e.id,
                   0 as vector_score,
                   COALESCE(ts_rank_cd(e.search_vector, plainto_tsquery('english', :query)), 0) as keyword_score
            FROM entries e
            WHERE e.file_id = ANY(:doc_ids)
            ORDER BY keyword_score DESC, e.id
            LIMIT :limit
        """)
        results = db.execute(sql_fallback, {
            "query": query,
            "doc_ids": doc_ids,
            "limit": k
        }).fetchall()
    
    entry_ids = [r[0] for r in results]
    if not entry_ids:
        return []
    
    entries = db.query(Entry).filter(Entry.id.in_(entry_ids)).all()
    
    # Build score map and sort
    score_map = {r[0]: {'vector_score': r[1], 'keyword_score': r[2], 'combined_score': r[3] if len(r) > 3 else r[2]} for r in results}
    entries.sort(key=lambda e: score_map.get(e.id, {}).get('combined_score', 0), reverse=True)
    
    # Attach scores
    for entry in entries:
        if entry.id in score_map:
            entry._search_scores = score_map[entry.id]
    
    return entries


def search_two_stage(
    db: Session,
    query: str,
    k: int = 10,
    filters: dict = None,
    stage1_docs: int = 30
) -> dict:
    """
    Two-stage retrieval:
    1. Search doc-level embeddings to find top N relevant documents
    2. Search chunks only within those documents
    
    This is much faster for large collections since:
    - Stage 1 searches 125k docs (small)
    - Stage 2 searches only chunks from ~30 docs instead of 8M chunks
    
    Returns dict with:
    - entries: List[Entry] - the final chunk results
    - docs: List[dict] - the doc-level matches with scores
    - stats: timing and count info
    """
    import time
    
    # Embed query once, reuse for both stages
    t0 = time.time()
    query_embedding = embed_text(query)
    embed_time = time.time() - t0
    
    if not query_embedding:
        logger.error("Failed to embed query, falling back to keyword search")
        return {
            "entries": [],
            "docs": [],
            "stats": {"error": "embedding_failed"}
        }
    
    # Stage 1: Doc-level search
    t1 = time.time()
    doc_results = search_docs_stage1(db, query, query_embedding, stage1_docs, filters)
    stage1_time = time.time() - t1
    
    if not doc_results:
        # No doc matches, try chunk-level fallback
        logger.info("No doc-level matches, trying direct chunk search")
        t2 = time.time()
        # Fallback to regular hybrid search on all chunks
        entries = search_entries_semantic(db, query, k, filters, SEARCH_MODE_HYBRID)
        stage2_time = time.time() - t2
        return {
            "entries": entries,
            "docs": [],
            "stats": {
                "mode": "fallback_chunk",
                "embed_ms": int(embed_time * 1000),
                "stage1_ms": int(stage1_time * 1000),
                "stage2_ms": int(stage2_time * 1000),
                "docs_searched": 0,
                "total_ms": int((time.time() - t0) * 1000)
            }
        }
    
    # Stage 2: Chunk search within top docs
    doc_ids = [d["doc_id"] for d in doc_results]
    t2 = time.time()
    entries = search_chunks_stage2(db, query, query_embedding, doc_ids, k)
    stage2_time = time.time() - t2
    
    # Fetch doc metadata for context
    docs_with_meta = []
    doc_map = {d.id: d for d in db.query(RawFile).filter(RawFile.id.in_(doc_ids)).all()}
    for dr in doc_results:
        doc = doc_map.get(dr["doc_id"])
        if doc:
            docs_with_meta.append({
                "id": doc.id,
                "filename": doc.filename,
                "path": doc.path,
                "doc_summary": doc.doc_summary[:200] if doc.doc_summary else None,
                "vector_score": dr["vector_score"],
                "keyword_score": dr["keyword_score"],
                "combined_score": dr["combined_score"]
            })
    
    return {
        "entries": entries,
        "docs": docs_with_meta,
        "stats": {
            "mode": "two_stage",
            "embed_ms": int(embed_time * 1000),
            "stage1_ms": int(stage1_time * 1000),
            "stage2_ms": int(stage2_time * 1000),
            "docs_searched": len(doc_ids),
            "total_ms": int((time.time() - t0) * 1000)
        }
    }


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
