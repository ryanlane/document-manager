# Archive Brain - Turnkey Solution Plan

> **Goal**: Make Archive Brain a true plug-and-play solution. Users pull our Docker image, run it, and do **everything else through the web UI** - including adding compute servers, managing workers, and scaling processing power up or down. Zero command-line interaction after the initial `docker compose up`.
>
> **Important Constraint**: One-time host setup is required for data access. Docker volumes must be mounted before startup - this is a pre-flight requirement, not a missing feature. The product promise is:
>
> *"No CLI after startup. Add GPUs, manage workers, and configure everything through the browser."*

This honest framing builds user trust and prevents perceived broken promises.

---

## Distribution & Versioning

### Supported Install Path
The **only** supported install path is Docker Compose. Users interact with two files:

| File | Purpose |
|------|---------|
| `compose.yml` | Service definitions, volume mounts, GPU config |
| `.env` | Environment overrides (optional) |

Everything else is configured through the web UI.

### Version Tags
| Tag | Purpose | Stability |
|-----|---------|-----------|
| `:1.2.3` | Pinned release (recommended) | ✅ Stable, reproducible |
| `:1.2` | Minor version track | ✅ Stable, receives patches |
| `:latest` | Convenience only | ⚠️ May change without notice |

**Documentation and Quickstart always use pinned versions.** `:latest` exists for convenience but is not the promised path.

### Editions

| Edition | Use Case | Components |
|---------|----------|------------|
| **Starter** | Single machine, getting started | API + UI + DB + Ollama (bundled) |
| **Scale-out** | Large archives, multiple GPUs | Starter + external Ollama servers + external workers |

The Setup Wizard detects which edition applies and tailors the experience accordingly. Scale-out features are hidden until the user adds their first external server.

### Configuration Contract

| Category | Mutability | Examples |
|----------|------------|----------|
| **Runtime (UI)** | Change anytime via Settings | Models, source folders, file types, enrichment settings |
| **Boot-time (env/.env)** | Requires container restart | `DATABASE_URL`, `OLLAMA_URL` (for bundled), log levels |
| **Host-level** | Requires compose edit + restart | Volume mounts, GPU passthrough, port mappings |

This contract is documented in-app and surfaced in the Setup Wizard.

---

## Development Environment

### Guiding Principle
The current running instance is **production-ish** - it contains real data and should never be reset during development. All feature work happens against a separate dev environment with isolated volumes, ports, and a resettable database.

### Compose Profiles

| Profile | Purpose | Ports | Volumes |
|---------|---------|-------|---------|
| `prod` (default) | Real data, stable | 3000, 8000 | `/data/archive`, `postgres_data` |
| `dev` | Feature development | 3001, 8001 | `/data/archive-dev`, `postgres_data_dev` |

**Usage:**
```bash
# Production (default)
docker compose up -d

# Development
docker compose --profile dev up -d
```

### Dev Environment Setup

**compose.dev.yml** (overlay for dev profile):
```yaml
services:
  api-dev:
    extends:
      service: api
    profiles: [dev]
    ports:
      - "8001:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db-dev:5432/archive_dev
    volumes:
      - ./archive_dev:/data/archive
      - ./backend/src:/app/src  # Hot reload

  frontend-dev:
    extends:
      service: frontend
    profiles: [dev]
    ports:
      - "3001:80"

  db-dev:
    extends:
      service: db
    profiles: [dev]
    volumes:
      - postgres_data_dev:/var/lib/postgresql/data

volumes:
  postgres_data_dev:
```

### Reset Dev Script

**scripts/reset-dev.sh:**
```bash
#!/bin/bash
set -e

echo "⚠️  This will DELETE all dev data. Production is untouched."
read -p "Continue? [y/N] " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || exit 1

# Stop dev containers
docker compose --profile dev down -v

# Remove dev volume
docker volume rm document-manager_postgres_data_dev 2>/dev/null || true

# Clear dev archive folder
rm -rf ./archive_dev/*

# Seed with test data
./scripts/seed-dev.sh

# Restart dev environment
docker compose --profile dev up -d

echo "✅ Dev environment reset and seeded"
```

### Seeded Test Dataset

**scripts/seed-dev.sh** creates a minimal but representative dataset:

| Folder | Contents | Purpose |
|--------|----------|---------|
| `archive_dev/docs/` | 5 markdown files, 3 PDFs | Text extraction, chunking |
| `archive_dev/images/` | 10 JPG/PNG files | Vision model testing |
| `archive_dev/mixed/` | Nested folders with various types | Hierarchy, file type detection |

**Total:** ~50 files, <10MB - processes in under 5 minutes with Fast Scan.

**Seed content includes:**
- Files with known metadata for assertion testing
- Edge cases: unicode filenames, empty files, deeply nested paths
- Sample series (book chapters) for series detection testing
- Duplicate content for deduplication testing

### Development Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  Development Workflow                                        │
│  ─────────────────────────────────────────────────────────── │
│                                                              │
│  1. Start dev environment:                                   │
│     docker compose --profile dev up -d                       │
│                                                              │
│  2. Make changes to code (hot reload for frontend/backend)   │
│                                                              │
│  3. Test at http://localhost:3001                            │
│                                                              │
│  4. If you need a clean slate:                               │
│     ./scripts/reset-dev.sh                                   │
│                                                              │
│  5. Production remains untouched at http://localhost:3000    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Files to Create

