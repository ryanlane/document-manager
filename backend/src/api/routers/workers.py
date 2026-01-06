"""
Workers API Router - Worker management and monitoring

This router handles both local worker process management and distributed worker registry:
- Local worker state (start/stop/pause services)
- Worker progress and stats
- Worker logs management
- Distributed worker registration and heartbeats
- Worker scheduling and status
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...db.models import Entry
from ...db.settings import get_setting
from ...db.session import get_db
from ...services import workers as workers_service
from ...services.worker_state import get_primary_worker_state
from .shared import (
    WORKER_LOG_FILE,
    WORKER_PROGRESS_FILE,
    INGEST_PROGRESS_FILE,
    ENRICH_PROGRESS_FILE,
    EMBED_PROGRESS_FILE,
    get_worker_state,
    save_worker_state,
)


router = APIRouter(tags=["workers"])


# ============================================================================
# Pydantic Models
# ============================================================================

class WorkerStateUpdate(BaseModel):
    ingest: Optional[bool] = None
    segment: Optional[bool] = None
    enrich: Optional[bool] = None
    enrich_docs: Optional[bool] = None
    embed: Optional[bool] = None
    embed_docs: Optional[bool] = None
    running: Optional[bool] = None


class WorkerRegister(BaseModel):
    worker_id: str
    name: str
    ollama_url: str
    config: Optional[dict] = None


class WorkerHeartbeat(BaseModel):
    status: str
    current_task: Optional[str] = None
    current_phase: Optional[str] = None
    stats: Optional[dict] = None


# ============================================================================
# Local Worker State Management
# ============================================================================

@router.get("/worker/state")
def get_worker_state_endpoint(db: Session = Depends(get_db)):
    """Get current worker process states from database."""
    # PRIMARY: Read from database
    state_manager = get_primary_worker_state(db)
    if state_manager:
        return state_manager.get_config()

    # FALLBACK: Read from file if no worker in DB yet
    return get_worker_state()


@router.get("/worker/schedule-status")
def get_worker_schedule_status(db: Session = Depends(get_db)):
    """Get current worker schedule status for dashboard display."""
    import pytz
    
    # Get schedule settings
    enabled_str = get_setting(db, "worker_schedule_enabled")
    enabled = enabled_str == "true" if enabled_str else False
    
    if not enabled:
        return {
            "enabled": False,
            "in_window": True,
            "message": None,
            "paused_services": []
        }
    
    schedule_str = get_setting(db, "worker_default_schedule")
    if not schedule_str:
        return {
            "enabled": True,
            "in_window": True,
            "message": "No schedule configured",
            "paused_services": []
        }
    
    try:
        schedule = json.loads(schedule_str) if isinstance(schedule_str, str) else schedule_str
    except:
        return {
            "enabled": True,
            "in_window": True,
            "message": "Invalid schedule configuration",
            "paused_services": []
        }
    
    # Get current time in schedule timezone
    tz_name = schedule.get("timezone", "UTC")
    try:
        tz = pytz.timezone(tz_name)
    except:
        tz = pytz.UTC
    
    now = datetime.now(tz)
    current_day = now.weekday()  # 0=Monday
    current_time = now.strftime("%H:%M")
    
    # Check if today is an active day
    active_days = schedule.get("days", [0, 1, 2, 3, 4, 5, 6])
    start_time = schedule.get("start_time", "22:00")
    end_time = schedule.get("end_time", "08:00")
    next_day = schedule.get("next_day", end_time <= start_time)
    
    # Determine if we're in the active window
    in_window = False
    
    if next_day:
        # Overnight schedule (e.g., 22:00 -> 08:00)
        if current_time >= start_time:
            # After start time - check if today is an active day
            in_window = current_day in active_days
        elif current_time < end_time:
            # Before end time - check if yesterday was an active day
            yesterday = (current_day - 1) % 7
            in_window = yesterday in active_days
    else:
        # Same-day schedule (e.g., 09:00 -> 17:00)
        if current_day in active_days and start_time <= current_time < end_time:
            in_window = True
    
    # Build message for dashboard
    if in_window:
        message = f"Active until {end_time}"
        if next_day:
            message += " tomorrow"
    else:
        # Find next active window
        next_start_day = None
        for i in range(7):
            check_day = (current_day + i) % 7
            if check_day in active_days:
                if i == 0 and current_time < start_time:
                    next_start_day = "today"
                    break
                elif i == 1:
                    next_start_day = "tomorrow"
                    break
                else:
                    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    next_start_day = day_names[check_day]
                    break
        
        if next_start_day:
            message = f"Paused • Resumes {start_time} {next_start_day}"
        else:
            message = "Paused • No active days configured"
    
    # List which services are affected when paused
    paused_services = []
    if not in_window:
        paused_services = ["enrich_docs", "embed_docs", "enrich", "embed"]
    
    return {
        "enabled": True,
        "in_window": in_window,
        "message": message,
        "start_time": start_time,
        "end_time": end_time,
        "timezone": tz_name,
        "paused_services": paused_services
    }


@router.post("/worker/state")
def update_worker_state(update: WorkerStateUpdate, db: Session = Depends(get_db)):
    """Update worker process states in database."""
    # Build updates dict
    updates = {}
    if update.ingest is not None:
        updates["ingest"] = update.ingest
    if update.segment is not None:
        updates["segment"] = update.segment
    if update.enrich is not None:
        updates["enrich"] = update.enrich
    if update.enrich_docs is not None:
        updates["enrich_docs"] = update.enrich_docs
    if update.embed is not None:
        updates["embed"] = update.embed
    if update.embed_docs is not None:
        updates["embed_docs"] = update.embed_docs
    if update.running is not None:
        updates["running"] = update.running

    # PRIMARY: Update in database
    state_manager = get_primary_worker_state(db)
    if state_manager:
        state_manager.update_config(updates)
        return state_manager.get_config()

    # FALLBACK: Update file if no worker in DB yet
    current = get_worker_state()
    current.update(updates)
    if save_worker_state(current):
        return current
    else:
        raise HTTPException(status_code=500, detail="Failed to save worker state")


@router.get("/worker/progress")
def get_worker_progress(db: Session = Depends(get_db)):
    """Get current batch progress for all worker phases from database."""
    result = {}

    # PRIMARY: Read from database
    state_manager = get_primary_worker_state(db)
    if state_manager:
        result = state_manager.get_progress() or {}

    # FALLBACK: Read from file if no worker in DB yet
    if not result:
        try:
            if os.path.exists(WORKER_PROGRESS_FILE):
                with open(WORKER_PROGRESS_FILE, 'r') as f:
                    result = json.load(f)
        except Exception:
            pass

        # Also read from legacy progress files if they exist
        def read_legacy_progress(filepath):
            try:
                if os.path.exists(filepath):
                    with open(filepath, 'r') as f:
                        return json.load(f)
            except Exception:
                pass
            return None

        # Merge legacy progress files (for backwards compatibility)
        if 'ingest' not in result:
            legacy = read_legacy_progress(INGEST_PROGRESS_FILE)
            if legacy:
                result['ingest'] = legacy
        if 'enrich' not in result:
            legacy = read_legacy_progress(ENRICH_PROGRESS_FILE)
            if legacy:
                result['enrich'] = legacy
        if 'embed' not in result:
            legacy = read_legacy_progress(EMBED_PROGRESS_FILE)
            if legacy:
                result['embed'] = legacy
    
    # Compute summary fields for notifications
    phases = {}
    any_active = False
    total_progress = 0
    active_phases = 0
    
    for phase_name, phase_data in result.items():
        if isinstance(phase_data, dict):
            phases[phase_name] = phase_data
            if phase_data.get('status') == 'running':
                any_active = True
                current = phase_data.get('current', 0) or 0
                total = phase_data.get('total', 0) or 0
                if total > 0:
                    total_progress += (current / total) * 100
                    active_phases += 1
    
    # Calculate overall progress as average of active phases
    overall_progress = total_progress / active_phases if active_phases > 0 else 0
    
    return {
        "phases": phases,
        "any_active": any_active,
        "overall_progress": round(overall_progress, 1)
    }


# ============================================================================
# Worker Logs Management
# ============================================================================

@router.get("/worker/logs")
def get_worker_logs(lines: int = 100):
    """Get the last N lines from the worker log file using tail for efficiency."""
    import subprocess
    
    try:
        if not os.path.exists(WORKER_LOG_FILE):
            return {"lines": [], "message": "Log file not found. Worker may need to be restarted."}
        
        # Use tail for efficient reading of large files
        # Limit to max 1000 lines to prevent memory issues
        lines = min(lines, 1000)
        
        try:
            result = subprocess.run(
                ['tail', '-n', str(lines), WORKER_LOG_FILE],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                log_lines = result.stdout.splitlines(keepends=True)
                return {"lines": log_lines}
            else:
                # Fallback: read last portion of file directly
                pass
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # tail not available or timed out, use Python fallback
            pass
        
        # Python fallback: read only the end of the file
        # Estimate ~200 bytes per line, read extra to be safe
        chunk_size = lines * 300
        with open(WORKER_LOG_FILE, 'rb') as f:
            f.seek(0, 2)  # Go to end
            file_size = f.tell()
            start_pos = max(0, file_size - chunk_size)
            f.seek(start_pos)
            content = f.read().decode('utf-8', errors='replace')
            all_lines = content.splitlines(keepends=True)
            # Skip first line if we started mid-line
            if start_pos > 0 and all_lines:
                all_lines = all_lines[1:]
            return {"lines": all_lines[-lines:]}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/worker/logs/rotate")
def rotate_worker_logs():
    """Rotate the worker log file - keeps last 10000 lines, archives the rest."""
    import subprocess
    
    try:
        if not os.path.exists(WORKER_LOG_FILE):
            return {"message": "No log file to rotate"}
        
        # Get file size
        file_size = os.path.getsize(WORKER_LOG_FILE)
        if file_size < 10 * 1024 * 1024:  # Less than 10MB, no need to rotate
            return {"message": "Log file is small, no rotation needed", "size_mb": round(file_size / (1024*1024), 2)}
        
        # Use tail to keep last 10000 lines
        try:
            result = subprocess.run(
                ['tail', '-n', '10000', WORKER_LOG_FILE],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                # Archive old log
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                archive_path = f"{WORKER_LOG_FILE}.{timestamp}"
                os.rename(WORKER_LOG_FILE, archive_path)
                
                # Write the last 10000 lines to new log file
                with open(WORKER_LOG_FILE, 'w') as f:
                    f.write(result.stdout)
                
                # Compress archive (optional, in background)
                subprocess.Popen(['gzip', archive_path])
                
                new_size = os.path.getsize(WORKER_LOG_FILE)
                return {
                    "message": "Log rotated successfully",
                    "old_size_mb": round(file_size / (1024*1024), 2),
                    "new_size_mb": round(new_size / (1024*1024), 2),
                    "archived_to": f"{archive_path}.gz"
                }
        except Exception as e:
            return {"error": f"Rotation failed: {str(e)}"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/worker/logs")
def clear_worker_logs():
    """Clear the worker log file."""
    try:
        if os.path.exists(WORKER_LOG_FILE):
            # Truncate the file
            with open(WORKER_LOG_FILE, 'w') as f:
                f.write("")
            return {"message": "Log file cleared"}
        return {"message": "No log file to clear"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Worker Statistics
# ============================================================================

def calculate_eta(pending_count: int, rate_per_min: float) -> dict:
    """Calculate ETA with friendly time string."""
    if rate_per_min <= 0 or pending_count <= 0:
        return {
            "pending_count": pending_count,
            "rate_per_minute": rate_per_min,
            "eta_minutes": None,
            "eta_string": "N/A" if pending_count > 0 else "Complete"
        }
    
    eta_minutes = pending_count / rate_per_min
    
    # Format as friendly string
    if eta_minutes < 60:
        eta_string = f"{int(eta_minutes)} min"
    elif eta_minutes < 1440:  # Less than 24 hours
        hours = eta_minutes / 60
        eta_string = f"{hours:.1f} hours"
    else:
        days = eta_minutes / 1440
        eta_string = f"{days:.1f} days"
    
    return {
        "pending_count": pending_count,
        "rate_per_minute": round(rate_per_min, 2),
        "eta_minutes": round(eta_minutes, 1),
        "eta_string": eta_string
    }


def get_doc_stats_with_eta(db: Session) -> dict:
    """Get document-level stats with enrichment ETAs."""
    from ...db.models import RawFile

    # Count docs by document-level status
    total_docs = db.query(RawFile).count()
    enriched_docs = db.query(RawFile).filter(RawFile.doc_status == 'enriched').count()
    pending_docs = db.query(RawFile).filter(RawFile.doc_status == 'pending').count()

    # Get recent doc enrichment rate (last hour)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_enriched_docs = db.execute(text("""
        SELECT COUNT(*) FROM raw_files
        WHERE doc_status = 'enriched'
          AND updated_at > :cutoff
    """), {"cutoff": one_hour_ago}).scalar() or 0
    
    doc_rate_per_min = recent_enriched_docs / 60 if recent_enriched_docs > 0 else 0
    doc_eta = calculate_eta(pending_docs, doc_rate_per_min)
    
    return {
        "total": total_docs,
        "enriched": enriched_docs,
        "pending": pending_docs,
        "rate_per_minute": round(doc_rate_per_min, 2),
        "rate_per_hour": recent_enriched_docs,
        "eta": doc_eta
    }


@router.get("/worker/stats")
def get_worker_stats(db: Session = Depends(get_db)):
    """Get comprehensive worker statistics including ETAs."""
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
    
    # Calculate chunk ETA
    chunk_eta = calculate_eta(pending, enrich_rate_per_min)
    
    # Get doc stats with rates
    doc_stats = get_doc_stats_with_eta(db)
    
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
        "eta": chunk_eta,
        "docs": doc_stats
    }


# ============================================================================
# Distributed Workers Registry API
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
    from ...services import servers as servers_service
    
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
