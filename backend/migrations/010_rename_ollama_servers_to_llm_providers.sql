-- Migration 010: Rename ollama_servers to llm_providers
-- This table now supports multiple LLM providers (Ollama, OpenAI, Anthropic, etc.)
-- so the name should reflect its broader purpose.

-- Rename the table
ALTER TABLE IF EXISTS ollama_servers RENAME TO llm_providers;

-- Rename indexes to match new table name
ALTER INDEX IF EXISTS ollama_servers_status_idx RENAME TO llm_providers_status_idx;
ALTER INDEX IF EXISTS ollama_servers_enabled_idx RENAME TO llm_providers_enabled_idx;
ALTER INDEX IF EXISTS ollama_servers_provider_type_idx RENAME TO llm_providers_provider_type_idx;
ALTER INDEX IF EXISTS ollama_servers_pkey RENAME TO llm_providers_pkey;
ALTER INDEX IF EXISTS ollama_servers_name_key RENAME TO llm_providers_name_key;

-- Rename the sequence
ALTER SEQUENCE IF EXISTS ollama_servers_id_seq RENAME TO llm_providers_id_seq;

-- Rename the trigger function (conditional)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc 
        WHERE proname = 'update_ollama_servers_updated_at'
    ) THEN
        ALTER FUNCTION update_ollama_servers_updated_at() RENAME TO update_llm_providers_updated_at;
    END IF;
END $$;

-- Drop and recreate the trigger with new names
DROP TRIGGER IF EXISTS update_ollama_servers_updated_at ON llm_providers;

-- Only create trigger if function exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc 
        WHERE proname = 'update_llm_providers_updated_at'
    ) THEN
        CREATE TRIGGER update_llm_providers_updated_at
            BEFORE UPDATE ON llm_providers
            FOR EACH ROW
            EXECUTE FUNCTION update_llm_providers_updated_at();
    END IF;
END $$;

-- Update the foreign key column name in workers table for clarity
-- Note: This is optional since the FK constraint still works, but improves clarity
DO $$
BEGIN
    -- Check if old column exists before renaming
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'workers' AND column_name = 'ollama_server_id'
    ) THEN
        ALTER TABLE workers RENAME COLUMN ollama_server_id TO llm_provider_id;
    END IF;
END $$;

-- Rename the index on workers table
ALTER INDEX IF EXISTS workers_ollama_server_id_idx RENAME TO workers_llm_provider_id_idx;

-- Recreate the foreign key constraint with new names (optional but cleaner)
DO $$
BEGIN
    -- Drop old constraint if it exists
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'workers_ollama_server_id_fkey'
    ) THEN
        ALTER TABLE workers DROP CONSTRAINT workers_ollama_server_id_fkey;
    END IF;
    
    -- Add new constraint
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'workers_llm_provider_id_fkey'
    ) THEN
        ALTER TABLE workers ADD CONSTRAINT workers_llm_provider_id_fkey 
            FOREIGN KEY (llm_provider_id) REFERENCES llm_providers(id) ON DELETE SET NULL;
    END IF;
END $$;
