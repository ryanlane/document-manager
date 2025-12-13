import time
import logging
import sys
import os
import json

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingest.ingest_files import main as ingest_main
from src.segment.segment_entries import main as segment_main
from src.enrich.enrich_entries import main as enrich_main
from src.rag.embed_entries import main as embed_main

# Shared paths
SHARED_DIR = "/app/shared"
STATE_FILE = os.path.join(SHARED_DIR, "worker_state.json")
LOG_FILE = os.path.join(SHARED_DIR, "worker.log")

# Ensure shared directory exists
os.makedirs(SHARED_DIR, exist_ok=True)

# Configure root logger so ALL modules write to both stdout and file
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE)
    ]
)
logger = logging.getLogger("worker_loop")

def get_state():
    """Read the current worker state from file."""
    default_state = {
        "ingest": True,
        "segment": True,
        "enrich": True,
        "embed": True,
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
    
    while True:
        state = get_state()
        
        if not state.get("running", True):
            logger.info("Worker paused. Sleeping...")
            time.sleep(5)
            continue
            
        try:
            # 1. Ingest
            if state.get("ingest", True):
                logger.info("--- Starting Ingestion Phase ---")
                ingest_main()
            
            # 2. Segment
            if state.get("segment", True):
                logger.info("--- Starting Segmentation Phase ---")
                segment_main()
            
            # 3. Enrich
            if state.get("enrich", True):
                logger.info("--- Starting Enrichment Phase ---")
                for _ in range(5): 
                    enrich_main()
                
            # 4. Embed
            if state.get("embed", True):
                logger.info("--- Starting Embedding Phase ---")
                for _ in range(5):
                    embed_main()
                
            logger.info("Cycle complete. Sleeping for 5 seconds...")
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            time.sleep(10)

if __name__ == "__main__":
    run_pipeline()
