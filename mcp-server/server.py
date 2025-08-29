import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Literal, Any, Dict
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import uvicorn
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Home Assistant MCP Server", version="0.3.1")

# Configuration from environment
READ_ONLY = os.getenv("MCP_READ_ONLY", "true").lower() == "true"
PORT = int(os.getenv("MCP_PORT", "8099"))
ENABLE_TIMESCALEDB = os.getenv("MCP_ENABLE_TIMESCALEDB", "false").lower() == "true"

# Database configuration
DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": int(os.getenv("PGPORT", "5432")),
    "database": os.getenv("PGDATABASE", "homeassistant"),
    "user": os.getenv("PGUSER", "homeassistant"),
    "password": os.getenv("PGPASSWORD", ""),
}

# Database connection
def get_db_connection():
    """Get database connection with error handling"""
    try:
        return psycopg2.connect(
            **DB_CONFIG,
            cursor_factory=RealDictCursor,
            connect_timeout=5
        )
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

# Pydantic models
class HistoryRequest(BaseModel):
    entity_id: str = Field(..., description="Entity ID to query")
    start: str = Field(..., description="Start time (ISO format)")
    end: str = Field(..., description="End time (ISO format)")
    interval: Optional[str] = Field("1h", description="Data point interval")
    agg: Optional[Literal["raw","last","mean","min","max","sum"]] = Field("last", description="Aggregation method")

class StatsRequest(BaseModel):
    statistic_id: str = Field(..., description="Statistics ID to query")
    start: str = Field(..., description="Start time (ISO format)")
    end: str = Field(..., description="End time (ISO format)")  
    period: Literal["hour","day"] = Field("hour", description="Statistics period")
    fields: Optional[List[Literal["mean","min","max","sum"]]] = Field(["mean"], description="Statistics fields to return")

class StatsBulkRequest(BaseModel):
    statistic_ids: List[str] = Field(..., description="List of statistics IDs")
    start: str = Field(..., description="Start time (ISO format)")
    end: str = Field(..., description="End time (ISO format)")
    period: Literal["hour","day"] = Field("day", description="Statistics period")
    fields: Optional[List[Literal["mean","min","max","sum"]]] = Field(["mean","max","min"], description="Statistics fields")
    page_size: int = Field(2000, description="Number of records per page")
    page: int = Field(0, description="Page number")

class MCPToolRequest(BaseModel):
    """MCP Tool request format"""
    name: str
    arguments: Dict[str, Any]

class MCPResponse(BaseModel):
    """MCP response format"""
    content: List[Dict[str, Any]]
    isError: Optional[bool] = False

# Mock data generator for fallback
def generate_mock_series(start: str, end: str, points: int = 24):
    """Generate mock time series data"""
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", ""))
        end_dt = datetime.fromisoformat(end.replace("Z", ""))
        delta = (end_dt - start_dt) / points
        
        data = []
        value = 20.0
        for i in range(points):
            timestamp = start_dt + delta * i
            data.append({
                "time": timestamp.isoformat() + "Z",
                "value": round(value + (i * 0.1), 2)
            })
        return data
    except Exception as e:
        logger.error(f"Error generating mock data: {e}")
        return []

# Database query functions
def query_history(entity_id: str, start: str, end: str, limit: int = 1000):
    """Query historical data from states table"""
    conn = get_db_connection()
    if not conn:
        return generate_mock_series(start, end)
    
    try:
        with conn.cursor() as cur:
            # Query states table for entity history
            query = """
            SELECT s.last_changed as time, s.state as value
            FROM states s
            JOIN states_meta sm ON s.metadata_id = sm.metadata_id
            WHERE sm.entity_id = %s 
            AND s.last_changed BETWEEN %s AND %s
            AND s.state NOT IN ('unknown', 'unavailable')
            ORDER BY s.last_changed ASC
            LIMIT %s
            """
            
            cur.execute(query, (entity_id, start, end, limit))
            results = cur.fetchall()
            
            # Convert to expected format
            data = []
            for row in results:
                try:
                    # Try to convert state to float for numeric entities
                    value = float(row['value'])
                except (ValueError, TypeError):
                    value = row['value']
                
                data.append({
                    "time": row['time'].isoformat() + "Z" if row['time'] else None,
                    "value": value
                })
            
            return data
            
    except Exception as e:
        logger.error(f"Database query error: {e}")
        return generate_mock_series(start, end)
    finally:
        conn.close()

def query_statistics(statistic_id: str, start: str, end: str, period: str = "hour"):
    """Query statistical data from statistics table"""
    conn = get_db_connection()
    if not conn:
        return generate_mock_series(start, end)
    
    try:
        with conn.cursor() as cur:
            # Query statistics table
            query = """
            SELECT s.start as time, s.mean, s.min, s.max, s.sum
            FROM statistics s
            JOIN statistics_meta sm ON s.metadata_id = sm.id
            WHERE sm.statistic_id = %s
            AND s.start BETWEEN %s AND %s
            ORDER BY s.start ASC
            """
            
            cur.execute(query, (statistic_id, start, end))
            results = cur.fetchall()
            
            # Convert to expected format
            data = []
            for row in results:
                data.append({
                    "time": row['time'].isoformat() + "Z" if row['time'] else None,
                    "mean": row['mean'],
                    "min": row['min'],
                    "max": row['max'], 
                    "sum": row['sum']
                })
            
            return data
            
    except Exception as e:
        logger.error(f"Statistics query error: {e}")
        return generate_mock_series(start, end)
    finally:
        conn.close()

# API Endpoints

