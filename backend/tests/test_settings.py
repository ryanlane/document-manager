"""
Tests for settings module with type safety.
"""
import pytest
from sqlalchemy.orm import Session

from src.db.settings import (
    get_setting,
    set_setting,
    get_all_settings,
    get_llm_config,
    get_source_folders,
    LLMSettings,
    SourcesConfig,
)


def test_get_setting_default(db_session: Session):
    """Test getting a setting returns default value."""
    setup_complete = get_setting(db_session, "setup_complete")
    assert setup_complete is False  # Default value


def test_get_setting_typed(db_session: Session):
    """Test that get_setting returns properly typed values."""
    # Type checkers should infer bool
    setup_complete = get_setting(db_session, "setup_complete")
    assert isinstance(setup_complete, bool)

    # Type checkers should infer str
    indexing_mode = get_setting(db_session, "indexing_mode")
    assert isinstance(indexing_mode, str)

    # Type checkers should infer dict
    llm_settings = get_setting(db_session, "llm")
    assert isinstance(llm_settings, dict)


def test_set_and_get_setting(db_session: Session):
    """Test setting and retrieving a value."""
    # Set a boolean
    assert set_setting(db_session, "setup_complete", True)
    value = get_setting(db_session, "setup_complete")
    assert value is True

    # Set a string
    assert set_setting(db_session, "indexing_mode", "full_enrichment")
    value = get_setting(db_session, "indexing_mode")
    assert value == "full_enrichment"


def test_get_all_settings(db_session: Session):
    """Test getting all settings returns merged defaults."""
    settings = get_all_settings(db_session)
    assert isinstance(settings, dict)
    assert "setup_complete" in settings
    assert "llm" in settings
    assert "sources" in settings


def test_get_llm_config(db_session: Session):
    """Test getting LLM configuration."""
    config = get_llm_config(db_session)
    assert isinstance(config, dict)
    assert "provider" in config

    # Should have provider-specific fields
    if config["provider"] == "ollama":
        assert "url" in config
        assert "model" in config


def test_get_source_folders(db_session: Session):
    """Test getting source folder configuration."""
    sources = get_source_folders(db_session)
    assert isinstance(sources, dict)
    assert "include" in sources
    assert "exclude" in sources
    assert isinstance(sources["include"], list)
    assert isinstance(sources["exclude"], list)


def test_setting_persistence(db_session: Session):
    """Test that settings persist across queries."""
    # Set a value
    test_value = {"test": "data", "nested": {"key": "value"}}
    assert set_setting(db_session, "test_key", test_value)

    # Retrieve in a new query
    retrieved = get_setting(db_session, "test_key")
    assert retrieved == test_value


def test_invalid_json_fallback(db_session: Session):
    """Test that invalid JSON falls back to string value."""
    from src.db.settings import Setting

    # Manually create setting with invalid JSON
    setting = Setting(key="bad_json", value="{invalid json}")
    db_session.add(setting)
    db_session.commit()

    # Should return the string value
    value = get_setting(db_session, "bad_json")
    assert value == "{invalid json}"
