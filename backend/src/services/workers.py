"""
Workers service - Registration, heartbeat, and lifecycle management for distributed workers.
Part of Phase 7: Dynamic Worker Scaling
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import logging
import uuid
import socket
import os

from sqlalchemy.orm import Session
from sqlalchemy import text
from src.db.models import Worker, OllamaServer

logger = logging.getLogger(__name__)

# Worker status constants
STATUS_STARTING = "starting"
STATUS_ACTIVE = "active"
STATUS_IDLE = "idle"
STATUS_STALE = "stale"
STATUS_STOPPED = "stopped"

# How long before a worker is considered stale (no heartbeat)
STALE_THRESHOLD_SECONDS = 120  # 2 minutes


def generate_worker_id() -> str:
    """Generate a unique worker ID based on hostname and UUID."""
    hostname = socket.gethostname()
    short_uuid = str(uuid.uuid4())[:8]
    return f"{hostname}-{short_uuid}"


def get_worker(db: Session, worker_id: str) -> Optional[Worker]:
    """Get a specific worker by ID."""
    return db.query(Worker).filter(Worker.id == worker_id).first()


def get_all_workers(db: Session, include_stopped: bool = False) -> List[Worker]:
    """Get all registered workers."""
    query = db.query(Worker)
    if not include_stopped:
        query = query.filter(Worker.status != STATUS_STOPPED)
    return query.order_by(Worker.started_at.desc()).all()


def get_active_workers(db: Session) -> List[Worker]:
    """Get all workers that are currently active or idle."""
    return (
        db.query(Worker)
        .filter(Worker.status.in_([STATUS_ACTIVE, STATUS_IDLE, STATUS_STARTING]))
        .order_by(Worker.started_at.desc())
        .all()
    )


def get_workers_by_server(db: Session, server_id: int) -> List[Worker]:
    """Get all workers associated with a specific Ollama server."""
    return (
        db.query(Worker)
        .filter(Worker.ollama_server_id == server_id)
        .filter(Worker.status != STATUS_STOPPED)
        .all()
    )


def register_worker(
    db: Session,
    worker_id: Optional[str] = None,
    name: Optional[str] = None,
    ollama_url: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    managed: bool = False
) -> Worker:
    """
    Register a new worker or re-register an existing one.
    Called when a worker starts up.
    """
    if not worker_id:
        worker_id = generate_worker_id()
    
    if not name:
        name = worker_id
    
    # Check if worker already exists (re-registration after restart)
    existing = get_worker(db, worker_id)
    if existing:
        existing.status = STATUS_STARTING
        existing.current_task = None
        existing.current_phase = None
        existing.last_heartbeat = datetime.now(timezone.utc)
        existing.started_at = datetime.now(timezone.utc)
        if config:
            existing.config = config
        db.commit()
        db.refresh(existing)
        logger.info(f"Re-registered worker: {worker_id}")
        return existing
    
    # Find Ollama server by URL if provided
    ollama_server_id = None
    if ollama_url:
        normalized_url = ollama_url.rstrip('/')
        server = db.query(OllamaServer).filter(OllamaServer.url == normalized_url).first()
        if server:
            ollama_server_id = server.id
        else:
            # Auto-create server entry for this URL
            server = OllamaServer(
                name=f"auto-{worker_id[:8]}",
                url=normalized_url,
                enabled=True,
                status='unknown'
            )
            db.add(server)
            db.flush()
            ollama_server_id = server.id
            logger.info(f"Auto-created Ollama server for worker: {normalized_url}")
    
    worker = Worker(
        id=worker_id,
        name=name,
        ollama_server_id=ollama_server_id,
        status=STATUS_STARTING,
        managed=managed,
        last_heartbeat=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
        config=config or {}
    )
    
    db.add(worker)
    db.commit()
    db.refresh(worker)
    
    logger.info(f"Registered new worker: {worker_id} (managed={managed})")
    return worker


def heartbeat(
    db: Session,
    worker_id: str,
    status: str = STATUS_ACTIVE,
    current_task: Optional[str] = None,
    current_phase: Optional[str] = None,
    stats: Optional[Dict[str, Any]] = None
) -> Optional[Worker]:
    """
    Update worker heartbeat and status.
    Called periodically by workers to indicate they're alive.
    """
    worker = get_worker(db, worker_id)
    if not worker:
        logger.warning(f"Heartbeat from unknown worker: {worker_id}")
        return None
    
    worker.status = status
    worker.current_task = current_task
    worker.current_phase = current_phase
    worker.last_heartbeat = datetime.now(timezone.utc)
    
    if stats:
        # Merge stats with existing
        existing_stats = worker.stats or {}
        existing_stats.update(stats)
        worker.stats = existing_stats
    
    db.commit()
    db.refresh(worker)
    
    return worker


def deregister_worker(db: Session, worker_id: str) -> bool:
    """
    Mark a worker as stopped (graceful shutdown).
    Worker record is kept for history.
    """
    worker = get_worker(db, worker_id)
    if not worker:
        return False
    
    worker.status = STATUS_STOPPED
    worker.current_task = None
    worker.current_phase = None
    worker.last_heartbeat = datetime.now(timezone.utc)
    
    db.commit()
    
    logger.info(f"Deregistered worker: {worker_id}")
    return True


def delete_worker(db: Session, worker_id: str) -> bool:
    """Permanently delete a worker record."""
    worker = get_worker(db, worker_id)
    if not worker:
        return False
    
    db.delete(worker)
    db.commit()
    
    logger.info(f"Deleted worker: {worker_id}")
    return True


def mark_stale_workers(db: Session) -> int:
    """
    Mark workers as stale if they haven't sent a heartbeat recently.
    Returns the number of workers marked as stale.
    """
    threshold = datetime.now(timezone.utc) - timedelta(seconds=STALE_THRESHOLD_SECONDS)
    
    stale_workers = (
        db.query(Worker)
        .filter(Worker.status.in_([STATUS_ACTIVE, STATUS_IDLE, STATUS_STARTING]))
        .filter(Worker.last_heartbeat < threshold)
        .all()
    )
    
    count = 0
    for worker in stale_workers:
        worker.status = STATUS_STALE
        count += 1
        logger.warning(f"Marked worker as stale: {worker.id}")
    
    if count > 0:
        db.commit()
    
    return count


def cleanup_old_workers(db: Session, days: int = 7) -> int:
    """
    Remove worker records older than specified days.
    Only removes stopped or stale workers.
    """
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    
    result = db.execute(
        text("""
            DELETE FROM workers 
            WHERE status IN ('stopped', 'stale') 
            AND last_heartbeat < :threshold
        """),
        {"threshold": threshold}
    )
    
    db.commit()
    count = result.rowcount
    
    if count > 0:
        logger.info(f"Cleaned up {count} old worker records")
    
    return count


def get_worker_stats_summary(db: Session) -> Dict[str, Any]:
    """Get aggregated stats across all active workers."""
    active = get_active_workers(db)
    
    total_docs_per_min = 0
    total_entries_per_min = 0
    worker_count = len(active)
    
    by_status = {"starting": 0, "active": 0, "idle": 0, "stale": 0}
    by_phase = {}
    
    for worker in active:
        by_status[worker.status] = by_status.get(worker.status, 0) + 1
        
        if worker.current_phase:
            by_phase[worker.current_phase] = by_phase.get(worker.current_phase, 0) + 1
        
        if worker.stats:
            total_docs_per_min += worker.stats.get("docs_per_min", 0)
            total_entries_per_min += worker.stats.get("entries_per_min", 0)
    
    return {
        "worker_count": worker_count,
        "by_status": by_status,
        "by_phase": by_phase,
        "total_docs_per_min": round(total_docs_per_min, 2),
        "total_entries_per_min": round(total_entries_per_min, 2)
    }


def worker_to_dict(worker: Worker) -> Dict[str, Any]:
    """Convert worker model to dictionary for API responses."""
    server_name = None
    server_url = None
    if worker.ollama_server:
        server_name = worker.ollama_server.name
        server_url = worker.ollama_server.url
    
    return {
        "id": worker.id,
        "name": worker.name,
        "status": worker.status,
        "current_task": worker.current_task,
        "current_phase": worker.current_phase,
        "stats": worker.stats or {},
        "managed": worker.managed,
        "ollama_server_id": worker.ollama_server_id,
        "ollama_server_name": server_name,
        "ollama_server_url": server_url,
        "config": worker.config or {},
        "last_heartbeat": worker.last_heartbeat.isoformat() if worker.last_heartbeat else None,
        "started_at": worker.started_at.isoformat() if worker.started_at else None
    }


def get_external_worker_command(
    db_url: str,
    ollama_url: str,
    worker_name: Optional[str] = None,
    image_tag: str = "latest"
) -> str:
    """
    Generate the docker run command for an external worker.
    This is shown in the UI for users to copy and run on remote machines.
    """
    name = worker_name or "archive-worker"
    
    return f"""docker run -d \\
  --name {name} \\
  -e DATABASE_URL={db_url} \\
  -e OLLAMA_URL={ollama_url} \\
  -e WORKER_NAME={name} \\
  ghcr.io/ryanlane/archive-brain-worker:{image_tag}"""
