from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, text
import os
import json
import yaml

from src.db.session import get_db
from src.db.models import RawFile, Entry, DocumentLink
from src.db.settings import (
    get_setting, set_setting, get_all_settings, get_llm_config,
    get_source_folders, add_source_folder, remove_source_folder,
    add_exclude_pattern, remove_exclude_pattern, Setting, DEFAULT_SETTINGS
)
from src.rag.search import search_entries_semantic, SEARCH_MODE_VECTOR, SEARCH_MODE_KEYWORD, SEARCH_MODE_HYBRID
from src.llm_client import generate_text, list_models, list_vision_models, describe_image, OLLAMA_URL, MODEL, EMBEDDING_MODEL, VISION_MODEL
import requests

app = FastAPI(title="Archive Brain API")

# Worker state file (shared with worker_loop.py)
if os.path.exists("/app/shared"):
    SHARED_DIR = "/app/shared"
else:
    # Local development fallback: backend/shared
    SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "shared")

# Ensure shared directory exists
os.makedirs(SHARED_DIR, exist_ok=True)

THUMBNAIL_DIR = os.path.join(SHARED_DIR, "thumbnails")
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
    search_mode: Optional[str] = 'hybrid'  # 'vector', 'keyword', or 'hybrid'
    vector_weight: Optional[float] = 0.7  # Weight for vector vs keyword in hybrid mode

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
    enrich_docs: Optional[bool] = None
    embed: Optional[bool] = None
    embed_docs: Optional[bool] = None
    running: Optional[bool] = None

def get_worker_state():
    """Read the current worker state."""
    default_state = {
        "ingest": True,
        "segment": True,
        "enrich": True,
        "enrich_docs": True,
        "embed": True,
        "embed_docs": True,
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
    if update.enrich_docs is not None:
        current["enrich_docs"] = update.enrich_docs
    if update.embed is not None:
        current["embed"] = update.embed
    if update.embed_docs is not None:
        current["embed_docs"] = update.embed_docs
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

@app.get("/worker/stats")
def get_worker_stats(db: Session = Depends(get_db)):
    """Get comprehensive worker statistics including ETAs."""
    from datetime import datetime, timedelta
    
    # Get counts by status
    status_counts = db.execute(text("""
        SELECT status, COUNT(*) as count 
        FROM entries 
        GROUP BY status
    """)).fetchall()
    
    counts = {row[0]: row[1] for row in status_counts}
    total_entries = sum(counts.values())
    
    pending = counts.get('pending', 0)
    enriched = counts.get('enriched', 0)
    embedded = db.query(Entry).filter(Entry.embedding.isnot(None)).count()
    
    # Get recent enrichment rate (last hour)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_enriched = db.execute(text("""
        SELECT COUNT(*) FROM entries 
        WHERE status = 'enriched' 
        AND updated_at > :cutoff
    """), {"cutoff": one_hour_ago}).scalar() or 0
    
    # Calculate rate per minute
    enrich_rate_per_min = recent_enriched / 60 if recent_enriched > 0 else 0
    
    # Calculate ETA
    eta_minutes = pending / enrich_rate_per_min if enrich_rate_per_min > 0 else None
    eta_hours = eta_minutes / 60 if eta_minutes else None
    eta_days = eta_hours / 24 if eta_hours else None
    
    # Format ETA string
    if eta_days is None:
        eta_str = "Calculating..."
    elif eta_days > 365:
        eta_str = f"{eta_days/365:.1f} years"
    elif eta_days > 30:
        eta_str = f"{eta_days/30:.1f} months"
    elif eta_days > 1:
        eta_str = f"{eta_days:.1f} days"
    elif eta_hours > 1:
        eta_str = f"{eta_hours:.1f} hours"
    else:
        eta_str = f"{eta_minutes:.0f} minutes"
    
    return {
        "counts": {
            "total": total_entries,
            "pending": pending,
            "enriched": enriched,
            "embedded": embedded,
            "error": counts.get('error', 0)
        },
        "rates": {
            "enrich_per_minute": round(enrich_rate_per_min, 2),
            "enrich_per_hour": recent_enriched,
            "sample_period": "1 hour"
        },
        "eta": {
            "pending_count": pending,
            "eta_minutes": round(eta_minutes, 0) if eta_minutes else None,
            "eta_hours": round(eta_hours, 1) if eta_hours else None,
            "eta_days": round(eta_days, 1) if eta_days else None,
            "eta_string": eta_str
        },
        "docs": get_doc_stats(db)
    }

def get_doc_stats(db: Session) -> dict:
    """Get doc-level enrichment/embedding stats."""
    try:
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE doc_status = 'pending') as pending,
                COUNT(*) FILTER (WHERE doc_status = 'enriched') as enriched,
                COUNT(*) FILTER (WHERE doc_status = 'embedded') as embedded,
                COUNT(*) FILTER (WHERE doc_status IN ('error', 'embed_error')) as error,
                COUNT(doc_embedding) as has_embedding
            FROM raw_files
        """)).fetchone()
        
        return {
            "total": result[0],
            "pending": result[1],
            "enriched": result[2],
            "embedded": result[3],
            "error": result[4],
            "has_embedding": result[5]
        }
    except Exception:
        return {"error": "Could not fetch doc stats"}

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

# ==================== Lightweight Metrics Endpoints ====================
# These are fast endpoints for incremental dashboard loading

@app.get("/system/counts")
def get_system_counts(db: Session = Depends(get_db)):
    """Fast endpoint - just core counts, no joins or heavy queries."""
    result = db.execute(text("""
        SELECT 
            (SELECT COUNT(*) FROM raw_files) as files_total,
            (SELECT COUNT(*) FROM raw_files WHERE status = 'ok') as files_processed,
            (SELECT COUNT(*) FROM entries) as entries_total,
            (SELECT COUNT(*) FROM entries WHERE status = 'enriched') as entries_enriched,
            (SELECT COUNT(*) FROM entries WHERE embedding IS NOT NULL) as entries_embedded
    """)).fetchone()
    return {
        "files": {"total": result[0], "processed": result[1]},
        "entries": {"total": result[2], "enriched": result[3], "embedded": result[4]}
    }

