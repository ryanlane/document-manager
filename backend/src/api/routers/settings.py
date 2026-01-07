"""
Settings API Router
Handles all settings and configuration management.
"""
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
import requests

from src.db.session import get_db, SessionLocal
from src.db.settings import get_setting, set_setting, get_all_settings
from src.services import jobs as jobs_service

router = APIRouter(tags=["settings"])


# ============================================================================
# Pydantic Models
# ============================================================================

class LLMSettingsUpdate(BaseModel):
    ollama: Optional[Dict] = None
    openai: Optional[Dict] = None
    anthropic: Optional[Dict] = None


class SourcesUpdate(BaseModel):
    folders: List[str]
    excluded_folders: Optional[List[str]] = None
    file_extensions: Optional[List[str]] = None


class HostPathMapping(BaseModel):
    container_path: str
    host_path: str


class LLMEndpointCreate(BaseModel):
    name: str
    url: str
    api_key: Optional[str] = None
    provider_type: str = 'ollama'
    default_model: Optional[str] = None
    enabled: bool = True


# ============================================================================
# General Settings Endpoints
# ============================================================================

@router.get("/settings")
async def get_all_settings_endpoint(db: Session = Depends(get_db)):
    """Get all settings."""
    settings = get_all_settings(db)
    return settings


@router.put("/settings")
async def update_all_settings(updates: Dict[str, Any], db: Session = Depends(get_db)):
    """Bulk update settings."""
    for key, value in updates.items():
        set_setting(db, key, value)
    return {"message": "Settings updated", "count": len(updates)}


@router.get("/settings/get/{key}")
async def get_single_setting(key: str, db: Session = Depends(get_db)):
    """Get a single setting by key."""
    value = get_setting(db, key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return {"key": key, "value": value}


@router.put("/settings/set")
async def set_single_setting(key: str, value: Any, db: Session = Depends(get_db)):
    """Set a single setting."""
    set_setting(db, key, value)
    return {"key": key, "value": value}


@router.get("/settings/env-overrides")
async def get_env_overrides():
    """Get settings that are overridden by environment variables."""
    overrides = {}
    env_keys = ["OLLAMA_URL", "OLLAMA_MODEL", "EMBEDDING_MODEL", "DB_HOST", "DB_PORT"]
    
    for key in env_keys:
        if key in os.environ:
            overrides[key] = os.environ[key]
    
    return {"overrides": overrides, "count": len(overrides)}


@router.get("/settings/extensions")
async def get_extensions(db: Session = Depends(get_db)):
    """Get configured file extensions."""
    extensions = get_setting(db, "file_extensions") or []
    return {"extensions": extensions}


@router.put("/settings/extensions")
async def update_extensions(extensions: List[str], db: Session = Depends(get_db)):
    """Update file extensions list."""
    set_setting(db, "file_extensions", extensions)
    return {"extensions": extensions}


# ============================================================================
# LLM Settings Endpoints
# ============================================================================

@router.get("/settings/llm")
async def get_llm_settings(db: Session = Depends(get_db)):
    """Get LLM configuration settings."""
    llm_settings = get_setting(db, "llm") or {}
    
    # Mask API keys
    if "openai" in llm_settings and "api_key" in llm_settings["openai"]:
        if llm_settings["openai"]["api_key"]:
            llm_settings["openai"]["api_key_masked"] = "***" + llm_settings["openai"]["api_key"][-4:]
            del llm_settings["openai"]["api_key"]
    
    if "anthropic" in llm_settings and "api_key" in llm_settings["anthropic"]:
        if llm_settings["anthropic"]["api_key"]:
            llm_settings["anthropic"]["api_key_masked"] = "***" + llm_settings["anthropic"]["api_key"][-4:]
            del llm_settings["anthropic"]["api_key"]
    
    return llm_settings


@router.put("/settings/llm")
async def update_llm_settings(settings: LLMSettingsUpdate, db: Session = Depends(get_db)):
    """Update LLM configuration settings."""
    current = get_setting(db, "llm") or {}
    
    if settings.ollama:
        current["ollama"] = {**current.get("ollama", {}), **settings.ollama}
    if settings.openai:
        current["openai"] = {**current.get("openai", {}), **settings.openai}
    if settings.anthropic:
        current["anthropic"] = {**current.get("anthropic", {}), **settings.anthropic}
    
    set_setting(db, "llm", current)
    return {"message": "LLM settings updated"}


@router.post("/settings/llm/test")
async def test_llm_connection(provider: str = "ollama", db: Session = Depends(get_db)):
    """Test LLM provider connection."""
    llm_settings = get_setting(db, "llm") or {}
    
    if provider == "ollama":
        ollama_url = llm_settings.get("ollama", {}).get("url", "http://localhost:11434")
        try:
            resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return {
                    "connected": True,
                    "url": ollama_url,
                    "model_count": len(models),
                    "models": [m.get("name") for m in models[:5]]
                }
            return {"connected": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"connected": False, "error": str(e)}
    
    elif provider == "openai":
        config = llm_settings.get("openai", {})
        api_key = config.get("api_key")
        if not api_key:
            return {"connected": False, "error": "API key not configured"}
        
        try:
            url = config.get("url", "https://api.openai.com/v1")
            resp = requests.get(
                f"{url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5
            )
            if resp.status_code == 200:
                return {"connected": True}
            return {"connected": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"connected": False, "error": str(e)}
    
    return {"connected": False, "error": "Unknown provider"}


# ============================================================================
# Chunk Enrichment Settings
# ============================================================================

class ChunkEnrichmentUpdate(BaseModel):
    mode: str  # "none", "embed_only", "full"


@router.get("/settings/chunk-enrichment")
async def get_chunk_enrichment_settings(db: Session = Depends(get_db)):
    """
    Get chunk enrichment mode setting.
    
    Modes:
    - none: Skip chunk LLM enrichment entirely, just inherit doc metadata
    - embed_only: Skip LLM enrichment, still embed chunk text (default, fast)
    - full: Full LLM enrichment per chunk (slow, not recommended for large archives)
    """
    mode = get_setting(db, "chunk_enrichment_mode") or "embed_only"
    
    # Get current pending counts for context
    from sqlalchemy import text
    result = db.execute(text("""
        SELECT 
            COUNT(*) FILTER (WHERE status = 'pending') as pending,
            COUNT(*) FILTER (WHERE status = 'enriched') as enriched,
            COUNT(*) as total
        FROM entries
    """)).fetchone()
    
    return {
        "mode": mode,
        "pending_chunks": result[0] if result else 0,
        "enriched_chunks": result[1] if result else 0,
        "total_chunks": result[2] if result else 0,
        "modes": {
            "none": {
                "name": "Skip All",
                "description": "Inherit doc metadata only. Fastest option, no embeddings.",
                "recommended_for": "When you only need document-level search"
            },
            "embed_only": {
                "name": "Embed Only (Default)",
                "description": "Skip LLM enrichment, just embed chunk text. Fast and effective.",
                "recommended_for": "Most use cases - good search quality without LLM overhead"
            },
            "full": {
                "name": "Full LLM Enrichment",
                "description": "Generate title, summary, tags for each chunk via LLM. Very slow.",
                "recommended_for": "Small archives where per-chunk metadata is valuable"
            }
        }
    }


@router.put("/settings/chunk-enrichment")
async def update_chunk_enrichment_settings(
    update: ChunkEnrichmentUpdate, 
    db: Session = Depends(get_db)
):
    """Update chunk enrichment mode."""
    valid_modes = ["none", "embed_only", "full"]
    if update.mode not in valid_modes:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid mode '{update.mode}'. Must be one of: {valid_modes}"
        )
    
    set_setting(db, "chunk_enrichment_mode", update.mode)
    return {"message": f"Chunk enrichment mode set to '{update.mode}'", "mode": update.mode}


