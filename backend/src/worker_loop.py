import time
import logging
import sys
import os

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingest.ingest_files import main as ingest_main
from src.segment.segment_entries import main as segment_main
from src.enrich.enrich_entries import main as enrich_main
from src.rag.embed_entries import main as embed_main

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("worker_loop")

def run_pipeline():
    logger.info("Worker loop started.")
    while True:
        try:
            # 1. Ingest
            logger.info("--- Starting Ingestion Phase ---")
            ingest_main()
            
            # 2. Segment
            logger.info("--- Starting Segmentation Phase ---")
            segment_main()
            
            # 3. Enrich
            logger.info("--- Starting Enrichment Phase ---")
            # Run multiple batches to make progress
            # enrich_main processes 10 entries
            for _ in range(5): 
                enrich_main()
                
            # 4. Embed
            logger.info("--- Starting Embedding Phase ---")
            # embed_main processes 50 entries
            for _ in range(5):
                embed_main()
                
            logger.info("Cycle complete. Sleeping for 5 seconds...")
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            time.sleep(10)

if __name__ == "__main__":
    run_pipeline()
