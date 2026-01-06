# OllamaServer to LLMProvider Rename

## Overview
Renamed the `ollama_servers` table and `OllamaServer` model to `llm_providers` and `LLMProvider` respectively, since the system now supports multiple LLM providers (Ollama, OpenAI, Anthropic, Google) beyond just Ollama.

## Changes Made

### Database Migration
- **File**: `backend/migrations/010_rename_ollama_servers_to_llm_providers.sql`
- Renamed table: `ollama_servers` → `llm_providers`
- Renamed indexes:
  - `ollama_servers_status_idx` → `llm_providers_status_idx`
  - `ollama_servers_enabled_idx` → `llm_providers_enabled_idx`
  - `ollama_servers_provider_type_idx` → `llm_providers_provider_type_idx`
  - `ollama_servers_pkey` → `llm_providers_pkey`
  - `ollama_servers_name_key` → `llm_providers_name_key`
- Renamed sequence: `ollama_servers_id_seq` → `llm_providers_id_seq`
- Renamed trigger function: `update_ollama_servers_updated_at()` → `update_llm_providers_updated_at()`
- Renamed foreign key column in workers table: `ollama_server_id` → `llm_provider_id`
- Renamed index in workers table: `workers_ollama_server_id_idx` → `workers_llm_provider_id_idx`
- Updated foreign key constraint: `workers_ollama_server_id_fkey` → `workers_llm_provider_id_fkey`

### Backend Code Changes

#### Models (`backend/src/db/models.py`)
- Renamed class: `OllamaServer` → `LLMProvider`
- Updated `__tablename__`: `'ollama_servers'` → `'llm_providers'`
- Updated docstring to reflect the rename
- Updated relationship in `Worker` model:
  - Column: `ollama_server_id` → `llm_provider_id`
  - Relationship attribute: `ollama_server` → `llm_provider`
  - Foreign key reference: `'ollama_servers.id'` → `'llm_providers.id'`
- Updated index names in `__table_args__`

#### Services (`backend/src/services/`)
- **servers.py**: Replaced all `OllamaServer` references with `LLMProvider`
- **workers.py**: 
  - Replaced all `OllamaServer` references with `LLMProvider`
  - Replaced all `ollama_server_id` references with `llm_provider_id`
  - Updated relationship access: `worker.ollama_server` → `worker.llm_provider`
  - Added new API response fields: `llm_provider_name`, `llm_provider_url`
  - Kept old field names (`ollama_server_name`, `ollama_server_url`) for backward compatibility

### Frontend
No changes required. The API continues to return `ollama_server_name` and `ollama_server_url` for backward compatibility with existing frontend code.

## Backward Compatibility
- API responses include both old field names (`ollama_server_name`, `ollama_server_url`) and new field names (`llm_provider_name`, `llm_provider_url`)
- Frontend continues to work without modifications

## Testing
- Database migration executed successfully
- API and worker containers restarted without errors
- All endpoints continue to function normally

## Related Files
- Migration: `backend/migrations/010_rename_ollama_servers_to_llm_providers.sql`
- Models: `backend/src/db/models.py` (lines 214-293)
- Services: 
  - `backend/src/services/servers.py`
  - `backend/src/services/workers.py`

## Notes
This rename improves code clarity and semantic accuracy, as the system now supports multiple LLM providers beyond just Ollama. The table structure and functionality remain unchanged; only naming has been updated to better reflect its purpose as a unified registry for all LLM providers.
