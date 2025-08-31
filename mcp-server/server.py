"""
Home Assistant MCP Server
Model Context Protocol server for Home Assistant historical data
Version: 6.1
"""
import os
import asyncio
import sys
import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
import asyncpg
from asyncpg.pool import Pool

# FastAPI for SSE transport
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, Response
import uvicorn

# MCP imports - using the correct import paths
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG" else logging.INFO,
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
MCP_PORT = int(os.getenv("MCP_PORT", "8099"))

logger.info(f"📝 Log level: {logging.getLogger().level}")
logger.info(f"🗄️ Database: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
logger.info(f"🔒 Read-only: {READ_ONLY}")
logger.info(f"⏱️ Query timeout: {QUERY_TIMEOUT}s")
logger.info(f"📅 Max query days: {MAX_QUERY_DAYS}")

# Global database pool
db_pool: Optional[Pool] = None

# FastAPI app
app = FastAPI(title="Home Assistant MCP Server", version="6.1")

# Global MCP server instance
mcp_server_instance = None
connected_clients = set()

class HAMCPServer:
    """Home Assistant MCP Server Implementation"""
    
    def __init__(self):
        self.server = Server("ha-mcp-server")
        self.tools = []
        self._register_handlers()
        self._setup_tools()
    
    def _setup_tools(self):
        """Setup the tool definitions"""
        self.tools = [
            types.Tool(
                name="get_history",
                description="Query historical state data from Home Assistant recorder",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity to query (e.g., 'sensor.temperature')"
                        },
                        "start": {
                            "type": "string",
                            "description": "Start datetime in ISO format"
                        },
                        "end": {
                            "type": "string",
                            "description": "End datetime in ISO format"
                        },
                        "interval": {
                            "type": "string",
                            "enum": ["raw", "5m", "15m", "30m", "1h", "6h", "1d"],
                            "description": "Time interval for aggregation",
                            "default": "1h"
                        },
                        "aggregation": {
                            "type": "string",
                            "enum": ["mean", "min", "max", "sum", "last", "first"],
                            "description": "Aggregation method",
                            "default": "mean"
                        }
                    },
                    "required": ["entity_id", "start", "end"]
                }
            ),
            types.Tool(
                name="get_statistics",
                description="Query aggregated statistics data from Home Assistant",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "statistic_id": {
                            "type": "string",
                            "description": "The statistic to query"
                        },
                        "start": {
                            "type": "string",
                            "description": "Start datetime in ISO format"
                        },
                        "end": {
                            "type": "string",
                            "description": "End datetime in ISO format"
                        },
                        "period": {
                            "type": "string",
                            "enum": ["5minute", "hour", "day", "month"],
                            "description": "Statistics period",
                            "default": "hour"
                        }
                    },
                    "required": ["statistic_id", "start", "end"]
                }
            ),
            types.Tool(
                name="list_entities",
                description="List available entities and statistics for querying",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of items to return",
                            "default": 100,
                            "minimum": 1,
                            "maximum": 500
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Filter by entity type (e.g., 'sensor', 'binary_sensor')",
                            "default": None
                        }
                    }
                }
            ),
            types.Tool(
                name="health_check",
                description="Check server and database health status",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
    
    def _register_handlers(self):
        """Register all MCP handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """List available MCP tools"""
            return self.tools
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Handle tool calls"""
            try:
                if name == "get_history":
                    result = await self.get_history(**arguments)
                elif name == "get_statistics":
                    result = await self.get_statistics(**arguments)
                elif name == "list_entities":
                    result = await self.list_entities(**arguments)
                elif name == "health_check":
                    result = await self.health_check()
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}")
                return [types.TextContent(
                    type="text", 
                    text=json.dumps({"error": str(e)}, indent=2)
                )]
    
    async def get_history(
        self, 
        entity_id: str,
        start: str, 
        end: str,
        interval: str = "1h",
        aggregation: str = "mean"
    ) -> Dict[str, Any]:
        """Query historical state data"""
        logger.info(f"get_history: {entity_id} from {start} to {end}")
        
        # Validate date range
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            
            if (end_dt - start_dt).days > MAX_QUERY_DAYS:
                raise ValueError(f"Query range exceeds {MAX_QUERY_DAYS} days")
        except Exception as e:
            return {"error": f"Invalid date format: {e}"}
        
        # Use mock data if no database connection
        if not db_pool:
            logger.warning("Using mock data - no database connection")
            return {
                "entity_id": entity_id,
                "series": self.generate_mock_series(start, end, interval),
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
                
                # Handle raw data requests
                if interval == "raw":
                    query = """
                        SELECT 
                            last_updated_ts as timestamp,
                            state
                        FROM states
                        WHERE metadata_id = $1
                            AND last_updated_ts >= $2
                            AND last_updated_ts < $3
                            AND state NOT IN ('unknown', 'unavailable', '')
                        ORDER BY last_updated_ts
                        LIMIT 5000
                    """
                    rows = await conn.fetch(query, entity_meta['metadata_id'], 
                                           start_dt.timestamp(), end_dt.timestamp())
                    
                    series = []
                    for row in rows:
                        try:
                            # Try to convert to float, fallback to string
                            value = float(row['state']) if row['state'].replace('.','').replace('-','').isdigit() else row['state']
                            series.append({
                                "t": datetime.fromtimestamp(row['timestamp']).isoformat() + "Z",
                                "v": value
                            })
                        except (ValueError, AttributeError):
                            continue
                else:
                    # Aggregated query
                    interval_sql = {
                        "5m": "5 minutes", "15m": "15 minutes", "30m": "30 minutes",
                        "1h": "1 hour", "6h": "6 hours", "1d": "1 day"
                    }.get(interval, "1 hour")
                    
                    # Build aggregation function
                    if aggregation == "mean":
                        agg_func = "AVG"
                    elif aggregation == "sum": 
                        agg_func = "SUM"
                    elif aggregation == "min":
                        agg_func = "MIN"
                    elif aggregation == "max":
                        agg_func = "MAX"
                    elif aggregation == "last":
                        agg_func = "LAST"
                    elif aggregation == "first":
                        agg_func = "FIRST"
                    else:
                        agg_func = "AVG"
                    
                    if agg_func in ["LAST", "FIRST"]:
                        order = "DESC" if agg_func == "LAST" else "ASC"
                        query = f"""
                            SELECT 
                                date_trunc($1, to_timestamp(last_updated_ts)) as timestamp,
                                (array_agg(
                                    CASE WHEN state ~ '^-?[0-9]+\.?[0-9]*$' 
                                         THEN state::numeric 
                                         ELSE NULL END 
                                    ORDER BY last_updated_ts {order}
                                ))[1] as value
                            FROM states
                            WHERE metadata_id = $2
                                AND last_updated_ts >= $3
                                AND last_updated_ts < $4
                                AND state NOT IN ('unknown', 'unavailable', '')
                            GROUP BY date_trunc($1, to_timestamp(last_updated_ts))
                            ORDER BY timestamp
                        """
                    else:
                        query = f"""
                            SELECT 
                                date_trunc($1, to_timestamp(last_updated_ts)) as timestamp,
                                {agg_func}(CASE 
                                    WHEN state ~ '^-?[0-9]+\.?[0-9]*$' THEN state::numeric 
                                    ELSE NULL 
                                END) as value
                            FROM states
                            WHERE metadata_id = $2
                                AND last_updated_ts >= $3
                                AND last_updated_ts < $4
                                AND state NOT IN ('unknown', 'unavailable', '')
                            GROUP BY date_trunc($1, to_timestamp(last_updated_ts))
                            ORDER BY timestamp
                        """
                    
                    rows = await conn.fetch(query, interval_sql, entity_meta['metadata_id'], 
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
                    "aggregation": aggregation,
                    "query_time": datetime.utcnow().isoformat() + "Z"
                }
                
        except Exception as e:
            logger.error(f"Database error in get_history: {e}")
            return {
                "entity_id": entity_id,
                "error": str(e),
                "series": []
            }
    
    async def get_statistics(
        self,
        statistic_id: str,
        start: str,
        end: str,
        period: str = "hour"
    ) -> Dict[str, Any]:
        """Query aggregated statistics data"""
        logger.info(f"get_statistics: {statistic_id} from {start} to {end}")
        
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except Exception as e:
            return {"error": f"Invalid date format: {e}"}
        
        if not db_pool:
            # Generate mock statistics
            series = self.generate_mock_series(start, end, "1h" if period == "hour" else "1d")
            for item in series:
                value = item["v"]
                item.update({
                    "mean": value,
                    "min": value - 2,
                    "max": value + 2,
                    "sum": value * 1.5
                })
                del item["v"]
            
            return {
                "statistic_id": statistic_id,
                "series": series,
                "period": period,
                "mock_data": True
            }
        
        try:
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
                
                # Select appropriate table
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
                        "t": datetime.fromtimestamp(row['timestamp']).isoformat() + "Z"
                    }
                    
                    if row['mean'] is not None:
                        item["mean"] = float(row['mean'])
                    if row['min'] is not None:
                        item["min"] = float(row['min'])
                    if row['max'] is not None:
                        item["max"] = float(row['max'])
                    if row['sum'] is not None:
                        item["sum"] = float(row['sum'])
                    
                    series.append(item)
                
                return {
                    "statistic_id": statistic_id,
                    "source": meta['source'],
                    "unit": meta['unit_of_measurement'],
                    "series": series,
                    "count": len(series),
                    "period": period,
                    "query_time": datetime.utcnow().isoformat() + "Z"
                }
                
        except Exception as e:
            logger.error(f"Database error in get_statistics: {e}")
            return {
                "statistic_id": statistic_id,
                "error": str(e),
                "series": []
            }
    
    async def list_entities(self, limit: int = 100, entity_type: Optional[str] = None) -> Dict[str, Any]:
        """List available entities and statistics"""
        logger.info(f"list_entities: limit={limit}, type={entity_type}")
        
        if not db_pool:
            # Return mock entities
            mock_entities = [
                {"entity_id": "sensor.temperature", "last_seen": datetime.utcnow().isoformat() + "Z"},
                {"entity_id": "sensor.humidity", "last_seen": datetime.utcnow().isoformat() + "Z"},
                {"entity_id": "sensor.pressure", "last_seen": datetime.utcnow().isoformat() + "Z"},
                {"entity_id": "binary_sensor.door", "last_seen": datetime.utcnow().isoformat() + "Z"}
            ]
            
            mock_statistics = [
                {"statistic_id": "sensor.temperature", "unit": "°C", "source": "recorder"},
                {"statistic_id": "sensor.humidity", "unit": "%", "source": "recorder"}
            ]
            
            if entity_type:
                mock_entities = [e for e in mock_entities if e["entity_id"].startswith(entity_type + ".")]
            
            return {
                "entities": mock_entities[:limit],
                "statistics": mock_statistics[:limit],
                "mock_data": True
            }
        
        try:
            async with db_pool.acquire() as conn:
                # Build entity query with optional type filter
                entity_where = ""
                params = []
                param_idx = 1
                
                if entity_type:
                    entity_where = f"AND sm.entity_id LIKE ${param_idx}"
                    params.append(f"{entity_type}.%")
                    param_idx += 1
                
                # Add time constraint and limit
                params.extend([
                    (datetime.utcnow() - timedelta(days=7)).timestamp(),
                    limit
                ])
                
                query = f"""
                    SELECT DISTINCT
                        sm.entity_id,
                        MAX(s.last_updated_ts) as last_seen_ts
                    FROM states_meta sm
                    LEFT JOIN states s ON s.metadata_id = sm.metadata_id
                        AND s.last_updated_ts > ${param_idx-1}
                    WHERE 1=1 {entity_where}
                    GROUP BY sm.entity_id
                    HAVING MAX(s.last_updated_ts) IS NOT NULL
                    ORDER BY MAX(s.last_updated_ts) DESC
                    LIMIT ${param_idx}
                """
                
                rows = await conn.fetch(query, *params)
                
                entities = [{
                    "entity_id": row['entity_id'],
                    "last_seen": datetime.fromtimestamp(row['last_seen_ts']).isoformat() + "Z"
                } for row in rows]
                
                # Get available statistics
                stats_params = [limit]
                stats_where = ""
                if entity_type:
                    stats_where = f"WHERE statistic_id LIKE ${len(stats_params)+1}"
                    stats_params.append(f"{entity_type}.%")
                
                stats_query = f"""
                    SELECT 
                        statistic_id,
                        source,
                        unit_of_measurement
                    FROM statistics_meta
                    {stats_where}
                    ORDER BY statistic_id
                    LIMIT $1
                """
                
                stats_rows = await conn.fetch(stats_query, *stats_params)
                
                statistics = [{
                    "statistic_id": row['statistic_id'],
                    "source": row['source'],
                    "unit": row['unit_of_measurement']
                } for row in stats_rows]
                
                return {
                    "entities": entities,
                    "statistics": statistics,
                    "entity_count": len(entities),
                    "statistic_count": len(statistics),
                    "query_time": datetime.utcnow().isoformat() + "Z"
                }
                
        except Exception as e:
            logger.error(f"Database error in list_entities: {e}")
            return {
                "entities": [],
                "statistics": [],
                "error": str(e)
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check server and database health"""
        db_status = "disconnected"
        db_info = None
        
        if db_pool:
            try:
                async with db_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                    db_status = "healthy"
                    
                    # Get database info
                    version = await conn.fetchval("SELECT version()")
                    db_info = {
                        "version": version,
                        "host": DB_HOST,
                        "database": DB_NAME,
                        "read_only": READ_ONLY
                    }
                    
                    # Check TimescaleDB
                    if ENABLE_TIMESCALE:
                        try:
                            result = await conn.fetchval(
                                "SELECT COUNT(*) FROM pg_extension WHERE extname = 'timescaledb'"
                            )
                            db_info["timescaledb"] = result > 0
                        except:
                            db_info["timescaledb"] = False
                    
            except Exception as e:
                db_status = "unhealthy"
                db_info = {"error": str(e)}
        
        return {
            "status": "ok",
            "version": "6.1",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "database": {
                "status": db_status,
                "info": db_info
            },
            "configuration": {
                "read_only": READ_ONLY,
                "timescaledb": ENABLE_TIMESCALE,
                "query_timeout": QUERY_TIMEOUT,
                "max_query_days": MAX_QUERY_DAYS
            },
            "transport": "SSE",
            "connected_clients": len(connected_clients)
        }
    
    def generate_mock_series(self, start: str, end: str, interval: str = "1h") -> List[Dict]:
        """Generate mock time series data for testing"""
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except:
            # Fallback to current time
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(hours=24)
        
        # Determine interval in hours
        interval_hours = {
            "5m": 1/12, "15m": 0.25, "30m": 0.5,
            "1h": 1, "6h": 6, "1d": 24
        }.get(interval, 1)
        
        series = []
        current = start_dt
        value = 20.0
        
        while current < end_dt and len(series) < 1000:  # Limit series length
            series.append({
                "t": current.isoformat() + "Z",
                "v": round(value + (hash(str(current)) % 10) - 5, 2)
            })
            current += timedelta(hours=interval_hours)
            value += 0.1
        
        return series

# =============================================================================
# Database Connection Management
# =============================================================================

async def init_database_connection() -> bool:
    """Initialize database connection pool"""
    global db_pool
    
    try:
        logger.info("🔍 Testing database connection...")
        
        # Connection parameters
        conn_params = {
            "host": DB_HOST,
            "port": DB_PORT,
            "database": DB_NAME,
            "user": DB_USER,
            "command_timeout": QUERY_TIMEOUT,
            "server_settings": {
                'application_name': 'ha-mcp-server'
            }
        }
        
        # Add password if provided
        if DB_PASSWORD:
            conn_params["password"] = DB_PASSWORD
        
        # Create connection pool
        db_pool = await asyncpg.create_pool(
            min_size=2,
            max_size=10,
            **conn_params
        )
        
        # Test connection and get database info
        async with db_pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            logger.info(f"✅ Database connection successful")
            logger.info(f"📊 Database version: {version}")
            
            # Check for required tables
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                    AND table_name IN ('states', 'states_meta', 'statistics', 'statistics_meta')
            """)
            
            table_names = [row['table_name'] for row in tables]
            logger.info(f"📋 Found tables: {table_names}")
            
            if 'states' not in table_names:
                logger.warning("⚠️ 'states' table not found - using mock data")
            
            # Check TimescaleDB
            if ENABLE_TIMESCALE:
                try:
                    result = await conn.fetchval(
                        "SELECT COUNT(*) FROM pg_extension WHERE extname = 'timescaledb'"
                    )
                    if result > 0:
                        logger.info("✅ TimescaleDB extension found")
                    else:
                        logger.info("📝 TimescaleDB extension not installed")
                except Exception as e:
                    logger.warning(f"⚠️ Could not check TimescaleDB: {e}")
            
            # Set read-only mode if configured
            if READ_ONLY:
                await conn.execute("SET default_transaction_read_only = ON")
                logger.info("🔒 Read-only mode enabled")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.warning("🔄 Server will run in mock mode")
        return False

