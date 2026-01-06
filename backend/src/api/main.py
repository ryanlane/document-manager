"""
Archive Brain API - Main Application
FastAPI application with modular routers for document management and RAG.
"""
import os
import json
import logging
from typing import Optional, Dict
from fastapi import FastAPI
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import all routers
from src.api.routers import (
    search_router,
    health_router,
    workers_router,
    jobs_router,
    servers_router,
    files_router,
    settings_router
)

# ============================================================================
# App Initialization
# ============================================================================

app = FastAPI(
    title="Archive Brain API",
    description="Local-first document archive with semantic search and RAG capabilities",
    version="1.0.0"
)


# ============================================================================
# Shared Directory Configuration
# ============================================================================

# Worker state file (shared with worker_loop.py)
if os.path.exists("/app/shared"):
    SHARED_DIR = "/app/shared"
else:
    # Local development fallback: backend/shared
    SHARED_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "shared"
    )

# Ensure shared directory exists
os.makedirs(SHARED_DIR, exist_ok=True)

THUMBNAIL_DIR = os.path.join(SHARED_DIR, "thumbnails")
WORKER_STATE_FILE = os.path.join(SHARED_DIR, "worker_state.json")
WORKER_LOG_FILE = os.path.join(SHARED_DIR, "worker.log")
WORKER_PROGRESS_FILE = os.path.join(SHARED_DIR, "worker_progress.json")
INGEST_PROGRESS_FILE = os.path.join(SHARED_DIR, "ingest_progress.json")
ENRICH_PROGRESS_FILE = os.path.join(SHARED_DIR, "enrich_progress.json")
EMBED_PROGRESS_FILE = os.path.join(SHARED_DIR, "embed_progress.json")


# ============================================================================
# Worker State Management (Shared with worker_loop.py)
# ============================================================================

class WorkerStateUpdate(BaseModel):
    ingest: Optional[bool] = None
    segment: Optional[bool] = None
    enrich: Optional[bool] = None
    enrich_docs: Optional[bool] = None
    embed: Optional[bool] = None
    embed_docs: Optional[bool] = None
    running: Optional[bool] = None


def get_worker_state() -> Dict:
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
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse worker state file: {e}")
    except IOError as e:
        logger.error(f"Failed to read worker state file: {e}")
    except Exception as e:
        logger.error(f"Unexpected error reading worker state: {e}")
    return default_state


def set_worker_state(updates: Dict) -> Dict:
    """Update worker state and return the new state."""
    state = get_worker_state()
    state.update(updates)
    try:
        with open(WORKER_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to write worker state file: {e}")
    except Exception as e:
        logger.error(f"Unexpected error writing worker state: {e}")
    return state


# Export for use in routers
__all__ = [
    'app',
    'SHARED_DIR',
    'THUMBNAIL_DIR',
    'WORKER_STATE_FILE',
    'WORKER_LOG_FILE',
    'WORKER_PROGRESS_FILE',
    'INGEST_PROGRESS_FILE',
    'ENRICH_PROGRESS_FILE',
    'EMBED_PROGRESS_FILE',
    'get_worker_state',
    'set_worker_state'
]


# ============================================================================
# Include Routers
# ============================================================================

app.include_router(health_router, tags=["health"])
app.include_router(search_router, tags=["search"])
app.include_router(files_router, tags=["files"])
app.include_router(settings_router, tags=["settings"])
app.include_router(workers_router, tags=["workers"])
app.include_router(jobs_router, tags=["jobs"])
app.include_router(servers_router, tags=["servers"])


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/")
async def root():
    """API root - returns basic information."""
    return {
        "name": "Archive Brain API",
        "version": "1.0.0",
        "description": "Local-first document archive with semantic search and RAG",
        "docs": "/docs",
        "health": "/health"
    }
