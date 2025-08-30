"""
Test suite for Home Assistant MCP Server
Tests work without database or Home Assistant
"""
import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp-server'))

# Mock the MCP imports before importing server
sys.modules['mcp'] = MagicMock()
sys.modules['mcp.server'] = MagicMock()
sys.modules['mcp.server.stdio'] = MagicMock()
sys.modules['mcp.server.fastmcp'] = MagicMock()

from mcp.server.fastmcp import FastMCP

# Now import our server module
import server

# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    return pool

@pytest.fixture
def mock_connection():
    """Mock database connection"""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value="PostgreSQL 14.5")
    conn.fetchrow = AsyncMock()
    conn.fetch = AsyncMock()
    conn.execute = AsyncMock()
    return conn

@pytest.fixture
def sample_entity_data():
    """Sample entity data for testing"""
    return {
        "entity_id": "sensor.temperature",
        "metadata_id": 123,
        "last_seen": datetime.utcnow().timestamp()
    }

@pytest.fixture
def sample_history_data():
    """Sample history data for testing"""
    base_time = datetime.utcnow()
    return [
        {
            "timestamp": (base_time - timedelta(hours=i)).timestamp(),
            "state": str(20.0 + i * 0.5)
        }
        for i in range(24)
    ]

@pytest.fixture
def sample_statistics_data():
    """Sample statistics data for testing"""
    base_time = datetime.utcnow()
    return [
        {
            "timestamp": (base_time - timedelta(hours=i)).timestamp(),
            "mean": 22.0 + i * 0.1,
            "min": 20.0 + i * 0.1,
            "max": 24.0 + i * 0.1,
            "sum": 528.0
        }
        for i in range(24)
    ]

# =============================================================================
# Unit Tests
# =============================================================================

class TestHelperFunctions:
    """Test helper functions"""
    
    def test_generate_mock_series(self):
        """Test mock series generation"""
        start = "2024-12-19T00:00:00Z"
        end = "2024-12-19T06:00:00Z"
        
        series = server.generate_mock_series(start, end, "1h")
        
        assert len(series) == 6
        assert all("t" in item and "v" in item for item in series)
        assert series[0]["t"].startswith("2024-12-19T00")
        assert isinstance(series[0]["v"], float)
    
    def test_generate_mock_series_different_intervals(self):
        """Test mock series with different intervals"""
        start = "2024-12-19T00:00:00Z"
        end = "2024-12-19T01:00:00Z"
        
        # Test 5-minute intervals
        series_5m = server.generate_mock_series(start, end, "5m")
        assert len(series_5m) == 12  # 60 minutes / 5 minutes
        
        # Test 15-minute intervals
        series_15m = server.generate_mock_series(start, end, "15m")
        assert len(series_15m) == 4  # 60 minutes / 15 minutes
        
        # Test daily intervals
        start_day = "2024-12-01T00:00:00Z"
        end_day = "2024-12-08T00:00:00Z"
        series_1d = server.generate_mock_series(start_day, end_day, "1d")
        assert len(series_1d) == 7  # 7 days

class TestDatabaseConnection:
    """Test database connection management"""
    
    @pytest.mark.asyncio
    async def test_init_db_pool_success(self, mock_connection):
        """Test successful database pool initialization"""
        with patch('asyncpg.create_pool') as mock_create_pool:
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_connection)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock()
            mock_create_pool.return_value = mock_pool
            
            result = await server.init_db_pool()
            
            assert result is True
            assert server.db_pool is not None
            mock_create_pool.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_init_db_pool_failure(self):
        """Test database pool initialization failure"""
        with patch('asyncpg.create_pool') as mock_create_pool:
            mock_create_pool.side_effect = Exception("Connection failed")
            
            result = await server.init_db_pool()
            
            assert result is False
            assert server.db_pool is None
    
    @pytest.mark.asyncio
    async def test_close_db_pool(self, mock_db_pool):
        """Test closing database pool"""
        server.db_pool = mock_db_pool
        
        await server.close_db_pool()
        
        mock_db_pool.close.assert_called_once()

