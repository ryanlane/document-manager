"""
Tests for file-related API endpoints with mocked database.
"""
import pytest
from unittest.mock import Mock, MagicMock
from fastapi.testclient import TestClient


@pytest.mark.api
def test_list_files_empty(client: TestClient, mock_db_session):
    """Test listing files when database is empty."""
    # The mock_db_session.query now returns fresh mocks with defaults:
    # count() = 0, all() = [], first() = None
    # No additional setup needed for empty results

    response = client.get("/files")
    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert "total" in data
    assert data["total"] == 0
    assert len(data["files"]) == 0


@pytest.mark.api
def test_list_files_with_data(client: TestClient, mock_db_session, sample_file):
    """Test listing files with sample data."""
    # Configure mock to return sample file
    def custom_query_mock(*args):
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = [sample_file]
        query_mock.count.return_value = 1
        return query_mock

    mock_db_session.query.side_effect = custom_query_mock

    response = client.get("/files")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["files"]) == 1
    assert data["files"][0]["filename"] == "sample.txt"


@pytest.mark.api
def test_list_files_pagination(client: TestClient, mock_db_session, sample_file):
    """Test file listing pagination."""
    # Mock query result
    mock_db_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [sample_file]
    mock_db_session.query.return_value.count.return_value = 1

    response = client.get("/files?skip=0&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "skip" in data
    assert "limit" in data
    assert data["skip"] == 0
    assert data["limit"] == 10


@pytest.mark.api
def test_list_files_sorting(client: TestClient, mock_db_session, sample_file):
    """Test file listing with different sort options."""
    # Mock query for each sort test
    mock_db_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [sample_file]
    mock_db_session.query.return_value.count.return_value = 1

    # Test sort by filename ascending
    response = client.get("/files?sort_by=filename&sort_dir=asc")
    assert response.status_code == 200

    # Test sort by size descending
    response = client.get("/files?sort_by=size&sort_dir=desc")
    assert response.status_code == 200


@pytest.mark.api
def test_get_file_by_id(client: TestClient, mock_db_session, sample_file):
    """Test getting a specific file by ID."""
    # Mock query to return sample file
    mock_db_session.query.return_value.filter.return_value.first.return_value = sample_file

    response = client.get(f"/files/{sample_file.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_file.id
    assert data["filename"] == "sample.txt"
    assert data["extension"] == ".txt"


@pytest.mark.api
def test_get_file_not_found(client: TestClient, mock_db_session):
    """Test getting a non-existent file."""
    # Mock query to return None
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    response = client.get("/api/files/99999")
    assert response.status_code == 404


@pytest.mark.api
def test_get_file_metadata(client: TestClient, mock_db_session, sample_file, sample_entry):
    """Test getting file metadata."""
    # Mock file query
    mock_db_session.query.return_value.filter.return_value.first.return_value = sample_file

    # Mock entries query
    mock_db_session.query.return_value.filter.return_value.all.return_value = [sample_entry]

    # Mock series query (return empty list)
    mock_db_session.query.return_value.filter.return_value.all.return_value = []

    response = client.get(f"/files/{sample_file.id}/metadata")
    assert response.status_code == 200
    data = response.json()
    assert "file_info" in data
    assert "processing" in data
    assert "enrichment" in data


@pytest.mark.api
def test_file_text_extraction_unsupported(client: TestClient, mock_db_session):
    """Test text extraction for unsupported file types."""
    # Create mock file with unsupported extension
    unsupported_file = Mock()
    unsupported_file.id = 999
    unsupported_file.path = "/test/sample.xyz"
    unsupported_file.filename = "sample.xyz"
    unsupported_file.extension = ".xyz"
    unsupported_file.file_type = "unknown"

    # Mock query to return unsupported file
    mock_db_session.query.return_value.filter.return_value.first.return_value = unsupported_file

    response = client.get(f"/files/{unsupported_file.id}/text")
    assert response.status_code == 400
    assert "not supported" in response.json()["detail"].lower()


@pytest.mark.api
def test_health_endpoint(client: TestClient):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
