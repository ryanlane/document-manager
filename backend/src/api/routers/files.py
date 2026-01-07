"""
Files API Router
Handles files, entries, images, series, links, and enrichment configuration.
"""
import os
import mimetypes
import json
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_, func
from pydantic import BaseModel

from src.db.session import get_db
from src.db.models import RawFile, Entry
from src.db.settings import get_setting
from src.enrich.inherit_doc_metadata import inherit_doc_metadata_batch
from src.extract.extractors import THUMBNAIL_DIR
from src.llm_client import list_vision_models, VISION_MODEL, describe_image

router = APIRouter(tags=["files"])


# ============================================================================
# Pydantic Models
# ============================================================================

class FileDetail(BaseModel):
    id: int
    path: str
    filename: str
    extension: str
    size_bytes: int
    created_at: str
    modified_at: str
    entry_count: int
    
    class Config:
        from_attributes = True


class EnrichmentConfigUpdate(BaseModel):
    enabled: bool
    quality_mode: str
    auto_reenrich: bool


# ============================================================================
# Files Endpoints
# ============================================================================

@router.get("/files")
async def list_files(
    skip: int = 0, limit: int = 50, extension: Optional[str] = None,
    sort_by: str = 'modified_at', sort_dir: str = 'desc',
    db: Session = Depends(get_db)
):
    """List files with pagination and filtering."""
    query = db.query(RawFile)
    
    if extension:
        query = query.filter(RawFile.extension == extension)
    
    # Apply sorting
    if sort_by == 'filename':
        order_col = RawFile.filename
    elif sort_by == 'size':
        order_col = RawFile.size_bytes
    elif sort_by == 'created_at':
        order_col = RawFile.created_at
    elif sort_by == 'modified_at':
        # RawFile uses `mtime` (filesystem modified time)
        order_col = RawFile.mtime
    else:
        # Default to mtime
        order_col = RawFile.mtime
    
    if sort_dir == 'asc':
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())
    
    total = query.count()
    files = query.offset(skip).limit(limit).all()
    
    return {
        "files": [
            {
                "id": f.id,
                "filename": f.filename,
                "path": f.path,
                "extension": f.extension,
                "size_bytes": f.size_bytes,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "modified_at": f.mtime.isoformat() if f.mtime else None,
                "doc_category": f.meta_json.get("doc_category") if f.meta_json else None,
                "doc_author": f.meta_json.get("doc_author") if f.meta_json else None,
            }
            for f in files
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/files/{file_id}", response_model=FileDetail)
async def get_file(file_id: int, db: Session = Depends(get_db)):
    """Get file details."""
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    entry_count = db.query(Entry).filter(Entry.file_id == file_id).count()
    
    return FileDetail(
        id=file.id,
        path=file.path,
        filename=file.filename,
        extension=file.extension,
        size_bytes=file.size_bytes or 0,
        created_at=file.created_at.isoformat() if file.created_at else "",
        modified_at=file.mtime.isoformat() if file.mtime else "",
        entry_count=entry_count
    )


@router.get("/files/{file_id}/content")
async def serve_file_content(file_id: int, db: Session = Depends(get_db)):
    """Serve the actual file content for download/preview."""
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = Path(file.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(
        path=str(file_path),
        media_type=mime_type or "application/octet-stream",
        filename=file.filename
    )


@router.get("/files/{file_id}/text")
async def get_file_text_preview(file_id: int, db: Session = Depends(get_db)):
    """Extract plain text from document for preview (supports PDF, DOCX, RTF, ePub)."""
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = Path(file.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    text_content = ""
    extension = file.extension.lower()

    try:
        # Extract text based on file type
        if extension == '.pdf':
            # Use PyMuPDF (fitz)
            import fitz
            doc = fitz.open(str(file_path))
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            text_content = "\n\n".join(text_parts)
            doc.close()

        elif extension in ['.docx', '.doc']:
            # Try python-docx first (works for .docx and misnamed .docx files)
            try:
                from docx import Document
                doc = Document(str(file_path))
                text_parts = []
                for para in doc.paragraphs:
                    if para.text.strip():
                        text_parts.append(para.text)
                text_content = "\n\n".join(text_parts)
            except Exception as docx_error:
                # Fall back to Tika for old .doc format or other issues
                try:
                    import requests
                    tika_url = os.getenv('TIKA_URL', 'http://tika:9998')
                    with open(str(file_path), 'rb') as f:
                        response = requests.put(
                            f"{tika_url}/tika",
                            data=f,
                            headers={'Accept': 'text/plain'},
                            timeout=30
                        )
                    if response.status_code == 200:
                        # Tika returns UTF-8 but sometimes response.text decodes incorrectly
                        # Use response.content and decode as UTF-8 explicitly
                        text_content = response.content.decode('utf-8', errors='replace')
                    else:
                        raise Exception(f"Tika extraction failed: {response.status_code}")
                except Exception as tika_error:
                    # Last resort: try reading as plain text with common encodings
                    try:
                        # Try common encodings for Windows documents
                        for encoding in ['utf-8', 'windows-1252', 'latin-1', 'cp1252']:
                            try:
                                with open(str(file_path), 'r', encoding=encoding) as f:
                                    text_content = f.read()
                                break  # Success, stop trying
                            except (UnicodeDecodeError, LookupError):
                                continue
                        else:
                            # If all encodings fail, use utf-8 with replace
                            with open(str(file_path), 'r', encoding='utf-8', errors='replace') as f:
                                text_content = f.read()
                    except IOError as io_error:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Could not read .doc file: {str(io_error)}"
                        )
                    except Exception as final_error:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Could not extract text from .doc file (tried python-docx, Tika, and plain text). Original error: {str(docx_error)}, Final error: {str(final_error)}"
                        )

        elif extension == '.rtf':
            # Use striprtf
            from striprtf.striprtf import rtf_to_text
            with open(str(file_path), 'r', encoding='utf-8', errors='ignore') as f:
                rtf_content = f.read()
                text_content = rtf_to_text(rtf_content)

        elif extension == '.epub':
            # Use ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup
            book = epub.read_epub(str(file_path))
            text_parts = []
            for item in book.get_items():
                if item.get_type() == 9:  # ITEM_DOCUMENT
                    soup = BeautifulSoup(item.get_content(), 'html.parser')
                    # Extract text and preserve paragraph breaks
                    for p in soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                        text = p.get_text().strip()
                        if text:
                            text_parts.append(text)
            text_content = "\n\n".join(text_parts)

        elif extension in ['.txt', '.md', '.markdown']:
            # Plain text files
            with open(str(file_path), 'r', encoding='utf-8', errors='ignore') as f:
                text_content = f.read()

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Text extraction not supported for {extension} files"
            )

        # Clean up text: remove excessive whitespace
        text_content = "\n\n".join(
            line.strip() for line in text_content.split("\n") if line.strip()
        )

        return {
            "text": text_content,
            "length": len(text_content),
            "extension": extension
        }

    except HTTPException:
        # Re-raise HTTP exceptions from inner code
        raise
    except Exception as e:
        # Log unexpected errors for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error extracting text from {file.filename} (id={file_id}): {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract text: {str(e)}"
        )


