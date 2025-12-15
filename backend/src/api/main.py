from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import os
import json

from src.db.session import get_db
from src.db.models import RawFile, Entry, DocumentLink
from src.rag.search import search_entries_semantic
from src.llm_client import generate_text, list_models, OLLAMA_URL, MODEL, EMBEDDING_MODEL
import requests

app = FastAPI(title="Archive Brain API")

# Worker state file (shared with worker_loop.py)
SHARED_DIR = "/app/shared"
WORKER_STATE_FILE = os.path.join(SHARED_DIR, "worker_state.json")
WORKER_LOG_FILE = os.path.join(SHARED_DIR, "worker.log")
INGEST_PROGRESS_FILE = os.path.join(SHARED_DIR, "ingest_progress.json")
ENRICH_PROGRESS_FILE = os.path.join(SHARED_DIR, "enrich_progress.json")
EMBED_PROGRESS_FILE = os.path.join(SHARED_DIR, "embed_progress.json")

class AskRequest(BaseModel):
    query: str
    k: int = 5
    model: Optional[str] = None
    filters: Optional[dict] = None

class AskResponse(BaseModel):
    answer: str
    sources: List[dict]

class FileDetail(BaseModel):
    id: int
    filename: str
    path: str
    raw_text: str

class WorkerStateUpdate(BaseModel):
    ingest: Optional[bool] = None
    segment: Optional[bool] = None
    enrich: Optional[bool] = None
    embed: Optional[bool] = None
    running: Optional[bool] = None

def get_worker_state():
    """Read the current worker state."""
    default_state = {
        "ingest": True,
        "segment": True,
        "enrich": True,
        "embed": True,
        "running": True
    }
    try:
        if os.path.exists(WORKER_STATE_FILE):
            with open(WORKER_STATE_FILE, 'r') as f:
                return {**default_state, **json.load(f)}
    except Exception:
        pass
    return default_state

def save_worker_state(state):
    """Save the worker state."""
    try:
        with open(WORKER_STATE_FILE, 'w') as f:
            json.dump(state, f)
        return True
    except Exception:
        return False

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/worker/state")
def get_worker_state_endpoint():
    """Get current worker process states."""
    return get_worker_state()

@app.post("/worker/state")
def update_worker_state(update: WorkerStateUpdate):
    """Update worker process states."""
    current = get_worker_state()
    
    if update.ingest is not None:
        current["ingest"] = update.ingest
    if update.segment is not None:
        current["segment"] = update.segment
    if update.enrich is not None:
        current["enrich"] = update.enrich
    if update.embed is not None:
        current["embed"] = update.embed
    if update.running is not None:
        current["running"] = update.running
    
    if save_worker_state(current):
        return current
    else:
        raise HTTPException(status_code=500, detail="Failed to save worker state")

@app.get("/worker/logs")
def get_worker_logs(lines: int = 100):
    """Get the last N lines from the worker log file."""
    try:
        if not os.path.exists(WORKER_LOG_FILE):
            return {"lines": [], "message": "Log file not found. Worker may need to be restarted."}
        
        with open(WORKER_LOG_FILE, 'r') as f:
            all_lines = f.readlines()
            return {"lines": all_lines[-lines:]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/worker/progress")
def get_worker_progress():
    """Get progress for all pipeline phases."""
    def read_progress(filepath, default_phase):
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "phase": default_phase,
            "current": 0,
            "total": 0,
            "percent": 0,
            "updated_at": None
        }
    
    return {
        "ingest": read_progress(INGEST_PROGRESS_FILE, "idle"),
        "enrich": read_progress(ENRICH_PROGRESS_FILE, "idle"),
        "embed": read_progress(EMBED_PROGRESS_FILE, "idle")
    }

@app.get("/system/status")
def get_system_status():
    ollama_status = "offline"
    available_models = []
    try:
        # Simple check to see if Ollama is responding
        resp = requests.get(f"{OLLAMA_URL}", timeout=1)
        if resp.status_code == 200:
            ollama_status = "online"
            available_models = list_models()
    except Exception:
        pass
        
    return {
        "ollama": {
            "status": ollama_status,
            "url": OLLAMA_URL,
            "chat_model": MODEL,
            "embedding_model": EMBEDDING_MODEL,
            "available_models": available_models
        }
    }

