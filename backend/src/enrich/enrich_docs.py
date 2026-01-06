"""
Document-level enrichment pipeline.

This module generates doc_summary for raw_files, which is then used for:
1. Two-stage retrieval (query docs first, then chunks)
2. Doc-level embeddings (faster similarity search)
3. Inheriting metadata to chunks

The enrichment is lighter than chunk-level to be faster.
"""

import logging
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text, func

from src.db.session import SessionLocal
from src.db.models import RawFile
from src.db.settings import get_llm_config
from src.llm_client import LLMClient
from src.constants import DOC_ENRICH_BATCH_SIZE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Max chars to sample from document for summary
MAX_SAMPLE_CHARS = 8000  # ~2000 tokens

# Prompt template for doc-level enrichment (lighter than chunk-level)
DOC_ENRICHMENT_PROMPT = """You are a document archivist. Analyze this document excerpt and provide a brief summary.

Return ONLY a JSON object with these fields:
- doc_title: A concise title for this document (string)
- doc_summary: A 2-3 sentence summary of the document's content (string)
- doc_themes: Main themes or topics, max 5 (array of strings)
- doc_type: Type of content - "story", "article", "reference", "correspondence", "other" (string)
- content_warning: Any content warnings if applicable, else null (string or null)

Document filename: {filename}
Document path: {path}

Document excerpt:
{text}

Return ONLY the JSON object, no other text."""


def get_doc_sample(raw_file: RawFile) -> str:
    """
    Get a representative sample of the document for summarization.
    Takes from beginning, middle, and end if document is long.
    """
    text = raw_file.raw_text or ""
    
    if len(text) <= MAX_SAMPLE_CHARS:
        return text
    
    # Take beginning (40%), middle (20%), end (40%)
    begin_len = int(MAX_SAMPLE_CHARS * 0.4)
    middle_len = int(MAX_SAMPLE_CHARS * 0.2)
    end_len = int(MAX_SAMPLE_CHARS * 0.4)
    
    begin = text[:begin_len]
    
    middle_start = (len(text) - middle_len) // 2
    middle = text[middle_start:middle_start + middle_len]
    
    end = text[-end_len:]
    
    return f"{begin}\n\n[...]\n\n{middle}\n\n[...]\n\n{end}"


def enrich_single_doc(raw_file: RawFile, llm_client: LLMClient) -> Optional[Dict[str, Any]]:
    """
    Enrich a single document with doc-level metadata.
    Returns the enrichment result or None on failure.
    """
    try:
        # Get sample text
        sample = get_doc_sample(raw_file)
        
        if not sample or len(sample.strip()) < 50:
            logger.warning(f"Doc {raw_file.id} has insufficient text for enrichment")
            return None
        
        # Build prompt
        prompt = DOC_ENRICHMENT_PROMPT.format(
            filename=raw_file.filename,
            path=raw_file.path,
            text=sample
        )
        
        # Call LLM
        result = llm_client.generate_json(prompt)
        
        if result:
            return result
        else:
            logger.warning(f"LLM returned None for doc {raw_file.id}")
            return None
            
    except Exception as e:
        logger.error(f"Error enriching doc {raw_file.id}: {e}")
        return None


def enrich_docs_batch(limit: int = DOC_ENRICH_BATCH_SIZE) -> int:
    """
    Enrich a batch of documents that need doc-level enrichment.
    Returns the number of documents successfully enriched.
    """
    db = SessionLocal()
    
    # Get LLM config from database settings
    llm_config = get_llm_config(db)
    llm_client = LLMClient(llm_config)
    enriched_count = 0
    
    try:
        # Get batch of docs needing enrichment
        # Prioritize docs that have at least one enriched chunk
        docs = db.execute(text("""
            SELECT rf.id
            FROM raw_files rf
            WHERE rf.doc_status = 'pending'
              AND rf.raw_text IS NOT NULL
              AND LENGTH(rf.raw_text) > 100
            ORDER BY rf.id
            LIMIT :limit
            FOR UPDATE SKIP LOCKED
        """), {"limit": limit}).fetchall()
        
        doc_ids = [row[0] for row in docs]
        
        if not doc_ids:
            logger.info("No documents pending doc-level enrichment")
            return 0
        
        # Mark as 'enriching' immediately to prevent other workers from picking them up
        if doc_ids:
            db.execute(text("""
                UPDATE raw_files 
                SET doc_status = 'enriching'
                WHERE id = ANY(:ids)
            """), {"ids": doc_ids})
            db.commit()
        
        logger.info(f"Enriching {len(doc_ids)} documents...")
        
        for doc_id in doc_ids:
            raw_file = db.query(RawFile).filter(RawFile.id == doc_id).first()
            if not raw_file:
                continue
            
            result = enrich_single_doc(raw_file, llm_client)
            
            if result:
                # Build doc_summary from result
                title = result.get('doc_title', raw_file.filename)
                summary = result.get('doc_summary', '')
                themes = result.get('doc_themes', [])
                doc_type = result.get('doc_type', 'other')
                
                # Combine into searchable summary
                themes_str = ', '.join(themes) if themes else ''
                doc_summary = f"{title}. {summary}"
                if themes_str:
                    doc_summary += f" Themes: {themes_str}."
                
                # Update raw_file
                raw_file.doc_summary = doc_summary
                raw_file.doc_status = 'enriched'
                
                # Store full result in meta_json
                if raw_file.meta_json is None:
                    raw_file.meta_json = {}
                raw_file.meta_json['doc_enrichment'] = result
                
                # Update search vector
                db.execute(text("""
                    UPDATE raw_files 
                    SET doc_search_vector = to_tsvector('english', :summary)
                    WHERE id = :id
                """), {"summary": doc_summary, "id": doc_id})
                
                enriched_count += 1
                title_preview = (title or raw_file.filename or "Unknown")[:50]
                logger.info(f"Enriched doc {doc_id}: {title_preview}...")
            else:
                # Mark as error to avoid retrying immediately
                raw_file.doc_status = 'error'
                logger.warning(f"Failed to enrich doc {doc_id}")
            
            db.commit()
        
        logger.info(f"Batch complete: {enriched_count}/{len(doc_ids)} docs enriched")
        return enriched_count
        
    except Exception as e:
        logger.error(f"Doc enrichment batch error: {e}", exc_info=True)
        db.rollback()
        return 0
    finally:
        db.close()


def get_doc_enrichment_stats() -> Dict[str, int]:
    """Get current doc enrichment statistics."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE doc_status = 'pending') as pending,
                COUNT(*) FILTER (WHERE doc_status = 'enriching') as enriching,
                COUNT(*) FILTER (WHERE doc_status = 'enriched') as enriched,
                COUNT(*) FILTER (WHERE doc_status = 'embedded') as embedded,
                COUNT(*) FILTER (WHERE doc_status = 'error') as error
            FROM raw_files
        """)).fetchone()
        
        return {
            "total": result[0],
            "pending": result[1],
            "enriching": result[2],
            "enriched": result[3],
            "embedded": result[4],
            "error": result[5]
        }
    finally:
        db.close()


def main():
    """Main entry point for doc enrichment."""
    stats = get_doc_enrichment_stats()
    logger.info(f"Doc enrichment stats: {stats}")
    
    enriched = enrich_docs_batch()
    logger.info(f"Enriched {enriched} documents this batch")
    
    return enriched


if __name__ == "__main__":
    main()
