"""
Updated worker_loop.py functions for database-backed state management.
These replace the existing file-based functions with dual-write support.

Copy these functions into worker_loop.py to complete the migration.
"""

def get_state():
    """Read the current worker state from database (with file fallback)."""
    default_state = {
        "ingest": True,
        "segment": True,
        "enrich": True,
        "enrich_docs": True,
        "embed": True,
        "embed_docs": True,
        "running": True
    }

    # PRIMARY: Read from database
    try:
        from src.db.session import SessionLocal
        from src.services.worker_state import WorkerState

        with SessionLocal() as db:
            state_manager = WorkerState(get_or_create_worker_id(), db)
            config = state_manager.get_config()
            logger.debug("Read worker state from database")
            return {**default_state, **config}
    except Exception as e:
        logger.warning(f"Failed to read state from DB, trying file fallback: {e}")

    # FALLBACK: Read from file (transition period)
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                logger.debug("Read worker state from file (fallback)")
                return {**default_state, **json.load(f)}
    except Exception as e:
        logger.error(f"Failed to read state from file: {e}")

    logger.warning("Using default worker state")
    return default_state


def save_state(state):
    """Save the worker state to database (with file dual-write)."""
    # PRIMARY: Write to database
    try:
        from src.db.session import SessionLocal
        from src.services.worker_state import WorkerState

        with SessionLocal() as db:
            state_manager = WorkerState(get_or_create_worker_id(), db)
            state_manager.update_config(state)
            logger.debug("Saved worker state to database")
    except Exception as e:
        logger.error(f"Failed to save state to DB: {e}")

    # FALLBACK: Also write to file (transition period)
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
            logger.debug("Saved worker state to file (backup)")
    except Exception as e:
        logger.warning(f"Failed to save state to file: {e}")


def update_progress(phase: str, current: int = None, total: int = None, status: str = "running"):
    """Update progress for a phase (database with file dual-write)."""

    # PRIMARY: Write to database
    try:
        from src.db.session import SessionLocal
        from src.services.worker_state import WorkerState

        with SessionLocal() as db:
            state_manager = WorkerState(get_or_create_worker_id(), db)
            state_manager.update_progress(phase, current, total, status)
            # logger.debug(f"Updated progress for {phase}: {current}/{total}")
    except Exception as e:
        logger.error(f"Failed to update progress in DB: {e}")

    # FALLBACK: Also write to file (transition period)
    try:
        progress = {}
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                progress = json.load(f)

        progress[phase] = {
            "current": current,
            "total": total,
            "status": status,
            "updated_at": time.time()
        }

        with open(PROGRESS_FILE, 'w') as f:
            json.dump(progress, f)
    except Exception as e:
        logger.warning(f"Failed to update progress file: {e}")


def check_phase_enabled(state: dict, phase: str) -> bool:
    """Check if a phase is still enabled (reads from database)."""
    try:
        current_state = get_state()  # Now reads from DB with file fallback
        enabled = current_state.get(phase, True)
        return enabled
    except Exception as e:
        logger.error(f"Failed to check phase status: {e}")
        return True  # Default to enabled on error