@app.get("/system/metrics")
def get_system_metrics(db: Session = Depends(get_db)):
    from sqlalchemy import func as sql_func
    
    total_files = db.query(RawFile).count()
    processed_files = db.query(RawFile).filter(RawFile.status == 'ok').count()
    failed_files = db.query(RawFile).filter(RawFile.status == 'extract_failed').count()
    total_entries = db.query(Entry).count()
    enriched_entries = db.query(Entry).filter(Entry.status == 'enriched').count()
    embedded_entries = db.query(Entry).filter(Entry.embedding.isnot(None)).count()
    pending_entries = db.query(Entry).filter(Entry.status == 'pending').count()
    
    # Get recent activity - last 10 files
    recent_files = db.query(RawFile).order_by(RawFile.created_at.desc()).limit(10).all()
    
    # Get file size stats
    size_result = db.query(sql_func.sum(RawFile.size_bytes)).scalar() or 0
    
    # Get extension breakdown
    ext_counts = db.query(RawFile.extension, sql_func.count(RawFile.id)).group_by(RawFile.extension).order_by(sql_func.count(RawFile.id).desc()).limit(10).all()
    
    return {
        "files": {
            "total": total_files,
            "processed": processed_files,
            "failed": failed_files,
            "pending": total_files - processed_files
        },
        "entries": {
            "total": total_entries,
            "enriched": enriched_entries,
            "embedded": embedded_entries,
            "pending": pending_entries
        },
        "storage": {
            "total_bytes": size_result,
            "total_mb": round(size_result / (1024 * 1024), 2) if size_result else 0
        },
        "extensions": [{"ext": ext, "count": count} for ext, count in ext_counts],
        "recent_files": [
            {
                "id": f.id,
                "filename": f.filename,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "status": f.status
            } for f in recent_files
        ]
    }

@app.get("/files/{file_id}/content")
def get_file_content(file_id: int, db: Session = Depends(get_db)):
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not os.path.exists(file.path):
        raise HTTPException(status_code=404, detail="File not found on disk")
        
    return FileResponse(file.path, filename=file.filename)

@app.get("/files")
def list_files(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    total = db.query(RawFile).count()
    files = db.query(RawFile).order_by(RawFile.id.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": f.id,
                "filename": f.filename,
                "path": f.path,
                "created_at": f.created_at,
                "status": f.status
            } for f in files
        ]
    }

@app.get("/files/{file_id}", response_model=FileDetail)
def get_file_details(file_id: int, db: Session = Depends(get_db)):
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file

@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, db: Session = Depends(get_db)):
    # 1. Search
    results = search_entries_semantic(db, request.query, k=request.k, filters=request.filters)
    
    if not results:
        return AskResponse(answer="I couldn't find any relevant documents in the archive.", sources=[])
    
    # 2. Build Context
    context_parts = []
    sources = []
    for i, entry in enumerate(results):
        # Fallback to filename if title is missing
        title = entry.title
        if not title and entry.raw_file:
            # Use filename without extension
            title = os.path.splitext(entry.raw_file.filename)[0]
            
        context_parts.append(f"Document {i+1}:\nTitle: {title}\nContent: {entry.entry_text}\n")
        sources.append({
            "id": entry.id,
            "file_id": entry.file_id,
            "title": title,
            "path": entry.raw_file.path if entry.raw_file else None
        })
    
    context = "\n".join(context_parts)
    
    # 3. Prompt
    prompt = f"""You are my personal archive assistant.
Use ONLY the following documents to answer the question.
If the answer is not in these documents, say "I can't find that in this archive."

Documents:
{context}

Question: {request.query}
"""

    # 4. Generate
    # Use requested model or default to env var
    model_to_use = request.model if request.model else MODEL
    answer = generate_text(prompt, model=model_to_use)
    
    if not answer:
        raise HTTPException(status_code=500, detail="Failed to generate answer")
        
    return AskResponse(answer=answer, sources=sources)

@app.get("/files/{file_id}/resolve")
def resolve_relative_path(file_id: int, path: str, db: Session = Depends(get_db)):
    """Resolve a relative path from a source file to a target file ID."""
    source_file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found")
    
    # Calculate absolute target path
    source_dir = os.path.dirname(source_file.path)
    # Normalize path to handle ../ etc
    target_path = os.path.normpath(os.path.join(source_dir, path))
    
    # Find target file
    target_file = db.query(RawFile).filter(RawFile.path == target_path).first()
    
    if not target_file:
        raise HTTPException(status_code=404, detail="Target file not found")
        
    return {"id": target_file.id, "filename": target_file.filename}

@app.get("/files/{file_id}/proxy/{relative_path:path}")
def proxy_file_content(file_id: int, relative_path: str, db: Session = Depends(get_db)):
    """Proxy content (images, etc) relative to a source file."""
    source_file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found")
    
    source_dir = os.path.dirname(source_file.path)
    target_path = os.path.normpath(os.path.join(source_dir, relative_path))
    
    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    # Security check: ensure we haven't traversed out of allowed areas?
    # For now, assuming all files in DB are safe or we trust the file system access.
    # Ideally we should check if target_path is within archive_root.
    
    return FileResponse(target_path)

@app.get("/health")
def health():
    return {"status": "ok"}

# === Entry Management Endpoints ===

