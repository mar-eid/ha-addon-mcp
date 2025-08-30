"""
Test MCP protocol communication
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp-server'))

# Mock MCP modules
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

import server

class TestMCPProtocol:
    """Test MCP protocol communication"""
    
    @pytest.mark.asyncio
    async def test_tool_registration(self):
        """Test that all tools are registered with MCP"""
        # Tools should be registered via decorator
        assert hasattr(server.mcp, 'tools')
        assert 'get_history' in server.mcp.tools
        assert 'get_statistics' in server.mcp.tools
        assert 'list_entities' in server.mcp.tools
        assert 'health_check' in server.mcp.tools
    
    @pytest.mark.asyncio
    async def test_tool_signatures(self):
        """Test tool function signatures"""
        # get_history should have correct parameters
        import inspect
        sig = inspect.signature(server.get_history)
        params = list(sig.parameters.keys())
        assert 'entity_id' in params
        assert 'start' in params
        assert 'end' in params
        assert 'interval' in params
        assert 'aggregation' in params
        
        # get_statistics should have correct parameters
        sig = inspect.signature(server.get_statistics)
        params = list(sig.parameters.keys())
        assert 'statistic_id' in params
        assert 'start' in params
        assert 'end' in params
        assert 'period' in params
    
    @pytest.mark.asyncio
    async def test_mcp_message_format(self):
        """Test MCP message format for tool calls"""
        server.db_pool = None
        
        # Simulate tool call
        result = await server.get_history(
            entity_id="sensor.test",
            start="2024-12-19T00:00:00Z",
            end="2024-12-19T01:00:00Z"
        )
        
        # Result should be serializable to JSON
        json_str = json.dumps(result)
        assert json_str is not None
        
        # Result should have expected structure
        assert 'entity_id' in result
        assert 'series' in result
        assert isinstance(result['series'], list)
    
    @pytest.mark.asyncio
    async def test_mcp_error_handling(self):
        """Test error handling in MCP protocol"""
        server.db_pool = None
        
        # Test with invalid date range
        try:
            await server.get_history(
                entity_id="sensor.test",
                start="2024-01-01T00:00:00Z",
                end="2024-12-31T23:59:59Z"  # Exceeds max days
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Query range exceeds" in str(e)

class TestMCPToolExecution:
    """Test MCP tool execution"""
    
    @pytest.mark.asyncio
    async def test_tool_execution_success(self):
        """Test successful tool execution"""
        server.db_pool = None
        
        # Execute each tool
        tools_to_test = [
            ('get_history', {
                'entity_id': 'sensor.test',
                'start': '2024-12-19T00:00:00Z',
                'end': '2024-12-19T01:00:00Z'
            }),
            ('get_statistics', {
                'statistic_id': 'sensor.test',
                'start': '2024-12-19T00:00:00Z',
                'end': '2024-12-19T01:00:00Z'
            }),
            ('list_entities', {}),
            ('health_check', {})
        ]
        
        for tool_name, args in tools_to_test:
            tool_func = server.mcp.tools.get(tool_name)
            assert tool_func is not None, f"Tool {tool_name} not found"
            
            result = await tool_func(**args)
            assert result is not None
            assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_tool_execution_with_mock_data(self):
        """Test tools return mock data when no database"""
        server.db_pool = None
        
        # Test get_history returns mock data
        result = await server.get_history(
            entity_id="sensor.test",
            start="2024-12-19T00:00:00Z",
            end="2024-12-19T06:00:00Z",
            interval="1h"
        )
        assert result.get('mock_data') is True
        assert len(result['series']) == 6
        
        # Test get_statistics returns mock data
        result = await server.get_statistics(
            statistic_id="sensor.test",
            start="2024-12-19T00:00:00Z",
            end="2024-12-19T06:00:00Z"
        )
        assert result.get('mock_data') is True
        
        # Test list_entities returns mock data
        result = await server.list_entities()
        assert result.get('mock_data') is True

class TestMCPServerLifecycle:
    """Test MCP server lifecycle"""
    
    @pytest.mark.asyncio
    async def test_server_initialization(self):
        """Test server initialization"""
        # Server should have MCP instance
        assert hasattr(server, 'mcp')
        assert server.mcp.name == "Home Assistant MCP Server"
    
    @pytest.mark.asyncio
    async def test_database_initialization_on_startup(self):
        """Test database initialization during startup"""
        with patch('server.init_db_pool') as mock_init:
            mock_init.return_value = True
            
            # Mock the stdio server context
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            
            with patch('mcp.server.stdio.stdio_server') as mock_stdio:
                mock_stdio.return_value.__aenter__ = AsyncMock(
                    return_value=(mock_read, mock_write)
                )
                mock_stdio.return_value.__aexit__ = AsyncMock()
                
                with patch.object(server.mcp, 'run', new_callable=AsyncMock):
                    try:
                        await asyncio.wait_for(server.main(), timeout=0.1)
                    except asyncio.TimeoutError:
                        pass  # Expected, as server.main() runs forever
                    
                    mock_init.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_server_cleanup_on_shutdown(self):
        """Test cleanup on server shutdown"""
        server.db_pool = AsyncMock()
        
        await server.close_db_pool()
        
        server.db_pool.close.assert_called_once()

class TestMCPMessageSerialization:
    """Test message serialization for MCP protocol"""
    
    def test_serialize_history_response(self):
        """Test serialization of history response"""
        response = {
            "entity_id": "sensor.temperature",
            "series": [
                {"t": "2024-12-19T00:00:00Z", "v": 20.5},
                {"t": "2024-12-19T01:00:00Z", "v": 21.0}
            ],
            "interval": "1h",
            "aggregation": "mean"
        }
        
        # Should serialize to JSON without errors
        json_str = json.dumps(response)
        assert json_str is not None
        
        # Should deserialize back correctly
        deserialized = json.loads(json_str)
        assert deserialized == response
    
    def test_serialize_error_response(self):
        """Test serialization of error response"""
        error_response = {
            "entity_id": "sensor.nonexistent",
            "error": "Entity not found",
            "series": []
        }
        
        json_str = json.dumps(error_response)
        assert json_str is not None
        
        deserialized = json.loads(json_str)
        assert deserialized["error"] == "Entity not found"
    
    def test_serialize_complex_response(self):
        """Test serialization of complex nested response"""
        complex_response = {
            "entities": [
                {"entity_id": "sensor.temp", "last_seen": "2024-12-19T00:00:00Z"},
                {"entity_id": "sensor.humidity", "last_seen": "2024-12-19T00:00:00Z"}
            ],
            "statistics": [
                {"statistic_id": "sensor.temp", "unit": "°C", "has_mean": True}
            ],
            "metadata": {
                "version": "0.5.0",
                "timestamp": "2024-12-19T00:00:00Z"
            }
        }
        
        json_str = json.dumps(complex_response)
        assert json_str is not None
        
        deserialized = json.loads(json_str)
        assert len(deserialized["entities"]) == 2
        assert deserialized["metadata"]["version"] == "0.5.0"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
