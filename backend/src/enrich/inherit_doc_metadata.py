"""
Inherit doc-level metadata to chunk entries.

This reduces LLM calls by copying enriched doc-level data down to chunks:
- doc_summary -> entries.summary (for chunks without summary)
- Extract title from doc_summary -> entries.title (for chunks without title)
- Extract category from doc_summary -> entries.category (if null)

Run after doc enrichment to bootstrap chunk metadata.
"""
import logging
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def extract_title_from_summary(doc_summary: str) -> str | None:
    """
    Extract the document title from doc_summary.
    Doc summaries typically start with the title followed by a period.
    Example: "The Dragon Knight. A story about..." -> "The Dragon Knight"
    """
    if not doc_summary:
        return None
    
    # Try to get title before first period (if short enough)
    first_sentence = doc_summary.split('.')[0].strip()
    if len(first_sentence) > 5 and len(first_sentence) < 100:
        return first_sentence
    
    return None


def extract_category_from_summary(doc_summary: str) -> str | None:
    """
    Try to extract category from doc_summary.
    Look for patterns like "Themes: romance, adventure" or "A story about..."
    """
    if not doc_summary:
        return None
    
    summary_lower = doc_summary.lower()
    
    # Category patterns based on content
    if any(word in summary_lower for word in ['romance', 'love story', 'relationship']):
        return 'Romance'
    elif any(word in summary_lower for word in ['horror', 'terror', 'scary', 'frightening']):
        return 'Horror'
    elif any(word in summary_lower for word in ['science fiction', 'sci-fi', 'space', 'alien']):
        return 'Science Fiction'
    elif any(word in summary_lower for word in ['fantasy', 'magic', 'wizard', 'dragon']):
        return 'Fantasy'
    elif any(word in summary_lower for word in ['mystery', 'detective', 'crime']):
        return 'Mystery'
    elif any(word in summary_lower for word in ['adventure', 'journey', 'quest']):
        return 'Adventure'
    elif any(word in summary_lower for word in ['erotica', 'erotic', 'sexual']):
        return 'Erotica'
    
    return 'Story'  # Default


def inherit_doc_metadata_batch(db: Session, batch_size: int = 500) -> dict:
    """
    Inherit doc-level metadata to entries that are missing enrichment.
    
    For entries that:
    - Have no summary -> copy abbreviated doc_summary
    - Have no title -> extract title from doc_summary
    - Have no category -> extract category from doc_summary
    
    Returns stats dict.
    """
    # Find docs with summaries that have non-enriched entries
    sql = text("""
        WITH docs_with_summaries AS (
            SELECT id, doc_summary 
            FROM raw_files 
            WHERE doc_summary IS NOT NULL 
              AND LENGTH(doc_summary) > 30
        ),
        entries_needing_inheritance AS (
            SELECT e.id as entry_id, 
                   e.file_id,
                   d.doc_summary,
                   e.title IS NULL as needs_title,
                   e.summary IS NULL as needs_summary,
                   e.category IS NULL as needs_category
            FROM entries e
            JOIN docs_with_summaries d ON e.file_id = d.id
            WHERE (e.title IS NULL OR e.summary IS NULL OR e.category IS NULL)
              AND e.status = 'pending'
            LIMIT :batch_size
        )
        SELECT entry_id, file_id, doc_summary, needs_title, needs_summary, needs_category
        FROM entries_needing_inheritance
    """)
    
    results = db.execute(sql, {"batch_size": batch_size}).fetchall()
    
    if not results:
        return {"inherited": 0, "message": "No entries need inheritance"}
    
    updated_count = 0
    
    for row in results:
        entry_id = row[0]
        doc_summary = row[2]
        needs_title = row[3]
        needs_summary = row[4]
        needs_category = row[5]
        
        updates = []
        params = {"entry_id": entry_id}
        
        if needs_title:
            title = extract_title_from_summary(doc_summary)
            if title:
                updates.append("title = :title")
                params["title"] = title[:200]  # Limit length
        
        if needs_summary:
            # Use abbreviated doc summary for chunks
            chunk_summary = f"From: {doc_summary[:150]}..." if len(doc_summary) > 150 else f"From: {doc_summary}"
            updates.append("summary = :summary")
            params["summary"] = chunk_summary
        
        if needs_category:
            category = extract_category_from_summary(doc_summary)
            if category:
                updates.append("category = :category")
                params["category"] = category
        
        if updates:
            update_sql = text(f"UPDATE entries SET {', '.join(updates)} WHERE id = :entry_id")
            db.execute(update_sql, params)
            updated_count += 1
    
    db.commit()
    
    return {
        "inherited": updated_count,
        "batch_size": len(results),
        "message": f"Inherited metadata to {updated_count} entries"
    }


def get_inheritance_stats(db: Session) -> dict:
    """Get stats on entries that could benefit from inheritance."""
    sql = text("""
        SELECT 
            COUNT(*) as total_entries,
            COUNT(*) FILTER (WHERE e.title IS NULL AND rf.doc_summary IS NOT NULL) as can_inherit_title,
            COUNT(*) FILTER (WHERE e.summary IS NULL AND rf.doc_summary IS NOT NULL) as can_inherit_summary,
            COUNT(*) FILTER (WHERE e.category IS NULL AND rf.doc_summary IS NOT NULL) as can_inherit_category
        FROM entries e
        JOIN raw_files rf ON e.file_id = rf.id
        WHERE e.status = 'pending'
    """)
    
    result = db.execute(sql).fetchone()
    return {
        "total_pending_entries": result[0],
        "can_inherit_title": result[1],
        "can_inherit_summary": result[2],
        "can_inherit_category": result[3]
    }
