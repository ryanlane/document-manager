"""
Shared utilities and constants for API routers.
"""
import os
import json
import logging

logger = logging.getLogger(__name__)

# Shared directory paths (shared with worker_loop.py)
if os.path.exists("/app/shared"):
    SHARED_DIR = "/app/shared"
else:
    # Local development fallback: backend/shared
    SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "shared")

# Ensure shared directory exists
os.makedirs(SHARED_DIR, exist_ok=True)

THUMBNAIL_DIR = os.path.join(SHARED_DIR, "thumbnails")
WORKER_STATE_FILE = os.path.join(SHARED_DIR, "worker_state.json")
WORKER_LOG_FILE = os.path.join(SHARED_DIR, "worker.log")
WORKER_PROGRESS_FILE = os.path.join(SHARED_DIR, "worker_progress.json")
INGEST_PROGRESS_FILE = os.path.join(SHARED_DIR, "ingest_progress.json")
ENRICH_PROGRESS_FILE = os.path.join(SHARED_DIR, "enrich_progress.json")
EMBED_PROGRESS_FILE = os.path.join(SHARED_DIR, "embed_progress.json")


def get_worker_state():
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


def save_worker_state(state):
    """Save the worker state."""
    try:
        with open(WORKER_STATE_FILE, 'w') as f:
            json.dump(state, f)
        return True
    except IOError as e:
        logger.error(f"Failed to write worker state file: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error writing worker state: {e}")
        return False


def calculate_eta(pending_count: int, rate_per_min: float) -> dict:
    """Calculate ETA with friendly time string."""
    if rate_per_min <= 0 or pending_count <= 0:
        return {
            "pending_count": pending_count,
            "eta_minutes": None,
            "eta_hours": None,
            "eta_days": None,
            "eta_string": "Calculating..." if pending_count > 0 else "Complete",
            "rate_per_min": rate_per_min
        }
    
    eta_minutes = pending_count / rate_per_min
    eta_hours = eta_minutes / 60
    eta_days = eta_hours / 24
    
    # Format friendly ETA string
    eta_str = format_friendly_time(eta_minutes)
    
    return {
        "pending_count": pending_count,
        "eta_minutes": round(eta_minutes, 0),
        "eta_hours": round(eta_hours, 1),
        "eta_days": round(eta_days, 1),
        "eta_string": eta_str,
        "rate_per_min": round(rate_per_min, 2)
    }


def format_friendly_time(minutes: float) -> str:
    """Format minutes into a friendly human-readable string."""
    if minutes is None or minutes <= 0:
        return "Complete"
    
    if minutes < 1:
        return "< 1 minute"
    elif minutes < 60:
        return f"{int(minutes)} minute{'s' if minutes != 1 else ''}"
    elif minutes < 60 * 24:
        hours = minutes / 60
        remaining_mins = int(minutes % 60)
        if remaining_mins > 0 and hours < 10:
            return f"{int(hours)}h {remaining_mins}m"
        return f"{hours:.1f} hours"
    elif minutes < 60 * 24 * 7:
        days = minutes / (60 * 24)
        remaining_hours = int((minutes % (60 * 24)) / 60)
        if remaining_hours > 0 and days < 3:
            return f"{int(days)}d {remaining_hours}h"
        return f"{days:.1f} days"
    elif minutes < 60 * 24 * 30:
        weeks = minutes / (60 * 24 * 7)
        return f"{weeks:.1f} weeks"
    elif minutes < 60 * 24 * 365:
        months = minutes / (60 * 24 * 30)
        return f"{months:.1f} months"
    else:
        years = minutes / (60 * 24 * 365)
        return f"{years:.1f} years"


# Known model families for capability detection
EMBEDDING_FAMILIES = {'nomic-bert', 'bert', 'e5', 'bge', 'gte', 'all-minilm'}
VISION_FAMILIES = {'clip', 'llava', 'bakllava', 'moondream'}
EMBEDDING_KEYWORDS = {'embed', 'embedding', 'e5', 'bge', 'gte', 'minilm'}
VISION_KEYWORDS = {'llava', 'vision', 'bakllava', 'moondream'}


def detect_model_capabilities(model_info: dict) -> dict:
    """Detect what capabilities a model has based on its families and name."""
    name = model_info.get("name", "").lower()
    families = set(f.lower() for f in model_info.get("details", {}).get("families", []))
    
    # Check for embedding capability
    is_embedding = bool(families & EMBEDDING_FAMILIES) or any(kw in name for kw in EMBEDDING_KEYWORDS)
    
    # Check for vision capability
    is_vision = bool(families & VISION_FAMILIES) or any(kw in name for kw in VISION_KEYWORDS)
    
    # Chat models are anything that's not purely an embedding model
    is_chat = not is_embedding or is_vision
    
    return {
        "chat": is_chat,
        "embedding": is_embedding,
        "vision": is_vision
    }
