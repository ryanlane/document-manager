# Dependency Management

## Pinned Requirements

This project uses **pinned dependencies** in `requirements.txt` to ensure reproducible builds across different environments and prevent "works on my machine" issues.

## Current Versions (as of January 2026)

- Python: 3.11
- FastAPI: 0.128.0
- SQLAlchemy: 2.0.45
- PostgreSQL Client: psycopg2-binary 2.9.11
- Pydantic: 2.12.5

See `requirements.txt` for the complete list of pinned dependencies.

## Updating Dependencies

### To update a single package:

```bash
# Update the package in the container
docker compose exec api pip install --upgrade <package-name>

# Get the new version
docker compose exec api pip freeze | grep <package-name>

# Update requirements.txt with the new version
```

### To update all dependencies:

```bash
# Generate a new freeze file with current versions
docker compose exec api pip freeze > backend/requirements-frozen.txt

# Review the changes and update requirements.txt accordingly
```

### To verify no conflicts exist:

```bash
docker compose exec api pip check
```

## Testing After Updates

After updating any dependencies:

1. Restart the containers: `docker compose restart`
2. Run the test suite: `docker compose exec api pytest`
3. Verify the API works: `curl http://localhost:8000/health`
4. Test key functionality (search, ingestion, etc.)

## Development Dependencies

All dependencies (including test frameworks) are in `requirements.txt` since this project doesn't separate dev/prod dependencies. This simplifies Docker builds and ensures consistent environments.

## Why Pinned Versions?

- **Reproducibility**: Same versions across dev, staging, and production
- **Stability**: Prevents unexpected breaking changes from automatic updates
- **Security**: Easier to track and update specific vulnerable packages
- **Debugging**: Eliminates "different versions" as a variable when troubleshooting
