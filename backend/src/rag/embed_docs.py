"""
Document-level embedding pipeline.

This module embeds doc_summary into doc_embedding for:
1. Fast "similar documents" search (125k vectors vs 8M)
2. Two-stage retrieval (find docs first, then chunks)
"""

import logging
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.orm import Session
from sqlalchemy import text

from src.db.session import SessionLocal
from src.db.models import RawFile
from src.llm_client import embed_text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Batch size for doc embedding
DOC_EMBED_BATCH_SIZE = 50

# Parallel workers for embedding (embedding is fast, can parallelize)
DOC_EMBED_WORKERS = 4


def embed_single_doc(doc_id: int, doc_summary: str) -> tuple:
    """
    Embed a single document's summary.
    Returns (doc_id, embedding) or (doc_id, None) on failure.
    """
    try:
        if not doc_summary or len(doc_summary.strip()) < 10:
            return (doc_id, None)
        
        embedding = embed_text(doc_summary)
        return (doc_id, embedding)
        
    except Exception as e:
        logger.error(f"Error embedding doc {doc_id}: {e}")
        return (doc_id, None)


def embed_docs_batch(limit: int = DOC_EMBED_BATCH_SIZE) -> int:
    """
    Embed a batch of documents that have been enriched but not yet embedded.
    Returns the number of documents successfully embedded.
    """
    db = SessionLocal()
    embedded_count = 0
    
    try:
        # Get batch of enriched docs needing embedding
        docs = db.execute(text("""
            SELECT id, doc_summary
            FROM raw_files
            WHERE doc_status = 'enriched'
              AND doc_summary IS NOT NULL
              AND LENGTH(doc_summary) > 10
            ORDER BY id
            LIMIT :limit
            FOR UPDATE SKIP LOCKED
        """), {"limit": limit}).fetchall()
        
        if not docs:
            logger.info("No documents pending doc-level embedding")
            return 0
        
        logger.info(f"Embedding {len(docs)} documents...")
        
        # Parallel embedding
        with ThreadPoolExecutor(max_workers=DOC_EMBED_WORKERS) as executor:
            futures = {
                executor.submit(embed_single_doc, doc[0], doc[1]): doc[0]
                for doc in docs
            }
            
            for future in as_completed(futures):
                doc_id, embedding = future.result()
                
                if embedding:
                    # Update the database
                    db.execute(text("""
                        UPDATE raw_files 
                        SET doc_embedding = :embedding,
                            doc_status = 'embedded'
                        WHERE id = :id
                    """), {"embedding": str(embedding), "id": doc_id})
                    
                    embedded_count += 1
                else:
                    # Mark as error
                    db.execute(text("""
                        UPDATE raw_files 
                        SET doc_status = 'embed_error'
                        WHERE id = :id
                    """), {"id": doc_id})
                    logger.warning(f"Failed to embed doc {doc_id}")
        
        db.commit()
        logger.info(f"Batch complete: {embedded_count}/{len(docs)} docs embedded")
        return embedded_count
        
    except Exception as e:
        logger.error(f"Doc embedding batch error: {e}", exc_info=True)
        db.rollback()
        return 0
    finally:
        db.close()


def get_doc_embedding_stats() -> Dict[str, int]:
    """Get current doc embedding statistics."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE doc_status = 'pending') as pending,
                COUNT(*) FILTER (WHERE doc_status = 'enriched') as enriched,
                COUNT(*) FILTER (WHERE doc_status = 'embedded') as embedded,
                COUNT(*) FILTER (WHERE doc_status IN ('error', 'embed_error')) as error,
                COUNT(doc_embedding) as has_embedding
            FROM raw_files
        """)).fetchone()
        
        return {
            "total": result[0],
            "pending": result[1],
            "enriched": result[2],
            "embedded": result[3],
            "error": result[4],
            "has_embedding": result[5]
        }
    finally:
        db.close()


def main():
    """Main entry point for doc embedding."""
    stats = get_doc_embedding_stats()
    logger.info(f"Doc embedding stats: {stats}")
    
    embedded = embed_docs_batch()
    logger.info(f"Embedded {embedded} documents this batch")
    
    return embedded


if __name__ == "__main__":
    main()