| File | Purpose |
|------|---------|
| `compose.dev.yml` | Dev profile overlay |
| `scripts/reset-dev.sh` | Wipe and reseed dev environment |
| `scripts/seed-dev.sh` | Create test dataset |
| `archive_dev/.gitkeep` | Placeholder for dev archive |
| `test_fixtures/` | Source files for seeding |

---

## Current State Assessment

### What Already Works ✅
- **Settings UI** - LLM workers, models, source folders, file types all configurable via `/settings`
- **Dashboard** - Real-time processing status, worker controls, progress tracking
- **Multi-worker support** - Can add/pause/test LLM endpoints from the UI
- **Model selection** - Chat, embedding, and vision models selectable from installed options
- **Source management** - Can add/remove source folders, exclude patterns via UI
- **GPU auto-detection** - docker-compose.yml includes GPU reservations by default

### What's Missing ❌
1. **First-Run/Setup Wizard** - No guided onboarding experience
2. **Volume mounting from UI** - Can only add already-mounted folders
3. **Model downloading from UI** - Must use CLI to pull new models
4. **Database initialization feedback** - No UI indication of first-run setup
5. **Health/Prerequisites check** - No verification that GPU/memory is sufficient
6. **Documentation in-app** - No contextual help for new users
7. **Export/Import config** - No way to backup/restore settings
8. **Progress notifications** - No alerts when processing completes

---

## Phase 1: First-Run Experience (High Priority)

### 1.1 Setup Wizard Component
Create a guided first-run wizard that appears when no files have been processed yet.

**Pages:**
1. **Welcome** - Brief intro, system requirements check
2. **Environment Check** - Show any env var overrides that will lock settings (surface constraints early)
3. **LLM Configuration** - Select between local Ollama or cloud providers
4. **Model Selection** - Choose/download models based on available VRAM
5. **Source Folders** - Show available mounts, let user select which to index
6. **Indexing Strategy** - Choose processing depth (see 1.4 below)
7. **File Types** - Quick presets (Documents, Images, Everything)
8. **Start Processing** - Summary and begin button

**Implementation:**
- New `frontend/src/pages/Setup.jsx` component
- API endpoint `GET /api/system/first-run` to detect if setup needed
- Store `setup_complete` flag in settings table
- Redirect to `/setup` if flag is false and accessing `/`

**Files to create/modify:**
- `frontend/src/pages/Setup.jsx` (new)
- `frontend/src/pages/Setup.module.css` (new)
- `frontend/src/App.jsx` (add route, redirect logic)
- `backend/src/api/main.py` (add first-run detection endpoint)
- `backend/src/db/settings.py` (add setup_complete flag)

### 1.2 System Health Check
Pre-flight checks before processing starts.

**Checks:**
- Docker resources (memory, CPU limits)
- GPU availability (via NVIDIA Container Toolkit)
- Available disk space
- Network connectivity to Ollama
- Database connection

**Behavior:**
- Runs **automatically on first load** (not just in wizard)
- Shown prominently in Navbar with indicator dot
- Fail **hard** only on true blockers (DB unreachable)
- **Warn** on weak GPU, low disk space, etc.
- "Fix it" guidance shown for each issue

**Implementation:**
- New `GET /api/system/health-check` endpoint
- Returns structured status for each component
- Frontend displays with green/yellow/red indicators
- Navbar shows overall health dot (green/yellow/red)

**Files:**
- `backend/src/api/main.py` (add health-check endpoint)
- `frontend/src/pages/Setup.jsx` (display results)

### 1.3 VRAM-Based Model Recommendations
Help users choose appropriate models for their hardware.

**Logic:**
| VRAM | Recommended Chat | Recommended Embedding |
|------|------------------|----------------------|
| ≤4GB | qwen2:1.5b, tinyllama | nomic-embed-text |
| 6-8GB | phi4-mini, mistral:7b | nomic-embed-text |
| 12GB+ | phi4, llama3:8b | nomic-embed-text |
| 24GB+ | llama3:70b | nomic-embed-text |

**Implementation:**
- Query `nvidia-smi` via Ollama container
- New `GET /api/system/gpu-info` endpoint
- Frontend shows model recommendations with "one-click install"

**⚠️ Caching Strategy:**
GPUs don't change during runtime - polling introduces unnecessary failure modes.

- Detect **once on backend startup** via NVIDIA Container Toolkit visibility (not nvidia-smi via Ollama)
- Query the container's own GPU context, not shell commands
- Persist GPU info in settings table
- Expose read-only via API
- If detection fails, fall back gracefully with explicit messaging:
  > "GPU detection unavailable. Showing conservative model recommendations."

**Files:**
- `backend/src/api/main.py` (GPU detection endpoint)
- `frontend/src/pages/Setup.jsx` (recommendation UI)

### 1.4 Indexing Strategy Choice
Give users control over processing depth upfront to set expectations.

**Options:**
| Mode | Description | Use Case |
|------|-------------|----------|
| **Fast Scan** | Metadata + embeddings only, minimal LLM calls | Quick setup, large archives |
| **Full Enrichment** | Titles, summaries, tags, themes | Best search quality |
| **Custom** | Advanced settings for power users | Fine-tuned control |

**Default for first-run:** Fast Scan (ensures <10 min to first search)

**Implementation:**
- Store as `indexing_mode` in settings
- Maps to existing worker flags (enrich, enrich_docs, etc.)
- Fast Scan: `enrich=false, embed=true`
- Full: `enrich=true, embed=true`
- Custom: opens advanced panel

