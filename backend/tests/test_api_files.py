"""
Tests for file-related API endpoints.
"""
import pytest
from fastapi.testclient import TestClient


def test_list_files_empty(client: TestClient):
    """Test listing files when database is empty."""
    response = client.get("/api/files")
    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert "total" in data
    assert data["total"] == 0
    assert len(data["files"]) == 0


def test_list_files_with_data(client: TestClient, sample_file):
    """Test listing files with sample data."""
    response = client.get("/api/files")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["files"]) == 1
    assert data["files"][0]["filename"] == "sample.txt"


def test_list_files_pagination(client: TestClient, sample_file):
    """Test file listing pagination."""
    response = client.get("/api/files?skip=0&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "skip" in data
    assert "limit" in data
    assert data["skip"] == 0
    assert data["limit"] == 10


def test_list_files_sorting(client: TestClient, sample_file):
    """Test file listing with different sort options."""
    # Test sort by filename ascending
    response = client.get("/api/files?sort_by=filename&sort_dir=asc")
    assert response.status_code == 200

    # Test sort by size descending
    response = client.get("/api/files?sort_by=size&sort_dir=desc")
    assert response.status_code == 200


def test_get_file_by_id(client: TestClient, sample_file):
    """Test getting a specific file by ID."""
    response = client.get(f"/api/files/{sample_file.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_file.id
    assert data["filename"] == "sample.txt"
    assert data["extension"] == ".txt"


def test_get_file_not_found(client: TestClient):
    """Test getting a non-existent file."""
    response = client.get("/api/files/99999")
    assert response.status_code == 404


def test_get_file_metadata(client: TestClient, sample_file):
    """Test getting file metadata."""
    response = client.get(f"/api/files/{sample_file.id}/metadata")
    assert response.status_code == 200
    data = response.json()
    assert "file_info" in data
    assert "processing" in data
    assert "enrichment" in data


def test_file_text_extraction_unsupported(client: TestClient, sample_file):
    """Test text extraction for unsupported file types."""
    # Create a file with unsupported extension
    from src.db.models import RawFile
    from datetime import datetime

    db = next(client.app.dependency_overrides[get_db]())
    unsupported_file = RawFile(
        path="/test/sample.xyz",
        filename="sample.xyz",
        extension=".xyz",
        file_type="unknown",
        size_bytes=100,
        sha256="test_hash_xyz",
        mtime=datetime.now()
    )
    db.add(unsupported_file)
    db.commit()

    response = client.get(f"/api/files/{unsupported_file.id}/text")
    assert response.status_code == 400
    assert "not supported" in response.json()["detail"].lower()
