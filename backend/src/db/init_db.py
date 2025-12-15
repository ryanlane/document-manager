import time
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from src.db.session import engine
from src.db.models import Base
# Import Setting to ensure it's registered with Base
from src.db.settings import Setting

def init_db():
    print("Creating database tables...")
    # Simple retry logic for waiting for DB to be ready
    retries = 5
    while retries > 0:
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
            
            Base.metadata.create_all(bind=engine)
            print("Tables created successfully.")
            return
        except OperationalError as e:
            print(f"Database not ready yet, retrying in 2 seconds... ({e})")
            time.sleep(2)
            retries -= 1
    print("Could not connect to database.")

if __name__ == "__main__":
    init_db()
