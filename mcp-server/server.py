"""
MCP Server for Home Assistant Historical Data
Version: 0.4.1
"""
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
import logging
import asyncpg
from asyncpg.pool import Pool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp-server")

# Configuration from environment
DB_HOST = os.getenv("PGHOST", "127.0.0.1")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_NAME = os.getenv("PGDATABASE", "homeassistant")
DB_USER = os.getenv("PGUSER", "homeassistant")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
READ_ONLY = os.getenv("MCP_READ_ONLY", "true").lower() == "true"
ENABLE_TIMESCALE = os.getenv("MCP_ENABLE_TIMESCALEDB", "false").lower() == "true"
PORT = int(os.getenv("MCP_PORT", "8099"))
QUERY_TIMEOUT = int(os.getenv("MCP_QUERY_TIMEOUT", "30"))
MAX_QUERY_DAYS = int(os.getenv("MCP_MAX_QUERY_DAYS", "90"))

app = FastAPI(
    title="Home Assistant MCP Server",
    version="0.4.1",
    description="Model Context Protocol server for Home Assistant historical data"
)

# Database connection pool
db_pool: Optional[Pool] = None

# =============================================================================
# Database Models & Connection
# =============================================================================

async def init_db_pool():
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
        
        # Test connection and check for TimescaleDB
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
# Pydantic Models for MCP Protocol
# =============================================================================

class MCPRequest(BaseModel):
    """Base MCP request model"""
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: str
    params: Optional[Dict[str, Any]] = None

class MCPResponse(BaseModel):
    """Base MCP response model"""
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

class HistoryRequest(BaseModel):
    """Request model for historical data queries"""
    entity_id: str = Field(..., description="Entity ID to query")
    start: str = Field(..., description="Start datetime (ISO format)")
    end: str = Field(..., description="End datetime (ISO format)")
    interval: Optional[str] = Field("1h", description="Downsample interval (5m, 1h, 1d)")
    agg: Optional[Literal["raw", "last", "mean", "min", "max", "sum"]] = Field("mean", description="Aggregation method")
    significant_changes_only: Optional[bool] = Field(True, description="Filter to significant changes")

class StatisticsRequest(BaseModel):
    """Request model for statistics queries"""
    statistic_id: str = Field(..., description="Statistic ID to query")
    start: str = Field(..., description="Start datetime (ISO format)")
    end: str = Field(..., description="End datetime (ISO format)")
    period: Literal["5minute", "hour", "day", "month"] = Field("hour", description="Statistics period")
    fields: Optional[List[Literal["mean", "min", "max", "sum", "state"]]] = Field(["mean"], description="Fields to return")

class StatisticsBulkRequest(BaseModel):
    """Request model for bulk statistics queries"""
    statistic_ids: List[str] = Field(..., description="List of statistic IDs")
    start: str = Field(..., description="Start datetime (ISO format)")
    end: str = Field(..., description="End datetime (ISO format)")
    period: Literal["5minute", "hour", "day", "month"] = Field("hour", description="Statistics period")
    fields: Optional[List[Literal["mean", "min", "max", "sum", "state"]]] = Field(["mean", "max", "min"], description="Fields to return")
    page_size: int = Field(1000, description="Results per page", ge=1, le=5000)
    page: int = Field(0, description="Page number", ge=0)

# =============================================================================
# MCP Tool Implementations
# =============================================================================

