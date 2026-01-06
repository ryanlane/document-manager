"""
Worker State Management Service

Database-backed worker state management replacing file-based JSON storage.
Provides ACID-compliant state updates with support for multiple workers.
"""

import logging
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session
from src.db.models import Worker

logger = logging.getLogger(__name__)


class WorkerState:
    """Database-backed worker state management."""

    def __init__(self, worker_id: str, db: Session):
        """
        Initialize worker state manager.

        Args:
            worker_id: Unique worker identifier
            db: Database session
        """
        self.worker_id = worker_id
        self.db = db

    def _get_worker(self) -> Optional[Worker]:
        """Get worker from database."""
        return self.db.query(Worker).filter(Worker.id == self.worker_id).first()

    def _ensure_worker_exists(self) -> Worker:
        """Ensure worker exists in database, create if needed."""
        worker = self._get_worker()
        if not worker:
            worker = Worker(
                id=self.worker_id,
                name=self.worker_id,
                status='starting',
                config={"phases": self._default_config()},
                progress={}
            )
            self.db.add(worker)
            self.db.commit()
            logger.info(f"Created new worker record: {self.worker_id}")
        return worker

    def _default_config(self) -> Dict[str, bool]:
        """Get default phase configuration."""
        return {
            "ingest": True,
            "segment": True,
            "enrich": True,
            "enrich_docs": True,
            "embed": True,
            "embed_docs": True,
            "running": True
        }

    def get_config(self) -> Dict[str, bool]:
        """
        Get worker phase configuration (enable/disable flags).

        Returns:
            Dict mapping phase names to boolean enabled/disabled state
        """
        worker = self._get_worker()
        if not worker or not worker.config:
            return self._default_config()

        # Support both old format (list) and new format (dict)
        config = worker.config
        if isinstance(config.get("phases"), list):
            # Old format: {phases: ['ingest', 'segment', ...]}
            # Convert to new format
            phases = {phase: True for phase in config["phases"]}
            return {**self._default_config(), **phases}
        elif isinstance(config.get("phases"), dict):
            # New format: {phases: {ingest: true, segment: true, ...}}
            return {**self._default_config(), **config["phases"]}
        else:
            return self._default_config()

    def update_config(self, updates: Dict[str, bool]):
        """
        Update phase configuration.

        Args:
            updates: Dict of phase name -> enabled/disabled updates

        Example:
            update_config({"ingest": False, "enrich": True})
        """
        worker = self._ensure_worker_exists()

        config = worker.config or {}
        phases = config.get("phases", self._default_config())

        # Ensure phases is a dict
        if isinstance(phases, list):
            phases = {phase: True for phase in phases}

        # Apply updates
        phases.update(updates)
        config["phases"] = phases

        worker.config = config
        worker.last_heartbeat = datetime.utcnow()
        self.db.commit()

        logger.debug(f"Updated worker config: {updates}")

    def update_progress(
        self,
        phase: str,
        current: Optional[int] = None,
        total: Optional[int] = None,
        status: str = "running"
    ):
        """
        Update progress for a phase.

        Args:
            phase: Phase name ('ingest', 'segment', 'enrich', 'embed', etc.)
            current: Current item count (optional)
            total: Total item count (optional)
            status: Status string ('running', 'stopping', 'stopped', 'idle')
        """
        worker = self._ensure_worker_exists()

        progress = worker.progress or {}
        progress[phase] = {
            "current": current,
            "total": total,
            "status": status,
            "updated_at": datetime.utcnow().timestamp()
        }

        worker.progress = progress
        worker.current_phase = phase
        worker.last_heartbeat = datetime.utcnow()
        worker.status = 'active' if status == 'running' else status

        self.db.commit()

    def get_progress(self) -> Dict:
        """
        Get current progress for all phases.

        Returns:
            Dict mapping phase names to progress info:
            {
                'ingest': {current: 50, total: 100, status: 'running', updated_at: 1704470400.0},
                'enrich': {current: 25, total: 75, status: 'running', updated_at: 1704470405.0}
            }
        """
        worker = self._get_worker()
        return worker.progress if worker and worker.progress else {}

    def clear_progress(self, phase: Optional[str] = None):
        """
        Clear progress for a phase or all phases.

        Args:
            phase: Phase name to clear, or None to clear all
        """
        worker = self._get_worker()
        if not worker:
            return

        if phase:
            # Clear specific phase
            progress = worker.progress or {}
            progress.pop(phase, None)
            worker.progress = progress
        else:
            # Clear all progress
            worker.progress = {}

        self.db.commit()

    def update_stats(self, stats: Dict):
        """
        Update worker statistics.

        Args:
            stats: Dict with performance metrics:
                   {docs_per_min: 12.5, entries_per_min: 45.2, memory_mb: 512}
        """
        worker = self._ensure_worker_exists()
        worker.stats = stats
        worker.last_heartbeat = datetime.utcnow()
        self.db.commit()

    def get_stats(self) -> Dict:
        """Get current worker statistics."""
        worker = self._get_worker()
        return worker.stats if worker and worker.stats else {}

    def set_status(self, status: str):
        """
        Set worker status.

        Args:
            status: One of 'starting', 'active', 'idle', 'stopped'
        """
        worker = self._ensure_worker_exists()
        worker.status = status
        worker.last_heartbeat = datetime.utcnow()
        self.db.commit()

    def heartbeat(self):
        """Update last heartbeat timestamp."""
        worker = self._ensure_worker_exists()
        worker.last_heartbeat = datetime.utcnow()
        self.db.commit()


# Convenience functions for single-worker scenarios
def get_primary_worker_state(db: Session) -> Optional[WorkerState]:
    """
    Get the primary (non-managed) worker state.

    Useful for single-worker deployments where there's one main worker process.

    Args:
        db: Database session

    Returns:
        WorkerState instance for the primary worker, or None if no workers exist
    """
    worker = db.query(Worker).filter(Worker.managed == False).first()
    if worker:
        return WorkerState(worker.id, db)
    return None


def get_or_create_primary_worker(db: Session, worker_id: str) -> WorkerState:
    """
    Get or create the primary worker.

    Args:
        db: Database session
        worker_id: Worker identifier

    Returns:
        WorkerState instance
    """
    return WorkerState(worker_id, db)
