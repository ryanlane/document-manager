#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ARCHIVE_DEV="$PROJECT_DIR/archive_dev"
FIXTURES_DIR="$PROJECT_DIR/test_fixtures"

echo -e "${YELLOW}Creating test dataset in archive_dev/...${NC}"

# Create folder structure
mkdir -p "$ARCHIVE_DEV/docs"
mkdir -p "$ARCHIVE_DEV/images"
mkdir -p "$ARCHIVE_DEV/mixed/subfolder/deep"
mkdir -p "$ARCHIVE_DEV/series"

# ============================================================================
# DOCS - Various text formats for extraction testing
# ============================================================================

cat > "$ARCHIVE_DEV/docs/welcome.md" << 'EOF'
# Welcome to Archive Brain

This is a test document for the Archive Brain system.

## Features

- Semantic search across your documents
- AI-powered enrichment with titles and summaries
- Support for multiple file formats

## Getting Started

1. Add your documents to a source folder
2. Configure your LLM settings
3. Let the system process your files
4. Search and explore!

---
*This is test content for development purposes.*
EOF

cat > "$ARCHIVE_DEV/docs/technical-notes.md" << 'EOF'
# Technical Architecture Notes

## Database Schema

The system uses PostgreSQL with pgvector for embedding storage.

### Key Tables

- `raw_files` - Source file metadata
- `entries` - Extracted text chunks
- `document_links` - Relationships between documents

## Processing Pipeline

1. **Ingest** - Discover and extract text from files
2. **Segment** - Split into manageable chunks
3. **Enrich** - Generate titles, summaries, tags
4. **Embed** - Create vector embeddings for search

## Performance Considerations

- Batch processing for efficiency
- GPU acceleration for embeddings
- Connection pooling for database access
EOF

cat > "$ARCHIVE_DEV/docs/meeting-notes.txt" << 'EOF'
Meeting Notes - Project Planning
Date: 2024-01-15
Attendees: Alice, Bob, Charlie

Action Items:
1. Alice to review the API documentation
2. Bob to set up the development environment
3. Charlie to prepare test datasets

Next meeting: January 22nd at 2pm

Notes:
- Discussed timeline for v1.0 release
- Need to prioritize search accuracy
- Consider adding batch export feature
EOF

cat > "$ARCHIVE_DEV/docs/recipe.txt" << 'EOF'
Chocolate Chip Cookies Recipe

Ingredients:
- 2 1/4 cups all-purpose flour
- 1 tsp baking soda
- 1 tsp salt
- 1 cup butter, softened
- 3/4 cup granulated sugar
- 3/4 cup packed brown sugar
- 2 large eggs
- 2 tsp vanilla extract
- 2 cups chocolate chips

Instructions:
1. Preheat oven to 375°F
2. Mix flour, baking soda, and salt
3. Beat butter and sugars until creamy
4. Add eggs and vanilla to butter mixture
5. Gradually blend in flour mixture
6. Stir in chocolate chips
7. Drop rounded tablespoons onto baking sheets
8. Bake 9 to 11 minutes or until golden brown

Makes about 5 dozen cookies.
EOF

cat > "$ARCHIVE_DEV/docs/research-paper.md" << 'EOF'
# The Impact of Large Language Models on Document Management

## Abstract

This paper explores how large language models (LLMs) are transforming 
the way we organize, search, and interact with document collections.

## Introduction

Traditional document management relied on manual tagging and keyword search.
With the advent of transformer-based models, we can now understand document
semantics and provide more intelligent retrieval.

## Methodology

We analyzed 10,000 documents across various domains using:
- Traditional keyword search (TF-IDF)
- Semantic search with embeddings
- Hybrid approaches

## Results

Semantic search showed 40% improvement in relevance for complex queries.
Hybrid approaches performed best overall, combining precision of keywords
with recall of semantic matching.

## Conclusion

LLM-powered document management represents a significant advancement,
particularly for large, heterogeneous document collections.

## References

1. Vaswani et al. "Attention Is All You Need" (2017)
2. Devlin et al. "BERT: Pre-training of Deep Bidirectional Transformers" (2019)
EOF

# ============================================================================
# IMAGES - For vision model testing (create placeholder text files for now)
# ============================================================================

echo "Placeholder for test image - sunset over mountains" > "$ARCHIVE_DEV/images/sunset.jpg.txt"
echo "Placeholder for test image - city skyline at night" > "$ARCHIVE_DEV/images/cityscape.png.txt"
echo "Placeholder for test image - technical diagram" > "$ARCHIVE_DEV/images/diagram.png.txt"

# Note: For real testing, copy actual images here
echo -e "${YELLOW}Note: Add real images to archive_dev/images/ for vision model testing${NC}"

# ============================================================================
# MIXED - Nested folder structure for hierarchy testing
# ============================================================================

cat > "$ARCHIVE_DEV/mixed/readme.md" << 'EOF'
# Mixed Content Folder

This folder contains various nested content for testing folder hierarchy handling.
EOF

cat > "$ARCHIVE_DEV/mixed/subfolder/notes.txt" << 'EOF'
These are notes in a subfolder.
Testing nested folder discovery.
EOF

cat > "$ARCHIVE_DEV/mixed/subfolder/deep/deeply-nested.md" << 'EOF'
# Deeply Nested Document

This document is several levels deep in the folder structure.
Used for testing path handling and folder traversal.
EOF

# Unicode filename test
cat > "$ARCHIVE_DEV/mixed/日本語ファイル.txt" << 'EOF'
This file has a Japanese filename.
Testing unicode path handling.
EOF

# Empty file test
touch "$ARCHIVE_DEV/mixed/empty-file.txt"

# ============================================================================
# SERIES - Book chapters for series detection testing
# ============================================================================

cat > "$ARCHIVE_DEV/series/chapter-01-introduction.md" << 'EOF'
# Chapter 1: Introduction

This is the first chapter of our test book series.
It introduces the main concepts and characters.

The story begins in a small village...
EOF

cat > "$ARCHIVE_DEV/series/chapter-02-rising-action.md" << 'EOF'
# Chapter 2: Rising Action

Following the events of the introduction, our protagonist
embarks on their journey.

The road ahead was long and uncertain...
EOF

cat > "$ARCHIVE_DEV/series/chapter-03-climax.md" << 'EOF'
# Chapter 3: The Climax

Everything comes together in this pivotal chapter.
Decisions are made that will change everything.

"This is the moment," she said...
EOF

cat > "$ARCHIVE_DEV/series/chapter-04-resolution.md" << 'EOF'
# Chapter 4: Resolution

The story reaches its conclusion.
Loose ends are tied up and lessons are learned.

And so it was that peace returned to the village...
EOF

# ============================================================================
# Summary
# ============================================================================

echo ""
echo -e "${GREEN}✅ Test dataset created!${NC}"
echo ""
echo "Contents:"
echo "  archive_dev/"
echo "  ├── docs/           (5 files - markdown and text)"
echo "  ├── images/         (3 placeholder files)"
echo "  ├── mixed/          (nested folders, unicode, edge cases)"
echo "  └── series/         (4 chapter files for series detection)"
echo ""
echo "Total: ~17 files, <50KB"
echo "Estimated processing time: <2 minutes with Fast Scan"
