-- Migration 002: Add content_hash column for deduplication
-- Run this against your PostgreSQL database

-- Add content_hash column to entries table
ALTER TABLE entries ADD COLUMN IF NOT EXISTS content_hash TEXT;

-- Create index for fast duplicate lookups
CREATE INDEX IF NOT EXISTS entries_content_hash_idx ON entries(content_hash);

-- Backfill existing entries with their content hashes
-- Uses MD5 for PostgreSQL compatibility (SHA256 would require pgcrypto extension)
UPDATE entries 
SET content_hash = md5(lower(regexp_replace(text, '\s+', ' ', 'g')))
WHERE content_hash IS NULL;

-- Verify the migration
SELECT 
    COUNT(*) as total_entries,
    COUNT(content_hash) as entries_with_hash,
    COUNT(*) - COUNT(content_hash) as entries_without_hash
FROM entries;
