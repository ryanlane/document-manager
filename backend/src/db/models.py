from sqlalchemy import Column, Integer, String, Text, BigInteger, DateTime, ForeignKey, Index, func, Float, Boolean
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TSVECTOR, UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import text
from pgvector.sqlalchemy import Vector
import re
import uuid

from src.constants import EMBEDDING_DIMENSIONS, AUTHOR_BUCKET_COUNT

Base = declarative_base()


def detect_series_info(filename: str) -> dict:
    """
    Detect series information from filename patterns.
    Returns dict with series_name, series_number, series_part if found.
    
    Patterns detected:
    - "Story Name Chapter 5.txt" -> {series_name: "Story Name", series_number: 5}
    - "Story Name - Part 3.txt" -> {series_name: "Story Name", series_number: 3}
    - "Story 01.txt" -> {series_name: "Story", series_number: 1}
    - "Story_Name_Ch03.txt" -> {series_name: "Story Name", series_number: 3}
    - "Story (1 of 5).txt" -> {series_name: "Story", series_number: 1, series_total: 5}
    """
    # Remove extension
    name = re.sub(r'\.[^.]+$', '', filename)
    
    patterns = [
        # "Name - Part 5" or "Name - Chapter 5"
        (r'^(.+?)\s*[-_]\s*(?:part|chapter|ch|pt|ep|episode|book|vol|volume)\s*[#]?(\d+)', 
         lambda m: {'series_name': m.group(1).strip(), 'series_number': int(m.group(2))}),
        
        # "Name (1 of 5)" or "Name [Part 2 of 10]"
        (r'^(.+?)\s*[\[(](?:part\s*)?(\d+)\s*(?:of|/)\s*(\d+)[\])]',
         lambda m: {'series_name': m.group(1).strip(), 'series_number': int(m.group(2)), 'series_total': int(m.group(3))}),
        
        # "Name Chapter5" or "Name Ch05"
        (r'^(.+?)(?:chapter|ch|part|pt|ep|episode|book|vol|volume)\s*[#]?(\d+)',
         lambda m: {'series_name': m.group(1).strip(), 'series_number': int(m.group(2))}),
        
        # "Name_05" or "Name-05" or "Name 05" (at end)
        (r'^(.+?)[_\-\s](\d{2,})$',
         lambda m: {'series_name': m.group(1).replace('_', ' ').strip(), 'series_number': int(m.group(2))}),
        
        # "Name5" (single digit at end, only if name is long enough)
        (r'^(.{5,}?)(\d+)$',
         lambda m: {'series_name': m.group(1).strip(), 'series_number': int(m.group(2))}),
    ]
    
    for pattern, extractor in patterns:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            result = extractor(match)
            # Clean up series name
            if result.get('series_name'):
                result['series_name'] = re.sub(r'[-_]+$', '', result['series_name']).strip()
            return result
    
    return {}


class RawFile(Base):
    __tablename__ = 'raw_files'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    path = Column(Text, nullable=False)
    filename = Column(Text, nullable=False)
    extension = Column(Text, nullable=False)
    size_bytes = Column(BigInteger)
    mtime = Column(DateTime(timezone=True))
    sha256 = Column(Text, unique=True)
    raw_text = Column(Text, nullable=False)
    meta_json = Column(JSONB)
    status = Column(Text, default='ok')  # 'ok', 'extract_failed', 'skipped'
    
    # File type classification
    file_type = Column(Text, default='text')  # 'text', 'image', 'pdf', 'document'
    
    # Image/PDF specific fields
    thumbnail_path = Column(Text)  # Relative path to thumbnail image
    ocr_text = Column(Text)  # Text extracted via OCR (for images/scanned PDFs)
    vision_description = Column(Text)  # AI-generated description from vision model
    vision_model = Column(Text)  # Which vision model was used
    
    # Image metadata
    image_width = Column(BigInteger)
    image_height = Column(BigInteger)
    
    # Series detection fields
    series_name = Column(Text)  # Detected series name
    series_number = Column(Integer)  # Part/chapter number in series
    series_total = Column(Integer)  # Total parts if known (e.g., "1 of 5")
    
    # Source and author normalization (for partitioning/filtering)
    source = Column(Text)  # e.g., 'story', 'docs' - derived from path
    author_key = Column(Text)  # Normalized author (lowercase, trimmed)
    author_bucket = Column(Integer)  # hash(author_key) % AUTHOR_BUCKET_COUNT for partitioning
    
    # Document-level embeddings (for two-stage retrieval)
    doc_summary = Column(Text)  # LLM-generated summary of entire document
    doc_embedding = Column(Vector(EMBEDDING_DIMENSIONS))  # Document-level embedding
    doc_search_vector = Column(TSVECTOR)  # Document-level FTS
    doc_status = Column(Text, default='pending')  # 'pending', 'enriched', 'embedded'
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    entries = relationship("Entry", back_populates="raw_file", cascade="all, delete-orphan")
    links = relationship("DocumentLink", back_populates="raw_file", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('raw_files_series_idx', 'series_name'),
        Index('raw_files_file_type_idx', 'file_type'),
        Index('raw_files_author_key_idx', 'author_key'),
        Index('raw_files_source_idx', 'source'),
        Index('raw_files_doc_search_idx', 'doc_search_vector', postgresql_using='gin'),
    )


class DocumentLink(Base):
    """Stores extracted links/URLs from documents for relationship mapping."""
    __tablename__ = 'document_links'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    file_id = Column(BigInteger, ForeignKey('raw_files.id', ondelete='CASCADE'), nullable=False)
    url = Column(Text, nullable=False)
    link_text = Column(Text)  # The anchor text if available
    link_type = Column(Text)  # 'html_href', 'markdown', 'raw_url', 'email'
    domain = Column(Text)  # Extracted domain for grouping
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    raw_file = relationship("RawFile", back_populates="links")

    __table_args__ = (
        Index('document_links_file_idx', 'file_id'),
        Index('document_links_url_idx', 'url'),
        Index('document_links_domain_idx', 'domain'),
    )


class Entry(Base):
    __tablename__ = 'entries'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    file_id = Column(BigInteger, ForeignKey('raw_files.id', ondelete='CASCADE'), nullable=False)
    entry_index = Column(Integer, nullable=False)
    char_start = Column(Integer)
    char_end = Column(Integer)
    entry_text = Column(Text, nullable=False)
    content_hash = Column(Text)  # SHA256 hash of entry_text for deduplication

    title = Column(Text)
    author = Column(Text)
    category = Column(Text)  # Extracted from folder structure
    created_hint = Column(DateTime(timezone=True))
    tags = Column(ARRAY(Text))
    summary = Column(Text)
    extra_meta = Column(JSONB)
    
    # Source and author normalization (denormalized for fast filtering)
    source = Column(Text)  # e.g., 'story', 'docs' - copied from raw_file
    author_key = Column(Text)  # Normalized author (lowercase, trimmed)
    author_bucket = Column(Integer)  # hash(author_key) % AUTHOR_BUCKET_COUNT for partitioning

    search_vector = Column(TSVECTOR)
    embedding = Column(Vector(EMBEDDING_DIMENSIONS))  # Standard dimensions for models (e.g. nomic-embed-text)
    status = Column(Text, default='pending')  # 'pending', 'enriched', 'error'
    retry_count = Column(Integer, default=0)  # Track failed enrichment attempts

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    raw_file = relationship("RawFile", back_populates="entries")

    __table_args__ = (
        Index('entries_file_idx', 'file_id'),
        Index('entries_search_idx', 'search_vector', postgresql_using='gin'),
        Index('entries_content_hash_idx', 'content_hash'),
        Index('entries_author_key_idx', 'author_key'),
        Index('entries_source_idx', 'source'),
        Index('entries_author_bucket_idx', 'author_bucket'),
    )


class Job(Base):
    """
    Generic jobs table for tracking all background operations.
    Used for model pulls, folder scans, config imports, vacuums, etc.
    """
    __tablename__ = 'jobs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(Text, nullable=False)  # 'model_pull', 'folder_scan', 'config_import', 'vacuum', etc.
    status = Column(Text, default='pending')  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    progress = Column(Integer)  # 0-100 or NULL
    message = Column(Text)  # Current status message
    error = Column(Text)  # Error message if failed
    job_metadata = Column('metadata', JSONB)  # Type-specific data (model name, folder path, etc.)
    
    # Timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('jobs_type_idx', 'type'),
        Index('jobs_status_idx', 'status'),
        Index('jobs_created_at_idx', 'created_at'),
    )


class LLMProvider(Base):
    """
    Registry of LLM providers for distributed processing.
    Supports Ollama servers and cloud providers (OpenAI, Anthropic, etc.).
    Renamed from OllamaServer to reflect support for multiple providers.
    """
    __tablename__ = 'llm_providers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    url = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True)
    status = Column(Text, default='unknown')  # 'online', 'offline', 'error', 'unknown', 'unconfigured'
    status_message = Column(Text)  # Error message or status details
    last_health_check = Column(DateTime(timezone=True))
    gpu_info = Column(JSONB)  # Detected GPU info: {name, vram_total, vram_free}
    models_available = Column(JSONB)  # Cached list of installed models
    capabilities = Column(JSONB)  # {chat: bool, embedding: bool, vision: bool}
    priority = Column(Integer, default=0)  # Higher = preferred for task assignment
    
    # Cloud provider support (migration 009)
    provider_type = Column(Text, default='ollama')  # 'ollama', 'openai', 'anthropic', 'google'
    api_key = Column(Text)  # API key for cloud providers (encrypted at app layer recommended)
    base_url = Column(Text)  # Override URL (e.g., Azure OpenAI endpoints)
    default_model = Column(Text)  # Default model for this provider
    rate_limits = Column(JSONB)  # {requests_per_minute, tokens_per_minute, current_usage}
    usage_stats = Column(JSONB)  # {total_tokens, total_cost_usd, last_reset}
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship to workers
    workers = relationship("Worker", back_populates="llm_provider", cascade="all, delete-orphan")

    __table_args__ = (
        Index('llm_providers_status_idx', 'status'),
        Index('llm_providers_enabled_idx', 'enabled'),
        Index('llm_providers_provider_type_idx', 'provider_type'),
    )


class Worker(Base):
    """
    Registry of active workers for distributed processing.
    Workers self-register and send periodic heartbeats.
    """
    __tablename__ = 'workers'

    id = Column(Text, primary_key=True)  # UUID or hostname-based ID
    name = Column(Text, nullable=False)
    llm_provider_id = Column(Integer, ForeignKey('llm_providers.id', ondelete='SET NULL'))
    status = Column(Text, default='starting')  # 'starting', 'active', 'idle', 'stale', 'stopped'
    current_task = Column(Text)  # e.g., 'enriching doc #12345' or null
    current_phase = Column(Text)  # 'ingest', 'segment', 'enrich', 'embed', etc.
    stats = Column(JSONB)  # {docs_per_min, entries_per_min, uptime_seconds, memory_mb}
    managed = Column(Boolean, default=False)  # True if spawned by API, False if external
    
    last_heartbeat = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Worker configuration (what phases it handles)
    config = Column(JSONB)  # {phases: ['ingest', 'segment', 'enrich', 'embed'], batch_size: 100}

    # Real-time progress tracking for each phase
    progress = Column(JSONB)  # {phase_name: {current: int, total: int, status: str, updated_at: float}}
    
    # Scheduling support (migration 009)
    schedule_type = Column(Text, default='always_on')  # 'always_on', 'use_default', 'custom', 'always_off'
    schedule = Column(JSONB)  # {start_time, end_time, next_day, days, timezone}
    schedule_status = Column(Text)  # 'in_window', 'outside_window', 'paused_by_schedule'
    
    # Relationship to server
    llm_provider = relationship("LLMProvider", back_populates="workers")

    __table_args__ = (
        Index('workers_status_idx', 'status'),
        Index('workers_last_heartbeat_idx', 'last_heartbeat'),
        Index('workers_llm_provider_id_idx', 'llm_provider_id'),
    )
