from src.db.session import get_db
from src.db.models import RawFile

def check_db():
    db = next(get_db())
    files = db.query(RawFile).all()
    print(f"Total files: {len(files)}")
    for f in files:
        print(f"ID: {f.id}, Path: {f.path}, SHA256: {f.sha256[:8]}..., Status: {f.status}")
        print(f"  Entries: {len(f.entries)}")
        for e in f.entries:
            print(f"    - Entry {e.entry_index}: {e.entry_text[:50]}...")
            print(f"      Title: {e.title}, Tags: {e.tags}, Status: {e.status}")
            print(f"      Search Vector: {e.search_vector is not None}")

if __name__ == "__main__":
    check_db()
