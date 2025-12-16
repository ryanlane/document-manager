 # Document Manager - Scaling & Architecture Improvements

> **Goal**: Scale the RAG pipeline to handle 8M+ entries efficiently with two-stage retrieval, proper indexing, and optimized enrichment.

---

## Current State (Dec 16, 2025)

| Metric | Value |
|--------|-------|
| Total entries (chunks) | 8,244,409 |
| Total raw_files (docs) | 125,544 |
| Entries enriched | ~110,000 (1.3%) |
| Entries embedded | ~15,500 |
| Avg chunks per doc | ~66 |
| Authors | 4,980 |

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

### 2.1 Create Doc Enrichment Pipeline
- [ ] Create `backend/src/enrich/enrich_docs.py`
- [ ] Generate doc_summary from first N chars or representative chunks
- [ ] Extract doc-level metadata (title, author, themes)
- [ ] Update `doc_status` to 'enriched'
- [ ] Lighter prompt than chunk enrichment (faster)

### 2.2 Create Doc Embedding Pipeline
- [ ] Create `backend/src/rag/embed_docs.py`
- [ ] Embed `doc_summary` to `doc_embedding`
- [ ] Populate `doc_search_vector` for FTS
- [ ] Update `doc_status` to 'embedded'

### 2.3 Add Doc Enrichment to Worker Loop
- [ ] Add doc enrichment phase before chunk enrichment
- [ ] Process docs in batches of 50-100
- [ ] Prioritize docs that have enriched chunks

---

## Phase 3: Two-Stage Retrieval

### 3.1 Update Search API
- [ ] Stage 1: Query doc-level vectors + FTS (fast, 125k docs)
- [ ] Stage 2: Query chunk vectors only within top N file_ids
- [ ] Return combined results with doc context

### 3.2 Add Vector Indexes (After Population)
- [ ] Create IVFFlat index on `raw_files.doc_embedding` (lists=200)
- [ ] Create IVFFlat index on `entries.embedding` (lists=2000)
- [ ] Test with `ivfflat.probes` = 5, 10, 20

### 3.3 Implement Ranking Fusion
- [ ] Normalize BM25 scores
- [ ] Normalize vector similarity scores  
- [ ] Weighted combination: `w1 * bm25 + w2 * vector + w3 * metadata_boost`
- [ ] Optional: Add reranker for top 50-200 results

---

## Phase 4: Chunk Enrichment Optimization

### 4.1 Split Enrichment into Tiers
- [ ] **Tier 1 (always)**: entities, tags, category, quality heuristic
- [ ] **Tier 2 (on-demand)**: full summary, themes, sentiment
- [ ] Only deep-enrich frequently retrieved or high-quality chunks

### 4.2 Inherit Doc Properties to Chunks
- [ ] Copy doc-level title to chunks without titles
- [ ] Inherit doc themes/sentiment unless chunk contradicts
- [ ] Reduces LLM calls significantly

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
