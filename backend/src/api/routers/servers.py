"""
Servers API Router
Handles LLM provider registry (servers) and distributed worker registry.
"""
import os
import json
from typing import Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
import requests

from src.db.session import get_db, SessionLocal
from src.services import servers as servers_service
from src.services import workers as workers_service
from src.services import jobs as jobs_service

router = APIRouter(tags=["servers"])


# ============================================================================
# Pydantic Models
# ============================================================================

class ServerCreate(BaseModel):
    name: str
    url: str
    enabled: bool = True
    priority: int = 0
    provider_type: str = 'ollama'  # 'ollama', 'openai', 'anthropic'
    api_key: Optional[str] = None
    default_model: Optional[str] = None


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    api_key: Optional[str] = None
    default_model: Optional[str] = None


class TestConnectionRequest(BaseModel):
    url: str
    provider_type: str = 'ollama'
    api_key: Optional[str] = None


class WorkerRegister(BaseModel):
    worker_id: Optional[str] = None
    name: Optional[str] = None
    ollama_url: Optional[str] = None
    config: Optional[dict] = None


class WorkerHeartbeat(BaseModel):
    status: str = "active"
    current_task: Optional[str] = None
    current_phase: Optional[str] = None
    stats: Optional[dict] = None


# ============================================================================
# Server Endpoints (LLM Providers)
# ============================================================================

@router.post("/servers/test-connection")
async def test_connection(request: TestConnectionRequest):
    """
    Test connection to a provider without saving.
    Used by the Add Provider wizard to validate before saving.
    """
    result = {
        "connected": False,
        "models": [],
        "capabilities": {},
        "error": None
    }
    
    try:
        if request.provider_type == 'ollama':
            # Test Ollama connection
            url = request.url.rstrip('/')
            resp = requests.get(f"{url}/api/tags", timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                result["connected"] = True
                result["models"] = [m.get("name") for m in models]
                
                # Detect capabilities
                caps = {"chat": False, "embedding": False, "vision": False}
                for m in models:
                    name = m.get("name", "").lower()
                    if any(x in name for x in ["embed", "nomic", "bge"]):
                        caps["embedding"] = True
                    elif any(x in name for x in ["llava", "vision", "bakllava"]):
                        caps["vision"] = True
                        caps["chat"] = True
                    else:
                        caps["chat"] = True
                result["capabilities"] = caps
            else:
                result["error"] = f"HTTP {resp.status_code}"
                
        elif request.provider_type == 'openai':
            if not request.api_key:
                result["error"] = "API key required"
            else:
                url = request.url or 'https://api.openai.com/v1'
                resp = requests.get(
                    f"{url}/models",
                    headers={"Authorization": f"Bearer {request.api_key}"},
                    timeout=10
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    result["connected"] = True
                    result["models"] = [m.get("id") for m in data.get("data", [])][:20]  # Limit for display
                    result["capabilities"] = {"chat": True, "embedding": True, "vision": True}
                elif resp.status_code == 401:
                    result["error"] = "Invalid API key"
                else:
                    result["error"] = f"HTTP {resp.status_code}"
                    
        elif request.provider_type == 'anthropic':
            if not request.api_key:
                result["error"] = "API key required"
            else:
                url = request.url or 'https://api.anthropic.com'
                # Anthropic doesn't have a models endpoint, do a minimal test
                resp = requests.post(
                    f"{url}/v1/messages",
                    headers={
                        "x-api-key": request.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}]
                    },
                    timeout=10
                )
                
                # Any 2xx or 4xx response (except 401) means we connected
                if resp.status_code in [200, 400]:
                    result["connected"] = True
                    result["models"] = [
                        "claude-3-5-sonnet-20241022",
                        "claude-3-5-haiku-20241022",
                        "claude-3-opus-20240229"
                    ]
                    result["capabilities"] = {"chat": True, "embedding": False, "vision": True}
                elif resp.status_code == 401:
                    result["error"] = "Invalid API key"
                else:
                    result["error"] = f"HTTP {resp.status_code}"
        else:
            result["error"] = f"Unknown provider type: {request.provider_type}"
            
    except requests.Timeout:
        result["error"] = "Connection timed out"
    except requests.ConnectionError:
        result["error"] = "Connection refused - is the server running?"
    except Exception as e:
        result["error"] = str(e)[:200]
    
    return result


@router.get("/servers")
async def list_servers(enabled_only: bool = False, db: Session = Depends(get_db)):
    """List all registered LLM providers."""
    servers = servers_service.get_all_servers(db, enabled_only=enabled_only)
    return {
        "servers": [servers_service.server_to_dict(s) for s in servers],
        "count": len(servers)
    }


