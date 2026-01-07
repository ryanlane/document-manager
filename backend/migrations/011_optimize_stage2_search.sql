-- Migration 011: Add composite index for Stage 2 search optimization
-- This index helps with the WHERE file_id = ANY(...) AND embedding IS NOT NULL query

-- Create composite index on file_id and embedding (for faster Stage 2 searches)
-- This allows the query planner to efficiently filter by file_id before doing vector search
CREATE INDEX CONCURRENTLY IF NOT EXISTS entries_file_id_embedding_not_null_idx 
    ON entries (file_id) 
    WHERE embedding IS NOT NULL;

-- Add comment
COMMENT ON INDEX entries_file_id_embedding_not_null_idx IS 
    'Composite partial index to optimize Stage 2 chunk search by file_id with embeddings';
