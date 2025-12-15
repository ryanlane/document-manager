-- Migration: Add category and retry_count columns to entries table
-- Run this against the PostgreSQL database

-- Add category column for storing document category (extracted from folder path)
ALTER TABLE entries ADD COLUMN IF NOT EXISTS category TEXT;

-- Add retry_count column for tracking failed enrichment attempts
ALTER TABLE entries ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;

-- Create an index on category for faster filtering
CREATE INDEX IF NOT EXISTS ix_entries_category ON entries(category);

-- Create an index on retry_count for finding entries that need retry
CREATE INDEX IF NOT EXISTS ix_entries_retry_count ON entries(retry_count);