@router.get("/files/{file_id}/metadata")
async def get_file_metadata(file_id: int, db: Session = Depends(get_db)):
    """Get full file metadata including entries."""
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    entries = db.query(Entry).filter(Entry.file_id == file_id).all()
    
    # Format file size
    size_bytes = file.size_bytes or 0
    if size_bytes < 1024:
        size_formatted = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_formatted = f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        size_formatted = f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        size_formatted = f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    # Get series info if available
    series_info = None
    if file.meta_json and file.meta_json.get("series_name"):
        series_info = {
            "name": file.meta_json.get("series_name"),
            "number": file.meta_json.get("series_number"),
            "total": file.meta_json.get("series_total")
        }

    return {
        "paths": {
            "container": file.path,
            "host": None  # TODO: Add host path mapping from settings
        },
        "file_info": {
            "size_formatted": size_formatted,
            "size_bytes": size_bytes,
            "file_type": file.file_type,
            "extension": file.extension,
            "modified": file.mtime.isoformat() if file.mtime else None,
            "sha256": file.sha256
        },
        "processing": {
            "entry_count": len(entries),
            "status": file.status or "ok",
            "doc_status": file.doc_status or "pending"
        },
        "enrichment": {
            "title": file.meta_json.get("doc_title") if file.meta_json else None,
            "summary": file.doc_summary,
            "category": file.meta_json.get("doc_category") if file.meta_json else None,
            "author": file.meta_json.get("doc_author") if file.meta_json else None,
            "tags": file.meta_json.get("doc_tags") if file.meta_json else None,
        },
        "series": series_info,
        "entries_info": {
            "count": len(entries),
            "entries": [
                {
                    "id": e.id,
                    "title": e.title,
                    "summary": e.summary,
                    "category": e.category,
                    "author": e.author,
                    "tags": e.tags,
                    "entry_text": e.entry_text[:500] if e.entry_text else None,
                }
                for e in entries
            ]
        }
    }