**Why this matters:**
- Names the choice explicitly, increasing perceived control
- Reduces "why is this taking so long?" support questions
- Advanced users get the control they expect

**Files:**
- `frontend/src/pages/Setup.jsx` (add step)
- `backend/src/db/settings.py` (add indexing_mode)

---

## Phase 2: Model Management (High Priority)

### 2.1 Model Download/Install from UI
Currently users must SSH in to pull models. Add UI for this.

**Features:**
- List of recommended models by category
- "Install" button that triggers `ollama pull`
- Real-time download progress via SSE (preferred for long operations)
- Show installed models with size/capabilities
- "Remove" button for unused models

**Implementation:**
- New `POST /api/settings/ollama/models/pull` - initiate download
- New `GET /api/settings/ollama/models/pull-status` - SSE stream for progress
- New `DELETE /api/settings/ollama/models/{name}` - remove model

**Ollama API:**
```python
# Pull with streaming
requests.post(f"{ollama_url}/api/pull", json={"name": model_name}, stream=True)
```

**⚠️ Streaming Caveats:**
Ollama's streaming pull output is not stable UX data - it can stall, restart, or emit partial JSON.

**Mitigation:**
- Treat progress as **best-effort**, not precise
- UI copy: "Downloading… this may pause or appear idle depending on model size."
- Use generic **Jobs table** for all background tasks (see 2.3)
- Auto-timeout stale jobs after 30 minutes

**Files:**
- `backend/src/api/main.py` (new model management endpoints)
- `frontend/src/pages/Settings.jsx` (add model download UI)

### 2.2 Model Library/Catalog
Show available models beyond what's installed.

**Data:**
- Curated list of recommended models with descriptions
- Categories: Fast, Balanced, Quality, Code, Vision
- Size, VRAM requirements, capabilities

**Implementation:**
- Static catalog in `backend/src/config/model_catalog.json`
- Endpoint returns catalog merged with installed status
- Frontend shows installed vs available

**Files:**
- `backend/src/config/model_catalog.json` (new)
- `backend/src/api/main.py` (catalog endpoint)
- `frontend/src/pages/Settings.jsx` (catalog UI)

### 2.3 Generic Jobs Table
A unified system for tracking all background operations.

**Job Types:**
| Type | Description |
|------|-------------|
| `model_pull` | Downloading a model from Ollama |
| `folder_scan` | Initial scan of a new source folder |
| `config_import` | Importing settings from backup |
| `vacuum` | Database maintenance |

**Schema:**
```sql
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, failed
    progress INTEGER,  -- 0-100 or NULL
    message TEXT,  -- Current status message
    metadata JSONB,  -- Type-specific data (model name, folder path, etc.)
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now()
);
```

**Benefits:**
- Unified UI pattern for all long-running operations
- SSE endpoint can stream updates for any job type
- Easy to add new job types without schema changes
- Dashboard can show "Active Jobs" section

**Files:**
- `backend/src/db/models.py` (add Job model)
- `backend/src/services/jobs.py` (new - job management)
- `backend/src/api/main.py` (jobs endpoints)
- `frontend/src/components/JobsPanel.jsx` (new - unified job display)

---

## Phase 3: Source Folder Management (Medium Priority)

### 3.1 Volume Discovery & Mounting Guidance
Users need to understand how to make folders available.

**Current limitation:** 
Docker volumes must be defined in docker-compose.yml before they can be used.

**Solution - Guided Instructions:**
1. Show current mounted volumes in UI
2. Provide copy-paste docker-compose snippet for adding new volumes
3. Link to documentation for common scenarios (NAS, network drives)

**Alternative - Docker Socket Access (Advanced):**
Could potentially modify docker-compose.yml from within container, but security implications make this inadvisable.

**Implementation:**
- Improve "Available Folders" section in Settings
- Add "How to add folders" expandable guide
- Show docker-compose.yml snippet for each common scenario

**Files:**
- `frontend/src/pages/Settings.jsx` (add guidance section)
- `docs/ADDING_FOLDERS.md` (new user guide)

### 3.2 Folder Browser Component
Let users browse available mounted folders visually.

**Features:**
- Tree view of `/data/archive` contents
- Checkbox to select folders for indexing
- Show file counts per folder (estimates only)
- Warn about very large folders (>100k files)

**⚠️ Risk Mitigation:**
This is high UX value but medium risk - large directories and network mounts can cause issues.

| Risk | Mitigation |
|------|------------|
| Large directories = slow tree | Hard cap recursion depth (3 levels default) |
| Network mounts = blocking I/O | Async loading with timeouts |
| File count hammers disks | Counts are **approximate**, labeled as estimates |
| Network mount file counts | **Skip counting on network mounts** - show "?" instead |
| Massive folder expansion | Warn before expanding >10k items |

**Implementation:**
- Lazy-load children on expand (not upfront)
- `GET /api/files/browse?path=/data/archive&depth=1`
- Detect network mounts and skip counting (show "~" or "unknown")
- Returns folder structure with approximate file counts
- Frontend renders as tree with checkboxes
- Show spinner during expansion, timeout after 5s

**Files:**
- `backend/src/api/main.py` (folder browse endpoint)
- `frontend/src/components/FolderBrowser.jsx` (new)
- `frontend/src/pages/Settings.jsx` (integrate browser)

---

## Phase 4: Processing UX Improvements (Medium Priority)

