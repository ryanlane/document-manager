from sqlalchemy import func
from src.db.session import get_db
from src.db.models import RawFile, Entry

def print_status():
    db = next(get_db())
    
    file_count = db.query(func.count(RawFile.id)).scalar()
    entry_count = db.query(func.count(Entry.id)).scalar()
    enriched_count = db.query(func.count(Entry.id)).filter(Entry.status == 'enriched').scalar()
    embedded_count = db.query(func.count(Entry.id)).filter(Entry.embedding.isnot(None)).scalar()
    
    print("-" * 30)
    print(f"Files Ingested:   {file_count}")
    print(f"Entries Segmented: {entry_count}")
    print(f"Entries Enriched:  {enriched_count}")
    print(f"Entries Embedded:  {embedded_count}")
    print("-" * 30)

if __name__ == "__main__":
    print_status()
