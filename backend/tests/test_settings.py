"""
Tests for settings module with mocked database.
"""
import pytest
import json
from unittest.mock import Mock, MagicMock

from src.db.settings import (
    get_setting,
    set_setting,
    get_all_settings,
    get_llm_config,
    get_source_folders,
    DEFAULT_SETTINGS,
)


@pytest.mark.unit
def test_get_setting_returns_default(mock_db_session):
    """Test that get_setting returns default when not in database."""
    # Mock query to return None (setting not found)
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    result = get_setting(mock_db_session, "setup_complete")

    # Should return default value
    assert result is False


@pytest.mark.unit
def test_get_setting_returns_stored_value(mock_db_session, mock_setting):
    """Test that get_setting returns value from database."""
    # Mock setting exists in database
    mock_setting.key = "setup_complete"
    mock_setting.value = "true"
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_setting

    result = get_setting(mock_db_session, "setup_complete")

    # Should return parsed JSON value
    assert result is True


@pytest.mark.unit
def test_get_setting_handles_json_objects(mock_db_session, mock_setting):
    """Test that get_setting correctly parses JSON objects."""
    mock_setting.key = "llm"
    mock_setting.value = json.dumps({"provider": "ollama", "url": "http://test:11434"})
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_setting

    result = get_setting(mock_db_session, "llm")

    assert isinstance(result, dict)
    assert result["provider"] == "ollama"


@pytest.mark.unit
def test_get_setting_fallback_on_invalid_json(mock_db_session, mock_setting):
    """Test that invalid JSON returns the raw string."""
    mock_setting.value = "{invalid json}"
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_setting

    result = get_setting(mock_db_session, "test_key")

    # Should return raw string on JSON parse error
    assert result == "{invalid json}"


@pytest.mark.unit
def test_set_setting_creates_new(mock_db_session):
    """Test that set_setting creates a new setting."""
    # Mock: setting doesn't exist
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    result = set_setting(mock_db_session, "test_key", "test_value")

    assert result is True
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()


@pytest.mark.unit
def test_set_setting_updates_existing(mock_db_session, mock_setting):
    """Test that set_setting updates an existing setting."""
    # Mock: setting exists
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_setting

    result = set_setting(mock_db_session, "test_key", "new_value")

    assert result is True
    # Should not call add (updating existing)
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_called_once()


@pytest.mark.unit
def test_set_setting_handles_dict_values(mock_db_session):
    """Test that set_setting correctly serializes dictionary values."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    test_dict = {"key": "value", "nested": {"data": 123}}
    result = set_setting(mock_db_session, "test_key", test_dict)

    assert result is True
    mock_db_session.commit.assert_called_once()


@pytest.mark.unit
def test_set_setting_rollback_on_error(mock_db_session):
    """Test that set_setting rolls back on error."""
    mock_db_session.commit.side_effect = Exception("Database error")

    result = set_setting(mock_db_session, "test_key", "value")

    assert result is False
    mock_db_session.rollback.assert_called_once()


@pytest.mark.unit
def test_get_all_settings_returns_defaults(mock_db_session):
    """Test that get_all_settings returns defaults when DB is empty."""
    # Mock empty database
    mock_db_session.query.return_value.all.return_value = []

    result = get_all_settings(mock_db_session)

    assert isinstance(result, dict)
    assert "setup_complete" in result
    assert "llm" in result
    assert result["setup_complete"] == DEFAULT_SETTINGS["setup_complete"]


@pytest.mark.unit
def test_get_all_settings_merges_stored_values(mock_db_session, mock_setting):
    """Test that get_all_settings merges stored values with defaults."""
    # Mock one stored setting
    mock_setting.key = "setup_complete"
    mock_setting.value = "true"
    mock_db_session.query.return_value.all.return_value = [mock_setting]

    result = get_all_settings(mock_db_session)

    # Should have both defaults and stored value
    assert result["setup_complete"] is True  # From database
    assert "llm" in result  # From defaults


@pytest.mark.unit
def test_get_llm_config_returns_provider_config(mock_db_session):
    """Test that get_llm_config returns active provider configuration."""
    # Mock LLM settings
    llm_settings = DEFAULT_SETTINGS["llm"]
    mock_setting = Mock()
    mock_setting.value = json.dumps(llm_settings)
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    result = get_llm_config(mock_db_session)

    assert "provider" in result
    assert result["provider"] == "ollama"
    # Should include provider-specific config
    assert "url" in result
    assert "model" in result


@pytest.mark.unit
def test_get_source_folders_returns_config(mock_db_session):
    """Test that get_source_folders returns sources configuration."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    result = get_source_folders(mock_db_session)

    assert isinstance(result, dict)
    assert "include" in result
    assert "exclude" in result
    assert isinstance(result["include"], list)
    assert isinstance(result["exclude"], list)


@pytest.mark.unit
def test_type_safety_with_overloads():
    """
    Test that type hints work correctly (this is a compile-time check).

    Type checkers like mypy will verify the overloads provide correct types.
    """
    # This test documents expected types but can't enforce them at runtime
    # Use mypy to verify: mypy tests/test_settings.py

    # These should type-check correctly:
    # setup_complete: Optional[bool] = get_setting(db, "setup_complete")
    # llm_settings: Optional[LLMSettings] = get_setting(db, "llm")
    # sources: Optional[SourcesConfig] = get_setting(db, "sources")

    assert True  # Type checking happens at static analysis time