async def get_history_data(params: HistoryRequest) -> Dict[str, Any]:
    """Fetch historical state data from recorder"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        # Parse dates
        start_dt = datetime.fromisoformat(params.start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(params.end.replace("Z", "+00:00"))
        
        # Validate date range
        if (end_dt - start_dt).days > MAX_QUERY_DAYS:
            raise HTTPException(status_code=400, detail=f"Query range exceeds {MAX_QUERY_DAYS} days")
        
        async with db_pool.acquire() as conn:
            # Get entity metadata
            entity_meta = await conn.fetchrow("""
                SELECT metadata_id, entity_id 
                FROM states_meta 
                WHERE entity_id = $1
            """, params.entity_id)
            
            if not entity_meta:
                return {"entity_id": params.entity_id, "series": [], "error": "Entity not found"}
            
            # Build query based on aggregation
            if params.agg == "raw":
                query = """
                    SELECT 
                        last_updated_ts as timestamp,
                        state,
                        attributes
                    FROM states
                    WHERE metadata_id = $1
                        AND last_updated_ts >= $2
                        AND last_updated_ts < $3
                    ORDER BY last_updated_ts
                    LIMIT 10000
                """
                rows = await conn.fetch(query, entity_meta['metadata_id'], 
                                       start_dt.timestamp(), end_dt.timestamp())
            else:
                # Use time buckets for aggregation
                interval_map = {
                    "5m": "5 minutes",
                    "15m": "15 minutes",
                    "30m": "30 minutes",
                    "1h": "1 hour",
                    "6h": "6 hours",
                    "1d": "1 day"
                }
                pg_interval = interval_map.get(params.interval, "1 hour")
                
                agg_func = {
                    "mean": "AVG",
                    "min": "MIN",
                    "max": "MAX",
                    "sum": "SUM",
                    "last": "LAST"
                }.get(params.agg, "AVG")
                
                if agg_func == "LAST":
                    query = f"""
                        SELECT 
                            date_trunc('hour', to_timestamp(last_updated_ts)) as timestamp,
                            (array_agg(state ORDER BY last_updated_ts DESC))[1] as state,
                            COUNT(*) as samples
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
                            END) as value,
                            COUNT(*) as samples
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
            
            # Format results
            series = []
            for row in rows:
                if params.agg == "raw":
                    series.append({
                        "t": datetime.fromtimestamp(row['timestamp']).isoformat() + "Z",
                        "v": row['state'],
                        "a": json.loads(row['attributes']) if row['attributes'] else None
                    })
                else:
                    value = row.get('value') or row.get('state')
                    if value is not None:
                        series.append({
                            "t": row['timestamp'].isoformat() + "Z",
                            "v": float(value) if isinstance(value, (int, float)) else value,
                            "samples": row['samples']
                        })
            
            return {
                "entity_id": params.entity_id,
                "series": series,
                "count": len(series),
                "interval": params.interval,
                "aggregation": params.agg
            }
            
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_statistics_data(params: StatisticsRequest) -> Dict[str, Any]:
    """Fetch statistics data"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        start_dt = datetime.fromisoformat(params.start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(params.end.replace("Z", "+00:00"))
        
        if (end_dt - start_dt).days > MAX_QUERY_DAYS:
            raise HTTPException(status_code=400, detail=f"Query range exceeds {MAX_QUERY_DAYS} days")
        
        async with db_pool.acquire() as conn:
            # Get statistics metadata
            meta = await conn.fetchrow("""
                SELECT id, statistic_id, source, unit_of_measurement
                FROM statistics_meta
                WHERE statistic_id = $1
            """, params.statistic_id)
            
            if not meta:
                return {"statistic_id": params.statistic_id, "series": [], "error": "Statistic not found"}
            
            # Build field selection
            fields = ["start_ts as timestamp"]
            for field in params.fields:
                fields.append(f"{field}")
            
            # Determine table based on period
            table = "statistics_short_term" if params.period == "5minute" else "statistics"
            
            query = f"""
                SELECT {', '.join(fields)}
                FROM {table}
                WHERE metadata_id = $1
                    AND start_ts >= $2
                    AND start_ts < $3
                ORDER BY start_ts
                LIMIT 5000
            """
            
            rows = await conn.fetch(query, meta['id'], 
                                   start_dt.timestamp(), end_dt.timestamp())
            
            # Format results
            series = []
            for row in rows:
                item = {"t": datetime.fromtimestamp(row['timestamp']).isoformat() + "Z"}
                for field in params.fields:
                    if field in row and row[field] is not None:
                        item[field] = float(row[field])
                series.append(item)
            
            return {
                "statistic_id": params.statistic_id,
                "source": meta['source'],
                "unit": meta['unit_of_measurement'],
                "series": series,
                "count": len(series),
                "period": params.period
            }
            
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_statistics_bulk(params: StatisticsBulkRequest) -> Dict[str, Any]:
    """Fetch bulk statistics data"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        start_dt = datetime.fromisoformat(params.start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(params.end.replace("Z", "+00:00"))
        
        if (end_dt - start_dt).days > MAX_QUERY_DAYS:
            raise HTTPException(status_code=400, detail=f"Query range exceeds {MAX_QUERY_DAYS} days")
        
        results = {}
        async with db_pool.acquire() as conn:
            for stat_id in params.statistic_ids:
                # Get metadata
                meta = await conn.fetchrow("""
                    SELECT id, statistic_id, source, unit_of_measurement
                    FROM statistics_meta
                    WHERE statistic_id = $1
                """, stat_id)
                
                if not meta:
                    results[stat_id] = {"error": "Not found"}
                    continue
                
                # Build query
                fields = ["start_ts as timestamp"] + list(params.fields)
                table = "statistics_short_term" if params.period == "5minute" else "statistics"
                
                query = f"""
                    SELECT {', '.join(fields)}
                    FROM {table}
                    WHERE metadata_id = $1
                        AND start_ts >= $2
                        AND start_ts < $3
                    ORDER BY start_ts
                    LIMIT $4 OFFSET $5
                """
                
                rows = await conn.fetch(
                    query, meta['id'], 
                    start_dt.timestamp(), end_dt.timestamp(),
                    params.page_size, params.page * params.page_size
                )
                
                # Format results
                series = []
                for row in rows:
                    item = {"t": datetime.fromtimestamp(row['timestamp']).isoformat() + "Z"}
                    for field in params.fields:
                        if field in row and row[field] is not None:
                            item[field] = float(row[field])
                    series.append(item)
                
                results[stat_id] = {
                    "source": meta['source'],
                    "unit": meta['unit_of_measurement'],
                    "series": series,
                    "count": len(series)
                }
        
        return {
            "items": results,
            "page": params.page,
            "page_size": params.page_size,
            "next_page": params.page + 1 if any(len(r.get("series", [])) == params.page_size for r in results.values()) else None
        }
        
    except Exception as e:
        logger.error(f"Error fetching bulk statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# MCP Protocol Endpoints
# =============================================================================

@app.post("/mcp")
async def mcp_handler(request: Request):
    """Main MCP protocol handler"""
    try:
        body = await request.json()
        mcp_request = MCPRequest(**body)
        
        # Route to appropriate tool
        if mcp_request.method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "ha.get_history",
                        "description": "Query historical state data from Home Assistant recorder",
                        "inputSchema": HistoryRequest.schema()
                    },
                    {
                        "name": "ha.get_statistics",
                        "description": "Query aggregated statistics data",
                        "inputSchema": StatisticsRequest.schema()
                    },
                    {
                        "name": "ha.get_statistics_bulk",
                        "description": "Query multiple statistics in bulk",
                        "inputSchema": StatisticsBulkRequest.schema()
                    },
                    {
                        "name": "ha.list_entities",
                        "description": "List available entities with recent data",
                        "inputSchema": {}
                    }
                ]
            }
        elif mcp_request.method == "tools/call":
            tool_name = mcp_request.params.get("name")
            tool_params = mcp_request.params.get("arguments", {})
            
            if tool_name == "ha.get_history":
                result = await get_history_data(HistoryRequest(**tool_params))
            elif tool_name == "ha.get_statistics":
                result = await get_statistics_data(StatisticsRequest(**tool_params))
            elif tool_name == "ha.get_statistics_bulk":
                result = await get_statistics_bulk(StatisticsBulkRequest(**tool_params))
            elif tool_name == "ha.list_entities":
                result = await list_entities()
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
        else:
            raise ValueError(f"Unknown method: {mcp_request.method}")
        
        return MCPResponse(
            jsonrpc="2.0",
            id=mcp_request.id,
            result=result
        ).dict()
        
    except Exception as e:
        logger.error(f"MCP handler error: {e}")
        return MCPResponse(
            jsonrpc="2.0",
            id=body.get("id") if "body" in locals() else None,
            error={
                "code": -32603,
                "message": str(e)
            }
        ).dict()