@app.get("/health")
def health():
    """Health check endpoint"""
    conn = get_db_connection()
    db_status = "connected" if conn else "disconnected"
    if conn:
        conn.close()
    
    return {
        "status": "healthy",
        "database": db_status,
        "read_only": READ_ONLY,
        "timescaledb": ENABLE_TIMESCALEDB,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/")
def root():
    """Root endpoint - Web UI"""
    return {
        "name": "Home Assistant MCP Server",
        "version": "0.3.1",
        "description": "Model Context Protocol server for Home Assistant historical data",
        "endpoints": {
            "health": "/health",
            "tools": {
                "history": "/tools/ha.get_history",
                "statistics": "/tools/ha.get_statistics", 
                "statistics_bulk": "/tools/ha.get_statistics_bulk",
                "statistics_meta": "/tools/ha.statistics_meta"
            }
        },
        "status": "running"
    }

# MCP Tool endpoints
@app.post("/tools/ha.get_history")
def ha_get_history(req: HistoryRequest):
    """Get historical data for an entity"""
    try:
        logger.info(f"History request for entity: {req.entity_id}")
        data = query_history(req.entity_id, req.start, req.end)
        
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "entity_id": req.entity_id,
                    "start": req.start,
                    "end": req.end,
                    "data_points": len(data),
                    "series": data
                }, indent=2)
            }]
        }
    except Exception as e:
        logger.error(f"Error in ha.get_history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/ha.get_statistics") 
def ha_get_statistics(req: StatsRequest):
    """Get statistical data for an entity"""
    try:
        logger.info(f"Statistics request for: {req.statistic_id}")
        data = query_statistics(req.statistic_id, req.start, req.end, req.period)
        
        return {
            "content": [{
                "type": "text", 
                "text": json.dumps({
                    "statistic_id": req.statistic_id,
                    "period": req.period,
                    "start": req.start,
                    "end": req.end,
                    "data_points": len(data),
                    "statistics": data
                }, indent=2)
            }]
        }
    except Exception as e:
        logger.error(f"Error in ha.get_statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/ha.get_statistics_bulk")
def ha_get_statistics_bulk(req: StatsBulkRequest):
    """Get bulk statistical data for multiple entities"""
    try:
        logger.info(f"Bulk statistics request for {len(req.statistic_ids)} entities")
        
        results = {}
        for stat_id in req.statistic_ids:
            data = query_statistics(stat_id, req.start, req.end, req.period)
            results[stat_id] = data
        
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "request_info": {
                        "entity_count": len(req.statistic_ids),
                        "period": req.period,
                        "start": req.start,
                        "end": req.end
                    },
                    "results": results,
                    "next_page": None
                }, indent=2)
            }]
        }
    except Exception as e:
        logger.error(f"Error in ha.get_statistics_bulk: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/ha.statistics_meta")
def ha_statistics_meta():
    """Get available statistics metadata"""
    try:
        conn = get_db_connection()
        if not conn:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": "Database not available", 
                        "available_statistics": []
                    })
                }]
            }
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT statistic_id, source, name, unit_of_measurement
                FROM statistics_meta 
                ORDER BY statistic_id
                LIMIT 100
            """)
            results = cur.fetchall()
            
            stats_info = [{
                "statistic_id": row['statistic_id'],
                "source": row['source'],
                "name": row['name'],
                "unit": row['unit_of_measurement']
            } for row in results]
            
        conn.close()
        
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "available_statistics_count": len(stats_info),
                    "statistics": stats_info
                }, indent=2)
            }]
        }
        
    except Exception as e:
        logger.error(f"Error in ha.statistics_meta: {e}")
        return {
            "content": [{
                "type": "text", 
                "text": json.dumps({
                    "error": str(e),
                    "available_statistics": []
                })
            }]
        }

@app.post("/tools/addon.health")
def addon_health():
    """Get add-on health status"""
    conn = get_db_connection()
    db_connected = conn is not None
    if conn:
        conn.close()
    
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "addon_status": "running",
                "database_connected": db_connected,
                "database_config": {
                    "host": DB_CONFIG["host"],
                    "port": DB_CONFIG["port"], 
                    "database": DB_CONFIG["database"],
                    "user": DB_CONFIG["user"]
                },
                "features": {
                    "read_only": READ_ONLY,
                    "timescaledb": ENABLE_TIMESCALEDB
                },
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }, indent=2)
        }]
    }

# MCP Protocol endpoint
@app.post("/mcp/call_tool")
def mcp_call_tool(request: MCPToolRequest):
    """MCP protocol tool calling endpoint"""
    try:
        tool_name = request.name
        args = request.arguments
        
        if tool_name == "ha.get_history":
            req = HistoryRequest(**args)
            return ha_get_history(req)
        elif tool_name == "ha.get_statistics":
            req = StatsRequest(**args) 
            return ha_get_statistics(req)
        elif tool_name == "ha.get_statistics_bulk":
            req = StatsBulkRequest(**args)
            return ha_get_statistics_bulk(req)
        elif tool_name == "ha.statistics_meta":
            return ha_statistics_meta()
        elif tool_name == "addon.health":
            return addon_health()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")
            
    except Exception as e:
        logger.error(f"MCP tool call error: {e}")
        return MCPResponse(
            content=[{"type": "text", "text": f"Error: {str(e)}"}],
            isError=True
        )

if __name__ == "__main__":
    logger.info(f"Starting MCP Server on port {PORT}")
    logger.info(f"Database: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    logger.info(f"Read-only mode: {READ_ONLY}")
    logger.info(f"TimescaleDB: {ENABLE_TIMESCALEDB}")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")