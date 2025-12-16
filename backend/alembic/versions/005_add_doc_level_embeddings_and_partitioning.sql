-- Migration: Add doc-level embeddings, author normalization, and partitioning prep
-- Run with: docker exec document-manager-db-1 psql -U postgres -d archive_brain -f /app/alembic/versions/005_add_doc_level_embeddings_and_partitioning.sql

-- =============================================================================
-- 1. Add source, author_key, author_bucket to raw_files
-- =============================================================================

-- Source column (e.g., 'story', 'docs') - derived from path
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS source TEXT;

-- Normalized author key (lowercase, trimmed)
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS author_key TEXT;

-- Author bucket for future partitioning (hash % 128)
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS author_bucket INTEGER;

-- =============================================================================
-- 2. Add doc-level embeddings and summary to raw_files
-- =============================================================================

-- Document summary (LLM-generated, covers whole file)
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS doc_summary TEXT;

-- Document-level embedding (768 dims for nomic-embed-text)
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS doc_embedding vector(768);

-- Document-level search vector for hybrid search
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS doc_search_vector TSVECTOR;

-- Status for doc-level enrichment (separate from chunk enrichment)
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS doc_status TEXT DEFAULT 'pending';

-- =============================================================================
-- 3. Add author_key, author_bucket, source to entries
-- =============================================================================

-- Source column on entries (denormalized for fast filtering)
ALTER TABLE entries ADD COLUMN IF NOT EXISTS source TEXT;

-- Normalized author key 
ALTER TABLE entries ADD COLUMN IF NOT EXISTS author_key TEXT;

-- Author bucket for partitioning
ALTER TABLE entries ADD COLUMN IF NOT EXISTS author_bucket INTEGER;

-- =============================================================================
-- 4. Populate source, author_key, author_bucket from existing data
-- =============================================================================

-- Update raw_files: extract source from path (4th segment: /data/archive/{source}/...)
UPDATE raw_files 
SET source = SPLIT_PART(path, '/', 4)
WHERE source IS NULL;

-- Update raw_files: extract and normalize author_key from path
-- Path pattern: /data/archive/story/authors/{author}/...
UPDATE raw_files 
SET author_key = LOWER(TRIM(SPLIT_PART(path, '/', 6)))
WHERE author_key IS NULL 
  AND SPLIT_PART(path, '/', 5) = 'authors';

-- Update raw_files: compute author_bucket (hash % 128)
UPDATE raw_files 
SET author_bucket = ABS(HASHTEXT(COALESCE(author_key, ''))) % 128
WHERE author_bucket IS NULL;

-- Update entries: copy source, author_key, author_bucket from raw_files
UPDATE entries e
SET 
    source = rf.source,
    author_key = rf.author_key,
    author_bucket = rf.author_bucket
FROM raw_files rf
WHERE e.file_id = rf.id
  AND (e.source IS NULL OR e.author_key IS NULL);

-- =============================================================================
-- 5. Create indexes for performance
-- =============================================================================

-- Index on author_key for filtered queries (both tables)
CREATE INDEX CONCURRENTLY IF NOT EXISTS raw_files_author_key_idx ON raw_files (author_key);
CREATE INDEX CONCURRENTLY IF NOT EXISTS entries_author_key_idx ON entries (author_key);

-- Index on source for filtered queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS raw_files_source_idx ON raw_files (source);
CREATE INDEX CONCURRENTLY IF NOT EXISTS entries_source_idx ON entries (source);

-- Index on author_bucket for future partitioning
CREATE INDEX CONCURRENTLY IF NOT EXISTS entries_author_bucket_idx ON entries (author_bucket);

-- Partial index for worker queue (huge speedup for enrichment)
CREATE INDEX CONCURRENTLY IF NOT EXISTS entries_queue_idx 
ON entries (status, retry_count)
WHERE status IN ('pending', 'error');

-- GIN index on doc_search_vector for doc-level FTS
CREATE INDEX CONCURRENTLY IF NOT EXISTS raw_files_doc_search_idx 
ON raw_files USING gin (doc_search_vector);

-- =============================================================================
-- 6. Doc-level vector index (IVFFlat for 125k docs)
-- Only create once doc_embedding is populated
-- =============================================================================

-- Note: Run this AFTER populating doc_embeddings:
-- CREATE INDEX CONCURRENTLY raw_files_doc_embedding_ivfflat
-- ON raw_files USING ivfflat (doc_embedding vector_cosine_ops)
-- WITH (lists = 200);

-- =============================================================================
-- 7. Chunk-level vector index (IVFFlat)
-- Only create once you have 100k+ embeddings
-- =============================================================================

-- Note: Run this AFTER populating embeddings:
-- CREATE INDEX CONCURRENTLY entries_embedding_ivfflat
-- ON entries USING ivfflat (embedding vector_cosine_ops)
-- WITH (lists = 2000);

-- =============================================================================
-- Done! Verify with:
-- \d raw_files
-- \d entries
-- =============================================================================