### 4.1 Progress Notifications
Alert users when milestones are reached.

**Notifications:**
- "Processing started" - when first file begins
- "X% complete" - at 25%, 50%, 75%
- "Processing complete" - when queue is empty
- "Error detected" - when error rate exceeds threshold

**⚠️ Staged Implementation:**
Browser notifications + service workers introduce permission friction, cross-browser inconsistencies, and background lifecycle complexity. Stage carefully:

| Stage | Scope | Complexity |
|-------|-------|------------|
| **Stage 1** | In-app only (bell icon + toast) | Low |
| **Stage 2** | Optional browser notifications | Medium |
| **Stage 3** | Service worker (background) | High - only if needed |

**Recommendation:** Stage 1 is sufficient to hit success metrics. Don't over-engineer early.

**Files:**
- `frontend/src/components/Notifications.jsx` (new - in-app only first)
- `frontend/src/components/Navbar.jsx` (add notification bell)

### 4.2 Processing Time Estimates
Show realistic ETAs based on current rate.

**Current:** Already shows ETA on Dashboard for some phases.

**Improvements:**
- Show total ETA across all phases
- Factor in historical processing rates
- Adjust for different document types (PDFs slower than txt)

**Files:**
- `backend/src/api/main.py` (enhance worker/stats endpoint)
- `frontend/src/pages/Dashboard.jsx` (display combined ETA)

### 4.3 Pause/Resume with Persistence
Ensure worker state survives container restarts.

**Current:** Worker state is in a JSON file, but may be lost on rebuild.

**Improvement:**
- Store worker state in database (settings table)
- Sync file and DB state on startup

**Files:**
- `backend/src/worker_loop.py` (persist to DB)
- `backend/src/db/settings.py` (add worker state methods)

---

## Phase 5: Configuration & Backup (Lower Priority)

### 5.1 Export/Import Settings
Let users backup and restore their configuration.

**Export includes:**
- LLM settings (models, endpoints)
- Source folders and exclusions
- File type preferences
- Enrichment prompt customizations
- Worker state preferences

**Format:** JSON file download

**⚠️ Import Validation:**
Merging configs is harder than it looks. What if imported config references missing models, unmounted folders, or exceeds system capacity?

**Implementation:**
- `GET /api/settings/export` - returns all settings as JSON
- `POST /api/settings/import` - accepts JSON with **validation + preview step**:
  - Parse and validate JSON structure
  - Check each referenced model against installed list
  - Check each folder against mounted paths
  - Return preview:
    ```json
    {
      "valid": true,
      "warnings": [
        "Model 'llama3:70b' not installed - will need to download",
        "Folder '/data/archive/old' not mounted - will be skipped"
      ],
      "will_apply": { ... },
      "will_ignore": { ... }
    }
    ```
  - User confirms before applying

This turns a fragile feature into a robust one.

**Files:**
- `backend/src/api/main.py` (export/import endpoints)
- `frontend/src/pages/Settings.jsx` (download/upload buttons)

### 5.2 Reset to Defaults
One-click restore of default settings.

**Options:**
- Reset LLM settings only
- Reset sources only
- Reset all settings
- Factory reset (clear all data)

**Files:**
- `backend/src/api/main.py` (reset endpoints)
- `frontend/src/pages/Settings.jsx` (reset buttons with confirmation)

### 5.3 Environment Variable Override Indication
Show when settings are overridden by env vars.

**Current issue:** User changes model in UI, but env var takes precedence on restart.

**Solution:**
- Show which settings come from env vars vs database
- Indicate that env var values are "locked"
- Document precedence clearly
- **Surface env overrides early in Setup Wizard** (not just Settings)

If the system is locked by env vars, users should learn that before making choices that won't persist.

**Implementation:**
- Backend detects which env vars are set
- API responses include `source: "env" | "database" | "default"` for each setting
- Frontend shows lock icon for env-var settings
- Setup Wizard Step 2 shows: "These settings are locked by your environment configuration"

**Files:**
- `backend/src/api/main.py` (add source indication to settings responses)
- `frontend/src/pages/Settings.jsx` (show lock icons for env-var settings)

---

## Phase 6: Documentation & Help (Lower Priority)

### 6.1 In-App Contextual Help
Add help tooltips and explanations throughout.

**Areas needing help:**
- What each model type is for (chat vs embedding vs vision)
- Why processing takes time
- What "enrichment" means
- How semantic search differs from keyword search
- What the similarity score means

**Implementation:**
- Add `<HelpTooltip>` component
- Pull content from `docs/HELP.json`
- Keyboard shortcut `?` to show all help

**Files:**
- `frontend/src/components/HelpTooltip.jsx` (new)
- `docs/HELP.json` (new - all help content)
- Various page components (add tooltips)

### 6.2 Video/GIF Tutorials
Embedded quick-start guides.

**Topics:**
- Adding your first folder
- Understanding the dashboard
- Using semantic search
- Configuring models

**Implementation:**
- Host on GitHub or embed from external source
- Show in Setup Wizard and Help sections

### 6.3 Troubleshooting Guide
Common issues and solutions.

**Topics:**
- "No models available" - Ollama not connected
- "Processing stuck" - Worker paused or crashed
- "Search returns nothing" - No files embedded yet
- "GPU not detected" - Driver/toolkit issues

**Implementation:**
- In-app troubleshooter with diagnostic checks
- Auto-detect common issues and suggest fixes

