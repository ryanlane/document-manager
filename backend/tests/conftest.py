"""
Pytest configuration and fixtures using mocks.

This approach uses pytest-mock for database mocking, making tests:
- Fast (no real database)
- Isolated (no side effects)
- Simple (no Docker containers needed)
"""
import os
import pytest
from unittest.mock import Mock, MagicMock
from typing import Generator
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture(scope="session", autouse=True)
def mock_ollama_mode():
    """Enable mock Ollama mode for all tests."""
    os.environ["OLLAMA_MOCK"] = "true"
    yield
    os.environ.pop("OLLAMA_MOCK", None)


@pytest.fixture
def mock_db_session(mocker):
    """
    Create a mocked database session.

    This fixture provides a Mock object that behaves like a SQLAlchemy Session
    but doesn't require a real database connection.
    """
    mock_session = MagicMock()

    # Create a factory for query mocks to ensure fresh mocks for each query
    def create_query_mock():
        query_mock = MagicMock()
        # Set up chaining for common query operations
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.group_by.return_value = query_mock
        # Default returns
        query_mock.all.return_value = []
        query_mock.first.return_value = None
        query_mock.count.return_value = 0
        query_mock.scalar.return_value = 0
        return query_mock

    # Make query() return a fresh mock each time
    mock_session.query.side_effect = lambda *args: create_query_mock()

    # Mock common session methods
    mock_session.add = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.rollback = MagicMock()
    mock_session.refresh = MagicMock()
    mock_session.close = MagicMock()
    mock_session.execute = MagicMock()

    return mock_session


@pytest.fixture
def client(mock_db_session):
    """
    Create a test client with mocked database dependency.

    The database session is overridden to use our mock,
    so no real database is needed.
    """
    from src.db.session import get_db

    def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_file():
    """
    Create a sample RawFile mock object.

    Returns a Mock that behaves like a RawFile model instance.
    """
    from datetime import datetime

    file_mock = Mock()
    file_mock.id = 1
    file_mock.path = "/test/sample.txt"
    file_mock.filename = "sample.txt"
    file_mock.extension = ".txt"
    file_mock.file_type = "text"
    file_mock.size_bytes = 1024
    file_mock.sha256 = "test_hash_123"
    file_mock.mtime = datetime.now()
    file_mock.created_at = datetime.now()
    file_mock.status = "ok"
    file_mock.doc_status = "pending"
    file_mock.meta_json = None
    file_mock.doc_summary = None

    return file_mock


@pytest.fixture
def sample_entry(sample_file):
    """
    Create a sample Entry mock object.

    Returns a Mock that behaves like an Entry model instance.
    """
    entry_mock = Mock()
    entry_mock.id = 1
    entry_mock.file_id = sample_file.id
    entry_mock.title = "Test Entry"
    entry_mock.entry_text = "This is a test entry for testing search functionality."
    entry_mock.category = "test"
    entry_mock.author = "Test Author"
    entry_mock.status = "ok"
    entry_mock.summary = "Test summary"
    entry_mock.tags = ["test", "example"]

    return entry_mock


@pytest.fixture
def mock_setting():
    """Create a sample Setting mock object."""
    setting_mock = Mock()
    setting_mock.key = "test_key"
    setting_mock.value = '{"test": "value"}'
    return setting_mock


# Test markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests with mocked dependencies")
    config.addinivalue_line("markers", "integration: Integration tests (if any)")
    config.addinivalue_line("markers", "api: API endpoint tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")
