import time
import logging
import sys
import os
import json
import socket
import uuid
import atexit
import psutil

# Shared paths - must be set before logging config
if os.path.exists("/app/shared"):
    SHARED_DIR = "/app/shared"
else:
    # Local development fallback: backend/shared
    SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared")

STATE_FILE = os.path.join(SHARED_DIR, "worker_state.json")
LOG_FILE = os.path.join(SHARED_DIR, "worker.log")
PROGRESS_FILE = os.path.join(SHARED_DIR, "worker_progress.json")
WORKER_ID_FILE = os.path.join(SHARED_DIR, "worker_id.txt")

# Ensure shared directory exists
os.makedirs(SHARED_DIR, exist_ok=True)

# Configure root logger BEFORE imports so ALL modules inherit this config
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE)
    ],
    force=True  # Override any existing config from imported modules
)
logger = logging.getLogger("worker_loop")

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingest.ingest_files import main as ingest_main
from src.segment.segment_entries import main as segment_main
from src.enrich.enrich_entries import main as enrich_main
from src.enrich.enrich_docs import main as enrich_docs_main
from src.rag.embed_entries import main as embed_main
from src.rag.embed_docs import main as embed_docs_main
from src.db.session import SessionLocal
from src.db.settings import get_llm_config
from src.llm_client import set_default_client, ensure_models_available
from src.services import workers as workers_service

# Re-apply file handler to root logger AFTER imports (child modules may have altered config)
root_logger = logging.getLogger()
# Remove any duplicate handlers and ensure our file handler is attached
file_handler_exists = any(isinstance(h, logging.FileHandler) and h.baseFilename == LOG_FILE for h in root_logger.handlers)
if not file_handler_exists:
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(fh)

# ============================================================================
# Worker Registration and Heartbeat
# ============================================================================

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = 30

# Worker identification
WORKER_ID = None
WORKER_NAME = os.environ.get("WORKER_NAME", socket.gethostname())
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")


def get_or_create_worker_id() -> str:
    """Get persistent worker ID or create a new one."""
    global WORKER_ID
    if WORKER_ID:
        return WORKER_ID
    
    # Try to load from file (persist across restarts)
    if os.path.exists(WORKER_ID_FILE):
        try:
            with open(WORKER_ID_FILE, 'r') as f:
                WORKER_ID = f.read().strip()
                if WORKER_ID:
                    return WORKER_ID
        except Exception:
            pass
    
    # Generate new ID
    short_uuid = str(uuid.uuid4())[:8]
    WORKER_ID = f"{WORKER_NAME}-{short_uuid}"
    
    # Save for next restart
    try:
        with open(WORKER_ID_FILE, 'w') as f:
            f.write(WORKER_ID)
    except Exception as e:
        logger.warning(f"Failed to save worker ID: {e}")
    
    return WORKER_ID


def register_worker():
    """Register this worker with the database."""
    worker_id = get_or_create_worker_id()
    
    try:
        db = SessionLocal()
        worker = workers_service.register_worker(
            db,
            worker_id=worker_id,
            name=WORKER_NAME,
            ollama_url=OLLAMA_URL,
            config={
                "phases": ["ingest", "segment", "enrich", "enrich_docs", "embed", "embed_docs"]
            },
            managed=False  # Docker compose workers are considered external
        )
        db.close()
        logger.info(f"Registered as worker: {worker_id}")
        return worker
    except Exception as e:
        logger.warning(f"Failed to register worker: {e}")
        return None


def send_heartbeat(status: str = "active", current_phase: str = None, current_task: str = None):
    """Send heartbeat to the database."""
    worker_id = get_or_create_worker_id()
    
    try:
        # Collect stats
        stats = {
            "memory_mb": round(psutil.Process().memory_info().rss / 1024 / 1024, 1),
            "cpu_percent": psutil.Process().cpu_percent()
        }
        
        db = SessionLocal()
        workers_service.heartbeat(
            db,
            worker_id=worker_id,
            status=status,
            current_task=current_task,
            current_phase=current_phase,
            stats=stats
        )
        db.close()
    except Exception as e:
        logger.warning(f"Failed to send heartbeat: {e}")


def deregister_worker():
    """Deregister this worker (called on shutdown)."""
    worker_id = get_or_create_worker_id()
    
    try:
        db = SessionLocal()
        workers_service.deregister_worker(db, worker_id)
        db.close()
        logger.info(f"Deregistered worker: {worker_id}")
    except Exception as e:
        logger.warning(f"Failed to deregister worker: {e}")


# Register shutdown handler
atexit.register(deregister_worker)

def get_state():
    """Read the current worker state from file."""
    default_state = {
        "ingest": True,
        "segment": True,
        "enrich": True,
        "enrich_docs": True,  # Doc-level enrichment
        "embed": True,
        "embed_docs": True,   # Doc-level embedding
        "running": True
    }
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return {**default_state, **json.load(f)}
    except Exception:
        pass
    return default_state

