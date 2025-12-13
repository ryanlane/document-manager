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
from src.db.models import RawFile
from src.db.session import get_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Progress tracking
SHARED_DIR = os.environ.get("SHARED_DIR", "/app/shared")
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

def extract_text(file_path: Path, extension: str) -> Optional[str]:
    # Simple extraction for now
    try:
        if extension in ['.txt', '.md', '.html', '.json', '.yaml', '.yml', '.py', '.js', '.ts', '.sql']:
            text = file_path.read_text(errors='ignore')
            # PostgreSQL cannot store NUL (0x00) characters in text fields
            return text.replace('\x00', '')
        else:
            # TODO: Integrate Tika for PDF, DOCX, etc.
            return None
    except Exception as e:
        logger.error(f"Failed to extract text from {file_path}: {e}")
        return None

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
                logger.debug(f"Skipping {file_path} (unchanged - fast path)")
                return "skipped"
        
        # If not in cache or file changed, query DB to double-check
        existing_by_path = db.query(RawFile).filter(RawFile.path == path_str).first()
        if existing_by_path:
            if existing_by_path.mtime == mtime and existing_by_path.size_bytes == size_bytes:
                logger.debug(f"Skipping {file_path} (unchanged)")
                return "skipped"
        
        # File is new or modified - now we need to compute SHA256
        sha256 = compute_sha256(file_path)
        
        # Check if this content already exists (deduplication by content)
        existing_by_sha = db.query(RawFile).filter(RawFile.sha256 == sha256).first()
        
        if existing_by_sha:
            # Content already exists - update path/metadata if different
            if existing_by_sha.path == path_str and existing_by_sha.mtime == mtime:
                logger.debug(f"Skipping {file_path} (unchanged)")
                return "skipped"
            
            if dry_run:
                logger.info(f"[DRY RUN] Would update {file_path} (SHA match)")
                return "skipped"

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
            
            raw_text = extract_text(file_path, extension)
            if raw_text is None:
                logger.warning(f"Could not extract text for {file_path}")
                raw_text = ""
                existing_by_path.status = "extract_failed"
            else:
                existing_by_path.status = "ok"
            
            existing_by_path.sha256 = sha256
            existing_by_path.raw_text = raw_text
            existing_by_path.size_bytes = size_bytes
            existing_by_path.mtime = mtime
            logger.info(f"Updated {file_path} (content changed)")
            db.commit()
            return "updated"
        
        # Truly new file - insert
        raw_text = extract_text(file_path, extension)
        if raw_text is None:
            logger.warning(f"Could not extract text for {file_path}, storing metadata only")
            raw_text = ""
            status = "extract_failed"
        else:
            status = "ok"
        
        if dry_run:
            logger.info(f"[DRY RUN] Would insert {file_path}")
            return "skipped"

        new_file = RawFile(
            path=path_str,
            filename=file_path.name,
            extension=extension,
            size_bytes=size_bytes,
            mtime=mtime,
            sha256=sha256,
            raw_text=raw_text,
            status=status
        )
        db.add(new_file)
        logger.info(f"Ingested {file_path}")
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

    config = load_config()
    include_paths = [Path(p) for p in config['sources']['include']]
    exclude_patterns = config['sources']['exclude']
    include_exts = set(config['extensions'])
    
    db = next(get_db())
    
    # Build a path cache from database for fast skip checks
    # This avoids computing SHA256 for files that haven't changed
    update_progress("loading_cache", 0, 0)
    logger.info("Building path cache from database...")
    path_cache = {}
    try:
        # Only fetch path, mtime, size - not the full row
        results = db.query(RawFile.path, RawFile.mtime, RawFile.size_bytes).all()
        for path, mtime, size in results:
            path_cache[path] = {'mtime': mtime, 'size': size}
        logger.info(f"Loaded {len(path_cache)} files into path cache")
    except Exception as e:
        logger.warning(f"Could not build path cache: {e}")
    
    # Phase 1: Count files to process
    update_progress("counting", 0, 0)
    logger.info("Counting files to process...")
    files_to_process = []
    count = 0
    for root in include_paths:
        if not root.exists():
            logger.warning(f"Source root {root} does not exist")
            continue
            
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
                
            if should_process(file_path, include_exts, exclude_patterns):
                files_to_process.append(file_path)
                count += 1
                if count % 1000 == 0:
                    if check_stop_signal():
                        logger.info("Ingest paused by user request during counting.")
                        update_progress("idle", 0, 0)
                        return
                    update_progress("counting", count, 0, current_file=str(file_path.name)[:50])

                if args.limit and len(files_to_process) >= args.limit:
                    break
        if args.limit and len(files_to_process) >= args.limit:
            break
    
    total = len(files_to_process)
    logger.info(f"Found {total} files to process")
    
    # Phase 2: Process files with progress tracking
    new_files = 0
    updated_files = 0
    skipped_files = 0
    errors = 0
    
    for i, file_path in enumerate(files_to_process):
        result = ingest_file(db, file_path, dry_run=args.dry_run, path_cache=path_cache)
        
        if result == "new":
            new_files += 1
            # Update cache with new file
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
            # Update cache
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
        
        # Update progress every 100 files or at key milestones (reduced frequency for speed)
        if i % 100 == 0 or i == total - 1:
            update_progress(
                phase="scanning",
                current=i + 1,
                total=total,
                new_files=new_files,
                updated_files=updated_files,
                skipped_files=skipped_files,
                current_file=str(file_path.name)[:50]
            )
    
    # Mark as complete
    update_progress(
        phase="complete",
        current=total,
        total=total,
        new_files=new_files,
        updated_files=updated_files,
        skipped_files=skipped_files,
        current_file=""
    )
    logger.info(f"Ingest complete: {new_files} new, {updated_files} updated, {skipped_files} skipped, {errors} errors")

if __name__ == "__main__":
    main()
