import logging
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.db.models import Entry
from src.llm_client import embed_text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def embed_entry(db: Session, entry: Entry):
    logger.info(f"Embedding entry {entry.id}...")
    
    # Combine title and text for embedding? Or just text?
    # Plan says "embed_text(text)".
    # Usually title + text is better.
    text_to_embed = f"{entry.title or ''}\n\n{entry.entry_text}"
    
    embedding = embed_text(text_to_embed)
    
    if embedding:
        entry.embedding = embedding
        db.commit()
        logger.info(f"Embedded entry {entry.id}")
    else:
        logger.error(f"Failed to embed entry {entry.id}")

def main():
    db = next(get_db())
    
    # Process entries without embedding
    entries = db.query(Entry).filter(Entry.embedding.is_(None)).limit(200).all()
    
    if not entries:
        logger.info("No entries needing embedding found.")
        return

    for entry in entries:
        embed_entry(db, entry)

if __name__ == "__main__":
    main()