**Files:**
- `frontend/src/pages/Troubleshoot.jsx` (new)
- `backend/src/api/main.py` (diagnostic endpoints)

---

## Phase 7: Dynamic Worker Scaling (High Priority)

> **Goal**: Users can add/remove Ollama servers and processing workers entirely through the web UI. Rent GPUs, add them via the UI, process your archive, then scale back - no CLI or docker-compose editing required.

### Current Architecture Limitation
| Component | Current State |
|-----------|---------------|
| Work Queue | ✅ PostgreSQL with `FOR UPDATE SKIP LOCKED` - supports multiple workers |
| Worker Deployment | ❌ Manual docker-compose files |
| Ollama Config | ❌ Per-worker env vars or single DB setting |
| Worker Visibility | ❌ No central registry of active workers |

### 7.1 Ollama Server Registry
Database table to manage multiple Ollama endpoints.

**UI: Settings > Compute Servers**
```
┌─────────────────────────────────────────────────────────────┐
│  Compute Servers                              [+ Add Server] │
│  ─────────────────────────────────────────────────────────── │
│  Name          URL                        Status    Workers  │
│  ─────────────────────────────────────────────────────────── │
│  local         http://ollama:11434        ● Online    1      │
│  oak           http://192.168.1.19:11434  ● Online    1      │
│  rented-gpu    http://x.x.x.x:11434       ○ Offline   0      │
│                                                              │
│  [Test All] [Remove Offline]                                 │
└─────────────────────────────────────────────────────────────┘
```

**Database Schema:**
```sql
CREATE TABLE ollama_servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    url VARCHAR(512) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    status VARCHAR(50) DEFAULT 'unknown',  -- online, offline, error
    last_health_check TIMESTAMP,
    gpu_info JSONB,  -- detected GPU, VRAM
    models_available JSONB,  -- cached list of installed models
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
```

**API Endpoints:**
- `GET /api/servers` - List all servers
- `POST /api/servers` - Add new server
- `DELETE /api/servers/{id}` - Remove server
- `POST /api/servers/{id}/test` - Test connectivity
- `POST /api/servers/{id}/pull-model` - Pull model to this server

**Health Check Logic:**
- Background task pings each server every 60s
- Updates status, GPU info, available models
- Marks offline after 3 failed checks

**Files:**
- `backend/src/db/models.py` (add OllamaServer model)
- `backend/src/api/main.py` (server management endpoints)
- `frontend/src/pages/Settings.jsx` (server management UI)

### 7.2 Worker Registration & Heartbeats
Workers self-register and send periodic heartbeats.

**Worker Behavior:**
1. On startup, worker registers with API: name, Ollama URL, capabilities
2. Every 30s, sends heartbeat with stats: docs/min, current task, memory usage
3. If no heartbeat for 2 min, marked as "stale"
4. On shutdown, sends deregister message

**Database Schema:**
```sql
CREATE TABLE workers (
    id VARCHAR(255) PRIMARY KEY,  -- UUID or hostname
    name VARCHAR(255),
    ollama_server_id INTEGER REFERENCES ollama_servers(id),
    status VARCHAR(50) DEFAULT 'starting',  -- starting, active, idle, stale, stopped
    current_task VARCHAR(255),  -- 'enriching doc 12345' or null
    stats JSONB,  -- { docs_per_min, entries_per_min, uptime_seconds }
    last_heartbeat TIMESTAMP,
    started_at TIMESTAMP DEFAULT now()
);
```

**Dashboard Integration:**
```
┌─────────────────────────────────────────────────────────────┐
│  Active Workers                                              │
│  ─────────────────────────────────────────────────────────── │
│  Worker          Server    Status    Rate       Task         │
│  ─────────────────────────────────────────────────────────── │
│  asgard-main     local     ● Active  15/min    doc #27094   │
│  oak-worker      oak       ● Active  12/min    doc #27122   │
│  rented-1        rented    ○ Idle    —         waiting      │
│                                                              │
│  Total throughput: 27 docs/min                               │
└─────────────────────────────────────────────────────────────┘
```

**Files:**
- `backend/src/db/models.py` (add Worker model)
- `backend/src/worker_loop.py` (add heartbeat sending)
- `backend/src/api/main.py` (worker registration endpoints)
- `frontend/src/pages/Dashboard.jsx` (worker visibility)

### 7.3 Dynamic Worker Spawning
When user adds an Ollama server, they can add workers to process with it.

**Option A: External Worker Deployment (Recommended)**
User runs a standalone worker container on any machine with database access.

```bash
# User runs on any machine (local, cloud, rented GPU):
docker run -d \
  --name archive-worker \
  -e DATABASE_URL=postgres://user:pass@your-host:5432/archive_brain \
  -e OLLAMA_URL=http://localhost:11434 \
  -e WORKER_NAME=rented-gpu-1 \
  ghcr.io/ryanlane/archive-brain-worker:1.2.3
```

**Why this is recommended:**
- No security implications (no Docker socket)
- Works on any machine with network access to the database
- User controls the worker lifecycle directly
- Works with rented VMs, cloud instances, etc.

**UI Support:**
- Settings shows "Add External Worker" with copy-paste command
- Command is pre-filled with current `DATABASE_URL` and selected Ollama server
- Worker auto-appears on Dashboard after first heartbeat

**Option B: Managed Worker Spawning (Advanced, Opt-in)**
For users who want the API to spawn workers automatically.

**⚠️ Security Warning:** This requires mounting the Docker socket, which grants the container root-equivalent access to the host. Only enable if you understand the implications.

