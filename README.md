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

## Getting Started

1.  **Configure Sources**: Edit `config/config.yaml` to point to your document directories.
2.  **Start Infrastructure**:
    ```bash
    docker-compose up -d
    ```
3.  **Run Ingestion** (Coming soon):
    ```bash
    docker-compose run worker python -m src.ingest.ingest_files
    ```

## Tech Stack

- **Database**: Postgres (with pgvector)
- **Orchestration**: Docker Compose
- **Language**: Python
- **LLM**: Ollama (External/Host)
- **Extraction**: Apache Tika


