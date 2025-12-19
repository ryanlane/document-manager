#!/bin/bash
# Convenience wrapper for common dev environment commands

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

case "${1:-help}" in
    up|start)
        echo "Starting dev environment..."
        docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev up -d
        
        # Wait for API to be ready, then ensure database is initialized
        echo "Waiting for API to be ready..."
        sleep 3
        docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev exec -T api-dev python -c "from src.db.init_db import init_db; init_db()" 2>/dev/null || true
        
        echo ""
        echo "Dev environment started!"
        echo "  - Frontend: http://localhost:3001"
        echo "  - API:      http://localhost:8001"
        echo "  - Database: localhost:5433"
        ;;
    down|stop)
        echo "Stopping dev environment..."
        docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev down
        ;;
    logs)
        docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev logs -f ${@:2}
        ;;
    restart)
        docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev restart ${@:2}
        ;;
    reset)
        "$SCRIPT_DIR/reset-dev.sh"
        ;;
    seed)
        "$SCRIPT_DIR/seed-dev.sh"
        ;;
    ps|status)
        docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev ps
        ;;
    exec)
        docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev exec ${@:2}
        ;;
    build)
        docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile dev build ${@:2}
        ;;
    help|*)
        echo "Development Environment Helper"
        echo ""
        echo "Usage: ./scripts/dev.sh <command>"
        echo ""
        echo "Commands:"
        echo "  up, start    Start the dev environment"
        echo "  down, stop   Stop the dev environment"
        echo "  logs         Follow logs (optionally specify service)"
        echo "  restart      Restart services"
        echo "  reset        Full reset with optional reseed"
        echo "  seed         Seed archive_dev with test data"
        echo "  ps, status   Show running containers"
        echo "  exec         Execute command in container"
        echo "  build        Rebuild containers"
        echo ""
        echo "Examples:"
        echo "  ./scripts/dev.sh up"
        echo "  ./scripts/dev.sh logs api-dev"
        echo "  ./scripts/dev.sh exec api-dev bash"
        echo "  ./scripts/dev.sh reset"
        ;;
esac