**Requirements:**
- Mount Docker socket: `/var/run/docker.sock:/var/run/docker.sock`
- Set `ENABLE_MANAGED_WORKERS=true` in `.env`
- API has permission to create containers

**Flow:**
1. User enables managed workers in Settings (with security warning)
2. User adds Ollama server via UI
3. User clicks "Start Managed Worker"
4. API spawns worker container with that server's URL
5. Worker registers itself via heartbeat
6. Dashboard shows worker with "Managed" badge

**UI shows both types:**
- "External" workers (self-registered, recommended)
- "Managed" workers (spawned by API, advanced)

**Files:**
- `backend/src/api/main.py` (worker spawn/stop endpoints)
- `backend/src/services/docker_manager.py` (new - Docker API wrapper)
- `frontend/src/pages/Settings.jsx` (spawn worker button per server)

### 7.4 Worker Lifecycle Management
Control workers from the Dashboard.

**Actions per worker:**
- **Pause** - Stop processing, keep running
- **Resume** - Continue processing  
- **Stop** - Graceful shutdown
- **Remove** - Stop and delete container (managed only)

**Actions for external workers:**
- Show command to run on remote machine
- Show "last seen" time
- Auto-remove from registry after extended absence

**Scaling Controls:**
```
┌─────────────────────────────────────────────────────────────┐
│  Scaling                                                     │
│  ─────────────────────────────────────────────────────────── │
│  Queue depth: 109,426 docs pending                          │
│  Current workers: 2                                          │
│  Estimated time: ~61 hours                                   │
│                                                              │
│  [+ Add Worker]  [Scale to 0]                                │
│                                                              │
│  💡 Add more Ollama servers to process faster               │
└─────────────────────────────────────────────────────────────┘
```

**Files:**
- `backend/src/api/main.py` (worker control endpoints)
- `frontend/src/pages/Dashboard.jsx` (worker controls)

### 7.5 Standalone Worker Image
Publish a dedicated worker image that can run anywhere.

**Image:** `ghcr.io/ryanlane/archive-brain-worker:latest`

**Required env vars:**
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `OLLAMA_URL` | Ollama server URL |
| `WORKER_NAME` | Friendly name for dashboard |

**Optional env vars:**
| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_MODEL` | (from DB) | Override enrichment model |
| `HEARTBEAT_INTERVAL` | 30 | Seconds between heartbeats |
| `BATCH_SIZE` | 20 | Docs per batch |

**Dockerfile changes:**
- Separate `Dockerfile.worker` that only includes worker code
- Smaller image, faster deploy

**Files:**
- `backend/Dockerfile.worker` (new - minimal worker image)
- `.github/workflows/publish-worker.yml` (new - publish to GHCR)
- `docs/ADDING_WORKERS.md` (new - deployment guide)

### 7.6 Auto-Scaling (Future Enhancement)
Automatically scale workers based on queue depth.

**Rules:**
- If queue > 10,000 and workers < available_servers: spawn more
- If queue = 0 for 10 min: scale to 1 (keep warm)
- If queue = 0 for 1 hour: scale to 0

**Implementation:**
- Background task evaluates rules every 5 min
- Only affects "managed" workers, not external
- User can disable auto-scaling

**This is Phase 2 of scaling - manual control first.**

### 7.7 Worker Scheduling
Allow users to configure active hours for workers - essential for shared machines used for other tasks during the day.

**UI: Settings > Worker Schedules**
```
┌─────────────────────────────────────────────────────────────┐
│  Worker Schedules                                            │
│  ─────────────────────────────────────────────────────────── │
│  ☑ Enable scheduling (workers pause outside active hours)   │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Default Schedule (applies to all unless overridden)    │ │
│  │  ───────────────────────────────────────────────────────│ │
│  │  Active hours: [22:00] to [08:00]  ☑ Next day           │ │
│  │  Active days:  ☑M ☑T ☑W ☑T ☑F ☑S ☑S                     │ │
│  │  Timezone:     [America/Denver ▼]                       │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  Per-Worker Overrides:                                       │
│  ─────────────────────────────────────────────────────────── │
│  Worker          Schedule              Status                │
│  ─────────────────────────────────────────────────────────── │
│  asgard-main     ○ Use default         ● Active (in window) │
│  oak-worker      ● Custom: 00:00-06:00 ○ Paused (outside)   │
│  rented-gpu      ○ Always on           ● Active             │
│                                                              │
│  [Save Schedules]                                            │
└─────────────────────────────────────────────────────────────┘
```

**Schedule Options per Worker:**
| Option | Behavior |
|--------|----------|
| **Use default** | Follows the global schedule above |
| **Custom** | Worker-specific active hours |
| **Always on** | Ignores scheduling, runs 24/7 |
| **Always off** | Manually paused until changed |

**Database Schema:**
```sql
-- Global schedule settings (in settings table)
-- schedule_enabled: boolean
-- schedule_default: jsonb

