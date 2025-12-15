# Document Manager - Improvement Roadmap

> **Goal**: This tool serves two purposes: (1) Archive and search documents using RAG, and (2) Help me understand how every step of the RAG pipeline works through transparency, visualization, and real-time feedback.

---

## 🎓 Educational & Transparency Features (NEW)

### E1. Pipeline Visualization Dashboard
- [ ] Visual flowchart showing data flow: File → Segments → Enriched → Embedded → Searchable
- [ ] Show counts at each stage with animated transitions
- [ ] Click on any stage to see detailed explanation of what happens there
- [ ] Color-coded status (pending/processing/complete/error) for each stage
- **Files**: `frontend/src/pages/Dashboard.jsx`

### E2. Real-time Processing Log Viewer
- [ ] Live-updating log stream on dashboard (WebSocket or polling)
- [ ] Filter logs by stage (ingest/segment/enrich/embed)
- [ ] Highlight important events (new file, LLM call, embedding generated)
- [ ] Show timing information (how long each step takes)
- **Files**: `frontend/src/pages/Logs.jsx`, `backend/src/api/main.py`

### E3. Entry Inspector / Debug View
- [ ] Click any entry to see its full journey: raw text → segments → enrichment prompt → LLM response → embedding
- [ ] Show the actual prompt sent to the LLM
- [ ] Show the raw JSON response from enrichment
- [ ] Visualize the embedding vector (dimensionality reduction to 2D/3D plot?)
- [ ] Show which other entries are "nearby" in vector space
- **Files**: New `frontend/src/pages/EntryInspector.jsx`

### E4. Search Explainer
- [ ] When searching, show WHY each result matched
- [ ] Display similarity scores for each result
- [ ] Show the query embedding vs result embeddings (visual comparison)
- [ ] Explain the difference between semantic search and keyword search
- [ ] Option to toggle between vector-only, keyword-only, and hybrid search
- **Files**: `frontend/src/pages/Home.jsx`, `backend/src/rag/search.py`

### E5. LLM Prompt Transparency
- [ ] Show the enrichment prompt template on a dedicated "How It Works" page
- [ ] Allow editing the prompt and seeing how it affects results (sandbox mode)
- [ ] Display token counts for prompts and responses
- [ ] Show model name and parameters used for each call
- **Files**: New `frontend/src/pages/HowItWorks.jsx`

### E6. Embedding Visualizer
- [ ] 2D/3D scatter plot of all embeddings using t-SNE or UMAP
- [ ] Color by category, author, or file type
- [ ] Hover to see entry title/summary
- [ ] Click to navigate to entry
- [ ] Show where a search query lands in the space
- **Files**: New `frontend/src/pages/EmbeddingViz.jsx`, need to add dimensionality reduction endpoint

### E7. Processing Statistics & Timing
- [ ] Track and display average time per: ingest, segment, enrich, embed
- [ ] Show LLM tokens used (input/output) per entry
- [ ] Display embedding API call times
- [ ] Historical charts of processing speed over time
- **Files**: `backend/src/enrich/enrich_entries.py`, `backend/src/rag/embed_entries.py`, new stats table

### E8. Step-by-Step Walkthrough Mode
- [ ] "Demo mode" that processes one file slowly with explanations
- [ ] Pause at each stage to show what's happening
- [ ] Side-by-side comparison: raw file → processed output at each stage
- [ ] Interactive tooltips explaining each transformation
- **Files**: New `frontend/src/pages/Walkthrough.jsx`

### E9. Glossary & Documentation
- [ ] In-app glossary of terms (embedding, vector, semantic search, RAG, etc.)
- [ ] Tooltips throughout the UI explaining concepts
- [ ] Links to relevant documentation/papers
- [ ] "Learn more" expandable sections on each page
- **Files**: New `frontend/src/components/Glossary.jsx`

