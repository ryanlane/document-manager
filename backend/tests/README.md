# Backend Tests

This directory contains the test suite for the Archive Brain backend.

## Important Note

**The current models use PostgreSQL-specific types (JSONB, vector) which are not compatible with SQLite.**

For now, tests should be run against a PostgreSQL test database. Future improvements:
1. Use a separate test PostgreSQL database
2. Or use database-agnostic mocks for unit tests
3. Or create SQLite-compatible model variants for testing

## Setup

Install test dependencies:

```bash
pip install -r requirements.txt
```

The following test packages are included:
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `httpx` - HTTP client for testing FastAPI

## Running Tests

### Run all tests

```bash
pytest
```

### Run specific test file

```bash
pytest tests/test_api_files.py
```

### Run specific test function

```bash
pytest tests/test_api_files.py::test_list_files_empty
```

### Run with coverage

```bash
pytest --cov=src --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`.

### Run with verbose output

```bash
pytest -v
```

### Run tests by marker

```bash
# Run only API tests
pytest -m api

# Run only unit tests
pytest -m unit

# Skip slow tests
pytest -m "not slow"
```

## Test Organization

- `conftest.py` - Shared fixtures and configuration
- `test_api_*.py` - API endpoint tests
- `test_*.py` - Unit tests for modules

## Fixtures

### Database Fixtures

- `db_engine` - Test database engine (SQLite in-memory)
- `db_session` - Test database session
- `sample_file` - Sample RawFile for testing
- `sample_entry` - Sample Entry for testing

### API Fixtures

- `client` - FastAPI TestClient with database override
- `mock_ollama_mode` - Enables mock mode for LLM calls

## Writing Tests

### Example API Test

```python
def test_list_files(client: TestClient):
    response = client.get("/api/files")
    assert response.status_code == 200
    data = response.json()
    assert "files" in data
```

### Example Unit Test

```python
def test_setting_persistence(db_session: Session):
    set_setting(db_session, "test_key", "test_value")
    value = get_setting(db_session, "test_key")
    assert value == "test_value"
```

### Using Fixtures

```python
def test_with_sample_data(client: TestClient, sample_file):
    # sample_file is automatically created
    response = client.get(f"/api/files/{sample_file.id}")
    assert response.status_code == 200
```

## Test Markers

Use markers to categorize tests:

```python
@pytest.mark.unit
def test_function():
    pass

@pytest.mark.slow
def test_slow_operation():
    pass

@pytest.mark.api
def test_endpoint():
    pass
```

## Docker Testing

To run tests in the Docker container:

```bash
docker-compose exec api pytest
```

## Continuous Integration

The test suite is designed to run in CI environments with:
- In-memory SQLite database (no external dependencies)
- Mock mode for LLM providers
- Fast execution (< 1 minute for full suite)

## Coverage Goals

- **API Endpoints**: 80%+ coverage
- **Core Logic**: 90%+ coverage
- **Database Models**: 70%+ coverage

## Best Practices

1. **Isolation**: Each test should be independent
2. **Fixtures**: Use fixtures for common setup
3. **Assertions**: One logical assertion per test
4. **Naming**: Use descriptive test names
5. **Speed**: Keep tests fast (mock external services)
6. **Cleanup**: Tests should clean up after themselves

## Troubleshooting

### ImportError

If you get import errors, ensure you're running pytest from the backend directory:

```bash
cd backend
pytest
```

### Database Errors

Tests use SQLite in-memory database. If you see database errors, check:
- SQLAlchemy models are compatible with SQLite
- Foreign key constraints are properly defined
- Fixtures properly clean up after themselves

### AsyncIO Errors

For async tests, use `pytest-asyncio`:

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```
