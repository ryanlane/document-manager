"""
Constants and Configuration Values for Archive Brain

This module centralizes magic numbers and configuration constants used throughout
the application to improve maintainability and reduce duplication.
"""

# ============================================================================
# Embedding and Vector Search Constants
# ============================================================================

# Embedding vector dimensions for nomic-embed-text and similar models
EMBEDDING_DIMENSIONS = 768

# Maximum text length for document summaries and chunks
MAX_TEXT_LENGTH = 4000  # ~1000 tokens

# Maximum characters for embedding input (prevents context length errors)
EMBEDDING_MAX_CHARS = 8000

# ============================================================================
# Database Partitioning Constants
# ============================================================================

# Number of author buckets for database partitioning
# Author keys are hashed and modulo this value for distribution
AUTHOR_BUCKET_COUNT = 128

# ============================================================================
# Batch Processing Constants
# ============================================================================

# Batch size for parallel entry embedding
EMBED_BATCH_SIZE = 10

# Batch size for document-level embedding
DOC_EMBED_BATCH_SIZE = 50

# Batch size for entry enrichment (metadata extraction)
ENRICH_BATCH_SIZE = 100

# Batch size for document enrichment (summary generation)
DOC_ENRICH_BATCH_SIZE = 20

# Batch size for metadata inheritance from documents to entries
INHERIT_BATCH_SIZE = 500

# ============================================================================
# Search and Ranking Constants
# ============================================================================

# Reciprocal Rank Fusion (RRF) constant for hybrid search
# Standard value used in information retrieval literature
RRF_K = 60

# Default number of search results to return
DEFAULT_SEARCH_RESULTS = 10

# Default vector weight for hybrid search (0.0 = keyword only, 1.0 = vector only)
DEFAULT_VECTOR_WEIGHT = 0.7

# ============================================================================
# Retry and Timeout Constants
# ============================================================================

# Number of retry attempts for embedding operations
EMBEDDING_RETRY_ATTEMPTS = 2

# Base delay in seconds for embedding retry (uses exponential backoff)
EMBEDDING_RETRY_BASE_DELAY_S = 0.25

# ============================================================================
# File Processing Constants
# ============================================================================

# Target maximum characters per text segment/chunk
MAX_ENTRY_LENGTH = 4000

# Minimum chunk size for text segmentation
MIN_CHUNK_SIZE = 100

# Thumbnail image dimensions (width x height)
THUMBNAIL_SIZE = (300, 300)

# JPEG quality for thumbnail generation (0-100)
THUMBNAIL_QUALITY = 85