-- Per-worker schedule (in workers table or new table)
CREATE TABLE worker_schedules (
    worker_id VARCHAR(255) PRIMARY KEY REFERENCES workers(id),
    schedule_type VARCHAR(50) DEFAULT 'default',  -- default, custom, always_on, always_off
    active_start TIME,           -- e.g., '22:00'
    active_end TIME,             -- e.g., '08:00'
    crosses_midnight BOOLEAN,    -- true if end < start
    active_days INTEGER[],       -- [0,1,2,3,4,5,6] = Sun-Sat
    timezone VARCHAR(100),       -- e.g., 'America/Denver'
    updated_at TIMESTAMP DEFAULT now()
);
```

**Worker Behavior:**
1. Worker checks schedule on startup and every 60 seconds
2. If outside active window → pause processing (don't exit)
3. If inside active window → resume processing
4. Dashboard shows schedule status: "Active", "Paused (resumes at 22:00)", etc.
5. Manual pause/resume still works and overrides schedule temporarily

**API Endpoints:**
- `GET /api/schedules` - Get global and per-worker schedules
- `PUT /api/schedules/default` - Update global schedule
- `PUT /api/schedules/worker/{id}` - Update worker-specific schedule
- `GET /api/schedules/status` - Current schedule state for all workers

**Schedule Evaluation Logic:**
```python
def is_within_schedule(schedule: WorkerSchedule) -> bool:
    if schedule.schedule_type == 'always_on':
        return True
    if schedule.schedule_type == 'always_off':
        return False
    
    now = datetime.now(pytz.timezone(schedule.timezone))
    current_time = now.time()
    current_day = now.weekday()  # 0=Monday
    
    # Check if today is an active day
    if current_day not in schedule.active_days:
        return False
    
    # Handle midnight crossing (e.g., 22:00 - 08:00)
    if schedule.crosses_midnight:
        return current_time >= schedule.active_start or current_time < schedule.active_end
    else:
        return schedule.active_start <= current_time < schedule.active_end
```

**Dashboard Integration:**
- Show schedule indicator next to each worker
- "⏰ Paused until 22:00" or "● Active (until 08:00)"
- Warning if all workers are scheduled off and queue is large

**Common Presets:**
| Preset | Hours | Use Case |
|--------|-------|----------|
| Overnight | 22:00 - 08:00 | Desktop used during day |
| Weekends only | Sat-Sun all day | Work machine |
| Off-peak | 00:00 - 06:00 | Minimal impact |
| Business hours inverse | 18:00 - 09:00 | Office machine |

**Files:**
- `backend/src/db/models.py` (add WorkerSchedule model)
- `backend/src/db/settings.py` (add schedule settings)
- `backend/src/worker_loop.py` (add schedule checking)
- `backend/src/api/main.py` (schedule endpoints)
- `frontend/src/pages/Settings.jsx` (schedule UI)
- `frontend/src/pages/Dashboard.jsx` (schedule status display)

---

## Implementation Priority Order

### Sprint 1: Core First-Run Experience
1. ⬜ Setup Wizard (1.1)
2. ⬜ System Health Check (1.2)
3. ⬜ **Indexing Strategy Choice (1.4)** ← Prevents 80% of "why is this slow?" questions
4. ⬜ Model Download from UI (2.1)
5. ⬜ Generic Jobs Table (2.3)
6. ⬜ Environment Variable Override Indication (5.3)

**Why Indexing Strategy is in Sprint 1:**
- Single choice prevents most "why is this taking forever?" confusion
- Cheap to implement (just maps to existing worker flags)
- Sets correct expectations from the start
- Default to "Fast Scan" ensures <10 min to first search

### Sprint 2: Dynamic Worker Infrastructure
7. ⬜ Ollama Server Registry (7.1)
8. ⬜ Worker Registration & Heartbeats (7.2)
9. ⬜ Worker Visibility on Dashboard (7.2)
10. ⬜ Standalone Worker Image (7.5)
11. ⬜ **Worker Scheduling (7.7)** ← Essential for shared machines

**Why Sprint 2 is workers:**
- Core differentiator: "add GPUs from the UI"
- Enables horizontal scaling without CLI
- Scheduling lets users share machines without manual pause/resume
- Foundation for Scale-out edition

### Sprint 3: Enhanced Configuration
11. ⬜ VRAM-based Recommendations (1.3)
12. ⬜ Model Catalog (2.2)
13. ⬜ Folder Browser (3.2)
14. ⬜ External Worker Spawning UI (7.3)

### Sprint 4: Polish & Help
15. ⬜ Worker Lifecycle Management (7.4)
16. ⬜ Progress Notifications - Stage 1 only (4.1)
17. ⬜ In-App Help (6.1)
18. ⬜ Export/Import with Validation (5.1)

### Sprint 5: Advanced Features
18. ⬜ Processing Time Estimates (4.2)
19. ⬜ Troubleshooting Guide (6.3)
20. ⬜ Folder Mounting Guidance (3.1)
21. ⬜ Auto-Scaling (7.6) - if needed

---

## Technical Decisions

### API Design Principles
- All configuration changes via REST API
- Real-time updates via polling (WebSockets future enhancement)
- Graceful degradation if optional services unavailable

### Security Considerations
- No shell access from web UI
- Validate all paths are within allowed mounts
- Sanitize model names before passing to Ollama
- Rate limit model download requests

### Performance Considerations
- Cache GPU info (doesn't change during runtime)
- Lazy-load model catalog
- Debounce settings saves
- Paginate folder browser for large directories

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Time from `docker compose up` to first search | < 10 minutes |
| Settings changes requiring CLI | 0 |
| Adding a new compute server | < 2 minutes via UI |
| Scaling workers up/down | 0 CLI commands |
| Setup wizard completion rate | > 90% |
| User-reported "it just works" | > 80% |
| **Support questions about setup** | **↓ trending over time** |

The last metric is critical: if support questions don't trend down, the wizard isn't doing its job - regardless of completion rate.

---

## Quick Wins (Can Do Now)

1. **Add "Getting Started" link to Dashboard** when file count is 0
2. **Show model download progress** in Settings (endpoint exists, needs UI)
3. **Add folder path examples** to Settings sources section
4. **Create QUICKSTART.md** with pinned version and screenshots for common setups
5. **Add health status to Navbar** (green/yellow/red dot)
6. **Add env var override detection** to existing settings endpoints (foundation for 5.3)
7. **Default to tiny/fast model** (qwen2:1.5b or similar) for first-run to ensure <10 min success
8. **Rename docker-compose.yml to compose.yml** (modern convention)

---

## Files to Create

| File | Purpose |
|------|---------|
| `frontend/src/pages/Setup.jsx` | First-run wizard |
| `frontend/src/pages/Setup.module.css` | Wizard styles |
| `frontend/src/components/FolderBrowser.jsx` | Folder selection tree (lazy-loading) |
| `frontend/src/components/HelpTooltip.jsx` | Contextual help |
| `frontend/src/components/Notifications.jsx` | In-app progress alerts (Stage 1) |
| `frontend/src/components/ServerManager.jsx` | Ollama server management UI |
| `frontend/src/components/WorkerList.jsx` | Active worker display with controls |
| `frontend/src/components/JobsPanel.jsx` | Unified background job display |
| `backend/src/config/model_catalog.json` | Recommended models with VRAM requirements |
| `backend/src/db/models.py` | OllamaServer, Worker, Job tables |
| `backend/src/services/jobs.py` | Generic job management service |
| `backend/src/services/heartbeat.py` | Worker heartbeat sending logic |
| `backend/Dockerfile.worker` | Minimal standalone worker image |
| `.github/workflows/publish.yml` | Publish main + worker images to GHCR with version tags |
| `docs/ADDING_FOLDERS.md` | User guide for Docker volumes |
| `docs/ADDING_WORKERS.md` | Guide for deploying external workers |
| `docs/QUICKSTART.md` | Visual getting started guide with pinned version |
| `docs/HELP.json` | All help text content |
| `install.sh` | Optional: writes `.env` and launches compose |

---

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/App.jsx` | Add Setup route, redirect logic |
| `frontend/src/components/Navbar.jsx` | Health indicator (auto-check on load), notification bell |
| `frontend/src/pages/Settings.jsx` | Model download UI, folder guidance, env var indicators, server management |
| `frontend/src/pages/Dashboard.jsx` | Getting started prompt when empty, worker visibility & controls, jobs panel |
| `backend/src/api/main.py` | Health check, GPU info, model management, folder browse, env var detection, server/worker/jobs endpoints |
| `backend/src/db/settings.py` | setup_complete flag, indexing_mode, worker state persistence, GPU cache |
| `backend/src/worker_loop.py` | Add heartbeat sending, self-registration |
| `docker-compose.yml` | Comments explaining volume mounting; Docker socket mount is opt-in with warning |
| `compose.yml` | Canonical compose file (rename from docker-compose.yml) |