def save_state(state):
    """Save the worker state to file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")

def update_progress(phase: str, current: int = None, total: int = None, status: str = "running"):
    """Update progress for a phase. Called between batch iterations."""
    try:
        progress = {}
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                progress = json.load(f)
        
        progress[phase] = {
            "current": current,
            "total": total,
            "status": status,  # running, stopping, stopped, idle
            "updated_at": time.time()
        }
        
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(progress, f)
    except Exception as e:
        logger.warning(f"Failed to update progress: {e}")

def check_phase_enabled(state: dict, phase: str) -> bool:
    """Check if a phase is still enabled. Used between iterations for responsive stopping."""
    # Re-read state to catch changes made via API
    current_state = get_state()
    return current_state.get(phase, True)

def run_pipeline():
    logger.info("Worker loop started.")
    
    # Register this worker with the database
    register_worker()
    
    # Initialize state file
    if not os.path.exists(STATE_FILE):
        save_state(get_state())
    
    last_ingest_time = 0
    INGEST_INTERVAL = 3600 # 1 hour
    
    # Refresh LLM config from database settings periodically
    last_config_refresh = 0
    CONFIG_REFRESH_INTERVAL = 60  # Refresh config every minute
    
    # Heartbeat tracking
    last_heartbeat_time = 0
    
    while True:
        state = get_state()
        current_time = time.time()
        
        # Send heartbeat periodically
        if current_time - last_heartbeat_time > HEARTBEAT_INTERVAL:
            if state.get("running", True):
                send_heartbeat(status="active")
            else:
                send_heartbeat(status="idle")
            last_heartbeat_time = current_time
        
        if not state.get("running", True):
            logger.info("Worker paused. Sleeping...")
            send_heartbeat(status="idle")
            time.sleep(5)
            continue
        
        # Refresh LLM client config from database settings
        if current_time - last_config_refresh > CONFIG_REFRESH_INTERVAL:
            try:
                db = SessionLocal()
                llm_config = get_llm_config(db)
                
                # Ensure required models are available (auto-pull if missing)
                if llm_config.get('provider') == 'ollama':
                    ensure_models_available(llm_config)
                
                set_default_client(llm_config)
                logger.info(f"Refreshed LLM config: provider={llm_config.get('provider')}, model={llm_config.get('model')}")
                db.close()
                last_config_refresh = current_time
            except Exception as e:
                logger.warning(f"Failed to refresh LLM config: {e}")
        try:
            # 1. Ingest
            # Only run if enabled AND enough time has passed
            if state.get("ingest", True):
                send_heartbeat(status="active", current_phase="ingest")
                current_time = time.time()
                if current_time - last_ingest_time > INGEST_INTERVAL:
                    logger.info("--- Starting Ingestion Phase ---")
                    ingest_main()
                    last_ingest_time = time.time()
                else:
                    # logger.debug("Skipping ingest (interval not reached)")
                    pass
            
            # 2. Segment
            if state.get("segment", True):
                send_heartbeat(status="active", current_phase="segment")
                logger.info("--- Starting Segmentation Phase ---")
                segment_main()
            
            # 3. Doc-level Enrichment (run before chunk enrichment)
            if state.get("enrich_docs", True):
                send_heartbeat(status="active", current_phase="enrich_docs")
                logger.info("--- Starting Doc Enrichment Phase ---")
                total_iterations = 5
                for i in range(total_iterations):  # 5 iterations x 20 batch = 100 docs/cycle
                    update_progress("enrich_docs", current=i+1, total=total_iterations, status="running")
                    enrich_docs_main()
                    if not check_phase_enabled(state, "enrich_docs"):
                        update_progress("enrich_docs", current=i+1, total=total_iterations, status="stopped")
                        logger.info("enrich_docs disabled mid-cycle, stopping early")
                        break
                else:
                    update_progress("enrich_docs", status="idle")
            
            # 4. Chunk Enrichment
            if state.get("enrich", True):
                send_heartbeat(status="active", current_phase="enrich")
                logger.info("--- Starting Chunk Enrichment Phase ---")
                total_iterations = 50
                for i in range(total_iterations):  # 50 iterations x 100 batch = 5000 entries/cycle
                    update_progress("enrich", current=i+1, total=total_iterations, status="running")
                    enrich_main()
                    if not check_phase_enabled(state, "enrich"):
                        update_progress("enrich", current=i+1, total=total_iterations, status="stopped")
                        logger.info("enrich disabled mid-cycle, stopping early")
                        break
                else:
                    update_progress("enrich", status="idle")
            
            # 5. Doc-level Embedding (fast, run before chunk embedding)
            if state.get("embed_docs", True):
                send_heartbeat(status="active", current_phase="embed_docs")
                logger.info("--- Starting Doc Embedding Phase ---")
                total_iterations = 10
                for i in range(total_iterations):  # 10 iterations x 50 batch = 500 docs/cycle
                    update_progress("embed_docs", current=i+1, total=total_iterations, status="running")
                    embed_docs_main()
                    if not check_phase_enabled(state, "embed_docs"):
                        update_progress("embed_docs", current=i+1, total=total_iterations, status="stopped")
                        logger.info("embed_docs disabled mid-cycle, stopping early")
                        break
                else:
                    update_progress("embed_docs", status="idle")
                
            # 6. Chunk Embedding
            if state.get("embed", True):
                send_heartbeat(status="active", current_phase="embed")
                logger.info("--- Starting Chunk Embedding Phase ---")
                total_iterations = 10
                for i in range(total_iterations):  # More embedding iterations
                    update_progress("embed", current=i+1, total=total_iterations, status="running")
                    embed_main()
                    if not check_phase_enabled(state, "embed"):
                        update_progress("embed", current=i+1, total=total_iterations, status="stopped")
                        logger.info("embed disabled mid-cycle, stopping early")
                        break
                else:
                    update_progress("embed", status="idle")
                
            logger.info("Cycle complete. Sleeping for 5 seconds...")
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            time.sleep(10)

if __name__ == "__main__":
    run_pipeline()
