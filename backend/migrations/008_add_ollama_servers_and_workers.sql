-- Migration 008: Add ollama_servers and workers tables for distributed processing
-- Part of Phase 7: Dynamic Worker Scaling

-- ============================================================================
-- Ollama Servers Registry
-- ============================================================================
CREATE TABLE IF NOT EXISTS ollama_servers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    enabled BOOLEAN DEFAULT true,
    status TEXT DEFAULT 'unknown',  -- 'online', 'offline', 'error', 'unknown'
    status_message TEXT,  -- Error message or status details
    last_health_check TIMESTAMP WITH TIME ZONE,
    gpu_info JSONB,  -- {name, vram_total, vram_free}
    models_available JSONB,  -- Cached list of installed models
    capabilities JSONB,  -- {chat: bool, embedding: bool, vision: bool}
    priority INTEGER DEFAULT 0,  -- Higher = preferred for task assignment
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ollama_servers_status_idx ON ollama_servers(status);
CREATE INDEX IF NOT EXISTS ollama_servers_enabled_idx ON ollama_servers(enabled);

-- ============================================================================
-- Workers Registry
-- ============================================================================
CREATE TABLE IF NOT EXISTS workers (
    id TEXT PRIMARY KEY,  -- UUID or hostname-based ID
    name TEXT NOT NULL,
    ollama_server_id INTEGER REFERENCES ollama_servers(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'starting',  -- 'starting', 'active', 'idle', 'stale', 'stopped'
    current_task TEXT,  -- e.g., 'enriching doc #12345'
    current_phase TEXT,  -- 'ingest', 'segment', 'enrich', 'embed', etc.
    stats JSONB,  -- {docs_per_min, entries_per_min, uptime_seconds, memory_mb}
    managed BOOLEAN DEFAULT false,  -- True if spawned by API
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    config JSONB  -- {phases: ['ingest', 'segment', 'enrich', 'embed'], batch_size: 100}
);

CREATE INDEX IF NOT EXISTS workers_status_idx ON workers(status);
CREATE INDEX IF NOT EXISTS workers_last_heartbeat_idx ON workers(last_heartbeat);
CREATE INDEX IF NOT EXISTS workers_ollama_server_id_idx ON workers(ollama_server_id);

-- ============================================================================
-- Triggers for updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION update_ollama_servers_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_ollama_servers_updated_at ON ollama_servers;
CREATE TRIGGER update_ollama_servers_updated_at
    BEFORE UPDATE ON ollama_servers
    FOR EACH ROW
    EXECUTE FUNCTION update_ollama_servers_updated_at();

-- ============================================================================
-- Seed with default local Ollama server if using docker-compose default
-- ============================================================================
INSERT INTO ollama_servers (name, url, enabled, status, priority)
VALUES ('local', 'http://ollama:11434', true, 'unknown', 10)
ON CONFLICT (name) DO NOTHING;
