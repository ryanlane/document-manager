"""
Jobs API Router - Background task tracking

This router handles generic background job tracking, providing endpoints to:
- List and filter jobs
- Monitor active jobs
- Get job details
- Cancel and delete jobs
- Clean up old jobs
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...services import jobs as jobs_service


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """List jobs with optional filtering."""
    if active_only:
        jobs = jobs_service.get_active_jobs(db)
    else:
        jobs = jobs_service.list_jobs(
            db,
            job_type=job_type,
            status=status,
            limit=limit,
            include_completed=True
        )
    
    return {
        "jobs": [jobs_service.job_to_dict(j) for j in jobs],
        "count": len(jobs)
    }


@router.get("/active")
async def get_active_jobs(db: Session = Depends(get_db)):
    """Get all currently active (pending or running) jobs."""
    jobs = jobs_service.get_active_jobs(db)
    return {
        "jobs": [jobs_service.job_to_dict(j) for j in jobs],
        "count": len(jobs),
        "has_active": len(jobs) > 0
    }


@router.get("/recent")
async def get_recent_jobs(limit: int = 10, db: Session = Depends(get_db)):
    """Get recent jobs including completed ones."""
    jobs = jobs_service.get_recent_jobs(db, limit=limit)
    return {
        "jobs": [jobs_service.job_to_dict(j) for j in jobs],
        "count": len(jobs)
    }


@router.get("/{job_id}")
async def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get a specific job by ID."""
    try:
        uuid_id = UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    job = jobs_service.get_job(db, uuid_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return jobs_service.job_to_dict(job)


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel a pending or running job."""
    try:
        uuid_id = UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    job = jobs_service.get_job(db, uuid_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [jobs_service.JOB_STATUS_PENDING, jobs_service.JOB_STATUS_RUNNING]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel job with status: {job.status}")
    
    job = jobs_service.cancel_job(db, uuid_id)
    return jobs_service.job_to_dict(job)


@router.delete("/{job_id}")
async def delete_job(job_id: str, db: Session = Depends(get_db)):
    """Delete a completed/failed/cancelled job."""
    try:
        uuid_id = UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    job = jobs_service.get_job(db, uuid_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status in [jobs_service.JOB_STATUS_PENDING, jobs_service.JOB_STATUS_RUNNING]:
        raise HTTPException(status_code=400, detail="Cannot delete active job - cancel it first")
    
    db.delete(job)
    db.commit()
    return {"deleted": True, "id": job_id}


@router.post("/cleanup")
async def cleanup_old_jobs(days: int = 7, db: Session = Depends(get_db)):
    """Delete completed/failed jobs older than specified days."""
    count = jobs_service.cleanup_old_jobs(db, days=days)
    return {"deleted": count, "days": days}