@router.post("/servers")
async def create_server(server: ServerCreate, db: Session = Depends(get_db)):
    """Register a new LLM provider (Ollama server or cloud API)."""
    # Check for duplicate name
    existing = servers_service.get_server_by_name(db, server.name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Provider with name '{server.name}' already exists")
    
    # Check for duplicate URL (only for Ollama providers)
    if server.provider_type == 'ollama':
        existing_url = servers_service.get_server_by_url(db, server.url)
        if existing_url:
            raise HTTPException(status_code=400, detail=f"Provider with URL already exists as '{existing_url.name}'")
    
    new_server = servers_service.create_server(
        db,
        name=server.name,
        url=server.url,
        enabled=server.enabled,
        priority=server.priority,
        provider_type=server.provider_type,
        api_key=server.api_key,
        default_model=server.default_model
    )
    
    # Immediately check health (for all provider types)
    servers_service.check_provider_health(db, new_server.id)
    db.refresh(new_server)
    
    return servers_service.server_to_dict(new_server)


@router.get("/servers/{server_id}")
async def get_server(server_id: int, db: Session = Depends(get_db)):
    """Get a specific server by ID."""
    server = servers_service.get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return servers_service.server_to_dict(server)


@router.put("/servers/{server_id}")
async def update_server(server_id: int, update: ServerUpdate, db: Session = Depends(get_db)):
    """Update a server's configuration."""
    # Check if name conflicts with another server
    if update.name:
        existing = servers_service.get_server_by_name(db, update.name)
        if existing and existing.id != server_id:
            raise HTTPException(status_code=400, detail=f"Server with name '{update.name}' already exists")
    
    server = servers_service.update_server(
        db,
        server_id,
        name=update.name,
        url=update.url,
        enabled=update.enabled,
        priority=update.priority
    )
    
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    return servers_service.server_to_dict(server)


@router.delete("/servers/{server_id}")
async def delete_server(server_id: int, db: Session = Depends(get_db)):
    """Delete a server from the registry."""
    server = servers_service.get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Check if there are active workers on this server
    workers = workers_service.get_workers_by_server(db, server_id)
    if workers:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete server with {len(workers)} active worker(s). Stop workers first."
        )
    
    if servers_service.delete_server(db, server_id):
        return {"deleted": True, "id": server_id}
    raise HTTPException(status_code=500, detail="Failed to delete server")


@router.post("/servers/{server_id}/test")
async def test_server(server_id: int, db: Session = Depends(get_db)):
    """Test connectivity to a specific provider."""
    result = servers_service.check_provider_health(db, server_id)
    if result.get("error") == "Provider not found":
        raise HTTPException(status_code=404, detail="Provider not found")
    return result


@router.post("/servers/test-all")
async def test_all_servers(enabled_only: bool = True, db: Session = Depends(get_db)):
    """Test connectivity to all registered servers."""
    results = servers_service.check_all_servers_health(db, enabled_only=enabled_only)
    online = sum(1 for r in results if r.get("connected"))
    return {
        "results": results,
        "online": online,
        "total": len(results)
    }


@router.get("/servers/{server_id}/models")
async def get_server_models(server_id: int, db: Session = Depends(get_db)):
    """Get the list of models available on a specific server."""
    server = servers_service.get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Refresh from server
    try:
        resp = requests.get(f"{server.url}/api/tags", timeout=10)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            model_list = [m.get("name") for m in models]
            server.models_available = model_list
            db.commit()
            return {"models": model_list, "server": server.name}
        else:
            raise HTTPException(status_code=502, detail=f"Server returned {resp.status_code}")
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Server timed out")
    except requests.ConnectionError:
        raise HTTPException(status_code=503, detail="Could not connect to server")


