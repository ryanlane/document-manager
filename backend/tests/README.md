# Backend Tests

This directory contains the test suite for the Archive Brain backend.

## Testing Approach

**This test suite uses database-agnostic mocks for fast, isolated testing.**

Tests use `pytest-mock` and `unittest.mock` to mock database interactions, making them:
- ⚡ **Fast** - No real database connection needed
- 🔒 **Isolated** - No side effects between tests
- 🎯 **Simple** - No Docker containers or test databases required
- 🚀 **CI-friendly** - Can run anywhere without external dependencies

## Setup

Install test dependencies:

```bash
pip install -r requirements.txt
```

The following test packages are included:
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking utilities
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

- `conftest.py` - Shared fixtures and configuration using mocks
- `test_api_*.py` - API endpoint tests with mocked database
- `test_*.py` - Unit tests for modules with mocked dependencies

## Fixtures

### Database Fixtures

- `mock_db_session` - Mocked SQLAlchemy session (using MagicMock)
- `sample_file` - Mock RawFile object for testing
- `sample_entry` - Mock Entry object for testing
- `mock_setting` - Mock Setting object for testing

### API Fixtures

- `client` - FastAPI TestClient with mocked database dependency
- `mock_ollama_mode` - Enables mock mode for LLM calls

## Writing Tests

### Example API Test

```python
@pytest.mark.api
def test_list_files(client: TestClient, mock_db_session, sample_file):
    # Mock the database query
    mock_db_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [sample_file]
    mock_db_session.query.return_value.count.return_value = 1

    response = client.get("/api/files")
    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 1
```

### Example Unit Test

```python
@pytest.mark.unit
def test_get_setting(mock_db_session):
    # Mock database query to return None (not found)
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    value = get_setting(mock_db_session, "test_key")
    assert value == DEFAULT_SETTINGS.get("test_key")
```

### Using Mock Objects

```python
@pytest.mark.api
def test_with_mock_file(client: TestClient, mock_db_session):
    # Create a custom mock file
    mock_file = Mock()
    mock_file.id = 1
    mock_file.filename = "test.txt"
    mock_file.extension = ".txt"

    # Configure the mock session to return it
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_file

    response = client.get(f"/api/files/{mock_file.id}")
    assert response.status_code == 200
```

## Test Markers

Use markers to categorize tests:

```python
@pytest.mark.unit
def test_function():
    """Unit test with mocked dependencies."""
    pass

@pytest.mark.api
def test_endpoint():
    """API endpoint test."""
    pass

@pytest.mark.slow
def test_slow_operation():
    """Test that takes longer to run."""
    pass
```

## Docker Testing

To run tests in the Docker container:

```bash
docker-compose exec api pytest
```

To run with coverage:

```bash
docker-compose exec api pytest --cov=src --cov-report=term-missing
```

## Continuous Integration

The test suite is designed to run in CI environments with:
- No external dependencies (mocked database)
- Mock mode for LLM providers
- Fast execution (< 1 minute for full suite)
- No Docker or PostgreSQL required

## Coverage Goals

- **API Endpoints**: 80%+ coverage
- **Core Logic**: 90%+ coverage
- **Database Models**: 70%+ coverage

## Best Practices

1. **Isolation**: Each test should be independent and not affect others
2. **Fixtures**: Use fixtures from conftest.py for common setup
3. **Mocking**: Mock external dependencies (database, file system, HTTP calls)
4. **Assertions**: One logical assertion per test
5. **Naming**: Use descriptive test names that explain what is being tested
6. **Speed**: Keep tests fast by avoiding I/O operations
7. **Cleanup**: Mocks are automatically reset between tests

## Troubleshooting

### ImportError

If you get import errors, ensure you're running pytest from the backend directory:

```bash
cd backend
pytest
```

### Mock Configuration Issues

If your mocks aren't working as expected:
- Check the return value chain: `mock.query.return_value.filter.return_value.first.return_value`
- Use `MagicMock` for automatic handling of chained calls
- Verify the mock is being injected via the fixture

### AsyncIO Errors

For async tests, use `pytest-asyncio`:

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

## Mock Patterns

### Mocking Database Queries

```python
# Query that returns a single object
mock_db_session.query.return_value.filter.return_value.first.return_value = mock_object

# Query that returns a list
mock_db_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_obj1, mock_obj2]

# Count query
mock_db_session.query.return_value.count.return_value = 5

# Query that returns None (not found)
mock_db_session.query.return_value.filter.return_value.first.return_value = None
```

### Mocking Database Operations

```python
# Add operation
mock_db_session.add = MagicMock()

# Commit operation
mock_db_session.commit = MagicMock()

# Rollback operation (for testing errors)
mock_db_session.commit.side_effect = Exception("Database error")
mock_db_session.rollback = MagicMock()
```

## Why Mock-Based Testing?

We chose mock-based testing over a test database for several reasons:

1. **Speed**: No database connection overhead
2. **Simplicity**: No need to manage test database state
3. **Portability**: Tests run anywhere without PostgreSQL
4. **Focus**: Tests verify logic, not database functionality
5. **Modern Standard**: Industry best practice for unit tests

For integration tests that need real database interactions, consider using a separate test suite with a PostgreSQL test container.