---

## Appendix A: User Journey (Target State)

### Initial Setup
1. User pulls image: `docker pull ghcr.io/ryanlane/archive-brain:latest`
2. User creates minimal `docker-compose.yml` with their data volumes
3. User runs `docker compose up -d`
4. User opens `http://localhost:3000`
5. **Setup Wizard appears** (first-run detected)
6. Wizard shows any **env var overrides** that will lock settings
7. Wizard checks system health, shows green checkmarks
8. User selects "Use built-in Ollama" (or configures cloud provider)
9. Wizard recommends models based on detected GPU, offers one-click install
10. User sees their mounted folders, selects which to index
11. User chooses **indexing strategy** (Fast/Full/Custom)
12. User picks file types (or accepts defaults)
13. User clicks "Start Processing"
14. **Dashboard shows live progress** with ETA

### Scaling Up (When Archive is Large)
15. User goes to Settings > Compute Servers
16. User clicks "+ Add Server" and enters rented GPU's Ollama URL
17. System tests connectivity, shows available models
18. User clicks "Start Worker" - new worker auto-spawns
19. Dashboard now shows 2 workers, combined throughput displayed
20. User repeats for additional rented machines as needed
21. Processing completes 3x faster with 3 workers

### Scaling Down (When Done)
22. User gets notification: "Processing complete!"
23. User goes to Dashboard > Active Workers
24. User clicks "Stop" on rented workers
25. User terminates rented VMs (workers auto-deregister)
26. Single local worker remains for ongoing search & new files

### Ongoing Use
27. User performs searches, browses archive
28. New files added to source folders auto-detected
29. Single worker handles incremental processing
30. 🎉 **Self-managing archive!**

---

## Appendix B: Design Principles

### Honesty Over Promise
- Be explicit about Docker/volume constraints
- "One-time host setup required" is honest, not a failure
- Show locked settings clearly, don't hide limitations

### Progressive Disclosure
- Simple defaults for new users
- Advanced options available but not overwhelming
- Indexing strategy names the choice without requiring expertise

### Defensive UX
- Treat streaming progress as best-effort
- Hard caps on recursion and timeouts
- Validation before applying imported configs
- Graceful fallbacks when detection fails

### Minimal Viable Scope
- Notifications: in-app first, browser later if needed
- Service workers: only if absolutely necessary
- Each feature should hit success metrics before expanding
