# Document Manager - Improvement Roadmap

## 🔴 High Priority (Performance & Quality)

### 1. Smarter Segmentation with Overlap
- [ ] Add configurable overlap between segments (e.g., 200 chars)
- [ ] Add max chunk size limit (target: 1000-1500 tokens / ~4000 chars)
- [ ] Intelligent splitting that respects sentence boundaries
- **Files**: `backend/src/segment/segment_entries.py`

### 2. Error Recovery & Retry Logic
- [ ] Add `retry_count` field to Entry model
- [ ] Mark entries as `error` after N failed attempts
- [ ] Add API endpoint to view/retry failed entries
- **Files**: `backend/src/db/models.py`, `backend/src/enrich/enrich_entries.py`

### 3. Genre/Category Detection from Path
- [ ] Extract category from folder structure (e.g., `/story/scifi/` → "sci-fi")
- [ ] Add `category` field to Entry model
- [ ] Include category in embedding text
- **Files**: `backend/src/enrich/enrich_entries.py`, `backend/src/db/models.py`

### 4. Batch Processing for Embeddings
- [ ] Process multiple entries in parallel
- [ ] Consider async/threading for API calls
- **Files**: `backend/src/rag/embed_entries.py`

### 5. Content Type Detection for Better Parsing
- [ ] Strip HTML tags properly before segmentation
- [ ] Preserve Markdown headers as context markers
- [ ] Handle code blocks differently
- **Files**: `backend/src/segment/segment_entries.py`

---

## 🟡 Medium Priority (Features)

### 6. Relationship/Link Extraction
- [ ] Parse and store document links in DB
- [ ] Add "related documents" feature to frontend
- **Files**: `backend/src/segment/segment_entries.py`, new table needed

### 7. Deduplication at Entry Level
- [ ] Hash entry text content
- [ ] Skip duplicate segments across files
- **Files**: `backend/src/segment/segment_entries.py`

### 8. Re-enrichment Trigger
- [ ] Add API endpoint to reset entry status to `pending`
- [ ] Add frontend button to trigger re-analysis
- **Files**: `backend/src/api/main.py`, frontend

### 9. Configurable Enrichment Prompt
- [ ] Move prompt template to config.yaml
- [ ] Allow custom metadata fields
- **Files**: `config/config.yaml`, `backend/src/enrich/enrich_entries.py`

### 10. Progress Tracking for All Stages
- [ ] Add progress file for enrichment phase
- [ ] Add progress file for embedding phase
- [ ] Update dashboard to show all stage progress
- **Files**: `backend/src/enrich/enrich_entries.py`, `backend/src/rag/embed_entries.py`

---

## 🟢 Lower Priority (Nice to Have)

### 11. Parallel Worker Processes
- [ ] Use multiprocessing for enrichment
- [ ] Consider async workers
- **Files**: `backend/src/worker_loop.py`

### 12. Quality Scoring
- [ ] Add confidence score from LLM
- [ ] Flag low-quality entries for review
- **Files**: `backend/src/enrich/enrich_entries.py`

### 13. Full-Text Search Hybrid
- [ ] Combine BM25 (search_vector) with vector similarity
- [ ] Weighted scoring system
- **Files**: `backend/src/rag/search.py`

### 14. Document Collections/Series
- [ ] Group entries from same file
- [ ] Series detection from filenames
- **Files**: `backend/src/db/models.py`

---

## Completed ✅

- [x] Fallback to filename for title
- [x] Author extraction from folder structure
- [x] Rich metadata in embeddings (title, author, tags, summary)
- [x] Wait for enrichment before embedding
- [x] Model selection persistence in frontend
- [x] Advanced search filters (author, tags, extension)
- [x] Reduced ingest frequency (1 hour interval)
- [x] Single-pass file scanning (removed counting phase)
