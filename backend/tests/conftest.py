"""
Pytest configuration and fixtures.
"""
import os
import pytest
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from src.db.models import Base
from src.db.session import get_db
from src.api.main import app


# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine():
    """Create a test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sample_file(db_session: Session):
    """Create a sample RawFile for testing."""
    from src.db.models import RawFile
    from datetime import datetime

    file = RawFile(
        path="/test/sample.txt",
        filename="sample.txt",
        extension=".txt",
        file_type="text",
        size_bytes=1024,
        sha256="test_hash_123",
        mtime=datetime.now(),
        status="ok"
    )
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    return file


@pytest.fixture(scope="function")
def sample_entry(db_session: Session, sample_file):
    """Create a sample Entry for testing."""
    from src.db.models import Entry

    entry = Entry(
        file_id=sample_file.id,
        title="Test Entry",
        entry_text="This is a test entry for testing search functionality.",
        category="test",
        author="Test Author",
        status="ok"
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.fixture(scope="session")
def mock_ollama_mode():
    """Enable mock Ollama mode for tests."""
    os.environ["OLLAMA_MOCK"] = "true"
    yield
    os.environ.pop("OLLAMA_MOCK", None)