async def close_database_connection():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("🔌 Database connection closed")

# =============================================================================
# FastAPI Routes - SSE Transport + Web UI
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with information about the MCP server"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Home Assistant MCP Server v6.1</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: system-ui, -apple-system, sans-serif; margin: 2rem; line-height: 1.6; }
            .header { background: #1976d2; color: white; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; }
            .section { background: #f5f5f5; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; }
            .status { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.9rem; }
            .status.ok { background: #4caf50; color: white; }
            .tools { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }
            .tool { background: white; padding: 1rem; border-radius: 6px; border-left: 4px solid #2196f3; }
            code { background: #e8e8e8; padding: 0.2rem 0.4rem; border-radius: 3px; }
            .endpoint { font-family: monospace; background: #263238; color: #4fc3f7; padding: 0.5rem; border-radius: 4px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🛠️ Home Assistant MCP Server</h1>
            <p>Model Context Protocol server for historical data access</p>
            <p><strong>Version:</strong> 6.1 | <strong>Transport:</strong> SSE (Server-Sent Events)</p>
        </div>

        <div class="section">
            <h2>🔌 Integration URLs</h2>
            <p><strong>For Home Assistant MCP Client Integration:</strong></p>
            <ul>
                <li><strong>Primary:</strong> <code>http://homeassistant.local:8099/sse</code></li>
                <li><strong>Alternative:</strong> <code>http://localhost:8099/sse</code></li>
                <li><strong>Internal:</strong> <code>http://addon_mcp_server:8099/sse</code></li>
            </ul>
            <p><em>Use the SSE endpoint URL in MCP Client configuration</em></p>
        </div>

        <div class="section">
            <h2>📡 MCP Protocol Endpoints</h2>
            <p><strong>HA MCP Client:</strong> <span class="endpoint">GET /sse</span></p>
            <p><strong>General MCP:</strong> <span class="endpoint">GET /mcp</span></p>
            <p><strong>Tool Calls:</strong> <span class="endpoint">POST /mcp/call</span></p>
            <p><strong>Health Check:</strong> <span class="endpoint">GET /health</span></p>
            <p><strong>Test SSE:</strong> <a href="/sse" target="_blank">Open HA SSE Stream</a> | <a href="/mcp" target="_blank">Open Generic SSE</a></p>
        </div>

        <div class="section">
            <h2>🧰 Available MCP Tools</h2>
            <div class="tools">
                <div class="tool">
                    <h3>get_history</h3>
                    <p>Query historical state data from Home Assistant recorder with flexible aggregation options.</p>
                </div>
                <div class="tool">
                    <h3>get_statistics</h3>
                    <p>Retrieve statistical summaries (mean, min, max) from recorder database.</p>
                </div>
                <div class="tool">
                    <h3>list_entities</h3>
                    <p>Discover available entities and statistics with recent activity filtering.</p>
                </div>
                <div class="tool">
                    <h3>health_check</h3>
                    <p>Monitor server and database connectivity status.</p>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>🔌 Integration</h2>
            <p><strong>Home Assistant MCP Client:</strong></p>
            <ul>
                <li>Install the <strong>Model Context Protocol</strong> integration</li>
                <li>Configure SSE endpoint: <code>http://localhost:8099/mcp</code></li>
                <li>Tools automatically available to AI assistants</li>
            </ul>
        </div>

        <div class="section">
            <h2>📊 Server Status</h2>
            <p id="status">Loading...</p>
            <p><strong>Connected SSE Clients:</strong> <span id="clients">0</span></p>
        </div>

        <script>
            async function updateStatus() {
                try {
                    const response = await fetch('/health');
                    const health = await response.json();
                    document.getElementById('status').innerHTML = `
                        <span class="status ok">✅ ${health.status.toUpperCase()}</span>
                        Database: ${health.database.status} | 
                        Version: ${health.version} |
                        Transport: ${health.transport}
                    `;
                    document.getElementById('clients').textContent = health.connected_clients || 0;
                } catch (e) {
                    document.getElementById('status').innerHTML = '<span class="status error">❌ ERROR</span>';
                }
            }
            updateStatus();
            setInterval(updateStatus, 5000);
        </script>
    </body>
    </html>
    """

@app.get("/health")
async def health_endpoint():
    """Health check endpoint"""
    if mcp_server_instance:
        return await mcp_server_instance.health_check()
    return {"status": "error", "message": "MCP server not initialized"}

@app.options("/sse")
async def sse_options():
    """Handle CORS preflight requests for SSE endpoint"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Cache-Control,Content-Type,Authorization",
            "Access-Control-Max-Age": "86400"
        }
    )

@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSE endpoint specifically for Home Assistant MCP Client"""
    client_id = str(uuid.uuid4())
    connected_clients.add(client_id)
    
    logger.info(f"🔗 HA MCP Client connected via /sse: {client_id}")
    logger.info(f"🌍 Client headers: {dict(request.headers)}")
    
    async def generate_mcp_events():
        try:
            # Send initialization event
            init_event = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "ha-mcp-server",
                        "version": "6.1"
                    }
                }
            }
            yield f"data: {json.dumps(init_event)}\\n\\n"
            logger.info("🔄 Sent initialization event to HA MCP Client")
            
            # Send tools list
            if mcp_server_instance:
                tools_event = {
                    "jsonrpc": "2.0", 
                    "method": "tools/list",
                    "result": {
                        "tools": [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.inputSchema
                            }
                            for tool in mcp_server_instance.tools
                        ]
                    }
                }
                yield f"data: {json.dumps(tools_event)}\\n\\n"
                logger.info(f"🛠️ Sent {len(mcp_server_instance.tools)} tools to HA MCP Client")
            
            # Keep connection alive with pings
            sequence = 0
            while True:
                await asyncio.sleep(30)  # Ping every 30 seconds
                
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"🔌 HA MCP Client disconnected: {client_id}")
                    break
                    
                sequence += 1
                ping_event = {
                    "jsonrpc": "2.0",
                    "method": "ping", 
                    "params": {
                        "sequence": sequence,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                }
                yield f"data: {json.dumps(ping_event)}\\n\\n"
                logger.debug(f"🏓 Ping {sequence} sent to HA MCP Client {client_id}")
                
        except Exception as e:
            logger.error(f"SSE error for HA MCP Client {client_id}: {e}")
        finally:
            connected_clients.discard(client_id)
            logger.info(f"🔌 HA MCP Client removed: {client_id}")
    
    return StreamingResponse(
        generate_mcp_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control,Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

@app.options("/mcp")
async def mcp_options():
    """Handle CORS preflight requests"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Cache-Control,Content-Type,Authorization",
            "Access-Control-Max-Age": "86400"
        }
    )

@app.get("/mcp")
async def mcp_sse_endpoint(request: Request):
    """SSE endpoint for MCP protocol"""
    client_id = str(uuid.uuid4())
    connected_clients.add(client_id)
    
    logger.info(f"🔗 New SSE client connected: {client_id}")
    logger.info(f"🌍 Client headers: {dict(request.headers)}")
    
    async def generate_mcp_events():
        try:
            # Send initialization event
            init_event = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "ha-mcp-server",
                        "version": "6.1"
                    }
                }
            }
            yield f"data: {json.dumps(init_event)}\\n\\n"
            logger.info("🔄 Sent initialization event")
            
            # Send tools list
            if mcp_server_instance:
                tools_event = {
                    "jsonrpc": "2.0", 
                    "method": "tools/list",
                    "result": {
                        "tools": [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.inputSchema
                            }
                            for tool in mcp_server_instance.tools
                        ]
                    }
                }
                yield f"data: {json.dumps(tools_event)}\\n\\n"
                logger.info(f"🛠️ Sent {len(mcp_server_instance.tools)} tools")
            
            # Keep connection alive with pings
            sequence = 0
            while True:
                await asyncio.sleep(30)  # Ping every 30 seconds
                
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"🔌 SSE client disconnected: {client_id}")
                    break
                    
                sequence += 1
                ping_event = {
                    "jsonrpc": "2.0",
                    "method": "ping", 
                    "params": {
                        "sequence": sequence,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                }
                yield f"data: {json.dumps(ping_event)}\\n\\n"
                logger.debug(f"🏓 Ping {sequence} sent to {client_id}")
                
        except Exception as e:
            logger.error(f"SSE error for client {client_id}: {e}")
        finally:
            connected_clients.discard(client_id)
            logger.info(f"🔌 SSE client removed: {client_id}")
    
    return StreamingResponse(
        generate_mcp_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control,Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

@app.post("/mcp/call")
async def mcp_call_tool(request: dict):
    """Handle MCP tool calls via HTTP POST"""
    try:
        if not mcp_server_instance:
            raise HTTPException(status_code=500, detail="MCP server not initialized")
        
        method = request.get("method")
        params = request.get("params", {})
        
        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            # Call the tool
            handler = mcp_server_instance.server._handlers.get("call_tool")
            if handler:
                result = await handler(tool_name, arguments)
                
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {"content": result}
                }
            else:
                raise HTTPException(status_code=404, detail="Tool handler not found")
                
        elif method == "tools/list":
            handler = mcp_server_instance.server._handlers.get("list_tools") 
            if handler:
                tools = await handler()
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "tools": [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.inputSchema
                            }
                            for tool in tools
                        ]
                    }
                }
            else:
                raise HTTPException(status_code=404, detail="Tools handler not found")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown method: {method}")
            
    except Exception as e:
        logger.error(f"MCP call error: {e}")
        return {
            "jsonrpc": "2.0", 
            "id": request.get("id"),
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }

# =============================================================================
# Main Entry Point
# =============================================================================

async def startup_event():
    """Initialize everything on startup"""
    global mcp_server_instance
    
    logger.info("🚀 Starting Home Assistant MCP Server")
    logger.info("📦 Version: 6.1")
    logger.info("🔧 Using SSE transport with official MCP SDK")
    
    # Initialize database connection
    db_connected = await init_database_connection()
    
    if not db_connected:
        logger.warning("⚠️ Running in mock mode - database not available")
        logger.info("🎭 All queries will return mock data")
    else:
        logger.info("✅ Database connected - ready to serve real data")
    
    # Create MCP server instance
    mcp_server_instance = HAMCPServer()
    logger.info("🌐 MCP server initialized with SSE transport")
    logger.info(f"🔗 SSE endpoint: http://localhost:{MCP_PORT}/mcp")

async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down MCP Server...")
    await close_database_connection()
    logger.info("🛑 Server shutdown complete")

# Add startup and shutdown events
app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", shutdown_event)

if __name__ == "__main__":
    logger.info(f"🌐 Starting FastAPI server on port {MCP_PORT}")
    logger.info(f"🔗 Internal URLs to try in MCP Client:")
    logger.info(f"   - http://localhost:8099/mcp")
    logger.info(f"   - http://addon_mcp_server:8099/mcp")
    logger.info(f"   - http://a0d7b954-mcp-server:8099/mcp")
    logger.info(f"   - http://mcp-server:8099/mcp")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=MCP_PORT,
        log_level="info" if os.getenv("LOG_LEVEL", "INFO").upper() != "DEBUG" else "debug"
    )
