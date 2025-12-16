import time
import logging
import sys
import os
import json

# Shared paths - must be set before logging config
if os.path.exists("/app/shared"):
    SHARED_DIR = "/app/shared"
else:
    # Local development fallback: backend/shared
    SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared")

STATE_FILE = os.path.join(SHARED_DIR, "worker_state.json")
LOG_FILE = os.path.join(SHARED_DIR, "worker.log")

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

# Re-apply file handler to root logger AFTER imports (child modules may have altered config)
root_logger = logging.getLogger()
# Remove any duplicate handlers and ensure our file handler is attached
file_handler_exists = any(isinstance(h, logging.FileHandler) and h.baseFilename == LOG_FILE for h in root_logger.handlers)
if not file_handler_exists:
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(fh)

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

def run_pipeline():
    logger.info("Worker loop started.")
    # Initialize state file
    if not os.path.exists(STATE_FILE):
        save_state(get_state())
    
    last_ingest_time = 0
    INGEST_INTERVAL = 3600 # 1 hour
    
    while True:
        state = get_state()
        
        if not state.get("running", True):
            logger.info("Worker paused. Sleeping...")
            time.sleep(5)
            continue
            
        try:
            # 1. Ingest
            # Only run if enabled AND enough time has passed
            if state.get("ingest", True):
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
                logger.info("--- Starting Segmentation Phase ---")
                segment_main()
            
            # 3. Doc-level Enrichment (run before chunk enrichment)
            if state.get("enrich_docs", True):
                logger.info("--- Starting Doc Enrichment Phase ---")
                for _ in range(10):  # 10 iterations x 20 batch = 200 docs/cycle
                    enrich_docs_main()
            
            # 4. Chunk Enrichment
            if state.get("enrich", True):
                logger.info("--- Starting Chunk Enrichment Phase ---")
                for _ in range(50):  # 50 iterations x 100 batch = 5000 entries/cycle
                    enrich_main()
            
            # 5. Doc-level Embedding (fast, run before chunk embedding)
            if state.get("embed_docs", True):
                logger.info("--- Starting Doc Embedding Phase ---")
                for _ in range(5):  # 5 iterations x 50 batch = 250 docs/cycle
                    embed_docs_main()
                
            # 6. Chunk Embedding
            if state.get("embed", True):
                logger.info("--- Starting Chunk Embedding Phase ---")
                for _ in range(10):  # More embedding iterations
                    embed_main()
                
            logger.info("Cycle complete. Sleeping for 5 seconds...")
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            time.sleep(10)

if __name__ == "__main__":
    run_pipeline()
