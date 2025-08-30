# Testing Guide for MCP Server

This guide explains how to test the MCP Server in a development environment without Home Assistant or a database.

## Quick Start

```bash
# Install test dependencies
pip install -r test-requirements.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=mcp-server --cov-report=html
```

## Test Structure

```
tests/
├── conftest.py           # Shared fixtures and configuration
├── test_server.py        # Unit tests for server functions
├── test_mcp_protocol.py  # MCP protocol tests
└── test_client.py        # Integration test client
```

## Running Tests

### Using Make (Recommended)

```bash
# Install dependencies
make dev-install

# Run all tests
make test

# Run only unit tests
make test-unit

# Run only integration tests
make test-integration

# Run with coverage report
make test-coverage

# Run linting
make lint

# Format code
make format
```

### Using Pytest Directly

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_server.py -v

# Run specific test class
pytest tests/test_server.py::TestMCPTools -v

# Run specific test
pytest tests/test_server.py::TestMCPTools::test_get_history_no_database -v

# Run with markers
pytest tests/ -v -m "not integration"  # Skip integration tests
pytest tests/ -v -m "unit"             # Only unit tests

# Run with coverage
pytest tests/ -v --cov=mcp-server --cov-report=html
# Then open htmlcov/index.html in browser
```

### Using Test Client

The test client simulates MCP protocol communication:

```bash
# Run test client (uses mock data)
python test_client.py

# Run with verbose output
python test_client.py --verbose

# Specify server path
python test_client.py --server-path ./mcp-server/server.py
```

## Test Categories

### Unit Tests
- Test individual functions in isolation
- Mock database connections
- Fast execution
- Located in `test_server.py`

### Integration Tests
- Test complete workflows
- May use real database (if available)
- Slower execution
- Marked with `@pytest.mark.integration`

### Protocol Tests
- Test MCP protocol compliance
- Message serialization/deserialization
- Tool registration
- Located in `test_mcp_protocol.py`

## Mock Mode

The server automatically runs in mock mode when no database is available:

```python
# In tests, db_pool is set to None to trigger mock mode
server.db_pool = None

# Then all tool calls return mock data
result = await server.get_history(...)
assert result["mock_data"] is True
```

## Test Coverage

Current test coverage includes:

### Server Functions (test_server.py)
- ✅ `generate_mock_series()` - Mock data generation
- ✅ `init_db_pool()` - Database connection
- ✅ `close_db_pool()` - Connection cleanup
- ✅ `get_history()` - Historical data queries
- ✅ `get_statistics()` - Statistics queries
- ✅ `list_entities()` - Entity listing
- ✅ `health_check()` - Health status

### MCP Protocol (test_mcp_protocol.py)
- ✅ Tool registration
- ✅ Tool signatures
- ✅ Message format
- ✅ Error handling
- ✅ Serialization

### Edge Cases
- ✅ Database connection failures
- ✅ Entity not found
- ✅ Invalid date ranges
- ✅ Concurrent requests
- ✅ Large data sets

## GitHub Actions CI/CD

Tests run automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main`
- Manual workflow dispatch

The CI pipeline:
1. Tests on Python 3.9, 3.10, 3.11
2. Runs linting (black, flake8)
3. Runs unit tests with coverage
4. Runs integration tests
5. Builds Docker image
6. Security scanning with Trivy

## Local Development Workflow

1. **Make changes to code**

2. **Format code**
   ```bash
   make format
   ```

3. **Run linting**
   ```bash
   make lint
   ```

4. **Run tests**
   ```bash
   make test
   ```

5. **Check coverage**
   ```bash
   make test-coverage
   open htmlcov/index.html  # View coverage report
   ```

6. **Test with mock server**
   ```bash
   make run-mock
   ```

7. **Build and test Docker image**
   ```bash
   make docker-build
   make docker-run
   ```

## Writing New Tests

### Basic Test Structure

```python
import pytest
from unittest.mock import AsyncMock, patch
import server

class TestNewFeature:
    """Test new feature"""
    
    @pytest.mark.asyncio
    async def test_feature_with_mock_data(self):
        """Test feature with mock data"""
        server.db_pool = None  # Use mock mode
        
        result = await server.your_function(...)
        
        assert result["expected_key"] == "expected_value"
    
    @pytest.mark.asyncio
    async def test_feature_with_database(self, mock_db_pool, mock_connection):
        """Test feature with mocked database"""
        server.db_pool = mock_db_pool
        mock_connection.fetch = AsyncMock(return_value=[...])
        
        result = await server.your_function(...)
        
        assert result is not None
```

### Using Fixtures

```python
@pytest.fixture
def sample_data():
    """Provide sample data for tests"""
    return {
        "key": "value",
        "timestamp": "2024-12-19T00:00:00Z"
    }

def test_with_fixture(sample_data):
    """Test using fixture"""
    assert sample_data["key"] == "value"
```

### Testing Async Functions

```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async function"""
    result = await server.async_function()
    assert result is not None
```

## Debugging Tests

### Run with verbose output
```bash
pytest tests/ -v -s
```

### Run with debugger
```bash
pytest tests/ --pdb  # Drop into debugger on failure
```

### Run specific test with print statements
```bash
pytest tests/test_server.py::TestMCPTools::test_get_history_no_database -v -s
```

### Check test markers
```bash
pytest --markers
```

### List all tests
```bash
pytest --collect-only
```

## Performance Testing

### Run with profiling
```bash
pytest tests/ --profile --profile-svg
```

### Measure test duration
```bash
pytest tests/ --durations=10  # Show 10 slowest tests
```

## Troubleshooting

### Import Errors
If you get import errors, ensure the path is set correctly:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp-server'))
```

### Async Test Issues
Always use `@pytest.mark.asyncio` for async tests:
```python
@pytest.mark.asyncio
async def test_async():
    ...
```

### Mock MCP Module
The MCP module is automatically mocked in `conftest.py`. If you need to modify the mock:
```python
from unittest.mock import MagicMock
sys.modules['mcp'] = MagicMock()
```

### Database Mock Issues
Ensure database pool is set to None for mock mode:
```python
server.db_pool = None
```

## Coverage Goals

We aim for:
- **Overall**: >80% coverage
- **Critical paths**: 100% coverage
- **Error handling**: 100% coverage
- **Edge cases**: >90% coverage

Current coverage can be viewed by running:
```bash
make test-coverage
```

## Contributing Tests

When adding new features:
1. Write tests first (TDD)
2. Ensure >80% coverage for new code
3. Add both unit and integration tests
4. Document test purpose and expected behavior
5. Run full test suite before committing

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [AsyncIO Testing](https://pytest-asyncio.readthedocs.io/)
- [Mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Coverage.py](https://coverage.readthedocs.io/)
