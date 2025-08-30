"""
MCP Server for Home Assistant Historical Data
Version: 0.5.0 - Using official MCP SDK
"""
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging
import asyncpg
from asyncpg.pool import Pool
import mcp.server.stdio
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ha-mcp-server")

# Configuration from environment
DB_HOST = os.getenv("PGHOST", "127.0.0.1")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_NAME = os.getenv("PGDATABASE", "homeassistant")
DB_USER = os.getenv("PGUSER", "homeassistant")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
READ_ONLY = os.getenv("MCP_READ_ONLY", "true").lower() == "true"
ENABLE_TIMESCALE = os.getenv("MCP_ENABLE_TIMESCALEDB", "false").lower() == "true"
QUERY_TIMEOUT = int(os.getenv("MCP_QUERY_TIMEOUT", "30"))
MAX_QUERY_DAYS = int(os.getenv("MCP_MAX_QUERY_DAYS", "90"))

# Create MCP server instance
mcp = FastMCP("Home Assistant MCP Server")

# Database connection pool
db_pool: Optional[Pool] = None

# =============================================================================
# Database Connection Management
# =============================================================================

async def init_db_pool() -> bool:
    """Initialize database connection pool"""
    global db_pool
    try:
        logger.info(f"Connecting to PostgreSQL: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
        
        db_pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            min_size=2,
            max_size=10,
            command_timeout=QUERY_TIMEOUT,
            server_settings={
                'application_name': 'ha-mcp-server'
            }
        )
        
        # Test connection
        async with db_pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            logger.info(f"Connected to: {version}")
            
            if ENABLE_TIMESCALE:
                try:
                    result = await conn.fetchval(
                        "SELECT COUNT(*) FROM pg_extension WHERE extname = 'timescaledb'"
                    )
                    if result > 0:
                        logger.info("✅ TimescaleDB extension found")
                    else:
                        logger.warning("⚠️ TimescaleDB extension not installed")
                except Exception as e:
                    logger.warning(f"Could not check TimescaleDB: {e}")
                    
            # Set read-only mode if configured
            if READ_ONLY:
                await conn.execute("SET default_transaction_read_only = ON")
                logger.info("🔒 Read-only mode enabled")
                
        return True
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return False

async def close_db_pool():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed")

# =============================================================================
# Helper Functions for Data Processing
# =============================================================================

def generate_mock_series(start: str, end: str, interval: str = "1h") -> List[Dict]:
    """Generate mock time series data for testing"""
    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    
    # Determine interval in hours
    interval_hours = {
        "5m": 1/12, "15m": 0.25, "30m": 0.5,
        "1h": 1, "6h": 6, "1d": 24
    }.get(interval, 1)
    
    series = []
    current = start_dt
    value = 20.0
    
    while current < end_dt:
        series.append({
            "t": current.isoformat() + "Z",
            "v": round(value + (hash(str(current)) % 10) - 5, 2)
        })
        current += timedelta(hours=interval_hours)
        value += 0.1
    
    return series

# =============================================================================
# MCP Tool Implementations
# =============================================================================

