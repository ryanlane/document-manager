 # Document Manager - Scaling & Architecture Improvements

> **Goal**: Scale the RAG pipeline to handle 8M+ entries efficiently with two-stage retrieval, proper indexing, and optimized enrichment.

---

## Current State (Dec 17, 2025 - Updated)

| Metric | Value |
|--------|-------|
| Total entries (chunks) | 8,244,409 |
| Total raw_files (docs) | 125,544 |
| Docs enriched | ~7,678 (6.1%) |
| Docs embedded | ~7,335 (5.8%) |
| Docs pending | ~117,866 (94%) |
| Entries with title | 546,941 (6.6%) |
| Entries with summary | 548,268 (6.6%) |
| Entries with category | 555,180 (6.7%) |
| Avg chunks per doc | ~66 |

**Active Workers**: asgard (3060) + oak (1070 Ti) running doc enrichment + embedding @ ~1 doc/sec

**Two-Stage Search**: ✅ Implemented with IVFFlat indexes and RRF ranking
- Stage 1: ~20ms to search ~7k doc embeddings (with indexes + RRF)
- Stage 2: ~10ms to search chunks within top N docs
- Total: ~80ms per query (down from 140ms)

---

## Phase 1: Foundation (Schema & Indexes) ✅

### 1.1 Add Source/Author Normalization ✅
- [x] Add `source`, `author_key`, `author_bucket` to `raw_files`
- [x] Add `source`, `author_key`, `author_bucket` to `entries`
- [x] Populate from existing path structure
- [x] Create indexes for filtered queries
- **Migration**: `005_add_doc_level_embeddings_and_partitioning.sql`

### 1.2 Add Doc-Level Embedding Columns ✅
- [x] Add `doc_summary` (text) to `raw_files`
- [x] Add `doc_embedding` (vector 768) to `raw_files`
- [x] Add `doc_search_vector` (tsvector) to `raw_files`
- [x] Add `doc_status` (pending/enriched/embedded) to `raw_files`

### 1.3 Add Worker Queue Optimization ✅
- [x] Create partial index `entries_queue_idx` on (status, retry_count) WHERE status IN ('pending', 'error')
- This speeds up worker batch selection dramatically

---

## Phase 2: Doc-Level Enrichment 🔄

### 2.1 Create Doc Enrichment Pipeline ✅
- [x] Create `backend/src/enrich/enrich_docs.py`
- [x] Generate doc_summary from first N chars or representative chunks
- [x] Extract doc-level metadata (title, author, themes)
- [x] Update `doc_status` to 'enriched'
- [x] Lighter prompt than chunk enrichment (faster)

### 2.2 Create Doc Embedding Pipeline ✅
- [x] Create `backend/src/rag/embed_docs.py`
- [x] Embed `doc_summary` to `doc_embedding`
- [x] Populate `doc_search_vector` for FTS
- [x] Update `doc_status` to 'embedded'

### 2.3 Add Doc Enrichment to Worker Loop ✅
- [x] Add doc enrichment phase before chunk enrichment
- [x] Process docs in batches of 20
- [x] Dashboard controls for enrich_docs and embed_docs
- **Status**: Running - ~120k docs pending enrichment

---

## Phase 3: Two-Stage Retrieval 🔄

### 3.1 Update Search API ✅
- [x] Stage 1: Query doc-level vectors + FTS (fast, 125k docs)
- [x] Stage 2: Query chunk vectors only within top N file_ids
- [x] Return combined results with doc context
- [x] Fallback to keyword search when chunks not embedded
- **Endpoint**: `POST /search/two-stage`
- **Performance**: ~166ms total (112ms stage1, 16ms stage2, 30ms embed)

### 3.2 Add Vector Indexes (After Population) ✅
- [x] Create IVFFlat index on `raw_files.doc_embedding` (lists=200) - 24MB
- [x] Create IVFFlat index on `entries.embedding` (lists=2000) - 74MB
- [x] Set `ivfflat.probes = 10` in search code for better recall
- **Performance with indexes**: Stage1=~130ms, Stage2=~6ms, Total=~175ms

