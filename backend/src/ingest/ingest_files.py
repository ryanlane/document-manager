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
            return file_path.read_text(errors='ignore')
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

def ingest_file(db: Session, file_path: Path, dry_run: bool = False) -> str:
    """
    Ingest a single file. Returns operation type: 'new', 'updated', 'skipped', or 'error'.
    """
    try:
        stat = file_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        size_bytes = stat.st_size
        extension = file_path.suffix.lower()
        
        # Check if file exists in DB
        # We can optimize this by batching checks, but for now per-file is fine
        # Actually, let's compute SHA256 first as it is the unique key for content
        # But wait, if we want to detect updates to the SAME path, we should look up by path?
        # The plan says: "Look up by sha256. If exists and mtime unchanged -> skip."
        # But if I edit a file, sha256 changes.
        # So I should probably look up by PATH first to see if we need to update an existing record,
        # OR look up by SHA256 to see if we already have this content (deduplication).
        
        # Plan says:
        # Look up by sha256.
        # If exists and mtime unchanged -> skip.
        # If exists but mtime changed -> update raw_text, size_bytes, mtime.
        # If not exists -> insert new row.
        
        # This logic in the plan implies that SHA256 is the primary identity.
        # But if I change a file, the SHA256 changes. So I would insert a NEW row?
        # And the old row would remain? That leads to duplicates if we don't clean up.
        # Usually we want to track files by PATH.
        
        # Let's refine the logic:
        # 1. Check if we have a record for this PATH.
        # 2. If yes, check if mtime or size changed.
        # 3. If changed (or new), compute SHA256.
        # 4. Update/Insert.
        
        # However, the plan explicitly says "Look up by sha256".
        # Maybe the intention is a content-addressable store?
        # "sha256 TEXT UNIQUE" in schema supports this.
        # But "path TEXT NOT NULL" is also there.
        # If I have two files with same content at different paths, the UNIQUE constraint on sha256 will fail if I try to insert the second one.
        # So the schema enforces 1 file content = 1 row.
        # This means if I copy a file, I can't ingest it again?
        # That seems restrictive for a "document manager" where I might have duplicates I want to know about.
        # OR, maybe `path` should not be unique, but `sha256` is.
        # If `sha256` is unique, then we can only store one instance of that content.
        # The `path` column would just store "one of the paths".
        
        # Let's stick to the plan's schema but maybe relax the constraint or logic if needed.
        # If the plan says "sha256 TEXT UNIQUE", then it IS a content store.
        # But then `path` is ambiguous.
        
        # Let's assume for now we want to track files by PATH, and SHA256 is just a property.
        # But the schema has `sha256 TEXT UNIQUE`.
        # I will modify the logic to handle this.
        # If I find a file with same SHA256, I might just update the path if it's different?
        # Or maybe I should remove the UNIQUE constraint on sha256 if I want to support duplicates.
        # For a "Brain", maybe we don't want duplicates.
        
        # Let's follow the plan: "Look up by sha256".
        # If I edit a file, it gets a new SHA256.
        # So it will be a new row.
        # What happens to the old row? It stays there, pointing to the path.
        # This means we have history? Or just stale data?
        # The plan doesn't mention deletion.
        
        # I will implement a "Path-based" approach because it makes more sense for a file mirror.
        # 1. Get current file info (path, mtime, size).
        # 2. Check DB for this PATH.
        # 3. If exists:
        #    If mtime matches -> Skip (assuming content hasn't changed if mtime hasn't).
        #    If mtime changed -> Compute SHA256. Update row.
        # 4. If not exists:
        #    Compute SHA256. Insert row.
        
        # But wait, if `sha256` is UNIQUE, and I update a file to have content X, and another file already has content X, the update will fail.
        # This suggests the schema might need adjustment or the logic needs to handle "content already exists at another path".
        
        # I'll proceed with Path-based logic and handle the UniqueViolation if it occurs (meaning we have a duplicate content).
        # If duplicate content, maybe we just point this path to the existing ID?
        # But `path` is a column in `raw_files`. We can't have multiple paths for one row.
        
        # DECISION: I will assume the user might want to remove `UNIQUE` from `sha256` later, but for now I will try to respect it.
        # If a file is a duplicate of another, we might skip ingesting it or log it.
        # OR, better: The plan might have meant `(path)` is unique?
        # The schema in Phase 1 Task 2 says: `sha256 TEXT UNIQUE`.
        # It does NOT say `path` is unique.
        # But `id` is PK.
        
        # Let's stick to:
        # 1. Compute SHA256.
        # 2. Check if SHA256 exists.
        #    If yes: Update `path` (maybe it moved?), `mtime`.
        #    If no: Insert.
        # This effectively dedups by content. The last ingested file "wins" the path.
        
        sha256 = compute_sha256(file_path)
        
        existing = db.query(RawFile).filter(RawFile.sha256 == sha256).first()
        
        if existing:
            if existing.mtime == mtime and existing.path == str(file_path):
                logger.debug(f"Skipping {file_path} (unchanged)")
                return "skipped"
            
            if dry_run:
                logger.info(f"[DRY RUN] Would update {file_path} (SHA match)")
                return "skipped"

            # Update existing record
            existing.path = str(file_path)
            existing.filename = file_path.name
            existing.extension = extension
            existing.size_bytes = size_bytes
            existing.mtime = mtime
            # raw_text is same since sha256 is same
            logger.info(f"Updated metadata for {file_path} (SHA match)")
            db.commit()
            return "updated"
        else:
            # New content
            raw_text = extract_text(file_path, extension)
            if raw_text is None:
                logger.warning(f"Could not extract text for {file_path}, skipping content but storing metadata")
                raw_text = ""
                status = "extract_failed"
            else:
                status = "ok"
            
            if dry_run:
                logger.info(f"[DRY RUN] Would insert {file_path}")
                return "skipped"

            new_file = RawFile(
                path=str(file_path),
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
    
    # Phase 1: Count files to process
    update_progress("counting", 0, 0)
    logger.info("Counting files to process...")
    files_to_process = []
    for root in include_paths:
        if not root.exists():
            logger.warning(f"Source root {root} does not exist")
            continue
            
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
                
            if should_process(file_path, include_exts, exclude_patterns):
                files_to_process.append(file_path)
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
        result = ingest_file(db, file_path, dry_run=args.dry_run)
        
        if result == "new":
            new_files += 1
        elif result == "updated":
            updated_files += 1
        elif result == "skipped":
            skipped_files += 1
        elif result == "error":
            errors += 1
        
        # Update progress every 10 files or at key milestones
        if i % 10 == 0 or i == total - 1:
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