@app.get("/entries/failed")
def get_failed_entries(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """Get entries that have failed enrichment (status='error' or hit max retries)."""
    from sqlalchemy import or_
    
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

@app.post("/entries/{entry_id}/retry")
def retry_entry(entry_id: int, db: Session = Depends(get_db)):
    """Reset a failed entry to pending status for re-enrichment."""
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    entry.status = 'pending'
    entry.retry_count = 0
    db.commit()
    
    return {"message": f"Entry {entry_id} reset to pending", "id": entry_id}

@app.post("/entries/retry-all-failed")
def retry_all_failed(db: Session = Depends(get_db)):
    """Reset all failed entries to pending status."""
    from sqlalchemy import or_
    
    count = db.query(Entry).filter(
        or_(Entry.status == 'error', Entry.retry_count >= 3)
    ).update({"status": "pending", "retry_count": 0})
    
    db.commit()
    
    return {"message": f"Reset {count} failed entries to pending"}

@app.post("/entries/{entry_id}/re-enrich")
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

@app.post("/files/{file_id}/re-enrich")
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

@app.get("/config/enrichment")
def get_enrichment_config():
    """Get current enrichment configuration for transparency/education."""
    import yaml
    import os
    
    config_path = os.environ.get("CONFIG_PATH", "/app/config/config.yaml")
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        enrichment = config.get('enrichment', {})
        return {
            "prompt_template": enrichment.get('prompt_template', '(using default prompt)'),
            "max_text_length": enrichment.get('max_text_length', 4000),
            "custom_fields": enrichment.get('custom_fields', []),
            "model": config.get('ollama', {}).get('model', 'unknown')
        }
    except Exception as e:
        return {
            "error": str(e),
            "prompt_template": "(config not available)",
            "max_text_length": 4000,
            "custom_fields": [],
            "model": "unknown"
        }

# ============================================================================
# Link Extraction & Related Documents
# ============================================================================

@app.get("/files/{file_id}/links")
def get_file_links(file_id: int, db: Session = Depends(get_db)):
    """Get all links extracted from a file."""
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    links = db.query(DocumentLink).filter(DocumentLink.file_id == file_id).all()
    
    return {
        "file_id": file_id,
        "file_path": file.path,
        "link_count": len(links),
        "links": [
            {
                "id": link.id,
                "url": link.url,
                "link_text": link.link_text,
                "link_type": link.link_type,
                "domain": link.domain
            }
            for link in links
        ]
    }

@app.get("/files/{file_id}/related")
def get_related_files(file_id: int, db: Session = Depends(get_db)):
    """Find files that share common domains/links with this file."""
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get domains from this file
    file_domains = db.query(DocumentLink.domain).filter(
        DocumentLink.file_id == file_id,
        DocumentLink.domain.isnot(None)
    ).distinct().all()
    domains = [d[0] for d in file_domains]
    
    if not domains:
        return {"file_id": file_id, "related_files": [], "shared_domains": []}
    
    # Find other files that share these domains
    related = db.query(
        RawFile.id,
        RawFile.path,
        RawFile.filename,
        func.count(DocumentLink.id).label('shared_link_count')
    ).join(DocumentLink).filter(
        DocumentLink.domain.in_(domains),
        RawFile.id != file_id
    ).group_by(RawFile.id).order_by(func.count(DocumentLink.id).desc()).limit(20).all()
    
    return {
        "file_id": file_id,
        "shared_domains": domains,
        "related_files": [
            {
                "id": r.id,
                "path": r.path,
                "filename": r.filename,
                "shared_link_count": r.shared_link_count
            }
            for r in related
        ]
    }

@app.get("/links/stats")
def get_link_stats(db: Session = Depends(get_db)):
    """Get overall statistics about extracted links."""
    total_links = db.query(func.count(DocumentLink.id)).scalar()
    files_with_links = db.query(func.count(func.distinct(DocumentLink.file_id))).scalar()
    unique_domains = db.query(func.count(func.distinct(DocumentLink.domain))).filter(
        DocumentLink.domain.isnot(None)
    ).scalar()
    
    # Top domains
    top_domains = db.query(
        DocumentLink.domain,
        func.count(DocumentLink.id).label('count')
    ).filter(
        DocumentLink.domain.isnot(None)
    ).group_by(DocumentLink.domain).order_by(func.count(DocumentLink.id).desc()).limit(20).all()
    
    # Link types breakdown
    link_types = db.query(
        DocumentLink.link_type,
        func.count(DocumentLink.id).label('count')
    ).group_by(DocumentLink.link_type).all()
    
    return {
        "total_links": total_links,
        "files_with_links": files_with_links,
        "unique_domains": unique_domains,
        "top_domains": [{"domain": d.domain, "count": d.count} for d in top_domains],
        "link_types": {lt.link_type: lt.count for lt in link_types}
    }
