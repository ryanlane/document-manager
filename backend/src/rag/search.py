import argparse
import logging
from typing import List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from src.db.session import get_db
from src.db.models import Entry, RawFile
from src.llm_client import embed_text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def search_entries_semantic(db: Session, query: str, k: int = 5, filters: dict = None) -> List[Entry]:
    q_emb = embed_text(query)
    if not q_emb:
        logger.error("Failed to embed query")
        return []
    
    # Start building the query
    stmt = db.query(Entry).join(RawFile)
    
    # Apply Filters
    if filters:
        # Filter by Tags (Postgres Array Overlap)
        if filters.get('tags') and len(filters['tags']) > 0:
            stmt = stmt.filter(Entry.tags.overlap(filters['tags']))
            
        # Filter by Author (Case-insensitive partial match)
        if filters.get('author'):
            stmt = stmt.filter(Entry.author.ilike(f"%{filters['author']}%"))
            
        # Filter by File Extension
        if filters.get('extension'):
            stmt = stmt.filter(RawFile.extension == filters['extension'])
            
        # Filter by Category
        if filters.get('category'):
            stmt = stmt.filter(Entry.category.ilike(f"%{filters['category']}%"))

        # Filter by Date Range (created_hint)
        if filters.get('date_start'):
            stmt = stmt.filter(Entry.created_hint >= filters['date_start'])
        if filters.get('date_end'):
            stmt = stmt.filter(Entry.created_hint <= filters['date_end'])

    # Hybrid Search Boost:
    # If the query contains specific keywords, we can use the search_vector to narrow down 
    # or we can just rely on the vector distance. 
    # For now, let's keep it simple: The filters narrow the scope, the vector sorts by relevance.
    
    results = stmt.order_by(Entry.embedding.cosine_distance(q_emb)).limit(k).all()
    
    return results

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