@app.get("/system/doc-counts")
def get_doc_counts(db: Session = Depends(get_db)):
    """Fast endpoint - doc-level stats only."""
    result = db.execute(text("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE doc_status = 'pending') as pending,
            COUNT(*) FILTER (WHERE doc_status IN ('enriched', 'embedded')) as enriched,
            COUNT(*) FILTER (WHERE doc_status = 'embedded') as embedded,
            COUNT(*) FILTER (WHERE doc_status IN ('error', 'embed_error')) as error
        FROM raw_files
    """)).fetchone()
    return {
        "total": result[0], "pending": result[1], 
        "enriched": result[2], "embedded": result[3], "error": result[4]
    }

@app.get("/system/storage")
def get_storage_stats(db: Session = Depends(get_db)):
    """Storage stats - can be loaded lazily."""
    from sqlalchemy import func as sql_func
    size_result = db.query(sql_func.sum(RawFile.size_bytes)).scalar() or 0
    return {
        "total_bytes": size_result,
        "total_mb": round(size_result / (1024 * 1024), 2) if size_result else 0,
        "total_gb": round(size_result / (1024 * 1024 * 1024), 2) if size_result else 0
    }

@app.get("/system/extensions")
def get_extension_stats(db: Session = Depends(get_db)):
    """Extension breakdown - can be loaded lazily."""
    from sqlalchemy import func as sql_func
    ext_counts = db.query(RawFile.extension, sql_func.count(RawFile.id)).group_by(RawFile.extension).order_by(sql_func.count(RawFile.id).desc()).limit(15).all()
    return [{"ext": ext or "none", "count": count} for ext, count in ext_counts]

@app.get("/system/recent")
def get_recent_files(db: Session = Depends(get_db), limit: int = 10):
    """Recent files - can be loaded lazily."""
    recent_files = db.query(RawFile).order_by(RawFile.created_at.desc()).limit(limit).all()
    return [
        {"id": f.id, "filename": f.filename, "status": f.status, 
         "created_at": f.created_at.isoformat() if f.created_at else None}
        for f in recent_files
    ]

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


# ==================== Settings Endpoints ====================

class LLMSettingsUpdate(BaseModel):
    provider: str  # ollama, openai, anthropic
    ollama: Optional[Dict[str, Any]] = None
    openai: Optional[Dict[str, Any]] = None
    anthropic: Optional[Dict[str, Any]] = None

class SourceFolderAdd(BaseModel):
    path: str

class ExcludePatternAdd(BaseModel):
    pattern: str

class ExtensionsUpdate(BaseModel):
    extensions: List[str]


def ensure_settings_table(db: Session):
    """Create settings table if it doesn't exist."""
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS settings (
                key VARCHAR(255) PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.commit()
    except Exception as e:
        db.rollback()


@app.get("/settings")
def get_settings_all(db: Session = Depends(get_db)):
    """Get all settings."""
    ensure_settings_table(db)
    return get_all_settings(db)


@app.get("/settings/llm")
def get_llm_settings(db: Session = Depends(get_db)):
    """Get LLM configuration."""
    ensure_settings_table(db)
    llm = get_setting(db, "llm") or DEFAULT_SETTINGS["llm"]
    
    # Test connectivity for the active provider
    provider = llm.get("provider", "ollama")
    status = "unknown"
    
    if provider == "ollama":
        url = llm.get("ollama", {}).get("url", "http://ollama:11434")
        try:
            resp = requests.get(f"{url}/api/tags", timeout=5)
            status = "connected" if resp.status_code == 200 else "error"
        except:
            status = "offline"
    elif provider == "openai":
        api_key = llm.get("openai", {}).get("api_key", "")
        status = "configured" if api_key else "not_configured"
    elif provider == "anthropic":
        api_key = llm.get("anthropic", {}).get("api_key", "")
        status = "configured" if api_key else "not_configured"
    
    return {
        **llm,
        "status": status
    }


@app.put("/settings/llm")
def update_llm_settings(settings: LLMSettingsUpdate, db: Session = Depends(get_db)):
    """Update LLM configuration."""
    ensure_settings_table(db)
    current = get_setting(db, "llm") or DEFAULT_SETTINGS["llm"]
    
    current["provider"] = settings.provider
    
    if settings.ollama:
        current["ollama"] = {**current.get("ollama", {}), **settings.ollama}
    if settings.openai:
        current["openai"] = {**current.get("openai", {}), **settings.openai}
    if settings.anthropic:
        current["anthropic"] = {**current.get("anthropic", {}), **settings.anthropic}
    
    if set_setting(db, "llm", current):
        return current
    raise HTTPException(status_code=500, detail="Failed to save LLM settings")


# Base path for archive data inside container
ARCHIVE_BASE = "/data/archive"


@app.get("/settings/sources/mounts")
def get_available_mounts():
    """
    Get available mounted directories that can be used as source folders.
    These are paths mounted into the Docker container from the host.
    """
    mounts = []
    
    # Check /data/archive which is the main mount point
    if os.path.exists(ARCHIVE_BASE):
        for item in sorted(os.listdir(ARCHIVE_BASE)):
            item_path = os.path.join(ARCHIVE_BASE, item)
            if os.path.isdir(item_path):
                try:
                    file_count = sum(1 for _ in os.scandir(item_path) if _.is_file())
                    subdir_count = sum(1 for _ in os.scandir(item_path) if _.is_dir())
                    mounts.append({
                        "path": item_path,
                        "name": item,
                        "file_count": file_count,
                        "subdir_count": subdir_count,
                        "accessible": True
                    })
                except PermissionError:
                    mounts.append({
                        "path": item_path,
                        "name": item,
                        "file_count": 0,
                        "subdir_count": 0,
                        "accessible": False
                    })
    
    return {
        "base_path": ARCHIVE_BASE,
        "mounts": mounts,
        "instructions": {
            "title": "Adding New Source Folders",
            "steps": [
                "1. Edit docker-compose.yml in the project root",
                "2. Add a volume mount under both 'worker' and 'api' services",
                "3. Format: - /host/path:/data/archive/foldername",
                "4. Run: docker compose down && docker compose up -d",
                "5. The folder will appear here and can be added as a source"
            ],
            "example": "- /mnt/documents:/data/archive/documents"
        }
    }


@app.get("/settings/sources/browse")
def browse_directory(path: str = ARCHIVE_BASE):
    """Browse directories within the archive mount."""
    # Security: Only allow browsing within /data/archive
    if not path.startswith(ARCHIVE_BASE):
        raise HTTPException(status_code=403, detail="Can only browse within archive directory")
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Path is not a directory")
    
    items = []
    try:
        for item in sorted(os.listdir(path)):
            item_path = os.path.join(path, item)
            is_dir = os.path.isdir(item_path)
            if is_dir:
                try:
                    child_count = len(os.listdir(item_path))
                except:
                    child_count = 0
                items.append({
                    "name": item,
                    "path": item_path,
                    "is_dir": True,
                    "child_count": child_count
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    return {
        "current_path": path,
        "parent_path": os.path.dirname(path) if path != ARCHIVE_BASE else None,
        "items": items
    }


@app.get("/settings/sources")
def get_sources_settings(db: Session = Depends(get_db)):
    """Get source folder configuration."""
    ensure_settings_table(db)
    sources = get_source_folders(db)
    
    # Add folder stats
    folder_stats = []
    for path in sources.get("include", []):
        stat = {"path": path, "exists": os.path.exists(path), "file_count": 0}
        if stat["exists"] and os.path.isdir(path):
            try:
                # Count files (non-recursive for performance)
                stat["file_count"] = len([f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))])
            except:
                pass
        folder_stats.append(stat)
    
    return {
        "include": folder_stats,
        "exclude": sources.get("exclude", [])
    }


@app.post("/settings/sources/include")
def add_source_folder_endpoint(folder: SourceFolderAdd, db: Session = Depends(get_db)):
    """Add a source folder."""
    ensure_settings_table(db)
    
    # Validate path exists
    if not os.path.exists(folder.path):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {folder.path}")
    if not os.path.isdir(folder.path):
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {folder.path}")
    
    if add_source_folder(db, folder.path):
        return {"message": f"Added source folder: {folder.path}"}
    raise HTTPException(status_code=500, detail="Failed to add source folder")


@app.delete("/settings/sources/include")
def remove_source_folder_endpoint(folder: SourceFolderAdd, db: Session = Depends(get_db)):
    """Remove a source folder."""
    ensure_settings_table(db)
    if remove_source_folder(db, folder.path):
        return {"message": f"Removed source folder: {folder.path}"}
    raise HTTPException(status_code=500, detail="Failed to remove source folder")


@app.post("/settings/sources/exclude")
def add_exclude_pattern_endpoint(pattern: ExcludePatternAdd, db: Session = Depends(get_db)):
    """Add an exclude pattern."""
    ensure_settings_table(db)
    if add_exclude_pattern(db, pattern.pattern):
        return {"message": f"Added exclude pattern: {pattern.pattern}"}
    raise HTTPException(status_code=500, detail="Failed to add exclude pattern")


@app.delete("/settings/sources/exclude")
def remove_exclude_pattern_endpoint(pattern: ExcludePatternAdd, db: Session = Depends(get_db)):
    """Remove an exclude pattern."""
    ensure_settings_table(db)
    if remove_exclude_pattern(db, pattern.pattern):
        return {"message": f"Removed exclude pattern: {pattern.pattern}"}
    raise HTTPException(status_code=500, detail="Failed to remove exclude pattern")


@app.get("/settings/extensions")
def get_extensions_settings(db: Session = Depends(get_db)):
    """Get file extension configuration."""
    ensure_settings_table(db)
    return {"extensions": get_setting(db, "extensions") or DEFAULT_SETTINGS["extensions"]}


@app.put("/settings/extensions")
def update_extensions_settings(update: ExtensionsUpdate, db: Session = Depends(get_db)):
    """Update file extension configuration."""
    ensure_settings_table(db)
    # Normalize extensions (ensure they start with .)
    extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in update.extensions]
    if set_setting(db, "extensions", extensions):
        return {"extensions": extensions}
    raise HTTPException(status_code=500, detail="Failed to save extensions")


@app.post("/settings/llm/test")
def test_llm_connection(db: Session = Depends(get_db)):
    """Test the current LLM configuration."""
    ensure_settings_table(db)
    llm = get_setting(db, "llm") or DEFAULT_SETTINGS["llm"]
    provider = llm.get("provider", "ollama")
    
    result = {"provider": provider, "status": "unknown", "message": "", "models": []}
    
    try:
        if provider == "ollama":
            url = llm.get("ollama", {}).get("url", "http://ollama:11434")
            resp = requests.get(f"{url}/api/tags", timeout=10)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                result["status"] = "connected"
                result["message"] = f"Connected to Ollama at {url}"
                result["models"] = [m["name"] for m in models]
            else:
                result["status"] = "error"
                result["message"] = f"Ollama returned status {resp.status_code}"
                
        elif provider == "openai":
            api_key = llm.get("openai", {}).get("api_key", "")
            if not api_key:
                result["status"] = "not_configured"
                result["message"] = "OpenAI API key not set"
            else:
                resp = requests.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10
                )
                if resp.status_code == 200:
                    result["status"] = "connected"
                    result["message"] = "Connected to OpenAI API"
                    models = resp.json().get("data", [])
                    result["models"] = [m["id"] for m in models if "gpt" in m["id"]][:10]
                else:
                    result["status"] = "error"
                    result["message"] = f"OpenAI API error: {resp.status_code}"
                    
        elif provider == "anthropic":
            api_key = llm.get("anthropic", {}).get("api_key", "")
            if not api_key:
                result["status"] = "not_configured"
                result["message"] = "Anthropic API key not set"
            else:
                # Anthropic doesn't have a models endpoint, just test with a simple message
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": "Hi"}]
                    },
                    timeout=10
                )
                if resp.status_code == 200:
                    result["status"] = "connected"
                    result["message"] = "Connected to Anthropic API"
                    result["models"] = ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
                else:
                    result["status"] = "error"
                    result["message"] = f"Anthropic API error: {resp.status_code}"
                    
    except requests.Timeout:
        result["status"] = "timeout"
        result["message"] = "Connection timed out"
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)
    
    return result


