# Archive Brain

A personal document archive assistant that ingests, segments, enriches, and allows semantic search and RAG (Retrieval Augmented Generation) over your local document collection.

## Project Structure

- **backend/**: Python source code for ingestion, processing, and API.
  - **src/db**: Database models and connection logic.
  - **src/ingest**: File ingestion scripts.
  - **src/segment**: Document segmentation logic.
  - **src/enrich**: Metadata enrichment using LLMs.
  - **src/rag**: Retrieval and generation logic.
  - **alembic/**: Database migrations.
- **config/**: Configuration files.
- **docs/**: Project documentation.
- **docker-compose.yml**: Orchestration for DB, Tika, and Worker.

## Prerequisites

1.  **Docker & Docker Compose** installed.
2.  **Ollama** running locally (default: `http://localhost:11434`).
3.  **Network Drives**: If using network paths, ensure they are mounted in WSL/Linux at the expected paths (e.g., `/mnt/mediaboy/story`).

## Configuration

1.  Edit `config/config.yaml` to define your source directories and file extensions.
2.  Update `docker-compose.yml` volumes if you need to map new host paths to the container.

## Running the System

1.  **Start the Infrastructure**:
    ```bash
    docker compose up -d --build
    ```
    This starts Postgres, Tika, the API server (port 8000), and a background worker container.

2.  **Run the Ingestion Pipeline**:
    You can run these commands interactively or with `-d` for background execution.

    *   **Step 1: Ingest Files** (Scans folders, computes hashes, stores raw text)
        ```bash
        docker compose exec worker python -m src.ingest.ingest_files
        ```

    *   **Step 2: Segment** (Splits files into logical chunks)
        ```bash
        docker compose exec worker python -m src.segment.segment_entries
        ```

    *   **Step 3: Enrich** (Uses Ollama to generate titles, summaries, tags)
        *Warning: This is slow as it runs LLM inference for every entry.*
        ```bash
        docker compose exec -d worker python -m src.enrich.enrich_entries
        ```

    *   **Step 4: Embed** (Generates vector embeddings for search)
        ```bash
        docker compose exec worker python -m src.rag.embed_entries
        ```

3.  **Monitor Progress**:
    View logs for the worker container:
    ```bash
    docker compose logs -f worker
    ```

## Using the API

The API runs at `http://localhost:8000`.

*   **Ask a Question**:
    ```bash
    curl -X POST "http://localhost:8000/ask" \
         -H "Content-Type: application/json" \
         -d '{"query": "What did I write about in 2020?", "k": 5}'
    ```

*   **Health Check**:
    ```bash
    curl http://localhost:8000/health
    ```

## Tech Stack

- **Database**: Postgres (with pgvector)
- **Orchestration**: Docker Compose
- **Language**: Python
- **LLM**: Ollama (External/Host)
- **Extraction**: Apache Tika


