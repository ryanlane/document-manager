-- Migration: Add settings table
-- Run this to enable persistent settings storage

CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on key for faster lookups
CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key);

-- Insert default LLM settings
INSERT INTO settings (key, value) VALUES 
('llm', '{"provider": "ollama", "ollama": {"url": "http://ollama:11434", "model": "dolphin-phi", "embedding_model": "nomic-embed-text", "vision_model": "llava"}, "openai": {"api_key": "", "model": "gpt-4o-mini", "embedding_model": "text-embedding-3-small", "vision_model": "gpt-4o"}, "anthropic": {"api_key": "", "model": "claude-3-haiku-20240307"}}')
ON CONFLICT (key) DO NOTHING;

-- Insert default source folders
INSERT INTO settings (key, value) VALUES 
('sources', '{"include": ["/data/archive/docs", "/data/archive/story"], "exclude": ["**/node_modules/**", "**/.git/**", "**/__pycache__/**", "**/*.tmp", "**/*.bak"]}')
ON CONFLICT (key) DO NOTHING;

-- Insert default extensions
INSERT INTO settings (key, value) VALUES 
('extensions', '[".txt", ".md", ".html", ".pdf", ".docx", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"]')
ON CONFLICT (key) DO NOTHING;
