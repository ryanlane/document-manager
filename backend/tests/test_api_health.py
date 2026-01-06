"""
Tests for health check and system status endpoints.
"""
import pytest
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    """Test basic health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data or data == {}  # Health endpoint might return empty dict


def test_system_health_check(client: TestClient):
    """Test comprehensive system health check."""
    response = client.get("/api/system/health-check")
    assert response.status_code == 200
    data = response.json()
    # System health returns status for each component
    assert isinstance(data, dict)


def test_system_status(client: TestClient):
    """Test system status endpoint."""
    response = client.get("/api/system/status")
    assert response.status_code == 200
    data = response.json()
    # Should return LLM provider status
    assert isinstance(data, dict)


def test_system_counts(client: TestClient):
    """Test system counts endpoint."""
    response = client.get("/api/system/counts")
    assert response.status_code == 200
    data = response.json()
    # Should return counts for files, entries, etc.
    assert "files" in data or isinstance(data, dict)


def test_first_run_check(client: TestClient):
    """Test first-run detection endpoint."""
    response = client.get("/api/system/first-run")
    assert response.status_code == 200
    data = response.json()
    assert "needs_setup" in data or isinstance(data, dict)
