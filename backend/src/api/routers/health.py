"""
Health check and system status endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, func
import os
import requests
import shutil
import psutil

from src.db.session import get_db
from src.db.models import RawFile, Entry
from src.db.settings import get_setting, set_setting, get_all_settings, get_llm_config, get_source_folders
from src.llm_client import list_models, OLLAMA_URL, MODEL, EMBEDDING_MODEL

router = APIRouter()

# Shared directory paths
if os.path.exists("/app/shared"):
    SHARED_DIR = "/app/shared"
else:
    SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "shared")

WORKER_STATE_FILE = os.path.join(SHARED_DIR, "worker_state.json")


def get_worker_state():
    """Read the current worker state."""
    import json
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


@router.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}


@router.get("/system/health-check")
def system_health_check(db: Session = Depends(get_db)):
    """
    Comprehensive system health check for first-run wizard and navbar indicator.
    Returns status for each component: 'ok', 'warning', or 'error'.
    """
    checks = {}
    overall_status = "ok"  # ok, warning, error
    
    # 1. Database connectivity
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {
            "status": "ok",
            "message": "Database connected"
        }
    except Exception as e:
        checks["database"] = {
            "status": "error",
            "message": f"Database unreachable: {str(e)}",
            "fix": "Check DATABASE_URL and ensure PostgreSQL is running"
        }
        overall_status = "error"
    
    # 2. Ollama connectivity
    try:
        resp = requests.get(f"{OLLAMA_URL}", timeout=3)
        if resp.status_code == 200:
            # Check if models are available
            models = list_models()
            if len(models) > 0:
                checks["ollama"] = {
                    "status": "ok",
                    "message": f"Ollama online with {len(models)} models",
                    "url": OLLAMA_URL,
                    "models": models[:5]  # First 5 for display
                }
            else:
                checks["ollama"] = {
                    "status": "warning",
                    "message": "Ollama online but no models installed",
                    "url": OLLAMA_URL,
                    "fix": "Pull a model: ollama pull phi4-mini"
                }
                if overall_status == "ok":
                    overall_status = "warning"
        else:
            raise Exception(f"HTTP {resp.status_code}")
    except Exception as e:
        checks["ollama"] = {
            "status": "error",
            "message": f"Ollama unreachable at {OLLAMA_URL}",
            "url": OLLAMA_URL,
            "fix": "Ensure Ollama container is running and OLLAMA_URL is correct"
        }
        if overall_status != "error":
            overall_status = "error"
    
    # 3. GPU availability (check via Ollama's API)
    gpu_info = None
    try:
        # First try Ollama's /api/ps endpoint which shows GPU usage for running models
        ps_resp = requests.get(f"{OLLAMA_URL}/api/ps", timeout=5)
        if ps_resp.status_code == 200:
            ps_data = ps_resp.json()
            models = ps_data.get("models", [])
            # Check if any model is using GPU (size_vram > 0)
            for model in models:
                size_vram = model.get("size_vram", 0)
                if size_vram > 0:
                    gpu_info = [{
                        "name": "GPU (via Ollama)",
                        "vram_used_mb": size_vram // (1024 * 1024),
                        "model_loaded": model.get("name", "unknown")
                    }]
                    checks["gpu"] = {
                        "status": "ok",
                        "message": f"GPU active - {size_vram // (1024 * 1024)}MB VRAM in use",
                        "gpus": gpu_info
                    }
                    break
        
        # If no GPU detected via ps, try nvidia-smi as fallback (for containers with GPU access)
        if gpu_info is None:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total,memory.free', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5, check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                gpus = []
                for line in lines:
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 3:
                        gpus.append({
                            "name": parts[0],
                            "vram_total_mb": int(parts[1]),
                            "vram_free_mb": int(parts[2])
                        })
                if gpus:
                    gpu_info = gpus
                    checks["gpu"] = {
                        "status": "ok",
                        "message": f"{len(gpus)} GPU(s) detected",
                        "gpus": gpus
                    }
    except Exception:
        pass
    
    if gpu_info is None:
        # No GPU detected - but check if Ollama at least responded (meaning it might have GPU but no model loaded)
        if checks.get("ollama", {}).get("status") == "ok":
            checks["gpu"] = {
                "status": "ok",
                "message": "GPU available via Ollama (no model currently loaded in VRAM)",
                "note": "GPU will be used when models are loaded for inference"
            }
        else:
            checks["gpu"] = {
                "status": "warning",
                "message": "GPU status unknown - Ollama not connected",
                "fix": "Connect to Ollama to detect GPU availability"
            }
            if overall_status == "ok":
                overall_status = "warning"
    
    # 4. Disk space
    try:
        # Check /data/archive if mounted, otherwise /app
        archive_path = "/data/archive" if os.path.exists("/data/archive") else "/app"
        disk = shutil.disk_usage(archive_path)
        free_gb = disk.free / (1024 ** 3)
        total_gb = disk.total / (1024 ** 3)
        used_pct = (disk.used / disk.total) * 100
        
        if free_gb < 1:
            checks["disk"] = {
                "status": "error",
                "message": f"Critical: Only {free_gb:.1f}GB free",
                "free_gb": round(free_gb, 1),
                "total_gb": round(total_gb, 1),
                "used_percent": round(used_pct, 1),
                "fix": "Free up disk space or add more storage"
            }
            overall_status = "error"
        elif free_gb < 10:
            checks["disk"] = {
                "status": "warning",
                "message": f"Low disk space: {free_gb:.1f}GB free",
                "free_gb": round(free_gb, 1),
                "total_gb": round(total_gb, 1),
                "used_percent": round(used_pct, 1),
                "fix": "Consider freeing up disk space"
            }
            if overall_status == "ok":
                overall_status = "warning"
        else:
            checks["disk"] = {
                "status": "ok",
                "message": f"{free_gb:.1f}GB free of {total_gb:.1f}GB",
                "free_gb": round(free_gb, 1),
                "total_gb": round(total_gb, 1),
                "used_percent": round(used_pct, 1)
            }
    except Exception as e:
        checks["disk"] = {
            "status": "warning",
            "message": f"Could not check disk space: {str(e)}"
        }
    
    # 5. Memory
    try:
        mem = psutil.virtual_memory()
        available_gb = mem.available / (1024 ** 3)
        total_gb = mem.total / (1024 ** 3)
        used_pct = mem.percent
        
        if available_gb < 1:
            checks["memory"] = {
                "status": "warning",
                "message": f"Low memory: {available_gb:.1f}GB available",
                "available_gb": round(available_gb, 1),
                "total_gb": round(total_gb, 1),
                "used_percent": round(used_pct, 1),
                "fix": "Close other applications or add more RAM"
            }
            if overall_status == "ok":
                overall_status = "warning"
        else:
            checks["memory"] = {
                "status": "ok",
                "message": f"{available_gb:.1f}GB available of {total_gb:.1f}GB",
                "available_gb": round(available_gb, 1),
                "total_gb": round(total_gb, 1),
                "used_percent": round(used_pct, 1)
            }
    except Exception as e:
        checks["memory"] = {
            "status": "warning",
            "message": f"Could not check memory: {str(e)}"
        }
    
    # 6. Worker status
    worker_state = get_worker_state()
    if worker_state.get("running", False):
        checks["worker"] = {
            "status": "ok",
            "message": "Worker is running",
            "state": worker_state
        }
    else:
        checks["worker"] = {
            "status": "warning",
            "message": "Worker is paused",
            "state": worker_state,
            "fix": "Enable worker from Dashboard to start processing"
        }
        # Don't change overall status for paused worker - that's intentional
    
    # 7. Source folders
    try:
        folders = get_source_folders(db)
        if len(folders) > 0:
            # Check if folders exist
            existing = [f for f in folders if os.path.exists(f)]
            if len(existing) == len(folders):
                checks["sources"] = {
                    "status": "ok",
                    "message": f"{len(folders)} source folder(s) configured",
                    "folders": folders
                }
            else:
                missing = [f for f in folders if f not in existing]
                checks["sources"] = {
                    "status": "warning",
                    "message": f"{len(missing)} folder(s) not accessible",
                    "folders": folders,
                    "missing": missing,
                    "fix": "Check volume mounts in docker-compose.yml"
                }
                if overall_status == "ok":
                    overall_status = "warning"
        else:
            checks["sources"] = {
                "status": "warning",
                "message": "No source folders configured",
                "fix": "Add source folders in Settings to start indexing"
            }
            if overall_status == "ok":
                overall_status = "warning"
    except Exception as e:
        checks["sources"] = {
            "status": "warning",
            "message": f"Could not check source folders: {str(e)}"
        }
    
    return {
        "status": overall_status,
        "checks": checks,
        "timestamp": __import__('datetime').datetime.utcnow().isoformat()
    }


@router.get("/system/first-run")
def check_first_run(db: Session = Depends(get_db)):
    """
    Detect if this is a first-run scenario requiring setup wizard.
    Returns whether setup is needed and current setup state.
    """
    setup_complete = get_setting(db, "setup_complete")
    indexing_mode = get_setting(db, "indexing_mode")
    
    # Count processed files to see if any work has been done
    file_count = db.query(func.count(RawFile.id)).scalar() or 0
    entry_count = db.query(func.count(Entry.id)).scalar() or 0
    
    # Get current settings for the wizard to pre-populate
    settings = get_all_settings(db)
    
    return {
        "setup_required": not setup_complete,
        "setup_complete": bool(setup_complete),
        "indexing_mode": indexing_mode or "fast_scan",
        "has_files": file_count > 0,
        "has_entries": entry_count > 0,
        "file_count": file_count,
        "entry_count": entry_count,
        "current_settings": {
            "llm_provider": settings.get("llm", {}).get("provider", "ollama"),
            "source_folders": settings.get("sources", {}).get("include", []),
            "extensions": settings.get("extensions", [])
        }
    }


@router.post("/system/complete-setup")
def complete_setup(db: Session = Depends(get_db)):
    """
    Mark setup as complete. Called when user finishes the setup wizard.
    """
    success = set_setting(db, "setup_complete", True)
    if success:
        return {"status": "ok", "message": "Setup marked as complete"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save setup status")


@router.get("/system/status")
def get_system_status(db: Session = Depends(get_db)):
    """Get Ollama and LLM provider status."""
    ollama_status = "offline"
    available_models = []
    
    # Get the active LLM config from database settings
    llm_config = get_llm_config(db)
    provider = llm_config.get("provider", "ollama")
    chat_model = llm_config.get("model", MODEL)
    embedding_model = llm_config.get("embedding_model", EMBEDDING_MODEL)
    
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
            "chat_model": chat_model,
            "embedding_model": embedding_model,
            "available_models": available_models
        },
        "provider": provider
    }


@router.get("/system/counts")
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


@router.get("/system/doc-counts")
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


@router.get("/system/storage")
def get_storage_stats(db: Session = Depends(get_db)):
    """Storage stats - can be loaded lazily."""
    size_result = db.query(func.sum(RawFile.size_bytes)).scalar() or 0
    return {
        "total_bytes": size_result,
        "total_mb": round(size_result / (1024 * 1024), 2) if size_result else 0,
        "total_gb": round(size_result / (1024 * 1024 * 1024), 2) if size_result else 0
    }


@router.get("/system/extensions")
def get_extension_stats(db: Session = Depends(get_db)):
    """Extension breakdown - can be loaded lazily."""
    ext_counts = db.query(RawFile.extension, func.count(RawFile.id)).group_by(RawFile.extension).order_by(func.count(RawFile.id).desc()).limit(15).all()
    return [{"ext": ext or "none", "count": count} for ext, count in ext_counts]


@router.get("/system/recent")
def get_recent_files(db: Session = Depends(get_db), limit: int = 10):
    """Recent files - can be loaded lazily."""
    recent_files = db.query(RawFile).order_by(RawFile.created_at.desc()).limit(limit).all()
    return [
        {"id": f.id, "filename": f.filename, "status": f.status, 
         "created_at": f.created_at.isoformat() if f.created_at else None}
        for f in recent_files
    ]


@router.get("/system/metrics")
def get_system_metrics(db: Session = Depends(get_db)):
    """Comprehensive system metrics."""
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
    size_result = db.query(func.sum(RawFile.size_bytes)).scalar() or 0

    # Get extension breakdown
    ext_counts = db.query(RawFile.extension, func.count(RawFile.id)).group_by(RawFile.extension).order_by(func.count(RawFile.id).desc()).limit(10).all()
    
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