# ============================================================================
# Sources Settings Endpoints
# ============================================================================

@router.get("/settings/sources")
async def get_sources(db: Session = Depends(get_db)):
    """Get configured source folders."""
    sources = get_setting(db, "sources") or {"folders": [], "excluded_folders": [], "file_extensions": []}
    return sources


@router.put("/settings/sources")
async def update_sources(sources: SourcesUpdate, db: Session = Depends(get_db)):
    """Update source folders configuration."""
    current = get_setting(db, "sources") or {}
    
    current["folders"] = sources.folders
    if sources.excluded_folders is not None:
        current["excluded_folders"] = sources.excluded_folders
    if sources.file_extensions is not None:
        current["file_extensions"] = sources.file_extensions
    
    set_setting(db, "sources", current)
    return {"message": "Sources updated", "sources": current}


@router.post("/settings/sources/include")
async def add_source_folder(folder: str, db: Session = Depends(get_db)):
    """Add a folder to the include list."""
    sources = get_setting(db, "sources") or {"folders": []}
    
    if folder not in sources.get("folders", []):
        sources.setdefault("folders", []).append(folder)
        set_setting(db, "sources", sources)
    
    return {"message": f"Added {folder}", "sources": sources}


@router.delete("/settings/sources/include")
async def remove_source_folder(folder: str, db: Session = Depends(get_db)):
    """Remove a folder from the include list."""
    sources = get_setting(db, "sources") or {"folders": []}
    
    if folder in sources.get("folders", []):
        sources["folders"].remove(folder)
        set_setting(db, "sources", sources)
    
    return {"message": f"Removed {folder}", "sources": sources}