@mcp.tool()
async def get_history(
    entity_id: str,
    start: str,
    end: str,
    interval: str = "1h",
    aggregation: str = "mean"
) -> Dict[str, Any]:
    """
    Query historical state data from Home Assistant recorder.
    
    Args:
        entity_id: The entity to query (e.g., 'sensor.temperature')
        start: Start datetime in ISO format
        end: End datetime in ISO format  
        interval: Time interval for aggregation (5m, 15m, 30m, 1h, 6h, 1d)
        aggregation: Aggregation method (raw, mean, min, max, sum, last)
    
    Returns:
        Historical data series with timestamps and values
    """
    logger.info(f"get_history called: {entity_id} from {start} to {end}")
    
    # Validate date range
    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    
    if (end_dt - start_dt).days > MAX_QUERY_DAYS:
        raise ValueError(f"Query range exceeds {MAX_QUERY_DAYS} days")
    
    if not db_pool:
        # Use mock data if no database
        logger.warning("Using mock data - no database connection")
        return {
            "entity_id": entity_id,
            "series": generate_mock_series(start, end, interval),
            "interval": interval,
            "aggregation": aggregation,
            "mock_data": True
        }
    
    try:
        async with db_pool.acquire() as conn:
            # Get entity metadata
            entity_meta = await conn.fetchrow("""
                SELECT metadata_id, entity_id 
                FROM states_meta 
                WHERE entity_id = $1
            """, entity_id)
            
            if not entity_meta:
                return {
                    "entity_id": entity_id,
                    "error": "Entity not found",
                    "series": []
                }
            
            # Query based on aggregation
            if aggregation == "raw":
                query = """
                    SELECT 
                        last_updated_ts as timestamp,
                        state
                    FROM states
                    WHERE metadata_id = $1
                        AND last_updated_ts >= $2
                        AND last_updated_ts < $3
                    ORDER BY last_updated_ts
                    LIMIT 5000
                """
                rows = await conn.fetch(query, entity_meta['metadata_id'], 
                                       start_dt.timestamp(), end_dt.timestamp())
                
                series = [{
                    "t": datetime.fromtimestamp(row['timestamp']).isoformat() + "Z",
                    "v": row['state']
                } for row in rows]
            else:
                # Aggregated query
                interval_map = {
                    "5m": "5 minutes", "15m": "15 minutes", "30m": "30 minutes",
                    "1h": "1 hour", "6h": "6 hours", "1d": "1 day"
                }
                pg_interval = interval_map.get(interval, "1 hour")
                
                agg_func = {
                    "mean": "AVG", "min": "MIN", "max": "MAX",
                    "sum": "SUM", "last": "LAST"
                }.get(aggregation, "AVG")
                
                if agg_func == "LAST":
                    query = f"""
                        SELECT 
                            date_trunc('hour', to_timestamp(last_updated_ts)) as timestamp,
                            (array_agg(state ORDER BY last_updated_ts DESC))[1] as value
                        FROM states
                        WHERE metadata_id = $1
                            AND last_updated_ts >= $2
                            AND last_updated_ts < $3
                            AND state NOT IN ('unknown', 'unavailable', '')
                        GROUP BY date_trunc('hour', to_timestamp(last_updated_ts))
                        ORDER BY timestamp
                    """
                else:
                    query = f"""
                        SELECT 
                            date_trunc('hour', to_timestamp(last_updated_ts)) as timestamp,
                            {agg_func}(CASE 
                                WHEN state ~ '^[0-9]+\.?[0-9]*$' THEN state::numeric 
                                ELSE NULL 
                            END) as value
                        FROM states
                        WHERE metadata_id = $1
                            AND last_updated_ts >= $2
                            AND last_updated_ts < $3
                            AND state NOT IN ('unknown', 'unavailable', '')
                        GROUP BY date_trunc('hour', to_timestamp(last_updated_ts))
                        ORDER BY timestamp
                    """
                
                rows = await conn.fetch(query, entity_meta['metadata_id'], 
                                       start_dt.timestamp(), end_dt.timestamp())
                
                series = [{
                    "t": row['timestamp'].isoformat() + "Z",
                    "v": float(row['value']) if row['value'] is not None else None
                } for row in rows if row.get('value') is not None]
            
            return {
                "entity_id": entity_id,
                "series": series,
                "count": len(series),
                "interval": interval,
                "aggregation": aggregation
            }
            
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return {
            "entity_id": entity_id,
            "error": str(e),
            "series": []
        }

@mcp.tool()
async def get_statistics(
    statistic_id: str,
    start: str,
    end: str,
    period: str = "hour"
) -> Dict[str, Any]:
    """
    Query aggregated statistics data.
    
    Args:
        statistic_id: The statistic to query
        start: Start datetime in ISO format
        end: End datetime in ISO format
        period: Statistics period (5minute, hour, day, month)
    
    Returns:
        Statistical data with mean, min, max values
    """
    logger.info(f"get_statistics called: {statistic_id}")
    
    if not db_pool:
        # Return mock data
        series = generate_mock_series(start, end, "1h" if period == "hour" else "1d")
        for item in series:
            value = item["v"]
            item.update({
                "mean": value,
                "min": value - 2,
                "max": value + 2
            })
        
        return {
            "statistic_id": statistic_id,
            "series": series,
            "period": period,
            "mock_data": True
        }
    
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        
        async with db_pool.acquire() as conn:
            # Get statistics metadata
            meta = await conn.fetchrow("""
                SELECT id, statistic_id, source, unit_of_measurement
                FROM statistics_meta
                WHERE statistic_id = $1
            """, statistic_id)
            
            if not meta:
                return {
                    "statistic_id": statistic_id,
                    "error": "Statistic not found",
                    "series": []
                }
            
            # Query statistics
            table = "statistics_short_term" if period == "5minute" else "statistics"
            
            query = f"""
                SELECT 
                    start_ts as timestamp,
                    mean, min, max, sum
                FROM {table}
                WHERE metadata_id = $1
                    AND start_ts >= $2
                    AND start_ts < $3
                ORDER BY start_ts
                LIMIT 5000
            """
            
            rows = await conn.fetch(query, meta['id'], 
                                   start_dt.timestamp(), end_dt.timestamp())
            
            series = []
            for row in rows:
                item = {
                    "t": datetime.fromtimestamp(row['timestamp']).isoformat() + "Z",
                    "mean": float(row['mean']) if row['mean'] is not None else None,
                    "min": float(row['min']) if row['min'] is not None else None,
                    "max": float(row['max']) if row['max'] is not None else None
                }
                if row['sum'] is not None:
                    item["sum"] = float(row['sum'])
                series.append(item)
            
            return {
                "statistic_id": statistic_id,
                "source": meta['source'],
                "unit": meta['unit_of_measurement'],
                "series": series,
                "count": len(series),
                "period": period
            }
            
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        return {
            "statistic_id": statistic_id,
            "error": str(e),
            "series": []
        }

