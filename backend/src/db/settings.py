"""
Settings storage for Archive Brain.
Stores user-configurable settings in the database.
"""
import json
import logging
import os
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Text, DateTime, func
from src.db.models import Base

logger = logging.getLogger(__name__)


class Setting(Base):
    """Key-value settings storage."""
    __tablename__ = "settings"
    
    key = Column(String(255), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# Default settings
DEFAULT_SETTINGS = {
    # Setup wizard completion flag
    "setup_complete": False,
    # Indexing strategy: "fast_scan", "full_enrichment", or "custom"
    "indexing_mode": "fast_scan",
    # GPU VRAM in GB (null = auto-detect, 0 = CPU only)
    "gpu_vram_gb": None,
    "llm": {
        "provider": "ollama",  # ollama, openai, anthropic
        "ollama": {
            "url": "http://ollama:11434",
            "model": "dolphin-phi",
            "embedding_model": "nomic-embed-text",
            "vision_model": "llava"
        },
        "openai": {
            "api_key": "",
            "model": "gpt-4o-mini",
            "embedding_model": "text-embedding-3-small",
            "vision_model": "gpt-4o"
        },
        "anthropic": {
            "api_key": "",
            "model": "claude-3-haiku-20240307"
        }
    },
    "sources": {
        "include": [
            "/data/archive/docs",
            "/data/archive/story"
        ],
        "exclude": [
            "**/node_modules/**",
            "**/.git/**",
            "**/__pycache__/**",
            "**/*.tmp",
            "**/*.bak"
        ]
    },
    "extensions": [
        ".txt", ".md", ".html", ".pdf", ".docx",
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"
    ]
}


def get_setting(db: Session, key: str) -> Optional[Any]:
    """Get a setting value by key."""
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        try:
            return json.loads(setting.value)
        except json.JSONDecodeError:
            return setting.value
    # Return default if not set
    return DEFAULT_SETTINGS.get(key)


def set_setting(db: Session, key: str, value: Any) -> bool:
    """Set a setting value."""
    try:
        json_value = json.dumps(value) if not isinstance(value, str) else value
        setting = db.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = json_value
        else:
            setting = Setting(key=key, value=json_value)
            db.add(setting)
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save setting {key}: {e}")
        db.rollback()
        return False


def get_all_settings(db: Session) -> Dict[str, Any]:
    """Get all settings, merged with defaults."""
    settings = dict(DEFAULT_SETTINGS)
    
    stored = db.query(Setting).all()
    for s in stored:
        try:
            settings[s.key] = json.loads(s.value)
        except json.JSONDecodeError:
            settings[s.key] = s.value
    
    return settings


def get_llm_config(db: Session) -> Dict[str, Any]:
    """
    Get the active LLM configuration.
    
    Environment variables can override database settings:
    - OLLAMA_URL: Override the Ollama URL (for multi-worker setups)
    - OLLAMA_MODEL: Override the model name
    - OLLAMA_EMBEDDING_MODEL: Override the embedding model
    """
    llm_settings = get_setting(db, "llm") or DEFAULT_SETTINGS["llm"]
    provider = llm_settings.get("provider", "ollama")
    
    config = {
        "provider": provider,
        **llm_settings.get(provider, {})
    }
    
    # Allow environment variable overrides for worker flexibility
    if provider == "ollama":
        if os.environ.get("OLLAMA_URL"):
            config["url"] = os.environ["OLLAMA_URL"]
        if os.environ.get("OLLAMA_MODEL"):
            config["model"] = os.environ["OLLAMA_MODEL"]
        if os.environ.get("OLLAMA_EMBEDDING_MODEL"):
            config["embedding_model"] = os.environ["OLLAMA_EMBEDDING_MODEL"]
        if os.environ.get("OLLAMA_VISION_MODEL"):
            config["vision_model"] = os.environ["OLLAMA_VISION_MODEL"]
    
    return config


def get_source_folders(db: Session) -> Dict[str, List[str]]:
    """Get source folder configuration."""
    return get_setting(db, "sources") or DEFAULT_SETTINGS["sources"]


def add_source_folder(db: Session, path: str) -> bool:
    """Add a source folder to the include list."""
    sources = get_source_folders(db)
    if path not in sources["include"]:
        sources["include"].append(path)
        return set_setting(db, "sources", sources)
    return True


def remove_source_folder(db: Session, path: str) -> bool:
    """Remove a source folder from the include list."""
    sources = get_source_folders(db)
    if path in sources["include"]:
        sources["include"].remove(path)
        return set_setting(db, "sources", sources)
    return True


def add_exclude_pattern(db: Session, pattern: str) -> bool:
    """Add an exclude pattern."""
    sources = get_source_folders(db)
    if pattern not in sources["exclude"]:
        sources["exclude"].append(pattern)
        return set_setting(db, "sources", sources)
    return True


def remove_exclude_pattern(db: Session, pattern: str) -> bool:
    """Remove an exclude pattern."""
    sources = get_source_folders(db)
    if pattern in sources["exclude"]:
        sources["exclude"].remove(pattern)
        return set_setting(db, "sources", sources)
    return True
