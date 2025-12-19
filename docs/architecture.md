# Architecture Overview

This document explains how Archive Brain is structured and how data flows through the system.

---

## 🧩 High-Level Components

- **Frontend** – React UI for search and browsing
- **API** – FastAPI service for queries and RAG
- **Worker** – Background ingestion and enrichment pipeline
- **Database** – PostgreSQL + pgvector
- **LLM Runtime** – Ollama (local or external)

All components communicate over Docker networks.

---

## 🔁 Data Flow

1. **Ingestion**
   - Files scanned from configured directories
   - Content extracted via Tika / OCR

2. **Segmentation**
   - Large files split into logical chunks
   - Chunk boundaries stored in the database

3. **Enrichment**
   - LLM generates metadata:
     - Title
     - Summary
     - Tags

4. **Embedding**
   - Each chunk converted into a vector embedding
   - Stored in pgvector for semantic search

5. **Retrieval & Generation**
   - Search queries retrieve relevant chunks
   - LLM synthesizes responses from retrieved context

---

## 🗄️ Database Model (Conceptual)

- **Files** – Original documents
- **Entries** – Segmented chunks
- **Metadata** – LLM-generated enrichment
- **Embeddings** – Vector representations

The database is the system’s source of truth.

---

## 🧠 Model Roles

- **Chat model** – Summaries, Q&A
- **Embedding model** – Semantic similarity
- **Vision model** – Image descriptions

Models are interchangeable via environment variables.

---

## ⚙️ Extensibility

Advanced users can customize:
- Chunking strategy
- Metadata schema
- Ranking and retrieval logic
- UI presentation

Most extensions live in the worker pipeline.

---

## 🧭 Design Philosophy

- Local-first
- Transparent processing
- Inspectable data
- Composable architecture

Archive Brain favors **clarity over cleverness**.