# Known model families for capability detection
EMBEDDING_FAMILIES = {'nomic-bert', 'bert', 'e5', 'bge', 'gte', 'all-minilm'}
VISION_FAMILIES = {'clip', 'llava', 'bakllava', 'moondream'}
EMBEDDING_KEYWORDS = {'embed', 'embedding', 'e5', 'bge', 'gte', 'minilm'}
VISION_KEYWORDS = {'llava', 'vision', 'bakllava', 'moondream'}


def detect_model_capabilities(model_info: dict) -> dict:
    """Detect what capabilities a model has based on its families and name."""
    name = model_info.get("name", "").lower()
    families = set(f.lower() for f in model_info.get("details", {}).get("families", []))
    
    # Check for embedding capability
    is_embedding = bool(families & EMBEDDING_FAMILIES) or any(kw in name for kw in EMBEDDING_KEYWORDS)
    
    # Check for vision capability
    is_vision = bool(families & VISION_FAMILIES) or any(kw in name for kw in VISION_KEYWORDS)
    
    # Chat models are anything that's not purely an embedding model
    is_chat = not is_embedding or is_vision
    
    return {
        "chat": is_chat,
        "embedding": is_embedding,
        "vision": is_vision
    }


@app.get("/settings/ollama/status")
def get_ollama_status(db: Session = Depends(get_db)):
    """
    Get Ollama connection status with server details.
    Returns info about which server is connected and its status.
    """
    ensure_settings_table(db)
    llm = get_setting(db, "llm") or DEFAULT_SETTINGS["llm"]
    url = llm.get("ollama", {}).get("url", "http://ollama:11434")
    
    # Determine server type based on URL
    is_docker = "ollama:11434" in url
    is_localhost = "localhost" in url or "127.0.0.1" in url
    
    result = {
        "url": url,
        "connected": False,
        "server_type": "docker" if is_docker else "localhost" if is_localhost else "network",
        "version": None,
        "model_count": 0,
        "error": None
    }
    
    try:
        # Try to get version/status
        resp = requests.get(f"{url}/api/tags", timeout=5)
        if resp.status_code == 200:
            result["connected"] = True
            models = resp.json().get("models", [])
            result["model_count"] = len(models)
            
            # Try to get version
            try:
                ver_resp = requests.get(f"{url}/api/version", timeout=3)
                if ver_resp.status_code == 200:
                    result["version"] = ver_resp.json().get("version")
            except:
                pass
        else:
            result["error"] = f"Server returned status {resp.status_code}"
    except requests.Timeout:
        result["error"] = "Connection timed out"
    except requests.ConnectionError as e:
        result["error"] = f"Cannot connect to server"
    except Exception as e:
        result["error"] = str(e)
    
    return result


class OllamaServerPreset(BaseModel):
    preset: str  # 'docker', 'localhost', 'custom'
    custom_url: Optional[str] = None


# Common Ollama presets
OLLAMA_PRESETS = {
    "docker": {
        "url": "http://ollama:11434",
        "name": "Docker (Built-in)",
        "description": "Ollama running in Docker container"
    },
    "localhost": {
        "url": "http://host.docker.internal:11434",
        "name": "Windows/Mac Host",
        "description": "Ollama on host machine (Windows/Mac)"
    },
    "localhost_linux": {
        "url": "http://172.17.0.1:11434",
        "name": "Linux Host",
        "description": "Ollama on Linux host machine"
    }
}


@app.get("/settings/ollama/presets")
def get_ollama_presets():
    """Get available Ollama server presets."""
    return OLLAMA_PRESETS


@app.post("/settings/ollama/preset")
def set_ollama_preset(preset_data: OllamaServerPreset, db: Session = Depends(get_db)):
    """Set Ollama URL based on preset or custom URL."""
    ensure_settings_table(db)
    
    if preset_data.preset == "custom":
        if not preset_data.custom_url:
            raise HTTPException(status_code=400, detail="custom_url required for custom preset")
        new_url = preset_data.custom_url
    elif preset_data.preset in OLLAMA_PRESETS:
        new_url = OLLAMA_PRESETS[preset_data.preset]["url"]
    else:
        raise HTTPException(status_code=400, detail=f"Unknown preset: {preset_data.preset}")
    
    # Update the LLM settings with new URL
    llm = get_setting(db, "llm") or DEFAULT_SETTINGS["llm"]
    if "ollama" not in llm:
        llm["ollama"] = {}
    llm["ollama"]["url"] = new_url
    set_setting(db, "llm", llm)
    
    # Test connection
    try:
        resp = requests.get(f"{new_url}/api/tags", timeout=5)
        connected = resp.status_code == 200
    except:
        connected = False
    
    return {
        "url": new_url,
        "preset": preset_data.preset,
        "connected": connected
    }


