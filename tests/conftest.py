"""
Pytest configuration and shared fixtures
"""
import pytest
import sys
import os
from unittest.mock import MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp-server'))

# Configure pytest
pytest_plugins = []

def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )

@pytest.fixture(scope="session", autouse=True)
def mock_mcp_modules():
    """Mock MCP modules for all tests"""
    # Mock MCP modules before any imports
    mock_mcp = MagicMock()
    mock_fastmcp = MagicMock()
    
    # Create a mock FastMCP class
    class MockFastMCP:
        def __init__(self, name):
            self.name = name
            self.tools = {}
            
        def tool(self):
            """Decorator for registering tools"""
            def decorator(func):
                self.tools[func.__name__] = func
                return func
            return decorator
        
        async def run(self, read_stream, write_stream, options):
            """Mock run method"""
            pass
        
        def create_initialization_options(self):
            """Mock initialization options"""
            return {}
    
    mock_fastmcp.FastMCP = MockFastMCP
    
    sys.modules['mcp'] = mock_mcp
    sys.modules['mcp.server'] = mock_mcp
    sys.modules['mcp.server.stdio'] = mock_mcp
    sys.modules['mcp.server.fastmcp'] = mock_fastmcp
    
    yield
    
    # Cleanup
    for module in ['mcp', 'mcp.server', 'mcp.server.stdio', 'mcp.server.fastmcp']:
        if module in sys.modules:
            del sys.modules[module]

@pytest.fixture
def reset_server_state():
    """Reset server state between tests"""
    import server
    server.db_pool = None
    yield
    server.db_pool = None

@pytest.fixture
def mock_environment(monkeypatch):
    """Mock environment variables"""
    env_vars = {
        'PGHOST': 'localhost',
        'PGPORT': '5432',
        'PGDATABASE': 'test_db',
        'PGUSER': 'test_user',
        'PGPASSWORD': 'test_pass',
        'MCP_READ_ONLY': 'true',
        'MCP_ENABLE_TIMESCALEDB': 'false',
        'MCP_QUERY_TIMEOUT': '30',
        'MCP_MAX_QUERY_DAYS': '90'
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars
