from sqlalchemy import Column, Integer, String, Text, BigInteger, DateTime, ForeignKey, Index, func, Float
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TSVECTOR
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import text
from pgvector.sqlalchemy import Vector
import re

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
    
    # Series detection fields
    series_name = Column(Text)  # Detected series name
    series_number = Column(Integer)  # Part/chapter number in series
    series_total = Column(Integer)  # Total parts if known (e.g., "1 of 5")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    entries = relationship("Entry", back_populates="raw_file", cascade="all, delete-orphan")
    links = relationship("DocumentLink", back_populates="raw_file", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('raw_files_series_idx', 'series_name'),
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

    search_vector = Column(TSVECTOR)
    embedding = Column(Vector(768)) # Assuming 768 dimensions for standard models (e.g. nomic-embed-text, or llama3 hidden state)
    status = Column(Text, default='pending')  # 'pending', 'enriched', 'error'
    retry_count = Column(Integer, default=0)  # Track failed enrichment attempts

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    raw_file = relationship("RawFile", back_populates="entries")

    __table_args__ = (
        Index('entries_file_idx', 'file_id'),
        Index('entries_search_idx', 'search_vector', postgresql_using='gin'),
        Index('entries_content_hash_idx', 'content_hash'),
    )
