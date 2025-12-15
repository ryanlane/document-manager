-- Migration 003: Add document_links table for link extraction
-- Run this against your PostgreSQL database

-- Create document_links table
CREATE TABLE IF NOT EXISTS document_links (
    id BIGSERIAL PRIMARY KEY,
    file_id BIGINT NOT NULL REFERENCES raw_files(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    link_text TEXT,
    link_type TEXT,  -- 'html_href', 'markdown', 'raw_url', 'email'
    domain TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS document_links_file_idx ON document_links(file_id);
CREATE INDEX IF NOT EXISTS document_links_url_idx ON document_links(url);
CREATE INDEX IF NOT EXISTS document_links_domain_idx ON document_links(domain);

-- Verify the migration
SELECT 
    'document_links table created' as status,
    COUNT(*) as row_count
FROM document_links;
