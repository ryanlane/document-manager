import logging
import json
import os
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import text

from src.db.session import get_db
from src.db.models import Entry
from src.llm_client import generate_json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

def enrich_entry(db: Session, entry: Entry):
    logger.info(f"Enriching entry {entry.id}...")
    
    prompt = ENRICH_PROMPT_TEMPLATE.format(text=entry.entry_text[:4000]) # Limit context window
    
    metadata = generate_json(prompt)
    
    if not metadata:
        logger.error(f"Failed to enrich entry {entry.id}")
        # entry.status = 'error' # Optional: mark as error or leave pending to retry
        return

    try:
        entry.title = metadata.get("title")
        
        # Fallback to filename if title is missing
        if not entry.title and entry.raw_file:
            entry.title = os.path.splitext(entry.raw_file.filename)[0]

        entry.author = metadata.get("author")
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
        db.commit()
        
        # Update search vector
        update_search_vector(db, entry.id)
        db.commit()
        
        logger.info(f"Enriched entry {entry.id}: {entry.title}")
        
    except Exception as e:
        logger.error(f"Error saving enrichment for entry {entry.id}: {e}")
        db.rollback()

def main():
    db = next(get_db())
    
    # Process pending entries
    entries = db.query(Entry).filter(Entry.status == 'pending').limit(10).all() # Batch size 10
    
    if not entries:
        logger.info("No pending entries found.")
        return

    for entry in entries:
        enrich_entry(db, entry)

if __name__ == "__main__":
    main()
