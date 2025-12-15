import logging
import json
import os
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.db.session import get_db
from src.db.models import Entry
from src.llm_client import embed_text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Progress tracking
SHARED_DIR = "/app/shared"
EMBED_PROGRESS_FILE = os.path.join(SHARED_DIR, "embed_progress.json")

def update_progress(current: int, total: int, entry_title: str = ""):
    """Update the embedding progress file."""
    try:
        os.makedirs(SHARED_DIR, exist_ok=True)
        progress = {
            "phase": "embedding",
            "current": current,
            "total": total,
            "percent": round((current / total) * 100, 1) if total > 0 else 0,
            "current_entry": entry_title,
            "updated_at": datetime.now().isoformat()
        }
        with open(EMBED_PROGRESS_FILE, 'w') as f:
            json.dump(progress, f)
    except Exception as e:
        logger.warning(f"Failed to update progress: {e}")

def embed_entry(db: Session, entry: Entry):
    logger.info(f"Embedding entry {entry.id}...")
    
    # Construct a rich context for embedding to get the best semantic representation
    parts = []
    if entry.title:
        parts.append(f"Title: {entry.title}")
    if entry.author:
        parts.append(f"Author: {entry.author}")
    if entry.category:
        parts.append(f"Category: {entry.category}")
    if entry.tags:
        parts.append(f"Tags: {', '.join(entry.tags)}")
    if entry.summary:
        parts.append(f"Summary: {entry.summary}")
    
    parts.append(f"Content:\n{entry.entry_text}")
    
    text_to_embed = "\n".join(parts)
    
    embedding = embed_text(text_to_embed)
    
    if embedding:
        entry.embedding = embedding
        db.commit()
        logger.info(f"Embedded entry {entry.id}")
    else:
        logger.error(f"Failed to embed entry {entry.id}")

def main():
    db = next(get_db())
    
    # Get total count for progress tracking
    total_needing_embed = db.query(func.count(Entry.id)).filter(
        Entry.embedding.is_(None),
        Entry.status == 'enriched'
    ).scalar()
    
    # Process entries without embedding that have been enriched
    # We wait for enrichment to ensure we have the best metadata (title, author, etc.)
    entries = db.query(Entry).filter(
        Entry.embedding.is_(None),
        Entry.status == 'enriched'
    ).limit(200).all()
    
    if not entries:
        logger.info("No enriched entries needing embedding found.")
        update_progress(0, 0, "")
        return

    for i, entry in enumerate(entries):
        update_progress(i + 1, total_needing_embed, entry.title or f"Entry {entry.id}")
        embed_entry(db, entry)

if __name__ == "__main__":
    main()
