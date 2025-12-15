# Archive Brain

A personal document archive assistant that ingests, segments, enriches, and allows semantic search and RAG (Retrieval Augmented Generation) over your local document collection. Supports text files, PDFs, images (with OCR and AI vision descriptions), and more.

## 🚀 Quick Start

```bash
# Clone and start (self-contained with Ollama included)
docker compose up -d --build

# First run will pull LLM models (~4GB) - check progress:
docker compose logs -f ollama-init

# Access the app at http://localhost:3000
```

That's it! The system includes everything needed: PostgreSQL, Apache Tika, Ollama, and the application.

## Project Structure

- **backend/**: Python source code for ingestion, processing, and API.
  - **src/api**: FastAPI server
  - **src/db**: Database models and connection logic.
  - **src/ingest**: File ingestion scripts.
  - **src/segment**: Document segmentation logic.
  - **src/enrich**: Metadata enrichment using LLMs.
  - **src/rag**: Retrieval and generation logic.
  - **src/extract**: File content extraction (OCR, PDF, images)
- **frontend/**: React application
- **config/**: Configuration files.
- **docs/**: Project documentation.

## Prerequisites

1. **Docker & Docker Compose** installed.
2. **16GB+ RAM** recommended (Ollama needs ~8GB for models).
3. **Network Drives** (optional): If using network paths, ensure they are mounted at the expected paths.

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key settings:
- `OLLAMA_MODEL`: Chat model (default: `dolphin-phi`)
- `OLLAMA_EMBEDDING_MODEL`: Embedding model (default: `nomic-embed-text`)
- `OLLAMA_VISION_MODEL`: Vision model for images (default: `llava`)
- `DB_PASSWORD`: Database password

### Source Directories

Edit `config/config.yaml` to define your source directories and file extensions.

## 🖥️ Deployment Options

### Option 1: Self-Contained (Default - Recommended for SaaS)

Everything runs in Docker, including Ollama. Just works on any system:

```bash
docker compose up -d
```

### Option 2: With GPU Acceleration (NVIDIA)

If you have an NVIDIA GPU and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

### Option 3: External Ollama (Development)

Use Ollama running on your host machine (e.g., with GPU):

```bash
# Start Ollama on host with: OLLAMA_HOST=0.0.0.0 ollama serve
export OLLAMA_URL=http://host.docker.internal:11434
docker compose -f docker-compose.yml -f docker-compose.external-llm.yml up -d
```

## Running the System

The worker container automatically processes files through the pipeline:

1. **Ingest** → Scans folders, extracts text (including OCR for images/PDFs)
2. **Segment** → Splits into logical chunks
3. **Enrich** → LLM generates titles, summaries, tags
4. **Embed** → Creates vector embeddings for semantic search

**Monitor progress:**
```bash
docker compose logs -f worker
```

**Manual pipeline steps** (if needed):
```bash
docker compose exec worker python -m src.ingest.ingest_files
docker compose exec worker python -m src.segment.segment_entries
docker compose exec worker python -m src.enrich.enrich_entries
docker compose exec worker python -m src.rag.embed_entries
```

## Using the Application

### Web Interface

- **Home** (`http://localhost:3000`): Semantic search with filters
- **Dashboard**: Processing status and statistics
- **Files**: Browse all ingested documents
- **Gallery**: View images with AI descriptions
- **How It Works**: Learn about the RAG pipeline

### API Endpoints

The API runs at `http://localhost:8000`.

```bash
# Semantic search
curl -X POST "http://localhost:8000/search" \
     -H "Content-Type: application/json" \
     -d '{"query": "machine learning tutorials", "k": 10}'

# Ask a question (RAG)
curl -X POST "http://localhost:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{"query": "What did I write about in 2020?", "k": 5}'

# Health check
curl http://localhost:8000/health

# List available models
curl http://localhost:8000/models
```

## Supported File Types

| Type | Extensions | Features |
|------|------------|----------|
| Text | `.txt`, `.md`, `.html` | Full text extraction |
| PDF | `.pdf` | Text + OCR fallback |
| Images | `.jpg`, `.png`, `.gif`, `.webp`, `.bmp`, `.tiff` | OCR + AI vision descriptions |
| Documents | `.docx` (planned) | Coming soon |

## Tech Stack

- **Database**: PostgreSQL with pgvector
- **LLM**: Ollama (containerized or external)
- **Backend**: Python, FastAPI
- **Frontend**: React, Vite
- **Extraction**: Apache Tika, Tesseract OCR, PyMuPDF
- **Orchestration**: Docker Compose

## Troubleshooting

**Models not loading?**
```bash
# Check Ollama status
docker compose logs ollama
# Manually pull models
docker compose exec ollama ollama pull nomic-embed-text
```

**Out of memory?**
- Reduce model size: Set `OLLAMA_MODEL=tinyllama` in `.env`
- Or use external Ollama with GPU

**Images not being analyzed?**
- Check vision model: `docker compose exec ollama ollama list`
- Pull if missing: `docker compose exec ollama ollama pull llava`