@router.get("/files/{file_id}/resolve")
def resolve_relative_path(file_id: int, path: str, db: Session = Depends(get_db)):
    """Resolve a relative path from a source file to a target file ID."""
    source_file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found")
    
    # Calculate absolute target path
    source_dir = os.path.dirname(source_file.path)
    target_path = os.path.normpath(os.path.join(source_dir, path))
    
    # Find target file
    target_file = db.query(RawFile).filter(RawFile.path == target_path).first()
    
    if not target_file:
        raise HTTPException(status_code=404, detail="Target file not found")
        
    return {"id": target_file.id, "filename": target_file.filename}


@router.get("/files/{file_id}/proxy/{relative_path:path}")
def proxy_file_content(file_id: int, relative_path: str, db: Session = Depends(get_db)):
    """Proxy content (images, etc) relative to a source file."""
    source_file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found")
    
    source_dir = os.path.dirname(source_file.path)
    target_path = os.path.normpath(os.path.join(source_dir, relative_path))
    
    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(target_path)


@router.get("/files/{file_id}/links")
def get_file_links(file_id: int, db: Session = Depends(get_db)):
    """Get all extracted links from a file."""
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    links = file.meta_json.get("links", []) if file.meta_json else []
    return {"file_id": file_id, "links": links, "count": len(links)}


@router.get("/files/{file_id}/related")
def get_related_files(file_id: int, limit: int = 10, db: Session = Depends(get_db)):
    """Get files related by links or similar content."""
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    related_files = []
    links = file.meta_json.get("links", []) if file.meta_json else []
    
    for link in links[:limit]:
        if link.get("type") == "file":
            target_path = link.get("target_path")
            if target_path:
                target = db.query(RawFile).filter(RawFile.path == target_path).first()
                if target:
                    related_files.append({
                        "id": target.id,
                        "filename": target.filename,
                        "path": target.path,
                        "link_type": "file_link"
                    })
    
    return {"file_id": file_id, "related": related_files, "count": len(related_files)}


@router.get("/files/{file_id}/series")
def get_file_series(file_id: int, db: Session = Depends(get_db)):
    """Get series information for a file."""
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    series_name = file.meta_json.get("series_name") if file.meta_json else None
    if not series_name:
        return {"series_name": None, "files": []}
    
    series_files = db.query(RawFile).filter(
        RawFile.meta_json['series_name'].astext == series_name
    ).order_by(
        func.cast(RawFile.meta_json['series_index'].astext, text('INTEGER'))
    ).all()
    
    return {
        "series_name": series_name,
        "files": [
            {
                "id": f.id,
                "filename": f.filename,
                "series_index": f.meta_json.get("series_index") if f.meta_json else None
            }
            for f in series_files
        ],
        "count": len(series_files)
    }


@router.post("/files/{file_id}/re-enrich")
def re_enrich_file(file_id: int, db: Session = Depends(get_db)):
    """Reset all entries for a file for re-enrichment."""
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    count = db.query(Entry).filter(Entry.file_id == file_id).update({
        "status": "pending",
        "retry_count": 0,
        "title": None,
        "author": None,
        "tags": None,
        "summary": None,
        "embedding": None,
        "category": None
    })
    
    db.commit()
    
    return {"message": f"Reset {count} entries for file {file_id} for re-enrichment"}


# ============================================================================
# Entries Endpoints
# ============================================================================

