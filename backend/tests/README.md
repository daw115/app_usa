# Tests

## Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest backend/tests/ -v

# Run specific test file
pytest backend/tests/test_cache.py -v

# Run with coverage
pytest backend/tests/ --cov=backend --cov-report=html
```

## Test Structure

- `test_routes.py` - API endpoint integration tests
- `test_cache.py` - Cache system unit tests
- `test_pricing.py` - Pricing calculation tests

## Writing Tests

Tests use pytest with FastAPI TestClient and in-memory SQLite database for isolation.