@mcp.tool()
async def list_entities(limit: int = 100) -> Dict[str, Any]:
    """
    List available entities with recent data.
    
    Args:
        limit: Maximum number of entities to return
    
    Returns:
        List of entities and statistics available for querying
    """
    logger.info("list_entities called")
    
    if not db_pool:
        # Return mock entities
        return {
            "entities": [
                {"entity_id": "sensor.temperature", "last_seen": datetime.utcnow().isoformat() + "Z"},
                {"entity_id": "sensor.humidity", "last_seen": datetime.utcnow().isoformat() + "Z"},
                {"entity_id": "sensor.pressure", "last_seen": datetime.utcnow().isoformat() + "Z"}
            ],
            "statistics": [
                {"statistic_id": "sensor.temperature", "unit": "°C"},
                {"statistic_id": "sensor.humidity", "unit": "%"}
            ],
            "mock_data": True
        }
    
    try:
        async with db_pool.acquire() as conn:
            # Get entities with recent data
            query = """
                SELECT DISTINCT
                    sm.entity_id,
                    MAX(s.last_updated_ts) as last_seen_ts
                FROM states_meta sm
                LEFT JOIN states s ON s.metadata_id = sm.metadata_id
                    AND s.last_updated_ts > $1
                GROUP BY sm.entity_id
                HAVING MAX(s.last_updated_ts) IS NOT NULL
                ORDER BY MAX(s.last_updated_ts) DESC
                LIMIT $2
            """
            
            since = (datetime.utcnow() - timedelta(days=7)).timestamp()
            rows = await conn.fetch(query, since, limit)
            
            entities = [{
                "entity_id": row['entity_id'],
                "last_seen": datetime.fromtimestamp(row['last_seen_ts']).isoformat() + "Z"
            } for row in rows]
            
            # Get available statistics
            stats_query = """
                SELECT 
                    statistic_id,
                    source,
                    unit_of_measurement
                FROM statistics_meta
                ORDER BY statistic_id
                LIMIT $1
            """
            
            stats_rows = await conn.fetch(stats_query, limit)
            
            statistics = [{
                "statistic_id": row['statistic_id'],
                "source": row['source'],
                "unit": row['unit_of_measurement']
            } for row in stats_rows]
            
            return {
                "entities": entities,
                "statistics": statistics,
                "entity_count": len(entities),
                "statistic_count": len(statistics)
            }
            
    except Exception as e:
        logger.error(f"Error listing entities: {e}")
        return {
            "entities": [],
            "statistics": [],
            "error": str(e)
        }

@mcp.tool()
async def health_check() -> Dict[str, Any]:
    """
    Check server and database health status.
    
    Returns:
        Health status information
    """
    db_status = "disconnected"
    
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                db_status = "healthy"
        except:
            db_status = "unhealthy"
    
    return {
        "status": "ok",
        "version": "0.5.0",
        "database": db_status,
        "read_only": READ_ONLY,
        "timescaledb": ENABLE_TIMESCALE,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# =============================================================================
# Main Entry Point
# =============================================================================

async def main():
    """Main entry point for the MCP server"""
    logger.info("Starting Home Assistant MCP Server v0.5.0")
    logger.info("Using official MCP SDK")
    
    # Initialize database connection
    db_connected = await init_db_pool()
    if not db_connected:
        logger.warning("⚠️ Running in mock mode - database not connected")
        logger.info("Server will use mock data for all queries")
    else:
        logger.info("✅ Database connected successfully")
    
    try:
        # Run the MCP server using stdio transport
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await mcp.run(
                read_stream,
                write_stream,
                mcp.create_initialization_options()
            )
    finally:
        # Cleanup
        await close_db_pool()
        logger.info("Server shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