@router.get("/entries/list")
def list_entries(
    skip: int = 0, limit: int = 50,
    category: Optional[str] = None, author: Optional[str] = None,
    status: Optional[str] = None, file_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """List entries with filtering."""
    query = db.query(Entry)
    
    if category:
        query = query.filter(Entry.category == category)
    if author:
        query = query.filter(Entry.author == author)
    if status:
        query = query.filter(Entry.status == status)
    if file_id:
        query = query.filter(Entry.file_id == file_id)
    
    total = query.count()
    entries = query.order_by(Entry.id.desc()).offset(skip).limit(limit).all()
    
    return {
        "entries": [
            {
                "id": e.id,
                "file_id": e.file_id,
                "title": e.title,
                "summary": e.summary,
                "category": e.category,
                "author": e.author,
                "tags": e.tags,
                "status": e.status,
                "filename": e.raw_file.filename if e.raw_file else None
            }
            for e in entries
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/entries/failed")
def get_failed_entries(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """Get entries that have failed enrichment."""
    failed = db.query(Entry).filter(
        or_(Entry.status == 'error', Entry.retry_count >= 3)
    ).offset(skip).limit(limit).all()
    
    total = db.query(Entry).filter(
        or_(Entry.status == 'error', Entry.retry_count >= 3)
    ).count()
    
    return {
        "total": total,
        "items": [
            {
                "id": e.id,
                "file_id": e.file_id,
                "title": e.title,
                "status": e.status,
                "retry_count": e.retry_count,
                "filename": e.raw_file.filename if e.raw_file else None
            } for e in failed
        ]
    }


@router.post("/entries/{entry_id}/retry")
def retry_entry(entry_id: int, db: Session = Depends(get_db)):
    """Reset a failed entry to pending status for re-enrichment."""
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    entry.status = 'pending'
    entry.retry_count = 0
    db.commit()
    
    return {"message": f"Entry {entry_id} reset to pending", "id": entry_id}


@router.post("/entries/retry-all-failed")
def retry_all_failed(db: Session = Depends(get_db)):
    """Reset all failed entries to pending status."""
    count = db.query(Entry).filter(
        or_(Entry.status == 'error', Entry.retry_count >= 3)
    ).update({"status": "pending", "retry_count": 0})
    
    db.commit()
    
    return {"message": f"Reset {count} failed entries to pending"}


@router.post("/entries/{entry_id}/re-enrich")
def re_enrich_entry(entry_id: int, db: Session = Depends(get_db)):
    """Reset an entry for re-enrichment (clears metadata and embedding)."""
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    entry.status = 'pending'
    entry.retry_count = 0
    entry.title = None
    entry.author = None
    entry.tags = None
    entry.summary = None
    entry.embedding = None
    entry.category = None
    db.commit()
    
    return {"message": f"Entry {entry_id} queued for re-enrichment", "id": entry_id}


# ============================================================================
# Images Endpoints
# ============================================================================

@router.get("/images")
def list_images(
    skip: int = 0,
    limit: int = 50,
    has_description: Optional[bool] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    db: Session = Depends(get_db)
):
    """List all image files with optional filters and sorting."""
    query = db.query(RawFile).filter(RawFile.file_type == 'image')

    if has_description is True:
        query = query.filter(RawFile.vision_description.isnot(None))
    elif has_description is False:
        query = query.filter(RawFile.vision_description.is_(None))

    # Apply sorting
    sort_column = {
        'created_at': RawFile.created_at,
        'modified_at': RawFile.mtime,
        'filename': RawFile.filename,
        'size': RawFile.size_bytes,
    }.get(sort_by, RawFile.created_at)

    if sort_dir == 'desc':
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    total = query.count()
    images = query.offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "items": [
            {
                "id": img.id,
                "filename": img.filename,
                "path": img.path,
                "thumbnail_path": img.thumbnail_path,
                "width": img.image_width,
                "height": img.image_height,
                "ocr_text": img.ocr_text[:200] if img.ocr_text else None,
                "vision_description": img.vision_description[:200] if img.vision_description else None,
                "vision_model": img.vision_model,
                "has_description": img.vision_description is not None,
                "created_at": img.created_at,
                "size_bytes": img.size_bytes,
            } for img in images
        ]
    }


@router.get("/images/stats")
def get_image_stats(db: Session = Depends(get_db)):
    """Get statistics about images in the archive."""
    total_images = db.query(RawFile).filter(RawFile.file_type == 'image').count()
    with_ocr = db.query(RawFile).filter(
        RawFile.file_type == 'image',
        RawFile.ocr_text.isnot(None),
        RawFile.ocr_text != ''
    ).count()
    with_description = db.query(RawFile).filter(
        RawFile.file_type == 'image',
        RawFile.vision_description.isnot(None)
    ).count()
    
    extension_counts = db.query(
        RawFile.extension, 
        func.count(RawFile.id)
    ).filter(
        RawFile.file_type == 'image'
    ).group_by(RawFile.extension).all()
    
    return {
        "total_images": total_images,
        "with_ocr_text": with_ocr,
        "with_vision_description": with_description,
        "without_description": total_images - with_description,
        "by_extension": {ext: count for ext, count in extension_counts}
    }


@router.get("/images/{image_id}")
def get_image_details(image_id: int, db: Session = Depends(get_db)):
    """Get full details for a specific image."""
    image = db.query(RawFile).filter(RawFile.id == image_id, RawFile.file_type == 'image').first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    return {
        "id": image.id,
        "filename": image.filename,
        "path": image.path,
        "thumbnail_path": image.thumbnail_path,
        "width": image.image_width,
        "height": image.image_height,
        "ocr_text": image.ocr_text,
        "vision_description": image.vision_description,
        "vision_model": image.vision_model,
        "raw_text": image.raw_text,
        "created_at": image.created_at,
        "size_bytes": image.size_bytes,
    }


@router.get("/images/{image_id}/thumbnail")
def serve_thumbnail(image_id: int, db: Session = Depends(get_db)):
    """Serve thumbnail image."""
    image = db.query(RawFile).filter(RawFile.id == image_id, RawFile.file_type == 'image').first()
    if not image or not image.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    
    # thumbnail_path in DB is just the filename; construct full path
    full_thumbnail_path = os.path.join(THUMBNAIL_DIR, image.thumbnail_path)
    
    if not os.path.exists(full_thumbnail_path):
        raise HTTPException(status_code=404, detail="Thumbnail file missing")
    
    return FileResponse(full_thumbnail_path, media_type="image/jpeg")


@router.get("/images/{image_id}/full")
def serve_full_image(image_id: int, db: Session = Depends(get_db)):
    """Serve full resolution image."""
    image = db.query(RawFile).filter(RawFile.id == image_id, RawFile.file_type == 'image').first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    if not os.path.exists(image.path):
        raise HTTPException(status_code=404, detail="Image file missing")
    
    mime_type, _ = mimetypes.guess_type(image.path)
    return FileResponse(image.path, media_type=mime_type or "image/jpeg")


# ============================================================================
# Series & Links Endpoints
# ============================================================================

@router.get("/series")
def list_series(db: Session = Depends(get_db)):
    """List all series in the archive."""
    series_result = db.execute(text("""
        SELECT 
            meta_json->>'series_name' as series_name,
            COUNT(*) as file_count,
            MIN(CAST(meta_json->>'series_index' AS INTEGER)) as start_index,
            MAX(CAST(meta_json->>'series_index' AS INTEGER)) as end_index
        FROM raw_files
        WHERE meta_json->>'series_name' IS NOT NULL
        GROUP BY meta_json->>'series_name'
        ORDER BY series_name
    """)).fetchall()
    
    return {
        "series": [
            {
                "name": row[0],
                "file_count": row[1],
                "start_index": row[2],
                "end_index": row[3]
            }
            for row in series_result
        ],
        "count": len(series_result)
    }


@router.get("/series/{series_name}")
def get_series_files(series_name: str, db: Session = Depends(get_db)):
    """Get all files in a series, ordered by index."""
    files = db.query(RawFile).filter(
        RawFile.meta_json['series_name'].astext == series_name
    ).order_by(
        func.cast(RawFile.meta_json['series_index'].astext, text('INTEGER'))
    ).all()
    
    if not files:
        raise HTTPException(status_code=404, detail="Series not found")
    
    return {
        "series_name": series_name,
        "files": [
            {
                "id": f.id,
                "filename": f.filename,
                "path": f.path,
                "series_index": f.meta_json.get("series_index") if f.meta_json else None,
                "doc_category": f.meta_json.get("doc_category") if f.meta_json else None,
                "doc_author": f.meta_json.get("doc_author") if f.meta_json else None,
            }
            for f in files
        ],
        "count": len(files)
    }


@router.get("/links/stats")
def get_links_stats(db: Session = Depends(get_db)):
    """Get statistics about extracted links."""
    result = db.execute(text("""
        SELECT 
            COUNT(*) as total_files_with_links,
            SUM(jsonb_array_length(meta_json->'links')) as total_links
        FROM raw_files
        WHERE meta_json->'links' IS NOT NULL
    """)).fetchone()
    
    return {
        "files_with_links": result[0] if result else 0,
        "total_links": int(result[1]) if result and result[1] else 0
    }


# ============================================================================
# Config Endpoints
# ============================================================================

@router.get("/config/enrichment")
def get_enrichment_config():
    """Get current enrichment configuration for transparency/education."""
    import yaml
    
    config_path = Path("config/enrichment.yaml")
    if not config_path.exists():
        return {"error": "Config file not found", "config": {}}
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    return {"config": config}


@router.get("/config/inheritance-stats")
def get_inheritance_stats(db: Session = Depends(get_db)):
    """Get statistics about metadata inheritance status."""
    result = db.execute(text("""
        SELECT 
            COUNT(*) as total_files,
            COUNT(CASE WHEN meta_json->'_inherited' = 'true' THEN 1 END) as inherited_count,
            COUNT(CASE WHEN meta_json->>'doc_category' IS NOT NULL THEN 1 END) as with_category,
            COUNT(CASE WHEN meta_json->>'doc_author' IS NOT NULL THEN 1 END) as with_author
        FROM raw_files
    """)).fetchone()
    
    return {
        "total_files": result[0],
        "inherited_count": result[1],
        "with_category": result[2],
        "with_author": result[3]
    }


@router.post("/config/inherit-metadata")
def inherit_metadata(db: Session = Depends(get_db)):
    """Trigger metadata inheritance job."""
    stats = inherit_doc_metadata_batch(db)
    return stats


# ============================================================================
# Vision Endpoints
# ============================================================================

@router.get("/vision/models")
def get_vision_models():
    """Get available vision models."""
    available = list_vision_models()
    return {
        "available": available,
        "default": VISION_MODEL,
    }


@router.post("/images/{image_id}/analyze")
async def analyze_image(image_id: int, model: Optional[str] = None, db: Session = Depends(get_db)):
    """Analyze an image with vision model."""
    image = db.query(RawFile).filter(RawFile.id == image_id, RawFile.file_type == 'image').first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    description = describe_image(image.path, model=model or "llava")
    
    # Save description
    image.vision_description = description
    image.vision_model = model or "default"
    db.commit()
    
    return {
        "image_id": image_id,
        "vision_description": description,
        "model": image.vision_model
    }


@router.post("/images/analyze-batch")
async def analyze_images_batch(
    image_ids: List[int],
    model: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Analyze multiple images in batch."""
    results = []
    for image_id in image_ids:
        image = db.query(RawFile).filter(RawFile.id == image_id, RawFile.file_type == 'image').first()
        if not image:
            results.append({"image_id": image_id, "error": "Image not found"})
            continue
        
        try:
            description = describe_image(image.path, model=model or "llava")
            image.vision_description = description
            image.vision_model = model or "default"
            db.commit()
            results.append({"image_id": image_id, "description": description})
        except Exception as e:
            results.append({"image_id": image_id, "error": str(e)})
    
    return {"results": results, "total": len(results)}


# ============================================================================
# Additional Entry Endpoints
# ============================================================================

@router.get("/entries/needs-review")
def get_needs_review_entries(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """Get entries flagged for quality review."""
    needs_review = db.query(Entry).filter(
        Entry.status == 'needs_review'
    ).offset(skip).limit(limit).all()
    
    total = db.query(Entry).filter(Entry.status == 'needs_review').count()
    
    return {
        "total": total,
        "items": [
            {
                "id": e.id,
                "file_id": e.file_id,
                "title": e.title,
                "summary": e.summary,
                "category": e.category,
                "filename": e.raw_file.filename if e.raw_file else None,
                "quality_score": e.meta_json.get("quality_score") if e.meta_json else None
            } for e in needs_review
        ]
    }


@router.get("/entries/quality-stats")
def get_quality_stats(db: Session = Depends(get_db)):
    """Get quality statistics for entries."""
    result = db.execute(text("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN status = 'needs_review' THEN 1 END) as needs_review,
            COUNT(CASE WHEN status = 'error' THEN 1 END) as errors,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'complete' THEN 1 END) as complete,
            AVG(CAST(meta_json->>'quality_score' AS FLOAT)) as avg_quality
        FROM entries
    """)).fetchone()
    
    return {
        "total": result[0],
        "needs_review": result[1],
        "errors": result[2],
        "pending": result[3],
        "complete": result[4],
        "avg_quality_score": round(result[5], 2) if result[5] else None
    }


@router.get("/entries/{entry_id}/inspect")
def inspect_entry(entry_id: int, db: Session = Depends(get_db)):
    """Get detailed entry information for inspection."""
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return {
        "id": entry.id,
        "file_id": entry.file_id,
        "title": entry.title,
        "summary": entry.summary,
        "category": entry.category,
        "author": entry.author,
        "tags": entry.tags,
        "entry_text": entry.entry_text,
        "status": entry.status,
        "retry_count": entry.retry_count,
        "page_num": entry.page_num,
        "meta_json": entry.meta_json,
        "has_embedding": entry.embedding is not None,
        "filename": entry.raw_file.filename if entry.raw_file else None,
        "file_path": entry.raw_file.path if entry.raw_file else None
    }


@router.get("/entries/{entry_id}/debug")
def entry_debug_info(entry_id: int, db: Session = Depends(get_db)):
    """Get debug information for an entry including embedding details."""
    import numpy as np
    
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    embedding_info = None
    if entry.embedding is not None:
        emb_array = np.array(entry.embedding)
        embedding_info = {
            "dimensions": len(entry.embedding),
            "norm": float(np.linalg.norm(emb_array)),
            "mean": float(np.mean(emb_array)),
            "std": float(np.std(emb_array)),
            "min": float(np.min(emb_array)),
            "max": float(np.max(emb_array))
        }
    
    return {
        "entry_id": entry.id,
        "file_id": entry.file_id,
        "title": entry.title,
        "text_length": len(entry.entry_text) if entry.entry_text else 0,
        "has_embedding": entry.embedding is not None,
        "embedding_info": embedding_info,
        "status": entry.status,
        "category": entry.category,
        "tags": entry.tags
    }


@router.get("/entries/{entry_id}/nearby")
def get_nearby_entries(entry_id: int, k: int = 10, db: Session = Depends(get_db)):
    """Get semantically similar entries using cosine similarity."""
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry or entry.embedding is None:
        raise HTTPException(status_code=404, detail="Entry not found or no embedding")
    
    from src.rag.search import search_entries_semantic
    
    results = search_entries_semantic(db, entry.entry_text or "", k=k+1, mode='vector')
    nearby = [r for r in results if r.id != entry_id][:k]
    
    return {
        "entry_id": entry_id,
        "nearby": [
            {
                "id": e.id,
                "title": e.title,
                "summary": e.summary,
                "category": e.category,
                "filename": e.raw_file.filename if e.raw_file else None
            }
            for e in nearby
        ],
        "count": len(nearby)
    }


@router.get("/entries/{entry_id}/embedding-viz")
def get_entry_embedding_viz(entry_id: int, db: Session = Depends(get_db)):
    """Get entry embedding for visualization."""
    import numpy as np
    
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    if entry.embedding is None:
        raise HTTPException(status_code=404, detail="Entry has no embedding")
    
    emb_array = np.array(entry.embedding)
    
    return {
        "entry_id": entry.id,
        "title": entry.title,
        "category": entry.category,
        "embedding": {
            "dimensions": len(entry.embedding),
            "values": entry.embedding[:50],
            "norm": float(np.linalg.norm(emb_array)),
            "mean": float(np.mean(emb_array)),
            "std": float(np.std(emb_array))
        }
    }
