-- Migration 004: Add series detection columns and quality scoring support
-- Run this against your PostgreSQL database

-- Add series columns to raw_files table
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS series_name TEXT;
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS series_number INTEGER;
ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS series_total INTEGER;

-- Create index for series lookup
CREATE INDEX IF NOT EXISTS raw_files_series_idx ON raw_files(series_name);

-- Verify the migration
SELECT 
    'Series columns added' as status,
    COUNT(*) as total_files,
    COUNT(series_name) as files_with_series
FROM raw_files;
