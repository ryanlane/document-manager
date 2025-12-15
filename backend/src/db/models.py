from sqlalchemy import Column, Integer, String, Text, BigInteger, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TSVECTOR
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import text
from pgvector.sqlalchemy import Vector

Base = declarative_base()

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    entries = relationship("Entry", back_populates="raw_file", cascade="all, delete-orphan")

class Entry(Base):
    __tablename__ = 'entries'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    file_id = Column(BigInteger, ForeignKey('raw_files.id', ondelete='CASCADE'), nullable=False)
    entry_index = Column(Integer, nullable=False)
    char_start = Column(Integer)
    char_end = Column(Integer)
    entry_text = Column(Text, nullable=False)

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
    )