# =============================================================================
# REST API Endpoints (for compatibility and testing)
# =============================================================================

@app.get("/health")
async def health():
    """Health check endpoint"""
    db_status = "connected" if db_pool else "disconnected"
    
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                db_status = "healthy"
        except:
            db_status = "unhealthy"
    
    return {
        "status": "ok",
        "version": "0.4.1",
        "database": db_status,
        "read_only": READ_ONLY,
        "timescaledb": ENABLE_TIMESCALE,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.post("/tools/ha.get_history")
async def rest_get_history(req: HistoryRequest):
    """REST endpoint for history queries"""
    return await get_history_data(req)

@app.post("/tools/ha.get_statistics")
async def rest_get_statistics(req: StatisticsRequest):
    """REST endpoint for statistics queries"""
    return await get_statistics_data(req)

@app.post("/tools/ha.get_statistics_bulk")
async def rest_get_statistics_bulk(req: StatisticsBulkRequest):
    """REST endpoint for bulk statistics queries"""
    return await get_statistics_bulk(req)

@app.get("/tools/ha.list_entities")
async def list_entities(limit: int = 100):
    """List available entities with recent data"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        async with db_pool.acquire() as conn:
            # Get entities with recent data
            query = """
                SELECT DISTINCT
                    sm.entity_id,
                    sm.metadata_id,
                    COUNT(s.state_id) as state_count,
                    MAX(s.last_updated_ts) as last_seen_ts
                FROM states_meta sm
                LEFT JOIN states s ON s.metadata_id = sm.metadata_id
                    AND s.last_updated_ts > $1
                GROUP BY sm.entity_id, sm.metadata_id
                HAVING MAX(s.last_updated_ts) IS NOT NULL
                ORDER BY MAX(s.last_updated_ts) DESC
                LIMIT $2
            """
            
            # Look for entities with data in the last 7 days
            since = (datetime.utcnow() - timedelta(days=7)).timestamp()
            rows = await conn.fetch(query, since, limit)
            
            entities = []
            for row in rows:
                entities.append({
                    "entity_id": row['entity_id'],
                    "state_count": row['state_count'],
                    "last_seen": datetime.fromtimestamp(row['last_seen_ts']).isoformat() + "Z"
                })
            
            # Also get available statistics
            stats_query = """
                SELECT 
                    statistic_id,
                    source,
                    unit_of_measurement,
                    has_mean,
                    has_sum
                FROM statistics_meta
                ORDER BY statistic_id
                LIMIT $1
            """
            
            stats_rows = await conn.fetch(stats_query, limit)
            
            statistics = []
            for row in stats_rows:
                statistics.append({
                    "statistic_id": row['statistic_id'],
                    "source": row['source'],
                    "unit": row['unit_of_measurement'],
                    "has_mean": row['has_mean'],
                    "has_sum": row['has_sum']
                })
            
            return {
                "entities": entities,
                "statistics": statistics,
                "entity_count": len(entities),
                "statistic_count": len(statistics)
            }
            
    except Exception as e:
        logger.error(f"Error listing entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Application Lifecycle
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Starting MCP Server v0.4.1")
    success = await init_db_pool()
    if not success:
        logger.warning("⚠️ Running in mock mode - database not connected")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down MCP Server")
    await close_db_pool()

# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    try:
        logger.info(f"Starting server on port {PORT}")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=PORT,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
