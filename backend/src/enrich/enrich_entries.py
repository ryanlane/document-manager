import logging
import json
import os
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import text, func

from src.db.session import get_db
from src.db.models import Entry
from src.llm_client import generate_json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Progress tracking
SHARED_DIR = "/app/shared"
ENRICH_PROGRESS_FILE = os.path.join(SHARED_DIR, "enrich_progress.json")

ENRICH_PROMPT_TEMPLATE = """
You are a document archivist. Analyze the following text and extract metadata in JSON format.
Return ONLY the JSON object.

Fields required:
- title: A concise title for this segment.
- author: The author if mentioned, else null.
- created_hint: A date string (YYYY-MM-DD) or approximate timeframe if mentioned, else null.
- tags: An array of 3-5 relevant tags.
- summary: A 2-4 sentence summary of the content.

Text:
{text}
"""

def update_search_vector(db: Session, entry_id: int):
    sql = text("""
        UPDATE entries
        SET search_vector =
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(entry_text, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(array_to_string(tags, ' '), '')), 'A')
        WHERE id = :id
    """)
    db.execute(sql, {"id": entry_id})

# Max retry attempts before marking as error
MAX_RETRIES = 3

# Known category folders to detect
CATEGORY_FOLDERS = ['scifi', 'sci-fi', 'fantasy', 'romance', 'horror', 'mystery', 
                    'thriller', 'drama', 'comedy', 'adventure', 'historical', 
                    'erotica', 'fiction', 'nonfiction', 'poetry', 'essay']


def extract_category_from_path(path: str) -> str:
    """Extract category/genre from folder structure."""
    path = path.replace('\\', '/').lower()
    path_parts = path.split('/')
    
    for part in path_parts:
        if part in CATEGORY_FOLDERS:
            return part.title()
    
    # Also check for patterns like "stories/category_name/"
    for i, part in enumerate(path_parts):
        if part in ['stories', 'story', 'docs', 'archive'] and i + 1 < len(path_parts):
            candidate = path_parts[i + 1]
            if candidate not in ['authors', 'files', 'data'] and len(candidate) > 2:
                return candidate.title()
    
    return None


def enrich_entry(db: Session, entry: Entry):
    logger.info(f"Enriching entry {entry.id} (attempt {(entry.retry_count or 0) + 1})...")
    
    prompt = ENRICH_PROMPT_TEMPLATE.format(text=entry.entry_text[:4000]) # Limit context window
    
    metadata = generate_json(prompt)
    
    if not metadata:
        # Increment retry count
        entry.retry_count = (entry.retry_count or 0) + 1
        if entry.retry_count >= MAX_RETRIES:
            entry.status = 'error'
            logger.error(f"Entry {entry.id} failed after {MAX_RETRIES} attempts, marking as error")
        else:
            logger.warning(f"Failed to enrich entry {entry.id}, will retry (attempt {entry.retry_count}/{MAX_RETRIES})")
        db.commit()
        return

    try:
        entry.title = metadata.get("title")
        
        # Fallback to filename if title is missing
        if not entry.title and entry.raw_file:
            entry.title = os.path.splitext(entry.raw_file.filename)[0]

        entry.author = metadata.get("author")

        # Fallback to folder structure for author if missing
        # Example path: .../story/authors/John Doe/story.txt
        if not entry.author and entry.raw_file:
            try:
                # Normalize path separators
                path = entry.raw_file.path.replace('\\', '/')
                path_parts = path.split('/')
                
                # Look for 'authors' directory
                if 'authors' in path_parts:
                    idx = path_parts.index('authors')
                    if idx + 1 < len(path_parts):
                        candidate_author = path_parts[idx + 1]
                        if candidate_author != entry.raw_file.filename:
                            entry.author = candidate_author
            except Exception as e:
                logger.warning(f"Failed to extract author from path: {e}")

        # Extract category from folder structure
        if entry.raw_file:
            entry.category = extract_category_from_path(entry.raw_file.path)

        entry.summary = metadata.get("summary")
        entry.tags = metadata.get("tags", [])
        
        # Handle created_hint - simple string storage for now, or try to parse
        # The model might return "2023-01-01" or "Unknown"
        # Our DB column is DateTime. If we can't parse, we might put it in extra_meta
        created_hint_str = metadata.get("created_hint")
        if created_hint_str:
            # Try simple parsing or just store in extra_meta if it fails
            # For now, let's just put it in extra_meta to avoid parsing errors
            if entry.extra_meta is None:
                entry.extra_meta = {}
            entry.extra_meta['created_hint_raw'] = created_hint_str
        
        entry.status = 'enriched'
        
        # Clear existing embedding to force re-embedding with new metadata
        entry.embedding = None
        
        db.commit()
        
        # Update search vector
        update_search_vector(db, entry.id)
        db.commit()
        
        logger.info(f"Enriched entry {entry.id}: {entry.title}")
        
    except Exception as e:
        logger.error(f"Error saving enrichment for entry {entry.id}: {e}")
        db.rollback()

def update_progress(current: int, total: int, entry_title: str = ""):
    """Update the enrichment progress file."""
    try:
        os.makedirs(SHARED_DIR, exist_ok=True)
        progress = {
            "phase": "enriching",
            "current": current,
            "total": total,
            "percent": round((current / total) * 100, 1) if total > 0 else 0,
            "current_entry": entry_title,
            "updated_at": datetime.now().isoformat()
        }
        with open(ENRICH_PROGRESS_FILE, 'w') as f:
            json.dump(progress, f)
    except Exception as e:
        logger.warning(f"Failed to update progress: {e}")

def main():
    db = next(get_db())
    
    # Get total pending count for progress tracking
    from sqlalchemy import or_
    total_pending = db.query(func.count(Entry.id)).filter(
        Entry.status == 'pending',
        or_(Entry.retry_count.is_(None), Entry.retry_count < MAX_RETRIES)
    ).scalar()
    
    # Process pending entries that haven't exceeded max retries
    entries = db.query(Entry).filter(
        Entry.status == 'pending',
        or_(Entry.retry_count.is_(None), Entry.retry_count < MAX_RETRIES)
    ).limit(10).all()
    
    if not entries:
        logger.info("No pending entries found.")
        # Clear progress
        update_progress(0, 0, "")
        return

    for i, entry in enumerate(entries):
        update_progress(i + 1, total_pending, entry.title or f"Entry {entry.id}")
        enrich_entry(db, entry)

if __name__ == "__main__":
    main()
