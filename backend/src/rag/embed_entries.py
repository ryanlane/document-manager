import logging
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.db.session import get_db
from src.db.models import Entry
from src.llm_client import embed_text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Progress tracking
if os.path.exists("/app/shared"):
    SHARED_DIR = "/app/shared"
else:
    SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "shared")

EMBED_PROGRESS_FILE = os.path.join(SHARED_DIR, "embed_progress.json")

# Batch processing config
BATCH_SIZE = 10  # Number of entries to embed in parallel
MAX_WORKERS = 4  # Number of concurrent threads

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

def build_embed_text(entry: Entry) -> str:
    """Build the text to embed from entry metadata and content."""
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
    return "\n".join(parts)

def embed_single(entry_id: int, text: str) -> tuple:
    """
    Embed a single text. Returns (entry_id, embedding) tuple.
    This function is thread-safe and doesn't access the database.
    """
    embedding = embed_text(text)
    return (entry_id, embedding)

def embed_entry(db: Session, entry: Entry):
    """Legacy single-entry embedding (still used for compatibility)."""
    logger.info(f"Embedding entry {entry.id}...")
    
    text_to_embed = build_embed_text(entry)
    embedding = embed_text(text_to_embed)
    
    if embedding:
        entry.embedding = embedding
        db.commit()
        logger.info(f"Embedded entry {entry.id}")
    else:
        logger.error(f"Failed to embed entry {entry.id}")

def embed_batch(db: Session, entries: list) -> int:
    """
    Embed multiple entries in parallel using ThreadPoolExecutor.
    Returns the number of successfully embedded entries.
    """
    if not entries:
        return 0
    
    # Prepare texts for embedding (outside of threads)
    entry_texts = [(e.id, build_embed_text(e)) for e in entries]
    entry_map = {e.id: e for e in entries}
    
    success_count = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all embedding tasks
        futures = {
            executor.submit(embed_single, entry_id, text): entry_id 
            for entry_id, text in entry_texts
        }
        
        # Collect results as they complete
        for future in as_completed(futures):
            entry_id = futures[future]
            try:
                result_id, embedding = future.result()
                if embedding:
                    entry = entry_map[result_id]
                    entry.embedding = embedding
                    success_count += 1
                    logger.info(f"Embedded entry {result_id}")
                else:
                    logger.error(f"Failed to embed entry {result_id}")
            except Exception as e:
                logger.error(f"Exception embedding entry {entry_id}: {e}")
    
    # Commit all successful embeddings at once
    db.commit()
    return success_count

def main():
    db = next(get_db())
    
    # Get total count for progress tracking
    total_needing_embed = db.query(func.count(Entry.id)).filter(
        Entry.embedding.is_(None),
        Entry.status == 'enriched'
    ).scalar()
    
    if total_needing_embed == 0:
        logger.info("No enriched entries needing embedding found.")
        update_progress(0, 0, "")
        return
    
    # Process in batches
    processed = 0
    while processed < total_needing_embed:
        # Fetch a batch of entries
        entries = db.query(Entry).filter(
            Entry.embedding.is_(None),
            Entry.status == 'enriched'
        ).limit(BATCH_SIZE).all()
        
        if not entries:
            break
        
        # Update progress
        update_progress(
            processed + len(entries), 
            total_needing_embed, 
            f"Batch of {len(entries)} entries"
        )
        
        # Process batch in parallel
        success = embed_batch(db, entries)
        processed += len(entries)
        
        logger.info(f"Batch complete: {success}/{len(entries)} successful. Total: {processed}/{total_needing_embed}")
    
    update_progress(processed, total_needing_embed, "Complete")
    logger.info(f"Embedding complete. Processed {processed} entries.")

if __name__ == "__main__":
    main()
