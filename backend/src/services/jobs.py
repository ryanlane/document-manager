"""
Jobs service for managing background operations.

Provides a unified interface for creating, updating, and querying jobs
that represent long-running background tasks like model pulls, folder scans, etc.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.db.models import Job


# Job type constants
JOB_TYPE_MODEL_PULL = 'model_pull'
JOB_TYPE_FOLDER_SCAN = 'folder_scan'
JOB_TYPE_CONFIG_IMPORT = 'config_import'
JOB_TYPE_VACUUM = 'vacuum'
JOB_TYPE_REINDEX = 'reindex'
JOB_TYPE_EMBED = 'embed'

# Job status constants
JOB_STATUS_PENDING = 'pending'
JOB_STATUS_RUNNING = 'running'
JOB_STATUS_COMPLETED = 'completed'
JOB_STATUS_FAILED = 'failed'
JOB_STATUS_CANCELLED = 'cancelled'


def create_job(
    db: Session,
    job_type: str,
    metadata: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None
) -> Job:
    """Create a new job entry."""
    job = Job(
        type=job_type,
        status=JOB_STATUS_PENDING,
        job_metadata=metadata or {},
        message=message
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: UUID) -> Optional[Job]:
    """Get a job by ID."""
    return db.query(Job).filter(Job.id == job_id).first()


def start_job(
    db: Session,
    job_id: UUID,
    message: Optional[str] = None
) -> Optional[Job]:
    """Mark a job as running."""
    job = get_job(db, job_id)
    if job:
        job.status = JOB_STATUS_RUNNING
        job.started_at = datetime.utcnow()
        if message:
            job.message = message
        db.commit()
        db.refresh(job)
    return job


def update_job_progress(
    db: Session,
    job_id: UUID,
    progress: int,
    message: Optional[str] = None,
    metadata_updates: Optional[Dict[str, Any]] = None
) -> Optional[Job]:
    """Update job progress (0-100)."""
    job = get_job(db, job_id)
    if job:
        job.progress = min(100, max(0, progress))
        if message:
            job.message = message
        if metadata_updates and job.job_metadata:
            job.job_metadata = {**job.job_metadata, **metadata_updates}
        elif metadata_updates:
            job.job_metadata = metadata_updates
        db.commit()
        db.refresh(job)
    return job


def complete_job(
    db: Session,
    job_id: UUID,
    message: Optional[str] = None,
    metadata_updates: Optional[Dict[str, Any]] = None
) -> Optional[Job]:
    """Mark a job as completed."""
    job = get_job(db, job_id)
    if job:
        job.status = JOB_STATUS_COMPLETED
        job.progress = 100
        job.completed_at = datetime.utcnow()
        if message:
            job.message = message
        if metadata_updates and job.job_metadata:
            job.job_metadata = {**job.job_metadata, **metadata_updates}
        elif metadata_updates:
            job.job_metadata = metadata_updates
        db.commit()
        db.refresh(job)
    return job


def fail_job(
    db: Session,
    job_id: UUID,
    error: str,
    message: Optional[str] = None
) -> Optional[Job]:
    """Mark a job as failed."""
    job = get_job(db, job_id)
    if job:
        job.status = JOB_STATUS_FAILED
        job.error = error
        job.completed_at = datetime.utcnow()
        if message:
            job.message = message
        db.commit()
        db.refresh(job)
    return job


def cancel_job(
    db: Session,
    job_id: UUID,
    message: Optional[str] = "Cancelled by user"
) -> Optional[Job]:
    """Mark a job as cancelled."""
    job = get_job(db, job_id)
    if job and job.status in [JOB_STATUS_PENDING, JOB_STATUS_RUNNING]:
        job.status = JOB_STATUS_CANCELLED
        job.message = message
        job.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
    return job


def list_jobs(
    db: Session,
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    include_completed: bool = True
) -> List[Job]:
    """List jobs with optional filtering."""
    query = db.query(Job)
    
    if job_type:
        query = query.filter(Job.type == job_type)
    
    if status:
        query = query.filter(Job.status == status)
    elif not include_completed:
        query = query.filter(Job.status.in_([JOB_STATUS_PENDING, JOB_STATUS_RUNNING]))
    
    return query.order_by(desc(Job.created_at)).limit(limit).all()


def get_active_jobs(db: Session) -> List[Job]:
    """Get all currently active (pending or running) jobs."""
    return db.query(Job).filter(
        Job.status.in_([JOB_STATUS_PENDING, JOB_STATUS_RUNNING])
    ).order_by(desc(Job.created_at)).all()


def get_recent_jobs(db: Session, limit: int = 10) -> List[Job]:
    """Get recent jobs including completed ones."""
    return db.query(Job).order_by(desc(Job.created_at)).limit(limit).all()


def cleanup_old_jobs(db: Session, days: int = 7) -> int:
    """Delete completed/failed jobs older than specified days."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    result = db.query(Job).filter(
        Job.status.in_([JOB_STATUS_COMPLETED, JOB_STATUS_FAILED, JOB_STATUS_CANCELLED]),
        Job.completed_at < cutoff
    ).delete(synchronize_session=False)
    
    db.commit()
    return result


def job_to_dict(job: Job) -> Dict[str, Any]:
    """Convert a Job model to a dictionary for API responses."""
    return {
        'id': str(job.id),
        'type': job.type,
        'status': job.status,
        'progress': job.progress,
        'message': job.message,
        'error': job.error,
        'metadata': job.job_metadata,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'updated_at': job.updated_at.isoformat() if job.updated_at else None
    }