### 3.3 Implement Ranking Fusion ✅
- [x] Implement Reciprocal Rank Fusion (RRF) for score normalization
- [x] RRF formula: `score = 0.7/(60+vector_rank) + 0.3/(60+keyword_rank)`
- [x] Limit candidate pools to top 100 from each source for efficiency
- [x] Applied to both Stage 1 (docs) and Stage 2 (chunks)
- **Performance**: Stage1=~20ms, Stage2=~10ms, Total=~80ms (down from 140ms)

---

## Phase 4: Chunk Enrichment Optimization 🔄

### 4.1 Split Enrichment into Tiers
- [ ] **Tier 1 (always)**: entities, tags, category, quality heuristic
- [ ] **Tier 2 (on-demand)**: full summary, themes, sentiment
- [ ] Only deep-enrich frequently retrieved or high-quality chunks

### 4.2 Inherit Doc Properties to Chunks ✅
- [x] Copy doc-level summary to chunks without summaries
- [x] Extract title from doc_summary for chunks
- [x] Infer category from doc_summary content
- [x] API endpoints: `GET /config/inheritance-stats`, `POST /config/inherit-metadata`
- [x] Created `backend/src/enrich/inherit_doc_metadata.py`
- **Results**: ~410k entries enriched via inheritance (no LLM calls needed!)
- **Remaining**: ~165k entries awaiting parent doc enrichment

### 4.3 Consider Smaller Chunks
- [ ] Current: 1000-1500 tokens per chunk
- [ ] Recommended: 400-900 tokens for varied content
- [ ] Run evaluation before changing

---

## Phase 5: Partitioning (Future)

### 5.1 Partition by author_bucket
- [ ] Create partitioned table with 128 buckets
- [ ] Migrate data from entries to partitioned table
- [ ] Update indexes per partition

### 5.2 Benefits
- Vacuum/reindex per partition (manageable)
- Author-filtered queries hit 1 partition (fast)
- Cascade deletes more efficient

---

## Performance Targets

| Query Type | Current | Target |
|------------|---------|--------|
| Author-filtered keyword | ~15ms | <10ms |
| Global keyword | ~50ms | <30ms |
| Author-filtered vector | N/A (no index) | <50ms |
| Global vector (2-stage) | N/A | <200ms |
| Similar stories (doc-level) | N/A | <100ms |

---

## Model Configuration

### Current Setup
| Machine | GPU | Model | Rate |
|---------|-----|-------|------|
| asgard | RTX 3060 12GB | qwen2:1.5b | ~95/min |
| oak | GTX 1070 Ti 8GB | qwen2:1.5b | ~89/min |
| **Combined** | - | - | **~184/min** |

### Models Available
- `qwen2:1.5b` - Fast, good quality (current)
- `phi4-mini` - Better reasoning, medium speed
- `phi4` - Best quality, slower
- `nomic-embed-text` - Embeddings (768 dims)

---

## Quick Reference Commands

```bash
# Check enrichment progress
curl -s http://localhost:8000/worker/stats | jq

# Start workers
docker compose -f docker-compose.yml -f docker-compose.oak.yml up -d worker worker-oak

# Stop workers
docker compose -f docker-compose.yml -f docker-compose.oak.yml stop worker worker-oak

# Set worker state
curl -X POST http://localhost:8000/worker/state \
  -H "Content-Type: application/json" \
  -d '{"ingest": true, "segment": true, "enrich": true, "embed": true, "running": true}'

# Check table sizes
docker exec document-manager-db-1 psql -U postgres -d archive_brain \
  -c "SELECT pg_size_pretty(pg_total_relation_size('entries'));"

# Check index usage
docker exec document-manager-db-1 psql -U postgres -d archive_brain \
  -c "SELECT indexrelname, idx_scan, idx_tup_read FROM pg_stat_user_indexes ORDER BY idx_scan DESC;"
```