@router.post("/settings/sources/exclude")
async def add_excluded_folder(folder: str, db: Session = Depends(get_db)):
    """Add a folder to the exclude list."""
    sources = get_setting(db, "sources") or {}
    
    if folder not in sources.get("excluded_folders", []):
        sources.setdefault("excluded_folders", []).append(folder)
        set_setting(db, "sources", sources)
    
    return {"message": f"Added {folder} to exclusions", "sources": sources}


@router.delete("/settings/sources/exclude")
async def remove_excluded_folder(folder: str, db: Session = Depends(get_db)):
    """Remove a folder from the exclude list."""
    sources = get_setting(db, "sources") or {}
    
    if folder in sources.get("excluded_folders", []):
        sources["excluded_folders"].remove(folder)
        set_setting(db, "sources", sources)
    
    return {"message": f"Removed {folder} from exclusions", "sources": sources}


@router.get("/settings/sources/mounts")
async def get_available_mounts():
    """Get available mount points for browsing."""
    if os.name == 'nt':
        import string
        from ctypes import windll
        
        drives = []
        bitmask = windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(f"{letter}:/")
            bitmask >>= 1
        return {"mounts": drives}
    else:
        common_mounts = ["/", "/home", "/mnt", "/media", "/var", "/opt"]
        available = [m for m in common_mounts if os.path.exists(m)]
        return {"mounts": available}


@router.get("/settings/sources/browse")
async def browse_directory(path: str = "/"):
    """Browse directories for folder selection."""
    path = Path(path).resolve()
    
    if not path.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    
    if not path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")
    
    try:
        items = []
        for item in sorted(path.iterdir()):
            if item.is_dir():
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "type": "directory"
                })
        
        parent = str(path.parent) if path.parent != path else None
        
        return {
            "current_path": str(path),
            "parent_path": parent,
            "items": items,
            "count": len(items)
        }
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")


# ============================================================================
# Host Path Mappings Endpoints
# ============================================================================

@router.get("/settings/host-path-mappings")
async def get_host_path_mappings(db: Session = Depends(get_db)):
    """Get host path mappings."""
    mappings = get_setting(db, "host_path_mappings") or []
    return {"mappings": mappings}


@router.post("/settings/host-path-mappings")
async def add_host_path_mapping(mapping: HostPathMapping, db: Session = Depends(get_db)):
    """Add a host path mapping."""
    mappings = get_setting(db, "host_path_mappings") or []
    
    mappings.append({"container_path": mapping.container_path, "host_path": mapping.host_path})
    set_setting(db, "host_path_mappings", mappings)
    
    return {"message": "Mapping added", "mappings": mappings}


@router.delete("/settings/host-path-mappings")
async def remove_host_path_mapping(container_path: str, db: Session = Depends(get_db)):
    """Remove a host path mapping."""
    mappings = get_setting(db, "host_path_mappings") or []
    
    mappings = [m for m in mappings if m.get("container_path") != container_path]
    set_setting(db, "host_path_mappings", mappings)
    
    return {"message": "Mapping removed", "mappings": mappings}


# ============================================================================
# Ollama-Specific Settings Endpoints
# ============================================================================

@router.get("/settings/ollama/status")
async def get_ollama_status(db: Session = Depends(get_db)):
    """Check Ollama connection status."""
    llm_settings = get_setting(db, "llm") or {}
    ollama_url = llm_settings.get("ollama", {}).get("url", "http://localhost:11434")
    
    try:
        resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return {
                "connected": True,
                "url": ollama_url,
                "model_count": len(models),
                "models": [m.get("name") for m in models]
            }
        return {"connected": False, "url": ollama_url, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"connected": False, "url": ollama_url, "error": str(e)}


@router.get("/settings/ollama/presets")
async def get_ollama_presets():
    """Get common Ollama server presets."""
    return {
        "presets": [
            {"name": "Local (Default)", "url": "http://localhost:11434"},
            {"name": "Docker Internal", "url": "http://ollama:11434"},
            {"name": "Custom", "url": ""}
        ]
    }


@router.post("/settings/ollama/preset")
async def set_ollama_preset(preset_url: str, db: Session = Depends(get_db)):
    """Set Ollama URL from a preset."""
    llm_settings = get_setting(db, "llm") or {}
    
    if "ollama" not in llm_settings:
        llm_settings["ollama"] = {}
    
    llm_settings["ollama"]["url"] = preset_url
    set_setting(db, "llm", llm_settings)
    
    return {"message": "Ollama URL updated", "url": preset_url}