@router.post("/servers/{server_id}/pull-model")
async def pull_model_to_server(
    server_id: int,
    background_tasks: BackgroundTasks,
    name: str = None,
    body: dict = None,
    db: Session = Depends(get_db)
):
    """Pull a model to a specific server. Creates a job to track progress."""
    server = servers_service.get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Get model name from query param or body
    model_name = name or (body.get("name") if body else None)
    if not model_name:
        raise HTTPException(status_code=400, detail="Model name required")
    
    # Create job to track the pull
    job = jobs_service.create_job(
        db,
        job_type=jobs_service.JOB_TYPE_MODEL_PULL,
        metadata={
            "model_name": model_name,
            "server_id": server_id,
            "server_name": server.name,
            "ollama_url": server.url
        }
    )
    job = jobs_service.start_job(db, job.id, message=f"Pulling {model_name} to {server.name}...")
    
    # Use the existing model pull logic but with the server's URL
    def pull_model_task():
        try:
            # Use streaming pull
            resp = requests.post(
                f"{server.url}/api/pull",
                json={"name": model_name, "stream": True},
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
            
            # If we got here without "success", assume it completed
            with SessionLocal() as task_db:
                jobs_service.complete_job(task_db, job.id, message="Download complete")
                
        except Exception as e:
            with SessionLocal() as task_db:
                jobs_service.fail_job(task_db, job.id, str(e))
    
    background_tasks.add_task(pull_model_task)
    
    return {
        "status": "started",
        "model": model_name,
        "server": server.name,
        "job_id": str(job.id)
    }


# ============================================================================
# Workers Endpoints (Distributed Worker Registry)
# ============================================================================

@router.get("/workers")
async def list_workers(include_stopped: bool = False, db: Session = Depends(get_db)):
    """List all registered workers."""
    workers = workers_service.get_all_workers(db, include_stopped=include_stopped)
    return {
        "workers": [workers_service.worker_to_dict(w) for w in workers],
        "count": len(workers)
    }


@router.get("/workers/active")
async def get_active_workers_list(db: Session = Depends(get_db)):
    """Get all currently active workers."""
    workers = workers_service.get_active_workers(db)
    return {
        "workers": [workers_service.worker_to_dict(w) for w in workers],
        "count": len(workers)
    }


@router.get("/workers/stats")
async def get_workers_stats(db: Session = Depends(get_db)):
    """Get aggregated stats across all active workers."""
    # Also mark stale workers
    stale_count = workers_service.mark_stale_workers(db)
    
    stats = workers_service.get_worker_stats_summary(db)
    stats["stale_marked"] = stale_count
    return stats


@router.get("/workers/command")
async def get_external_worker_command(
    server_id: Optional[int] = None,
    worker_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get the docker run command for starting an external worker.
    This is displayed in the UI for users to copy and run on remote machines.
    """
    # Build database URL from environment
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_user = os.environ.get("DB_USER", "postgres")
    db_pass = os.environ.get("DB_PASSWORD", "password")
    db_name = os.environ.get("DB_NAME", "archive_brain")
    
    # For external workers, they need to reach the DB from outside docker network
    # Replace internal hostnames with user-friendly placeholders
    if db_host in ["db", "localhost"]:
        db_url = f"postgres://{db_user}:{db_pass}@<YOUR_HOST>:{db_port}/{db_name}"
    else:
        db_url = f"postgres://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    # Get Ollama URL from server or default
    if server_id:
        server = servers_service.get_server(db, server_id)
        if server:
            ollama_url = server.url
            # Replace internal docker hostnames
            if "ollama:11434" in ollama_url:
                ollama_url = "http://<YOUR_HOST>:11434"
        else:
            ollama_url = "http://<OLLAMA_HOST>:11434"
    else:
        ollama_url = "http://<OLLAMA_HOST>:11434"
    
    command = workers_service.get_external_worker_command(
        db_url=db_url,
        ollama_url=ollama_url,
        worker_name=worker_name
    )
    
    return {
        "command": command,
        "notes": [
            "Replace <YOUR_HOST> with your server's IP or hostname",
            "Replace <OLLAMA_HOST> with the Ollama server's IP or hostname",
            "Ensure the worker can reach both the database and Ollama server"
        ]
    }


@router.post("/workers/register")
async def register_worker(worker: WorkerRegister, db: Session = Depends(get_db)):
    """
    Register a new worker or re-register an existing one.
    Called by workers on startup.
    """
    new_worker = workers_service.register_worker(
        db,
        worker_id=worker.worker_id,
        name=worker.name,
        ollama_url=worker.ollama_url,
        config=worker.config,
        managed=False  # API registrations are external workers
    )
    return workers_service.worker_to_dict(new_worker)


@router.get("/workers/{worker_id}")
async def get_worker_detail(worker_id: str, db: Session = Depends(get_db)):
    """Get a specific worker by ID."""
    worker = workers_service.get_worker(db, worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    return workers_service.worker_to_dict(worker)


@router.post("/workers/{worker_id}/heartbeat")
async def worker_heartbeat(worker_id: str, heartbeat: WorkerHeartbeat, db: Session = Depends(get_db)):
    """
    Update worker heartbeat and status.
    Called periodically by workers to indicate they're alive.
    """
    worker = workers_service.heartbeat(
        db,
        worker_id,
        status=heartbeat.status,
        current_task=heartbeat.current_task,
        current_phase=heartbeat.current_phase,
        stats=heartbeat.stats
    )
    
    if not worker:
        # Worker not registered - tell it to register first
        raise HTTPException(status_code=404, detail="Worker not registered. Call /workers/register first.")
    
    return {"ok": True, "status": worker.status}


@router.post("/workers/{worker_id}/deregister")
async def deregister_worker_endpoint(worker_id: str, db: Session = Depends(get_db)):
    """
    Mark a worker as stopped (graceful shutdown).
    Called by workers during shutdown.
    """
    if workers_service.deregister_worker(db, worker_id):
        return {"ok": True, "worker_id": worker_id}
    raise HTTPException(status_code=404, detail="Worker not found")


@router.delete("/workers/{worker_id}")
async def delete_worker_endpoint(worker_id: str, db: Session = Depends(get_db)):
    """Permanently delete a worker record."""
    worker = workers_service.get_worker(db, worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    if worker.status in [workers_service.STATUS_ACTIVE, workers_service.STATUS_STARTING]:
        raise HTTPException(status_code=400, detail="Cannot delete active worker. Stop it first.")
    
    if workers_service.delete_worker(db, worker_id):
        return {"deleted": True, "worker_id": worker_id}
    raise HTTPException(status_code=500, detail="Failed to delete worker")


@router.post("/workers/cleanup")
async def cleanup_old_workers_endpoint(days: int = 7, db: Session = Depends(get_db)):
    """Delete stopped/stale worker records older than specified days."""
    count = workers_service.cleanup_old_workers(db, days=days)
    return {"deleted": count, "days": days}
