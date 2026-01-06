import argparse
import hashlib
import logging
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Set

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from src.config import load_config
from src.db.models import RawFile, detect_series_info
from src.db.session import get_db
from src.db.settings import get_setting, DEFAULT_SETTINGS
from src.extract.extractors import (
    extract_file_content, 
    generate_thumbnail, 
    get_file_type,
    IMAGE_EXTENSIONS,
    PDF_EXTENSIONS,
    TEXT_EXTENSIONS,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Progress tracking
SHARED_DIR = os.environ.get("SHARED_DIR")
if not SHARED_DIR:
    if os.path.exists("/app/shared"):
        SHARED_DIR = "/app/shared"
    else:
        SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "shared")

PROGRESS_FILE = os.path.join(SHARED_DIR, "ingest_progress.json")
STATE_FILE = os.path.join(SHARED_DIR, "worker_state.json")

def check_stop_signal():
    """Check if the worker has been paused or ingest disabled."""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                if not state.get("running", True) or not state.get("ingest", True):
                    return True
    except Exception:
        pass
    return False

def update_progress(phase: str, current: int, total: int, new_files: int = 0, updated_files: int = 0, skipped_files: int = 0, current_file: str = ""):
    """Update the progress file for the dashboard."""
    try:
        progress = {
            "phase": phase,
            "current": current,
            "total": total,
            "percent": round((current / total) * 100, 1) if total > 0 else 0,
            "new_files": new_files,
            "updated_files": updated_files,
            "skipped_files": skipped_files,
            "current_file": current_file,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        os.makedirs(SHARED_DIR, exist_ok=True)
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(progress, f)
    except Exception as e:
        logger.debug(f"Could not update progress: {e}")

def compute_sha256(file_path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def extract_text(file_path: Path, extension: str) -> tuple:
    """
    Extract text from file using appropriate method based on file type.
    Returns (raw_text, file_type, metadata_dict).
    """
    return extract_file_content(file_path, extension)

def should_process(file_path: Path, include_exts: Set[str], exclude_patterns: List[str]) -> bool:
    if file_path.suffix.lower() not in include_exts:
        return False
    
    for pattern in exclude_patterns:
        if file_path.match(pattern):
            return False
            
    return True

def ingest_file(db: Session, file_path: Path, dry_run: bool = False, path_cache: dict = None) -> str:
    """
    Ingest a single file. Returns operation type: 'new', 'updated', 'skipped', or 'error'.
    
    Uses a path-first approach for efficiency:
    1. Check if path exists in cache/DB with same mtime/size → skip (no hashing needed)
    2. Only compute SHA256 if file is new or modified
    """
    try:
        stat = file_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        size_bytes = stat.st_size
        extension = file_path.suffix.lower()
        path_str = str(file_path)
        
        # FAST PATH: Check if we already have this exact file (same path, mtime, size)
        # This avoids expensive SHA256 computation for unchanged files
        if path_cache is not None and path_str in path_cache:
            cached = path_cache[path_str]
            if cached['mtime'] == mtime and cached['size'] == size_bytes:
                # If extraction previously failed, retry even if file is unchanged.
                if cached.get('status') != 'extract_failed':
                    logger.debug(f"Skipping {file_path} (unchanged - fast path)")
                    return "skipped"
        
        # If not in cache or file changed, query DB to double-check
        existing_by_path = db.query(RawFile).filter(RawFile.path == path_str).first()
        if existing_by_path:
            if existing_by_path.mtime == mtime and existing_by_path.size_bytes == size_bytes:
                # If extraction previously failed, retry even if file is unchanged.
                if existing_by_path.status != 'extract_failed':
                    logger.debug(f"Skipping {file_path} (unchanged)")
                    return "skipped"
        
        # File is new or modified - now we need to compute SHA256
        sha256 = compute_sha256(file_path)
        
        # Check if this content already exists (deduplication by content)
        existing_by_sha = db.query(RawFile).filter(RawFile.sha256 == sha256).first()
        
        if existing_by_sha:
            # Content already exists - update path/metadata if different
            if existing_by_sha.path == path_str and existing_by_sha.mtime == mtime:
                # If extraction previously failed, retry even if content is unchanged.
                if existing_by_sha.status != 'extract_failed':
                    logger.debug(f"Skipping {file_path} (unchanged)")
                    return "skipped"
            
            if dry_run:
                logger.info(f"[DRY RUN] Would update {file_path} (SHA match)")
                return "skipped"

            # If the existing record previously failed extraction, retry extraction now.
            if existing_by_sha.status == "extract_failed":
                raw_text, file_type, extract_meta = extract_text(file_path, extension)
                if not raw_text and file_type not in ('image',):  # Images may have no OCR text
                    logger.warning(f"Could not extract text for {file_path}")
                    existing_by_sha.status = "extract_failed"
                else:
                    existing_by_sha.status = "ok"

                existing_by_sha.path = path_str
                existing_by_sha.filename = file_path.name
                existing_by_sha.extension = extension
                existing_by_sha.size_bytes = size_bytes
                existing_by_sha.mtime = mtime
                existing_by_sha.raw_text = raw_text or ""
                existing_by_sha.file_type = file_type

                # Update image/PDF specific fields
                if file_type == 'image':
                    existing_by_sha.ocr_text = raw_text
                    existing_by_sha.image_width = extract_meta.get('image_width')
                    existing_by_sha.image_height = extract_meta.get('image_height')
                    thumbnail = generate_thumbnail(file_path, sha256)
                    if thumbnail:
                        existing_by_sha.thumbnail_path = thumbnail
                elif file_type == 'pdf':
                    if extract_meta.get('is_scanned'):
                        existing_by_sha.ocr_text = raw_text

                logger.info(f"Re-extracted {file_path} (SHA match, type: {file_type})")
                db.commit()
                return "updated"

            # Update existing record with new path/metadata
            existing_by_sha.path = path_str
            existing_by_sha.filename = file_path.name
            existing_by_sha.extension = extension
            existing_by_sha.size_bytes = size_bytes
            existing_by_sha.mtime = mtime
            logger.info(f"Updated metadata for {file_path} (SHA match)")
            db.commit()
            return "updated"
        
        # If path exists but SHA changed, the file content was modified
        # We need to update the existing record with new content
        if existing_by_path:
            if dry_run:
                logger.info(f"[DRY RUN] Would update {file_path} (content changed)")
                return "skipped"
            
            raw_text, file_type, extract_meta = extract_text(file_path, extension)
            if not raw_text and file_type not in ('image',):  # Images may have no OCR text
                logger.warning(f"Could not extract text for {file_path}")
                existing_by_path.status = "extract_failed"
            else:
                existing_by_path.status = "ok"
            
            existing_by_path.sha256 = sha256
            existing_by_path.raw_text = raw_text or ""
            existing_by_path.size_bytes = size_bytes
            existing_by_path.mtime = mtime
            existing_by_path.file_type = file_type
            
            # Update image/PDF specific fields
            if file_type == 'image':
                existing_by_path.ocr_text = raw_text
                existing_by_path.image_width = extract_meta.get('image_width')
                existing_by_path.image_height = extract_meta.get('image_height')
                # Generate thumbnail
                thumbnail = generate_thumbnail(file_path, sha256)
                if thumbnail:
                    existing_by_path.thumbnail_path = thumbnail
            elif file_type == 'pdf':
                if extract_meta.get('is_scanned'):
                    existing_by_path.ocr_text = raw_text
            
            logger.info(f"Updated {file_path} (content changed, type: {file_type})")
            db.commit()
            return "updated"
        
        # Truly new file - insert
        raw_text, file_type, extract_meta = extract_text(file_path, extension)
        if not raw_text and file_type not in ('image',):  # Images may have no OCR text
            logger.warning(f"Could not extract text for {file_path}, storing metadata only")
            status = "extract_failed"
        else:
            status = "ok"
        
        if dry_run:
            logger.info(f"[DRY RUN] Would insert {file_path}")
            return "skipped"

        # Detect series information from filename
        series_info = detect_series_info(file_path.name)
        
        # Generate thumbnail for images and PDFs
        thumbnail_path = None
        if file_type in ('image', 'pdf'):
            thumbnail_path = generate_thumbnail(file_path, sha256)

        new_file = RawFile(
            path=path_str,
            filename=file_path.name,
            extension=extension,
            size_bytes=size_bytes,
            mtime=mtime,
            sha256=sha256,
            raw_text=raw_text or "",
            status=status,
            file_type=file_type,
            thumbnail_path=thumbnail_path,
            ocr_text=raw_text if file_type == 'image' else (raw_text if file_type == 'pdf' and extract_meta.get('is_scanned') else None),
            image_width=extract_meta.get('image_width'),
            image_height=extract_meta.get('image_height'),
            series_name=series_info.get('series_name'),
            series_number=series_info.get('series_number'),
            series_total=series_info.get('series_total')
        )
        db.add(new_file)
        if series_info.get('series_name'):
            logger.info(f"Ingested {file_path} (type: {file_type}, Series: {series_info.get('series_name')} #{series_info.get('series_number')})")
        else:
            logger.info(f"Ingested {file_path} (type: {file_type})")
        db.commit()
        return "new"

    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        db.rollback()
        return "error"

def main():
    parser = argparse.ArgumentParser(description="Ingest files into the archive")
    parser.add_argument("--dry-run", action="store_true", help="Don't modify database")
    parser.add_argument("--limit", type=int, help="Max files to process")
    args = parser.parse_args()

    db = next(get_db())
    
    # Read source folders from database settings (set via UI)
    # Fall back to YAML config if database settings don't exist
    sources = get_setting(db, "sources")
    if sources:
        include_paths = [Path(p) for p in sources.get('include', [])]
        exclude_patterns = sources.get('exclude', [])
    else:
        # Fallback to YAML config for backwards compatibility
        config = load_config()
        include_paths = [Path(p) for p in config['sources']['include']]
        exclude_patterns = config['sources']['exclude']
    
    # Read extensions from database settings
    extensions = get_setting(db, "extensions")
    if extensions:
        include_exts = set(extensions)
    else:
        config = load_config()
        include_exts = set(config['extensions'])
    
    logger.info(f"Source folders: {[str(p) for p in include_paths]}")
    logger.info(f"Extensions: {sorted(include_exts)}")
    
    # Build a path cache from database for fast skip checks
    # This avoids computing SHA256 for files that haven't changed
    update_progress("loading_cache", 0, 0)
    logger.info("Building path cache from database...")
    path_cache = {}
    try:
        # Only fetch path, mtime, size, status - still lightweight, but enables retry of extract_failed
        results = db.query(RawFile.path, RawFile.mtime, RawFile.size_bytes, RawFile.status).all()
        for path, mtime, size, status in results:
            path_cache[path] = {'mtime': mtime, 'size': size, 'status': status}
        logger.info(f"Loaded {len(path_cache)} files into path cache")
    except Exception as e:
        logger.warning(f"Could not build path cache: {e}")
    
    # Single Pass: Scan and Process
    # We removed the separate counting phase to speed up the loop.
    # Total is unknown initially, so we just track count.
    
    new_files = 0
    updated_files = 0
    skipped_files = 0
    errors = 0
    processed_count = 0
    
    logger.info("Scanning and processing files...")
    update_progress("scanning", 0, 0)

    for root in include_paths:
        if not root.exists():
            logger.warning(f"Source root {root} does not exist")
            continue
            
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
                
            if should_process(file_path, include_exts, exclude_patterns):
                # Process immediately
                result = ingest_file(db, file_path, dry_run=args.dry_run, path_cache=path_cache)
                processed_count += 1
                
                if result == "new":
                    new_files += 1
                    try:
                        stat = file_path.stat()
                        path_cache[str(file_path)] = {
                            'mtime': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                            'size': stat.st_size
                        }
                    except:
                        pass
                elif result == "updated":
                    updated_files += 1
                    try:
                        stat = file_path.stat()
                        path_cache[str(file_path)] = {
                            'mtime': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                            'size': stat.st_size
                        }
                    except:
                        pass
                elif result == "skipped":
                    skipped_files += 1
                elif result == "error":
                    errors += 1
                
                # Update progress periodically
                if processed_count % 100 == 0:
                    if check_stop_signal():
                        logger.info("Ingest paused by user request.")
                        update_progress("idle", 0, 0)
                        return
                    
                    # We don't know total, so we pass 0 or processed_count as total to avoid div/0 in UI if it calculates %
                    # Or we can just pass processed_count as current and 0 as total.
                    update_progress(
                        phase="scanning",
                        current=processed_count,
                        total=0, # Unknown total
                        new_files=new_files,
                        updated_files=updated_files,
                        skipped_files=skipped_files,
                        current_file=str(file_path.name)[:50]
                    )

                if args.limit and processed_count >= args.limit:
                    break
        if args.limit and processed_count >= args.limit:
            break
    
    # Mark as complete
    update_progress(
        phase="complete",
        current=processed_count,
        total=processed_count,
        new_files=new_files,
        updated_files=updated_files,
        skipped_files=skipped_files,
        current_file=""
    )
    logger.info(f"Ingest complete: {new_files} new, {updated_files} updated, {skipped_files} skipped, {errors} errors")

if __name__ == "__main__":
    main()
