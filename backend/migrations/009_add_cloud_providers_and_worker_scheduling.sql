-- Migration 009: Add cloud provider support and worker scheduling
-- Extends Phase 7 for cloud LLMs (OpenAI, Anthropic) and worker active hours

-- ============================================================================
-- Extend ollama_servers to support cloud providers
-- Conceptually becomes "LLM Providers" (Ollama, OpenAI, Anthropic, etc.)
-- ============================================================================

-- Add provider_type to distinguish Ollama from cloud APIs
ALTER TABLE ollama_servers ADD COLUMN IF NOT EXISTS provider_type TEXT DEFAULT 'ollama';
-- 'ollama' (default), 'openai', 'anthropic', 'google'

-- Add API key storage for cloud providers (encrypted in application layer)
ALTER TABLE ollama_servers ADD COLUMN IF NOT EXISTS api_key TEXT;

-- Add base_url override for cloud providers (e.g., Azure OpenAI endpoints)
ALTER TABLE ollama_servers ADD COLUMN IF NOT EXISTS base_url TEXT;

-- Add default model for cloud providers
ALTER TABLE ollama_servers ADD COLUMN IF NOT EXISTS default_model TEXT;

-- Add rate limit tracking for cloud providers
ALTER TABLE ollama_servers ADD COLUMN IF NOT EXISTS rate_limits JSONB;
-- {requests_per_minute: 60, tokens_per_minute: 100000, current_usage: {...}}

-- Add cost tracking for cloud providers
ALTER TABLE ollama_servers ADD COLUMN IF NOT EXISTS usage_stats JSONB;
-- {total_tokens: 12345, total_cost_usd: 0.50, last_reset: '2024-01-01'}

-- Create index for provider_type
CREATE INDEX IF NOT EXISTS ollama_servers_provider_type_idx ON ollama_servers(provider_type);

-- ============================================================================
-- Worker Scheduling
-- ============================================================================

-- Add schedule fields to workers table
ALTER TABLE workers ADD COLUMN IF NOT EXISTS schedule_type TEXT DEFAULT 'always_on';
-- 'always_on', 'use_default', 'custom', 'always_off'

ALTER TABLE workers ADD COLUMN IF NOT EXISTS schedule JSONB;
-- {
--   start_time: '22:00',
--   end_time: '08:00',
--   next_day: true,
--   days: [0,1,2,3,4,5,6],  -- 0=Monday, 6=Sunday
--   timezone: 'America/Denver'
-- }

ALTER TABLE workers ADD COLUMN IF NOT EXISTS schedule_status TEXT;
-- 'in_window', 'outside_window', 'paused_by_schedule'

-- ============================================================================
-- Global worker schedule settings
-- ============================================================================
INSERT INTO settings (key, value)
VALUES (
    'worker_schedule_enabled',
    'false'
)
ON CONFLICT (key) DO NOTHING;

INSERT INTO settings (key, value)
VALUES (
    'worker_default_schedule',
    '{"start_time": "22:00", "end_time": "08:00", "next_day": true, "days": [0,1,2,3,4,5,6], "timezone": "UTC"}'
)
ON CONFLICT (key) DO NOTHING;

-- ============================================================================
-- Migrate legacy llm_endpoints to ollama_servers if they exist
-- ============================================================================
DO $$
BEGIN
    -- Check if llm_endpoints table exists and has data
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'llm_endpoints'
    ) THEN
        -- Insert endpoints that don't already exist in ollama_servers
        INSERT INTO ollama_servers (name, url, enabled, provider_type)
        SELECT 
            COALESCE(name, 'Legacy ' || id::text),
            url,
            enabled,
            'ollama'
        FROM llm_endpoints
        WHERE url NOT IN (SELECT url FROM ollama_servers)
        ON CONFLICT (name) DO NOTHING;
        
        RAISE NOTICE 'Migrated legacy llm_endpoints to ollama_servers';
    END IF;
END $$;

-- ============================================================================
-- Add cloud provider presets (not enabled by default)
-- ============================================================================
INSERT INTO ollama_servers (name, url, provider_type, enabled, status, capabilities)
VALUES 
    ('OpenAI', 'https://api.openai.com/v1', 'openai', false, 'unconfigured', 
     '{"chat": true, "embedding": true, "vision": true}'),
    ('Anthropic', 'https://api.anthropic.com', 'anthropic', false, 'unconfigured',
     '{"chat": true, "embedding": false, "vision": true}')
ON CONFLICT (name) DO NOTHING;