@router.get("/settings/ollama/models")
async def list_ollama_models(db: Session = Depends(get_db)):
    """List all models available on Ollama."""
    llm_settings = get_setting(db, "llm") or {}
    ollama_url = llm_settings.get("ollama", {}).get("url", "http://localhost:11434")
    
    try:
        resp = requests.get(f"{ollama_url}/api/tags", timeout=10)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return {
                "models": [
                    {
                        "name": m.get("name"),
                        "size": m.get("size"),
                        "modified_at": m.get("modified_at"),
                        "details": m.get("details", {})
                    }
                    for m in models
                ],
                "count": len(models)
            }
        raise HTTPException(status_code=502, detail=f"Ollama returned {resp.status_code}")
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Ollama server timed out")
    except requests.ConnectionError:
        raise HTTPException(status_code=503, detail="Could not connect to Ollama")


@router.post("/settings/ollama/models/pull")
async def pull_ollama_model(
    name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Pull a model from Ollama library."""
    llm_settings = get_setting(db, "llm") or {}
    ollama_url = llm_settings.get("ollama", {}).get("url", "http://localhost:11434")
    
    job = jobs_service.create_job(
        db,
        job_type=jobs_service.JOB_TYPE_MODEL_PULL,
        metadata={"model_name": name, "ollama_url": ollama_url}
    )
    job = jobs_service.start_job(db, job.id, message=f"Pulling {name}...")
    
    def pull_model_task():
        try:
            resp = requests.post(
                f"{ollama_url}/api/pull",
                json={"name": name, "stream": True},
                stream=True,
                timeout=600
            )
            
            if resp.status_code != 200:
                with SessionLocal() as task_db:
                    jobs_service.fail_job(task_db, job.id, f"Server returned {resp.status_code}")
                return
            
            for line in resp.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "completed" in data and "total" in data and data["total"] > 0:
                            pct = int((data["completed"] / data["total"]) * 100)
                            with SessionLocal() as task_db:
                                jobs_service.update_job_progress(
                                    task_db, job.id, pct,
                                    message=f"Downloading: {pct}%"
                                )
                        elif data.get("status") == "success":
                            with SessionLocal() as task_db:
                                jobs_service.complete_job(task_db, job.id, message="Download complete")
                            return
                    except json.JSONDecodeError:
                        pass
            
            with SessionLocal() as task_db:
                jobs_service.complete_job(task_db, job.id, message="Download complete")
                
        except Exception as e:
            with SessionLocal() as task_db:
                jobs_service.fail_job(task_db, job.id, str(e))
    
    background_tasks.add_task(pull_model_task)
    
    return {
        "status": "started",
        "model": name,
        "job_id": str(job.id)
    }


@router.get("/settings/ollama/models/pull/{model_name:path}")
async def get_model_pull_status(model_name: str, db: Session = Depends(get_db)):
    """Get the status of a model pull operation."""
    job = jobs_service.get_recent_job_by_type(db, jobs_service.JOB_TYPE_MODEL_PULL, model_name)
    
    if not job:
        return {"status": "not_found"}
    
    return {
        "status": job.status,
        "progress": job.progress,
        "message": job.message
    }


@router.delete("/settings/ollama/models/{model_name:path}")
async def delete_ollama_model(model_name: str, db: Session = Depends(get_db)):
    """Delete a model from Ollama."""
    llm_settings = get_setting(db, "llm") or {}
    ollama_url = llm_settings.get("ollama", {}).get("url", "http://localhost:11434")
    
    try:
        resp = requests.delete(f"{ollama_url}/api/delete", json={"name": model_name}, timeout=10)
        if resp.status_code == 200:
            return {"message": f"Model {model_name} deleted"}
        raise HTTPException(status_code=502, detail=f"Ollama returned {resp.status_code}")
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Ollama server timed out")
    except requests.ConnectionError:
        raise HTTPException(status_code=503, detail="Could not connect to Ollama")


@router.get("/settings/ollama/models/popular")
async def get_popular_models():
    """Get a list of popular Ollama models."""
    return {
        "models": [
            {"name": "llama3.2:latest", "description": "Meta Llama 3.2 - Latest version"},
            {"name": "qwen2.5:latest", "description": "Alibaba Qwen 2.5"},
            {"name": "phi4:latest", "description": "Microsoft Phi-4"},
            {"name": "nomic-embed-text:latest", "description": "Nomic embeddings for semantic search"},
            {"name": "llava:latest", "description": "Vision model for image understanding"}
        ]
    }


@router.get("/settings/ollama/catalog")
async def get_ollama_catalog():
    """Get the full Ollama model catalog."""
    catalog_file = Path("config/ollama_catalog.json")
    
    if catalog_file.exists():
        with open(catalog_file) as f:
            catalog = json.load(f)
        return catalog
    
    return {"models": [], "error": "Catalog file not found"}
