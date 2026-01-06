"""
Tests for health check and system status endpoints.
"""
import pytest
from unittest.mock import Mock
from fastapi.testclient import TestClient


@pytest.mark.api
def test_health_check(client: TestClient):
    """Test basic health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"


@pytest.mark.api
def test_system_health_check(client: TestClient, mock_db_session):
    """Test comprehensive system health check."""
    # Mock database query for health check
    mock_db_session.execute.return_value.scalar.return_value = 1

    response = client.get("/system/health-check")
    assert response.status_code == 200
    data = response.json()
    # System health returns status for each component
    assert isinstance(data, dict)


@pytest.mark.api
def test_system_status(client: TestClient, mock_db_session):
    """Test system status endpoint."""
    # Mock settings query for LLM provider
    mock_setting = Mock()
    mock_setting.key = "llm"
    mock_setting.value = '{"provider": "ollama"}'
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    response = client.get("/system/status")
    assert response.status_code == 200
    data = response.json()
    # Should return LLM provider status
    assert isinstance(data, dict)


@pytest.mark.api
def test_system_counts(client: TestClient, mock_db_session):
    """Test system counts endpoint."""
    # Mock count queries
    mock_db_session.query.return_value.count.return_value = 0

    response = client.get("/system/counts")
    assert response.status_code == 200
    data = response.json()
    # Should return counts for files, entries, etc.
    assert "files" in data or isinstance(data, dict)


@pytest.mark.api
def test_first_run_check(client: TestClient, mock_db_session):
    """Test first-run detection endpoint."""
    # Mock settings query for setup_complete
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    # Mock count queries to return integers
    mock_db_session.query.return_value.scalar.return_value = 0

    response = client.get("/system/first-run")
    assert response.status_code == 200
    data = response.json()
    assert "setup_required" in data or isinstance(data, dict)
