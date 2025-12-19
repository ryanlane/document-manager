#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}⚠️  This will DELETE all dev environment data.${NC}"
echo -e "${GREEN}✓ Production data is untouched.${NC}"
echo ""
echo "This will:"
echo "  - Stop all dev containers"
echo "  - Remove dev database volume (postgres_data_dev)"
echo "  - Clear archive_dev folder"
echo "  - Optionally reseed with test data"
echo ""
read -p "Continue? [y/N] " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || exit 1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo ""
echo -e "${YELLOW}Stopping dev containers...${NC}"
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev down 2>/dev/null || true

echo -e "${YELLOW}Removing dev volumes...${NC}"
docker volume rm document-manager_postgres_data_dev 2>/dev/null || true
docker volume rm document-manager_worker_shared_dev 2>/dev/null || true
# Note: We keep ollama_models_dev to avoid re-downloading models

echo -e "${YELLOW}Clearing archive_dev folder...${NC}"
rm -rf ./archive_dev/*
mkdir -p ./archive_dev

echo ""
read -p "Seed with test data? [Y/n] " seed_confirm
if [[ ! "$seed_confirm" =~ ^[Nn]$ ]]; then
    echo -e "${YELLOW}Seeding test data...${NC}"
    "$SCRIPT_DIR/seed-dev.sh"
fi

echo ""
read -p "Start dev environment now? [Y/n] " start_confirm
if [[ ! "$start_confirm" =~ ^[Nn]$ ]]; then
    echo -e "${YELLOW}Starting dev environment...${NC}"
    docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev up -d
    echo ""
    echo -e "${GREEN}✅ Dev environment is starting!${NC}"
    echo ""
    echo "Access points:"
    echo "  - Frontend: http://localhost:3001"
    echo "  - API:      http://localhost:8001"
    echo "  - Database: localhost:5433"
    echo ""
    echo "View logs with:"
    echo "  docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev logs -f"
else
    echo ""
    echo -e "${GREEN}✅ Dev environment reset complete!${NC}"
    echo ""
    echo "Start with:"
    echo "  docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev up -d"
fi