class TestMCPTools:
    """Test MCP tool functions"""
    
    @pytest.mark.asyncio
    async def test_get_history_no_database(self):
        """Test get_history with no database (mock mode)"""
        server.db_pool = None
        
        result = await server.get_history(
            entity_id="sensor.test",
            start="2024-12-19T00:00:00Z",
            end="2024-12-19T12:00:00Z",
            interval="1h",
            aggregation="mean"
        )
        
        assert result["entity_id"] == "sensor.test"
        assert result["mock_data"] is True
        assert len(result["series"]) == 12
        assert result["interval"] == "1h"
        assert result["aggregation"] == "mean"
    
    @pytest.mark.asyncio
    async def test_get_history_with_database(self, mock_db_pool, mock_connection, sample_entity_data, sample_history_data):
        """Test get_history with database connection"""
        server.db_pool = mock_db_pool
        mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_db_pool.acquire.return_value.__aexit__ = AsyncMock()
        
        # Mock entity metadata query
        mock_connection.fetchrow = AsyncMock(side_effect=[
            {"metadata_id": 123, "entity_id": "sensor.temperature"},  # Entity exists
        ])
        
        # Mock history data query
        mock_connection.fetch = AsyncMock(return_value=[
            {"timestamp": item["timestamp"], "value": float(item["state"])}
            for item in sample_history_data
        ])
        
        result = await server.get_history(
            entity_id="sensor.temperature",
            start="2024-12-19T00:00:00Z",
            end="2024-12-19T12:00:00Z",
            interval="1h",
            aggregation="mean"
        )
        
        assert result["entity_id"] == "sensor.temperature"
        assert "error" not in result
        assert isinstance(result["series"], list)
    
    @pytest.mark.asyncio
    async def test_get_history_entity_not_found(self, mock_db_pool, mock_connection):
        """Test get_history when entity doesn't exist"""
        server.db_pool = mock_db_pool
        mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_db_pool.acquire.return_value.__aexit__ = AsyncMock()
        
        # Entity not found
        mock_connection.fetchrow = AsyncMock(return_value=None)
        
        result = await server.get_history(
            entity_id="sensor.nonexistent",
            start="2024-12-19T00:00:00Z",
            end="2024-12-19T12:00:00Z"
        )
        
        assert result["entity_id"] == "sensor.nonexistent"
        assert result["error"] == "Entity not found"
        assert result["series"] == []
    
    @pytest.mark.asyncio
    async def test_get_history_date_range_validation(self):
        """Test date range validation in get_history"""
        server.db_pool = None
        
        # Test exceeding max days
        with pytest.raises(ValueError, match="Query range exceeds"):
            await server.get_history(
                entity_id="sensor.test",
                start="2024-01-01T00:00:00Z",
                end="2024-12-31T00:00:00Z"  # Almost a year
            )
    
    @pytest.mark.asyncio
    async def test_get_statistics_no_database(self):
        """Test get_statistics with no database"""
        server.db_pool = None
        
        result = await server.get_statistics(
            statistic_id="sensor.test",
            start="2024-12-19T00:00:00Z",
            end="2024-12-19T12:00:00Z",
            period="hour"
        )
        
        assert result["statistic_id"] == "sensor.test"
        assert result["mock_data"] is True
        assert len(result["series"]) > 0
        assert all("mean" in item and "min" in item and "max" in item for item in result["series"])
    
    @pytest.mark.asyncio
    async def test_list_entities_no_database(self):
        """Test list_entities with no database"""
        server.db_pool = None
        
        result = await server.list_entities(limit=10)
        
        assert result["mock_data"] is True
        assert len(result["entities"]) > 0
        assert len(result["statistics"]) > 0
        assert all("entity_id" in e for e in result["entities"])
        assert all("statistic_id" in s for s in result["statistics"])
    
    @pytest.mark.asyncio
    async def test_health_check_no_database(self):
        """Test health_check with no database"""
        server.db_pool = None
        
        result = await server.health_check()
        
        assert result["status"] == "ok"
        assert result["version"] == "0.5.0"
        assert result["database"] == "disconnected"
        assert result["read_only"] is True
    
    @pytest.mark.asyncio
    async def test_health_check_with_database(self, mock_db_pool, mock_connection):
        """Test health_check with database"""
        server.db_pool = mock_db_pool
        mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_db_pool.acquire.return_value.__aexit__ = AsyncMock()
        mock_connection.fetchval = AsyncMock(return_value=1)
        
        result = await server.health_check()
        
        assert result["status"] == "ok"
        assert result["database"] == "healthy"

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.mark.asyncio
    async def test_get_history_database_error(self, mock_db_pool, mock_connection):
        """Test database error handling in get_history"""
        server.db_pool = mock_db_pool
        mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_db_pool.acquire.return_value.__aexit__ = AsyncMock()
        mock_connection.fetchrow = AsyncMock(side_effect=Exception("Database error"))
        
        result = await server.get_history(
            entity_id="sensor.test",
            start="2024-12-19T00:00:00Z",
            end="2024-12-19T12:00:00Z"
        )
        
        assert "error" in result
        assert "Database error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_get_statistics_invalid_period(self):
        """Test get_statistics with different periods"""
        server.db_pool = None
        
        # Test 5minute period
        result = await server.get_statistics(
            statistic_id="sensor.test",
            start="2024-12-19T00:00:00Z",
            end="2024-12-19T01:00:00Z",
            period="5minute"
        )
        assert result["period"] == "5minute"
        
        # Test month period
        result = await server.get_statistics(
            statistic_id="sensor.test",
            start="2024-12-01T00:00:00Z",
            end="2024-12-31T00:00:00Z",
            period="month"
        )
        assert result["period"] == "month"
    
    @pytest.mark.asyncio
    async def test_list_entities_with_limit(self, mock_db_pool, mock_connection):
        """Test list_entities respects limit parameter"""
        server.db_pool = mock_db_pool
        mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_db_pool.acquire.return_value.__aexit__ = AsyncMock()
        
        # Mock entity query with 5 results
        mock_connection.fetch = AsyncMock(side_effect=[
            [{"entity_id": f"sensor.test_{i}", "last_seen_ts": datetime.utcnow().timestamp()} 
             for i in range(5)],
            []  # Empty statistics
        ])
        
        result = await server.list_entities(limit=5)
        
        assert len(result["entities"]) == 5

# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the complete flow"""
    
    @pytest.mark.asyncio
    async def test_full_workflow_mock_mode(self):
        """Test complete workflow in mock mode"""
        server.db_pool = None
        
        # 1. Check health
        health = await server.health_check()
        assert health["status"] == "ok"
        assert health["database"] == "disconnected"
        
        # 2. List entities
        entities = await server.list_entities()
        assert len(entities["entities"]) > 0
        entity_id = entities["entities"][0]["entity_id"]
        
        # 3. Get history for an entity
        history = await server.get_history(
            entity_id=entity_id,
            start="2024-12-19T00:00:00Z",
            end="2024-12-19T06:00:00Z",
            interval="1h",
            aggregation="mean"
        )
        assert history["entity_id"] == entity_id
        assert len(history["series"]) == 6
        
        # 4. Get statistics
        if entities["statistics"]:
            stat_id = entities["statistics"][0]["statistic_id"]
            stats = await server.get_statistics(
                statistic_id=stat_id,
                start="2024-12-19T00:00:00Z",
                end="2024-12-19T06:00:00Z",
                period="hour"
            )
            assert stats["statistic_id"] == stat_id
            assert len(stats["series"]) > 0

# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance and load tests"""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling multiple concurrent requests"""
        server.db_pool = None
        
        # Create multiple concurrent requests
        tasks = []
        for i in range(10):
            tasks.append(server.get_history(
                entity_id=f"sensor.test_{i}",
                start="2024-12-19T00:00:00Z",
                end="2024-12-19T01:00:00Z",
                interval="5m"
            ))
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks)
        
        # Verify all completed successfully
        assert len(results) == 10
        assert all(r["entity_id"].startswith("sensor.test_") for r in results)
        assert all(r["mock_data"] is True for r in results)
    
    @pytest.mark.asyncio
    async def test_large_date_range(self):
        """Test handling large date ranges within limits"""
        server.db_pool = None
        
        # Test maximum allowed range (90 days by default)
        result = await server.get_history(
            entity_id="sensor.test",
            start="2024-10-01T00:00:00Z",
            end="2024-12-30T00:00:00Z",  # 89 days
            interval="1d"
        )
        
        assert result["entity_id"] == "sensor.test"
        assert len(result["series"]) == 89

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