@app.get("/settings/ollama/models")
def get_ollama_models(capability: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get available Ollama models with capability detection.
    
    Args:
        capability: Filter by capability - 'chat', 'embedding', or 'vision'
    """
    ensure_settings_table(db)
    llm = get_setting(db, "llm") or DEFAULT_SETTINGS["llm"]
    url = llm.get("ollama", {}).get("url", "http://ollama:11434")
    
    try:
        resp = requests.get(f"{url}/api/tags", timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Ollama returned status {resp.status_code}")
        
        models = resp.json().get("models", [])
        result = []
        
        for m in models:
            caps = detect_model_capabilities(m)
            model_info = {
                "name": m["name"],
                "size": m.get("size", 0),
                "size_human": f"{m.get('size', 0) / 1e9:.1f}GB" if m.get("size", 0) > 1e9 else f"{m.get('size', 0) / 1e6:.0f}MB",
                "parameter_size": m.get("details", {}).get("parameter_size", ""),
                "family": m.get("details", {}).get("family", ""),
                "quantization": m.get("details", {}).get("quantization_level", ""),
                "capabilities": caps
            }
            
            # Filter by capability if specified
            if capability:
                if capability == "chat" and not caps["chat"]:
                    continue
                elif capability == "embedding" and not caps["embedding"]:
                    continue
                elif capability == "vision" and not caps["vision"]:
                    continue
            
            result.append(model_info)
        
        return {"models": result, "url": url}
        
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Ollama connection timed out")
    except requests.ConnectionError:
        raise HTTPException(status_code=502, detail=f"Cannot connect to Ollama at {url}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class OllamaModelPull(BaseModel):
    name: str


# Track active pull operations
_active_pulls: Dict[str, dict] = {}


@app.post("/settings/ollama/models/pull")
async def pull_ollama_model(model: OllamaModelPull, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start pulling/downloading an Ollama model."""
    ensure_settings_table(db)
    llm = get_setting(db, "llm") or DEFAULT_SETTINGS["llm"]
    url = llm.get("ollama", {}).get("url", "http://ollama:11434")
    
    model_name = model.name
    
    # Check if already pulling
    if model_name in _active_pulls and _active_pulls[model_name].get("status") == "pulling":
        return {"status": "already_pulling", "model": model_name}
    
    # Start the pull in background
    _active_pulls[model_name] = {"status": "pulling", "progress": 0, "message": "Starting download..."}
    
    def do_pull():
        try:
            # Use streaming to track progress
            resp = requests.post(
                f"{url}/api/pull",
                json={"name": model_name, "stream": True},
                stream=True,
                timeout=3600  # 1 hour timeout for large models
            )
            
            for line in resp.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        status = data.get("status", "")
                        
                        if "completed" in data and "total" in data:
                            progress = int(data["completed"] / data["total"] * 100) if data["total"] > 0 else 0
                            _active_pulls[model_name] = {
                                "status": "pulling",
                                "progress": progress,
                                "message": status,
                                "completed": data["completed"],
                                "total": data["total"]
                            }
                        elif status == "success":
                            _active_pulls[model_name] = {"status": "complete", "progress": 100, "message": "Download complete"}
                        else:
                            _active_pulls[model_name]["message"] = status
                    except json.JSONDecodeError:
                        pass
            
            # Mark as complete
            _active_pulls[model_name] = {"status": "complete", "progress": 100, "message": "Download complete"}
            
        except Exception as e:
            _active_pulls[model_name] = {"status": "error", "progress": 0, "message": str(e)}
    
    background_tasks.add_task(do_pull)
    
    return {"status": "started", "model": model_name, "message": "Download started"}


@app.get("/settings/ollama/models/pull/{model_name:path}")
def get_pull_status(model_name: str):
    """Get the status of a model pull operation."""
    if model_name in _active_pulls:
        return {"model": model_name, **_active_pulls[model_name]}
    return {"model": model_name, "status": "not_found", "message": "No active download for this model"}


@app.delete("/settings/ollama/models/{model_name:path}")
def delete_ollama_model(model_name: str, db: Session = Depends(get_db)):
    """Delete an Ollama model."""
    ensure_settings_table(db)
    llm = get_setting(db, "llm") or DEFAULT_SETTINGS["llm"]
    url = llm.get("ollama", {}).get("url", "http://ollama:11434")
    
    try:
        resp = requests.delete(f"{url}/api/delete", json={"name": model_name}, timeout=30)
        if resp.status_code == 200:
            return {"status": "deleted", "model": model_name}
        else:
            raise HTTPException(status_code=resp.status_code, detail=f"Failed to delete model: {resp.text}")
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Ollama connection timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Popular models for easy download - comprehensive list
POPULAR_OLLAMA_MODELS = {
    "chat": [
        # Llama 3.2 family
        {"name": "llama3.2:1b", "description": "Meta Llama 3.2 1B - Ultra fast, edge-friendly", "size": "1.3GB"},
        {"name": "llama3.2:3b", "description": "Meta Llama 3.2 3B - Fast, capable", "size": "2GB"},
        # Llama 3.1 family
        {"name": "llama3.1:8b", "description": "Meta Llama 3.1 8B - Great balance", "size": "4.7GB"},
        {"name": "llama3.1:70b", "description": "Meta Llama 3.1 70B - Very powerful", "size": "40GB"},
        # Llama 3 family
        {"name": "llama3:8b", "description": "Meta Llama 3 8B - Proven reliable", "size": "4.7GB"},
        {"name": "llama3:70b", "description": "Meta Llama 3 70B - High quality", "size": "40GB"},
        # Mistral family
        {"name": "mistral:7b", "description": "Mistral 7B - Excellent all-rounder", "size": "4.1GB"},
        {"name": "mistral-nemo:12b", "description": "Mistral Nemo 12B - Enhanced reasoning", "size": "7.1GB"},
        {"name": "mixtral:8x7b", "description": "Mixtral 8x7B MoE - Top tier open", "size": "26GB"},
        # Phi family (Microsoft)
        {"name": "phi3:mini", "description": "Microsoft Phi-3 Mini - Efficient, smart", "size": "2.2GB"},
        {"name": "phi3:medium", "description": "Microsoft Phi-3 Medium - Stronger", "size": "7.9GB"},
        {"name": "phi3.5:3.8b", "description": "Microsoft Phi-3.5 - Latest, efficient", "size": "2.2GB"},
        # Gemma family (Google)
        {"name": "gemma2:2b", "description": "Google Gemma 2 2B - Lightweight", "size": "1.6GB"},
        {"name": "gemma2:9b", "description": "Google Gemma 2 9B - Balanced", "size": "5.4GB"},
        {"name": "gemma2:27b", "description": "Google Gemma 2 27B - Powerful", "size": "16GB"},
        # Qwen family (Alibaba)
        {"name": "qwen2.5:0.5b", "description": "Qwen 2.5 0.5B - Tiny, fast", "size": "397MB"},
        {"name": "qwen2.5:1.5b", "description": "Qwen 2.5 1.5B - Small, capable", "size": "986MB"},
        {"name": "qwen2.5:3b", "description": "Qwen 2.5 3B - Good balance", "size": "1.9GB"},
        {"name": "qwen2.5:7b", "description": "Qwen 2.5 7B - Strong performer", "size": "4.7GB"},
        {"name": "qwen2.5:14b", "description": "Qwen 2.5 14B - Very capable", "size": "9GB"},
        {"name": "qwen2.5:32b", "description": "Qwen 2.5 32B - Excellent quality", "size": "20GB"},
        {"name": "qwen2.5:72b", "description": "Qwen 2.5 72B - Top tier", "size": "47GB"},
        {"name": "qwen2.5-coder:7b", "description": "Qwen 2.5 Coder 7B - Code specialist", "size": "4.7GB"},
        # DeepSeek family
        {"name": "deepseek-coder:6.7b", "description": "DeepSeek Coder 6.7B - Code focused", "size": "3.8GB"},
        {"name": "deepseek-coder-v2:16b", "description": "DeepSeek Coder V2 - Advanced coding", "size": "8.9GB"},
        # CodeLlama
        {"name": "codellama:7b", "description": "Meta CodeLlama 7B - Code generation", "size": "3.8GB"},
        {"name": "codellama:13b", "description": "Meta CodeLlama 13B - Better code", "size": "7.4GB"},
        {"name": "codellama:34b", "description": "Meta CodeLlama 34B - Best code", "size": "19GB"},
        # Dolphin (uncensored)
        {"name": "dolphin-phi", "description": "Dolphin Phi-2 - Uncensored, fast", "size": "1.6GB"},
        {"name": "dolphin-mistral:7b", "description": "Dolphin Mistral - Uncensored 7B", "size": "4.1GB"},
        {"name": "dolphin-mixtral:8x7b", "description": "Dolphin Mixtral - Uncensored MoE", "size": "26GB"},
        {"name": "dolphin-llama3:8b", "description": "Dolphin Llama 3 - Uncensored 8B", "size": "4.7GB"},
        # Wizard family
        {"name": "wizardlm2:7b", "description": "WizardLM 2 7B - Instruction following", "size": "4.1GB"},
        {"name": "wizardcoder:7b", "description": "WizardCoder 7B - Code wizard", "size": "3.8GB"},
        # Command R (Cohere)
        {"name": "command-r:35b", "description": "Cohere Command R - RAG optimized", "size": "20GB"},
        {"name": "command-r-plus:104b", "description": "Cohere Command R+ - Best RAG", "size": "59GB"},
        # Other popular
        {"name": "neural-chat:7b", "description": "Intel Neural Chat - Conversational", "size": "4.1GB"},
        {"name": "openchat:7b", "description": "OpenChat 7B - Good chat model", "size": "4.1GB"},
        {"name": "starling-lm:7b", "description": "Starling LM 7B - RLHF tuned", "size": "4.1GB"},
        {"name": "solar:10.7b", "description": "Solar 10.7B - Korean/English", "size": "6.1GB"},
        {"name": "yi:6b", "description": "01.AI Yi 6B - Bilingual", "size": "3.5GB"},
        {"name": "yi:34b", "description": "01.AI Yi 34B - Very capable", "size": "19GB"},
        {"name": "orca-mini:3b", "description": "Orca Mini 3B - Small but smart", "size": "1.9GB"},
        {"name": "vicuna:7b", "description": "Vicuna 7B - Classic fine-tune", "size": "3.8GB"},
        {"name": "zephyr:7b", "description": "Zephyr 7B - Helpful assistant", "size": "4.1GB"},
        {"name": "nous-hermes2:10.7b", "description": "Nous Hermes 2 - Versatile", "size": "6.1GB"},
        {"name": "openhermes:7b", "description": "OpenHermes 7B - General purpose", "size": "4.1GB"},
        {"name": "tinyllama:1.1b", "description": "TinyLlama 1.1B - Tiny but capable", "size": "637MB"},
        {"name": "stablelm2:1.6b", "description": "StableLM 2 1.6B - Stable Diffusion team", "size": "982MB"},
    ],
    "embedding": [
        {"name": "nomic-embed-text", "description": "Nomic Embed - Best quality/size ratio", "size": "274MB"},
        {"name": "all-minilm", "description": "MiniLM L6 - Ultra fast, compact", "size": "45MB"},
        {"name": "mxbai-embed-large", "description": "MixedBread Large - High quality", "size": "670MB"},
        {"name": "snowflake-arctic-embed", "description": "Snowflake Arctic - Production ready", "size": "669MB"},
        {"name": "bge-m3", "description": "BGE M3 - Multilingual, versatile", "size": "1.2GB"},
        {"name": "bge-large", "description": "BGE Large - High quality English", "size": "670MB"},
        {"name": "gte-large", "description": "GTE Large - Alibaba embedding", "size": "670MB"},
        {"name": "paraphrase-multilingual", "description": "Paraphrase - 50+ languages", "size": "1.1GB"},
    ],
    "vision": [
        {"name": "llava:7b", "description": "LLaVA 7B - Standard vision model", "size": "4.7GB"},
        {"name": "llava:13b", "description": "LLaVA 13B - Better quality", "size": "8GB"},
        {"name": "llava:34b", "description": "LLaVA 34B - Best LLaVA quality", "size": "19GB"},
        {"name": "llama3.2-vision:11b", "description": "Llama 3.2 Vision - Latest from Meta", "size": "7.9GB"},
        {"name": "llama3.2-vision:90b", "description": "Llama 3.2 Vision 90B - Largest", "size": "55GB"},
        {"name": "llava-llama3:8b", "description": "LLaVA Llama 3 - Llama 3 based", "size": "4.7GB"},
        {"name": "llava-phi3:3.8b", "description": "LLaVA Phi-3 - Efficient vision", "size": "2.9GB"},
        {"name": "bakllava", "description": "BakLLaVA - Mistral-based vision", "size": "4.7GB"},
        {"name": "moondream", "description": "Moondream - Tiny vision model", "size": "1.7GB"},
        {"name": "minicpm-v:8b", "description": "MiniCPM-V - Efficient multimodal", "size": "5.5GB"},
    ]
}


@app.get("/settings/ollama/models/popular")
def get_popular_models():
    """Get list of popular Ollama models for each capability."""
    return POPULAR_OLLAMA_MODELS


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


# ==================== Image Gallery Endpoints ====================

@app.get("/images/stats")
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
    
    # Count by extension
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


@app.get("/vision/models")
def get_vision_models():
    """Get available vision models."""
    available = list_vision_models()
    return {
        "available": available,
        "default": VISION_MODEL,
    }


@app.get("/images")
def list_images(
    skip: int = 0, 
    limit: int = 50, 
    has_description: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List all image files with optional filters."""
    query = db.query(RawFile).filter(RawFile.file_type == 'image')
    
    if has_description is True:
        query = query.filter(RawFile.vision_description.isnot(None))
    elif has_description is False:
        query = query.filter(RawFile.vision_description.is_(None))
    
    total = query.count()
    images = query.order_by(RawFile.id.desc()).offset(skip).limit(limit).all()
    
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
                "ocr_text": img.ocr_text[:200] if img.ocr_text else None,  # Preview only
                "vision_description": img.vision_description[:200] if img.vision_description else None,
                "vision_model": img.vision_model,
                "has_description": img.vision_description is not None,
                "created_at": img.created_at,
                "size_bytes": img.size_bytes,
            } for img in images
        ]
    }


@app.get("/images/{image_id}")
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
        "extension": image.extension,
        "series_name": image.series_name,
        "series_number": image.series_number,
    }


@app.get("/images/{image_id}/thumbnail")
def get_image_thumbnail(image_id: int, db: Session = Depends(get_db)):
    """Serve the thumbnail for an image."""
    image = db.query(RawFile).filter(RawFile.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    if not image.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not available")
    
    thumbnail_full_path = os.path.join(THUMBNAIL_DIR, image.thumbnail_path)
    if not os.path.exists(thumbnail_full_path):
        raise HTTPException(status_code=404, detail="Thumbnail file not found")
    
    return FileResponse(thumbnail_full_path, media_type="image/jpeg")


@app.get("/images/{image_id}/full")
def get_image_full(image_id: int, db: Session = Depends(get_db)):
    """Serve the full-resolution image."""
    image = db.query(RawFile).filter(RawFile.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    if not os.path.exists(image.path):
        raise HTTPException(status_code=404, detail="Image file not found on disk")
    
    # Determine media type from extension
    media_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff',
        '.tif': 'image/tiff',
    }
    media_type = media_types.get(image.extension.lower(), 'application/octet-stream')
    
    return FileResponse(image.path, media_type=media_type)


class VisionAnalyzeRequest(BaseModel):
    model: Optional[str] = None
    prompt: Optional[str] = None


@app.post("/images/{image_id}/analyze")
def analyze_image_with_vision(
    image_id: int, 
    request: VisionAnalyzeRequest,
    db: Session = Depends(get_db)
):
    """Analyze an image using a vision model and store the description."""
    image = db.query(RawFile).filter(RawFile.id == image_id, RawFile.file_type == 'image').first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    if not os.path.exists(image.path):
        raise HTTPException(status_code=404, detail="Image file not found on disk")
    
    # Use provided model or default
    model = request.model or VISION_MODEL
    prompt = request.prompt or "Describe this image in detail. Include any visible text, objects, people, settings, colors, and notable features."
    
    # Call vision model
    description = describe_image(image.path, model=model, prompt=prompt)
    
    if not description:
        raise HTTPException(status_code=500, detail="Vision model failed to generate description")
    
    # Update database
    image.vision_description = description
    image.vision_model = model
    db.commit()
    
    return {
        "id": image.id,
        "filename": image.filename,
        "vision_description": description,
        "vision_model": model,
    }


@app.post("/images/analyze-batch")
def analyze_images_batch(
    limit: int = 10,
    model: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Analyze multiple images that don't have descriptions yet."""
    images = db.query(RawFile).filter(
        RawFile.file_type == 'image',
        RawFile.vision_description.is_(None)
    ).limit(limit).all()
    
    if not images:
        return {"message": "No images need analysis", "processed": 0}
    
    vision_model = model or VISION_MODEL
    processed = 0
    errors = 0
    
    for image in images:
        if not os.path.exists(image.path):
            errors += 1
            continue
        
        description = describe_image(image.path, model=vision_model)
        if description:
            image.vision_description = description
            image.vision_model = vision_model
            processed += 1
        else:
            errors += 1
    
    db.commit()
    
    return {
        "processed": processed,
        "errors": errors,
        "remaining": db.query(RawFile).filter(
            RawFile.file_type == 'image',
            RawFile.vision_description.is_(None)
        ).count()
    }


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, db: Session = Depends(get_db)):
    # 1. Search with configurable mode
    search_mode = request.search_mode or 'hybrid'
    vector_weight = request.vector_weight or 0.7
    
    results = search_entries_semantic(
        db, 
        request.query, 
        k=request.k, 
        filters=request.filters,
        mode=search_mode,
        vector_weight=vector_weight
    )
    
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
    
    config_path = os.environ.get("CONFIG_PATH")
    if not config_path:
        if os.path.exists("/app/config/config.yaml"):
            config_path = "/app/config/config.yaml"
        else:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "config.yaml")
    
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

# ============================================================================
# Quality Review & Low-Quality Entries
# ============================================================================

@app.get("/entries/needs-review")
def get_entries_needing_review(limit: int = 50, db: Session = Depends(get_db)):
    """Get entries flagged as needing review due to low quality scores."""
    from sqlalchemy import cast
    from sqlalchemy.dialects.postgresql import JSONB
    
    entries = db.query(Entry).filter(
        Entry.extra_meta['needs_review'].astext == 'true'
    ).limit(limit).all()
    
    return {
        "count": len(entries),
        "entries": [
            {
                "id": e.id,
                "title": e.title,
                "summary": e.summary,
                "quality_score": e.extra_meta.get('quality_score') if e.extra_meta else None,
                "file_path": e.raw_file.path if e.raw_file else None
            }
            for e in entries
        ]
    }

@app.get("/entries/quality-stats")
def get_quality_stats(db: Session = Depends(get_db)):
    """Get quality score distribution statistics."""
    from sqlalchemy import text
    
    # Use raw SQL for JSON field aggregation
    sql = text("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN (extra_meta->>'quality_score')::float >= 0.8 THEN 1 END) as excellent,
            COUNT(CASE WHEN (extra_meta->>'quality_score')::float >= 0.6 AND (extra_meta->>'quality_score')::float < 0.8 THEN 1 END) as good,
            COUNT(CASE WHEN (extra_meta->>'quality_score')::float >= 0.4 AND (extra_meta->>'quality_score')::float < 0.6 THEN 1 END) as fair,
            COUNT(CASE WHEN (extra_meta->>'quality_score')::float < 0.4 THEN 1 END) as poor,
            COUNT(CASE WHEN extra_meta->>'needs_review' = 'true' THEN 1 END) as needs_review,
            AVG((extra_meta->>'quality_score')::float) as avg_score
        FROM entries
        WHERE extra_meta->>'quality_score' IS NOT NULL
    """)
    
    result = db.execute(sql).fetchone()
    
    return {
        "total_scored": result[0],
        "excellent": result[1],  # >= 0.8
        "good": result[2],       # 0.6-0.8
        "fair": result[3],       # 0.4-0.6
        "poor": result[4],       # < 0.4
        "needs_review": result[5],
        "average_score": round(float(result[6]), 2) if result[6] else None
    }

# ============================================================================
# Document Series & Collections
# ============================================================================

@app.get("/series")
def get_all_series(limit: int = 50, db: Session = Depends(get_db)):
    """Get all detected document series."""
    series = db.query(
        RawFile.series_name,
        func.count(RawFile.id).label('file_count'),
        func.min(RawFile.series_number).label('min_part'),
        func.max(RawFile.series_number).label('max_part')
    ).filter(
        RawFile.series_name.isnot(None)
    ).group_by(RawFile.series_name).order_by(func.count(RawFile.id).desc()).limit(limit).all()
    
    return {
        "series_count": len(series),
        "series": [
            {
                "name": s.series_name,
                "file_count": s.file_count,
                "part_range": f"{s.min_part}-{s.max_part}"
            }
            for s in series
        ]
    }

@app.get("/series/{series_name}")
def get_series_files(series_name: str, db: Session = Depends(get_db)):
    """Get all files in a specific series, ordered by part number."""
    from urllib.parse import unquote
    series_name = unquote(series_name)
    
    files = db.query(RawFile).filter(
        RawFile.series_name == series_name
    ).order_by(RawFile.series_number).all()
    
    if not files:
        raise HTTPException(status_code=404, detail="Series not found")
    
    return {
        "series_name": series_name,
        "file_count": len(files),
        "files": [
            {
                "id": f.id,
                "filename": f.filename,
                "part_number": f.series_number,
                "total_parts": f.series_total,
                "path": f.path
            }
            for f in files
        ]
    }

@app.get("/files/{file_id}/series")
def get_file_series(file_id: int, db: Session = Depends(get_db)):
    """Get series information for a specific file and other files in the same series."""
    file = db.query(RawFile).filter(RawFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not file.series_name:
        return {"file_id": file_id, "series_name": None, "related_files": []}
    
    # Get other files in the same series
    related = db.query(RawFile).filter(
        RawFile.series_name == file.series_name,
        RawFile.id != file_id
    ).order_by(RawFile.series_number).all()
    
    return {
        "file_id": file_id,
        "series_name": file.series_name,
        "part_number": file.series_number,
        "total_parts": file.series_total,
        "related_files": [
            {
                "id": f.id,
                "filename": f.filename,
                "part_number": f.series_number
            }
            for f in related
        ]
    }

# ============================================================================
# Educational / Transparency Endpoints
# ============================================================================

class SimilarityRequest(BaseModel):
    text1: str
    text2: str

@app.post("/similarity")
def calculate_similarity(request: SimilarityRequest):
    """
    Calculate cosine similarity between two pieces of text.
    Educational tool to demonstrate how semantic search works.
    """
    from src.llm_client import embed_text
    import numpy as np
    
    if not request.text1.strip() or not request.text2.strip():
        raise HTTPException(status_code=400, detail="Both texts are required")
    
    # Get embeddings for both texts
    emb1 = embed_text(request.text1)
    emb2 = embed_text(request.text2)
    
    if not emb1 or not emb2:
        raise HTTPException(status_code=500, detail="Failed to generate embeddings")
    
    # Calculate cosine similarity
    emb1 = np.array(emb1)
    emb2 = np.array(emb2)
    
    dot_product = np.dot(emb1, emb2)
    norm1 = np.linalg.norm(emb1)
    norm2 = np.linalg.norm(emb2)
    
    similarity = dot_product / (norm1 * norm2)
    
    return {
        "similarity": float(similarity),
        "text1_length": len(request.text1),
        "text2_length": len(request.text2),
        "embedding_dimensions": len(emb1)
    }

@app.get("/entries/{entry_id}/debug")
def get_entry_debug_info(entry_id: int, db: Session = Depends(get_db)):
    """
    Get detailed debug/educational information about an entry's processing journey.
    Shows raw text, enrichment results, embedding info, and nearby entries.
    """
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Get the raw file info
    raw_file = entry.raw_file
    
    # Find nearby entries in vector space (if embedding exists)
    nearby = []
    if entry.embedding is not None:
        nearby_results = db.query(Entry).filter(
            Entry.id != entry_id,
            Entry.embedding.isnot(None)
        ).order_by(
            Entry.embedding.cosine_distance(entry.embedding)
        ).limit(5).all()
        
        nearby = [
            {
                "id": e.id,
                "title": e.title,
                "similarity": 1 - float(db.execute(
                    text("SELECT :emb1 <=> :emb2"),
                    {"emb1": str(entry.embedding), "emb2": str(e.embedding)}
                ).scalar()) if e.embedding else 0
            }
            for e in nearby_results
        ]
    
    return {
        "entry": {
            "id": entry.id,
            "file_id": entry.file_id,
            "entry_index": entry.entry_index,
            "status": entry.status,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at
        },
        "raw_text": {
            "content": entry.entry_text[:2000] + ("..." if len(entry.entry_text) > 2000 else ""),
            "full_length": len(entry.entry_text),
            "char_start": entry.char_start,
            "char_end": entry.char_end
        },
        "enrichment": {
            "title": entry.title,
            "author": entry.author,
            "category": entry.category,
            "summary": entry.summary,
            "tags": entry.tags,
            "quality_score": entry.extra_meta.get('quality_score') if entry.extra_meta else None,
            "needs_review": entry.extra_meta.get('needs_review') if entry.extra_meta else None
        },
        "embedding": {
            "has_embedding": entry.embedding is not None,
            "dimensions": 768 if entry.embedding else 0,
            "content_hash": entry.content_hash
        },
        "source_file": {
            "id": raw_file.id if raw_file else None,
            "filename": raw_file.filename if raw_file else None,
            "path": raw_file.path if raw_file else None,
            "extension": raw_file.extension if raw_file else None,
            "series_name": raw_file.series_name if raw_file else None,
            "series_number": raw_file.series_number if raw_file else None
        },
        "nearby_entries": nearby
    }

@app.get("/search/explain")
def search_with_explanation(
    query: str,
    k: int = 5,
    mode: str = 'hybrid',
    db: Session = Depends(get_db)
):
    """
    Search with detailed explanation of results.
    Shows similarity scores and why each result matched.
    """
    from src.llm_client import embed_text
    
    # Get query embedding
    query_embedding = embed_text(query)
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to embed query")
    
    # Perform search
    results = search_entries_semantic(db, query, k=k, mode=mode)
    
    explained_results = []
    for entry in results:
        # Calculate individual scores
        vector_score = None
        keyword_score = None
        
        if entry.embedding is not None:
            # Calculate vector similarity
            import numpy as np
            entry_emb = np.array(entry.embedding)
            query_emb = np.array(query_embedding)
            vector_score = float(np.dot(entry_emb, query_emb) / (np.linalg.norm(entry_emb) * np.linalg.norm(query_emb)))
        
        # Check for keyword matches
        query_words = set(query.lower().split())
        text_words = set((entry.entry_text or '').lower().split()[:500])
        title_words = set((entry.title or '').lower().split())
        matching_words = query_words & (text_words | title_words)
        
        explained_results.append({
            "id": entry.id,
            "title": entry.title,
            "summary": entry.summary,
            "category": entry.category,
            "author": entry.author,
            "scores": {
                "vector_similarity": round(vector_score, 4) if vector_score else None,
                "combined": getattr(entry, '_search_scores', {}).get('combined_score'),
                "keyword": getattr(entry, '_search_scores', {}).get('keyword_score')
            },
            "match_explanation": {
                "matching_keywords": list(matching_words),
                "keyword_match_count": len(matching_words)
            },
            "file_path": entry.raw_file.path if entry.raw_file else None
        })
    
    return {
        "query": query,
        "search_mode": mode,
        "result_count": len(explained_results),
        "results": explained_results,
        "explanation": {
            "vector_search": "Converts query to 768-dimensional embedding and finds entries with similar semantic meaning.",
            "keyword_search": "Uses PostgreSQL full-text search (BM25) to find exact word matches.",
            "hybrid_search": "Combines vector (70%) and keyword (30%) scores for best results."
        }
    }











@app.get("/entries/list")
def list_entries(
    skip: int = 0,
    limit: int = 50,
    status: str = None,
    has_embedding: bool = None,
    db: Session = Depends(get_db)
):
    """List entries with optional filtering for the Entry Inspector."""
    query = db.query(Entry).join(RawFile)
    
    if status:
        query = query.filter(Entry.status == status)
    if has_embedding is not None:
        if has_embedding:
            query = query.filter(Entry.embedding.isnot(None))
        else:
            query = query.filter(Entry.embedding.is_(None))
    
    total = query.count()
    entries = query.order_by(Entry.updated_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "entries": [
            {
                "id": e.id,
                "title": e.title,
                "summary": e.summary[:100] + "..." if e.summary and len(e.summary) > 100 else e.summary,
                "category": e.category,
                "author": e.author,
                "status": e.status,
                "has_embedding": e.embedding is not None,
                "file_id": e.file_id,
                "filename": e.raw_file.filename if e.raw_file else None,
                "updated_at": e.updated_at.isoformat() if e.updated_at else None
            }
            for e in entries
        ]
    }

@app.get("/entries/{entry_id}/inspect")
def inspect_entry(entry_id: int, db: Session = Depends(get_db)):
    """
    Get full details for an entry inspector view:
    - Raw text
    - Current metadata
    - Constructed prompt (simulation)
    - Pipeline journey status
    """
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Get the file info
    file = db.query(RawFile).filter(RawFile.id == entry.file_id).first()
    
    # Reconstruct the prompt
    config_path = "/app/config/config.yaml"
    if not os.path.exists(config_path):
        # Fallback for local development
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "config.yaml")

    prompt_template = """
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
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config and 'enrichment' in yaml_config:
                    if 'prompt_template' in yaml_config['enrichment']:
                        prompt_template = yaml_config['enrichment']['prompt_template']
    except Exception:
        pass
        
    constructed_prompt = prompt_template.replace("{text}", entry.entry_text)
    
    # Determine pipeline stages
    stages = [
        {"name": "Ingest", "status": "complete", "description": "File uploaded and text extracted"},
        {"name": "Segment", "status": "complete", "description": f"Split into chunk {entry.chunk_index}"}
    ]
    
    if entry.title:
        stages.append({"name": "Enrich", "status": "complete", "description": "Metadata extracted by LLM"})
    else:
        stages.append({"name": "Enrich", "status": "pending", "description": "Waiting for LLM processing"})
        
    if entry.embedding is not None:
        stages.append({"name": "Embed", "status": "complete", "description": "Vector embedding generated"})
    else:
        stages.append({"name": "Embed", "status": "pending", "description": "Waiting for vectorization"})

    # Embedding stats
    embedding_stats = None
    if entry.embedding is not None:
        # Convert numpy array or list to list
        vec = entry.embedding
        if hasattr(vec, 'tolist'):
            vec = vec.tolist()
            
        import numpy as np
        arr = np.array(vec)
        embedding_stats = {
            "dimensions": len(vec),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "norm": float(np.linalg.norm(arr)),
            "first_10_values": vec[:10],
            "last_10_values": vec[-10:]
        }

    return {
        "entry": {
            "id": entry.id,
            "file_id": entry.file_id,
            "chunk_index": entry.chunk_index,
            "entry_text": entry.entry_text,
            "entry_index": entry.chunk_index,
            "char_start": 0,
            "char_end": len(entry.entry_text),
            "content_hash": entry.content_hash,
            "title": entry.title,
            "summary": entry.summary,
            "tags": entry.tags,
            "author": entry.author,
            "category": entry.category,
            "created_hint": entry.created_hint,
            "status": entry.status,
            "has_embedding": entry.embedding is not None,
            "updated_at": entry.updated_at
        },
        "source_file": {
            "id": file.id,
            "filename": file.filename,
            "path": file.file_path,
            "series_name": file.series_name,
            "series_number": file.series_number
        } if file else None,
        "enrichment": {
            "prompt_length_chars": len(constructed_prompt),
            "actual_prompt": constructed_prompt,
            "raw_response": entry.extra_meta
        },
        "embedding": embedding_stats,
        "pipeline_journey": {
            "stages": stages
        }
    }

@app.get("/entries/{entry_id}/nearby")
def get_nearby_entries(entry_id: int, k: int = 8, db: Session = Depends(get_db)):
    """Get entries that are semantically close to this one."""
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
        
    if entry.embedding is None:
        return {"nearby": []}
        
    # Use pgvector <-> operator for L2 distance (or <=> for cosine distance)
    sql = text("""
        SELECT e.id, e.title, e.summary, e.category, rf.filename, 
               1 - (e.embedding <=> (SELECT embedding FROM entries WHERE id = :id)) as similarity
        FROM entries e
        JOIN raw_files rf ON e.file_id = rf.id
        WHERE e.id != :id AND e.embedding IS NOT NULL
        ORDER BY e.embedding <=> (SELECT embedding FROM entries WHERE id = :id) ASC
        LIMIT :k
    """)
    
    rows = db.execute(sql, {"id": entry_id, "k": k}).fetchall()
    
    return {
        "nearby": [
            {
                "id": row[0],
                "title": row[1],
                "summary": row[2],
                "category": row[3],
                "filename": row[4],
                "similarity": float(row[5])
            }
            for row in rows
        ]
    }

@app.get("/entries/{entry_id}/embedding-viz")
def get_embedding_viz(entry_id: int, db: Session = Depends(get_db)):
    """Get visualization data for the embedding vector."""
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry or entry.embedding is None:
        raise HTTPException(status_code=404, detail="Entry or embedding not found")
        
    vec = entry.embedding
    if hasattr(vec, 'tolist'):
        vec = vec.tolist()
        
    # Create 64 buckets for visualization
    import numpy as np
    arr = np.array(vec)
    
    # Normalize to 0-1 for visualization
    min_val = np.min(arr)
    max_val = np.max(arr)
    range_val = max_val - min_val if max_val > min_val else 1.0
    
    normalized = (arr - min_val) / range_val
    
    # Downsample to 64 buckets by averaging
    bucket_size = len(normalized) // 64
    if bucket_size < 1: bucket_size = 1
    
    buckets = []
    raw_buckets = []
    
    for i in range(0, len(normalized), bucket_size):
        chunk = normalized[i:i+bucket_size]
        raw_chunk = arr[i:i+bucket_size]
        if len(chunk) > 0:
            buckets.append(float(np.mean(chunk)))
            raw_buckets.append(float(np.mean(raw_chunk)))
            
    return {
        "visualization": {
            "buckets": buckets[:64], # Ensure max 64
            "raw_buckets": raw_buckets[:64]
        }
    }


@app.get("/embeddings/visualize")
def visualize_embeddings(
    dimensions: int = 2,
    algorithm: str = "tsne",
    category: Optional[str] = None,
    author: Optional[str] = None,
    limit: int = 1000,
    db: Session = Depends(get_db)
):
    """
    Get dimensionality-reduced embeddings for visualization.
    
    Parameters:
    - dimensions: 2 or 3 for 2D/3D visualization
    - algorithm: 'tsne' or 'umap'
    - category: Optional filter by category
    - author: Optional filter by author
    - limit: Max number of entries to visualize (default 1000)
    """
    import numpy as np
    from sklearn.manifold import TSNE
    try:
        from umap import UMAP
    except ImportError:
        UMAP = None
    
    # Validate parameters
    if dimensions not in [2, 3]:
        raise HTTPException(status_code=400, detail="dimensions must be 2 or 3")
    
    if algorithm not in ['tsne', 'umap']:
        raise HTTPException(status_code=400, detail="algorithm must be 'tsne' or 'umap'")
    
    if algorithm == 'umap' and UMAP is None:
        raise HTTPException(status_code=400, detail="UMAP not installed. Use 'tsne' or install umap-learn")
    
    # Query entries with embeddings (check for embedding presence, not status)
    query = db.query(Entry).filter(
        Entry.embedding.isnot(None)
    )
    
    if category:
        query = query.filter(Entry.category == category)
    if author:
        query = query.filter(Entry.author == author)
    
    entries = query.limit(limit).all()
    
    if len(entries) < 2:
        return {
            "error": "Not enough entries with embeddings",
            "count": len(entries),
            "points": []
        }
    
    # Extract embeddings and metadata
    embeddings = []
    metadata = []
    
    for entry in entries:
        if entry.embedding is not None and len(entry.embedding) > 0:
            embeddings.append(entry.embedding)
            
            # Get file info
            raw_file = db.query(RawFile).filter(RawFile.id == entry.file_id).first()
            
            metadata.append({
                "entry_id": entry.id,
                "title": entry.title or "Untitled",
                "category": entry.category or "Unknown",
                "author": entry.author or "Unknown",
                "file_type": raw_file.extension if raw_file else "unknown",
                "filename": raw_file.filename if raw_file else "",
                "summary": (entry.summary or "")[:100]  # First 100 chars
            })
    
    # Convert to numpy array
    embeddings_array = np.array(embeddings)
    
    # Perform dimensionality reduction
    if algorithm == 'tsne':
        reducer = TSNE(
            n_components=dimensions,
            random_state=42,
            perplexity=min(30, len(embeddings) - 1)
        )
    else:  # umap
        reducer = UMAP(
            n_components=dimensions,
            random_state=42,
            n_neighbors=min(15, len(embeddings) - 1)
        )
    
    reduced = reducer.fit_transform(embeddings_array)
    
    # Combine with metadata
    points = []
    for i, coords in enumerate(reduced):
        point = metadata[i].copy()
        point['x'] = float(coords[0])
        point['y'] = float(coords[1])
        if dimensions == 3:
            point['z'] = float(coords[2])
        points.append(point)
    
    # Get unique categories and authors for legend
    categories = list(set(p['category'] for p in points))
    authors = list(set(p['author'] for p in points))
    file_types = list(set(p['file_type'] for p in points))
    
    return {
        "points": points,
        "count": len(points),
        "dimensions": dimensions,
        "algorithm": algorithm,
        "categories": sorted(categories),
        "authors": sorted(authors),
        "file_types": sorted(file_types)
    }
