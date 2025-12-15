import logging
import json
import os
import yaml
import re
from datetime import datetime
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.orm import Session
from sqlalchemy import text, func

from src.db.session import get_db, SessionLocal
from src.db.models import Entry
from src.llm_client import generate_json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Progress tracking
SHARED_DIR = "/app/shared"
ENRICH_PROGRESS_FILE = os.path.join(SHARED_DIR, "enrich_progress.json")
CONFIG_FILE = "/app/config/config.yaml"

# Default prompt template (fallback if config not found)
DEFAULT_PROMPT_TEMPLATE = """
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

def load_enrichment_config():
    """Load enrichment configuration from config.yaml."""
    config = {
        'prompt_template': DEFAULT_PROMPT_TEMPLATE,
        'max_text_length': 4000,
        'custom_fields': []
    }
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config and 'enrichment' in yaml_config:
                    enrichment = yaml_config['enrichment']
                    if 'prompt_template' in enrichment:
                        config['prompt_template'] = enrichment['prompt_template']
                    if 'max_text_length' in enrichment:
                        config['max_text_length'] = enrichment['max_text_length']
                    if 'custom_fields' in enrichment:
                        config['custom_fields'] = enrichment['custom_fields']
                    logger.info("Loaded enrichment config from config.yaml")
    except Exception as e:
        logger.warning(f"Failed to load config.yaml, using defaults: {e}")
    
    return config

# Load config once at module level
ENRICHMENT_CONFIG = load_enrichment_config()

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

# Parallel processing settings
ENRICH_WORKERS = 3  # Number of parallel enrichment workers
ENRICH_BATCH_SIZE = 15  # Entries to process per batch

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


def calculate_quality_score(entry_text: str, metadata: dict) -> float:
    """
    Calculate a quality score (0-1) for the enrichment based on:
    - Completeness of metadata fields
    - Length and quality of summary
    - Tag relevance
    - Title quality
    """
    score = 0.0
    max_score = 0.0
    
    # Title quality (0-20 points)
    max_score += 20
    title = metadata.get('title', '')
    if title:
        score += 5  # Has title
        if len(title) > 10:
            score += 5  # Reasonable length
        if len(title) < 100:
            score += 5  # Not too long
        if not title.lower().startswith('untitled'):
            score += 5  # Not generic
    
    # Summary quality (0-30 points)
    max_score += 30
    summary = metadata.get('summary', '')
    if summary:
        score += 10  # Has summary
        word_count = len(summary.split())
        if word_count >= 20:
            score += 10  # Good length
        if word_count <= 100:
            score += 5  # Not too verbose
        # Check if summary seems relevant (contains some words from text)
        text_words = set(entry_text.lower().split()[:100])
        summary_words = set(summary.lower().split())
        overlap = len(text_words & summary_words)
        if overlap > 5:
            score += 5  # Some relevance
    
    # Tags quality (0-25 points)
    max_score += 25
    tags = metadata.get('tags', [])
    if tags and len(tags) > 0:
        score += 10  # Has tags
        if 2 <= len(tags) <= 7:
            score += 10  # Good number of tags
        # Check tag quality (not too generic)
        generic_tags = {'text', 'document', 'content', 'file', 'data', 'unknown'}
        quality_tags = [t for t in tags if t.lower() not in generic_tags]
        if len(quality_tags) >= 2:
            score += 5
    
    # Author detection (0-15 points)
    max_score += 15
    if metadata.get('author'):
        score += 15
    
    # Date detection (0-10 points)
    max_score += 10
    if metadata.get('created_hint'):
        score += 10
    
    return round(score / max_score, 2) if max_score > 0 else 0.0


def enrich_entry(db: Session, entry: Entry):
    logger.info(f"Enriching entry {entry.id} (attempt {(entry.retry_count or 0) + 1})...")
    
    # Use config for prompt and text length
    max_length = ENRICHMENT_CONFIG['max_text_length']
    prompt_template = ENRICHMENT_CONFIG['prompt_template']
    prompt = prompt_template.format(text=entry.entry_text[:max_length])
    
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
        
        # Calculate quality score
        quality_score = calculate_quality_score(entry.entry_text, metadata)
        if entry.extra_meta is None:
            entry.extra_meta = {}
        entry.extra_meta['quality_score'] = quality_score
        
        # Flag low quality entries for review
        if quality_score < 0.4:
            entry.extra_meta['needs_review'] = True
            logger.warning(f"Entry {entry.id} has low quality score: {quality_score}")
        
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

def enrich_entry_worker(entry_id: int) -> tuple:
    """
    Worker function for parallel enrichment.
    Creates its own database session for thread safety.
    Returns (entry_id, success, error_message)
    """
    db = SessionLocal()
    try:
        entry = db.query(Entry).filter(Entry.id == entry_id).first()
        if entry:
            enrich_entry(db, entry)
            return (entry_id, True, None)
        return (entry_id, False, "Entry not found")
    except Exception as e:
        logger.error(f"Worker error for entry {entry_id}: {e}")
        return (entry_id, False, str(e))
    finally:
        db.close()


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
    ).limit(ENRICH_BATCH_SIZE).all()
    
    if not entries:
        logger.info("No pending entries found.")
        # Clear progress
        update_progress(0, 0, "")
        return

    # Get entry IDs for parallel processing
    entry_ids = [e.id for e in entries]
    
    # Use ThreadPoolExecutor for parallel enrichment
    completed = 0
    with ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as executor:
        futures = {executor.submit(enrich_entry_worker, eid): eid for eid in entry_ids}
        
        for future in as_completed(futures):
            entry_id = futures[future]
            try:
                eid, success, error = future.result()
                completed += 1
                if success:
                    update_progress(completed, total_pending, f"Entry {eid}")
                else:
                    logger.warning(f"Entry {eid} failed: {error}")
            except Exception as e:
                logger.error(f"Future error for entry {entry_id}: {e}")
    
    logger.info(f"Batch complete: processed {completed}/{len(entry_ids)} entries")

if __name__ == "__main__":
    main()