### E10. Vector Space Distance Calculator
- [ ] Tool to compare two pieces of text and see their similarity score
- [ ] Show how changing words affects the embedding distance
- [ ] Demonstrate why semantic search finds related content even with different words
- **Files**: New endpoint + frontend component

---

## 🔴 High Priority (Performance & Quality)

### 1. Smarter Segmentation with Overlap ✅
- [x] Add configurable overlap between segments (e.g., 200 chars)
- [x] Add max chunk size limit (target: 1000-1500 tokens / ~4000 chars)
- [x] Intelligent splitting that respects sentence boundaries
- **Files**: `backend/src/segment/segment_entries.py`

### 2. Error Recovery & Retry Logic ✅
- [x] Add `retry_count` field to Entry model
- [x] Mark entries as `error` after N failed attempts
- [x] Add API endpoint to view/retry failed entries
- **Files**: `backend/src/db/models.py`, `backend/src/enrich/enrich_entries.py`, `backend/src/api/main.py`
- **Migration**: `backend/migrations/001_add_category_retry_count.sql`

### 3. Genre/Category Detection from Path ✅
- [x] Extract category from folder structure (e.g., `/story/scifi/` → "sci-fi")
- [x] Add `category` field to Entry model
- [x] Include category in embedding text
- [x] Add category to search filters (frontend + backend)
- **Files**: `backend/src/enrich/enrich_entries.py`, `backend/src/db/models.py`
- **Migration**: `backend/migrations/001_add_category_retry_count.sql`

### 4. Batch Processing for Embeddings ✅
- [x] Process multiple entries in parallel (ThreadPoolExecutor with 4 workers)
- [x] Batch size of 10 entries per iteration
- **Files**: `backend/src/rag/embed_entries.py`

### 5. Content Type Detection for Better Parsing ✅
- [x] Strip HTML tags properly before segmentation
- [x] Preserve Markdown headers as context markers
- [x] Handle code blocks differently (extract, preserve, restore)
- **Files**: `backend/src/segment/segment_entries.py`

---

## 🟡 Medium Priority (Features)

### 6. Relationship/Link Extraction ✅
- [x] Parse and store document links in DB (HTML href, Markdown, raw URLs, emails)
- [x] New `DocumentLink` model with file_id, url, link_text, link_type, domain
- [x] API endpoints: `/files/{id}/links`, `/files/{id}/related`, `/links/stats`
- [x] Find related documents based on shared domains
- **Files**: `backend/src/db/models.py`, `backend/src/segment/segment_entries.py`, `backend/src/api/main.py`
- **Migration**: `backend/migrations/003_add_document_links.sql`

### 7. Deduplication at Entry Level ✅
- [x] Hash entry text content (SHA256 of normalized text)
- [x] Skip duplicate segments across files
- [x] Added `content_hash` column to Entry model
- **Files**: `backend/src/segment/segment_entries.py`, `backend/src/db/models.py`
- **Migration**: `backend/migrations/002_add_content_hash.sql`

### 8. Re-enrichment Trigger ✅
- [x] Add API endpoint to reset entry status to `pending`
- [x] Add frontend button to trigger re-analysis
- **Files**: `backend/src/api/main.py`, `frontend/src/pages/DocumentView.jsx`

### 9. Configurable Enrichment Prompt ✅
- [x] Move prompt template to config.yaml
- [x] Allow custom metadata fields via `custom_fields` in config
- [x] Add API endpoint to view current enrichment config
- **Files**: `config/config.yaml`, `backend/src/enrich/enrich_entries.py`, `backend/src/api/main.py`

### 10. Progress Tracking for All Stages ✅
- [x] Add progress file for enrichment phase
- [x] Add progress file for embedding phase
- [x] Update dashboard to show all stage progress
- **Files**: `backend/src/enrich/enrich_entries.py`, `backend/src/rag/embed_entries.py`, `frontend/src/pages/Dashboard.jsx`

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
