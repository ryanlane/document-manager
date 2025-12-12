import argparse
import logging
from typing import List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from src.db.session import get_db
from src.db.models import Entry
from src.llm_client import embed_text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def search_entries_semantic(db: Session, query: str, k: int = 5) -> List[Tuple[Entry, float]]:
    q_emb = embed_text(query)
    if not q_emb:
        logger.error("Failed to embed query")
        return []
    
    # Use pgvector's <-> operator (L2 distance) or <=> (Cosine distance)
    # Usually cosine distance is better for embeddings.
    # Note: pgvector's <=> is cosine distance.
    # We want to order by distance ASC.
    
    # SQLAlchemy with pgvector:
    # .order_by(Entry.embedding.cosine_distance(q_emb))
    
    results = db.query(Entry).order_by(Entry.embedding.cosine_distance(q_emb)).limit(k).all()
    
    # If we want the distance, we need to select it.
    # But for now just returning entries is fine.
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
