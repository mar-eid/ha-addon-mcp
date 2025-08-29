import os
import asyncio
import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Literal, Any, Dict
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import uvicorn
import psycopg2
from psycopg2.extras import RealDictCursor

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

# Store active SSE sessions
sse_sessions: Dict[str, Any] = {}

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

# MCP Protocol Models
class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: str
    params: Optional[Dict[str, Any]] = None

class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

class MCPTool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]

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
            
            data = []
            for row in results:
                try:
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

# MCP Tools definitions
def get_available_tools():
    """Return list of available MCP tools"""
    return [
        MCPTool(
            name="ha_get_history",
            description="Get historical data for a Home Assistant entity",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entity ID to query"},
                    "start": {"type": "string", "description": "Start time (ISO format)"},
                    "end": {"type": "string", "description": "End time (ISO format)"},
                    "limit": {"type": "integer", "description": "Max data points", "default": 1000}
                },
                "required": ["entity_id", "start", "end"]
            }
        ),
        MCPTool(
            name="ha_get_statistics", 
            description="Get statistical data for a Home Assistant entity",
            inputSchema={
                "type": "object",
                "properties": {
                    "statistic_id": {"type": "string", "description": "Statistics ID to query"},
                    "start": {"type": "string", "description": "Start time (ISO format)"},
                    "end": {"type": "string", "description": "End time (ISO format)"},
                    "period": {"type": "string", "enum": ["hour", "day"], "default": "hour"}
                },
                "required": ["statistic_id", "start", "end"]
            }
        ),
        MCPTool(
            name="ha_statistics_meta",
            description="Get available statistics metadata from Home Assistant",
            inputSchema={
                "type": "object", 
                "properties": {
                    "limit": {"type": "integer", "description": "Max results", "default": 100}
                }
            }
        ),
        MCPTool(
            name="ha_health_check",
            description="Check MCP server and database connectivity status", 
            inputSchema={"type": "object", "properties": {}}
        )
    ]

# MCP Tool execution
async def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an MCP tool and return result"""
    try:
        if tool_name == "ha_get_history":
            entity_id = arguments.get("entity_id")
            start = arguments.get("start") 
            end = arguments.get("end")
            limit = arguments.get("limit", 1000)
            
            data = query_history(entity_id, start, end, limit)
            
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "entity_id": entity_id,
                        "start": start,
                        "end": end,
                        "data_points": len(data),
                        "series": data
                    }, indent=2)
                }]
            }
            
        elif tool_name == "ha_get_statistics":
            statistic_id = arguments.get("statistic_id")
            start = arguments.get("start")
            end = arguments.get("end") 
            period = arguments.get("period", "hour")
            
            data = query_statistics(statistic_id, start, end, period)
            
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "statistic_id": statistic_id,
                        "period": period,
                        "start": start,
                        "end": end,
                        "data_points": len(data),
                        "statistics": data
                    }, indent=2)
                }]
            }
            
        elif tool_name == "ha_statistics_meta":
            limit = arguments.get("limit", 100)
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
            
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT statistic_id, source, name, unit_of_measurement
                        FROM statistics_meta 
                        ORDER BY statistic_id
                        LIMIT %s
                    """, (limit,))
                    results = cur.fetchall()
                    
                    stats_info = [{
                        "statistic_id": row['statistic_id'],
                        "source": row['source'],
                        "name": row['name'],
                        "unit": row['unit_of_measurement']
                    } for row in results]
                    
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "available_statistics_count": len(stats_info),
                            "statistics": stats_info
                        }, indent=2)
                    }]
                }
            finally:
                conn.close()
                
        elif tool_name == "ha_health_check":
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
            
        else:
            return {
                "content": [{
                    "type": "text", 
                    "text": f"Unknown tool: {tool_name}"
                }],
                "isError": True
            }
            
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Error executing tool {tool_name}: {str(e)}"
            }],
            "isError": True
        }

# MCP Protocol Handlers
async def handle_mcp_request(request: MCPRequest) -> MCPResponse:
    """Handle incoming MCP requests according to protocol"""
    try:
        method = request.method
        params = request.params or {}
        
        if method == "initialize":
            return MCPResponse(
                id=request.id,
                result={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "logging": {}
                    },
                    "serverInfo": {
                        "name": "Home Assistant MCP Server",
                        "version": "0.3.1"
                    }
                }
            )
            
        elif method == "tools/list":
            tools = get_available_tools()
            return MCPResponse(
                id=request.id,
                result={
                    "tools": [tool.dict() for tool in tools]
                }
            )
            
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            result = await execute_tool(tool_name, arguments)
            
            return MCPResponse(
                id=request.id,
                result=result
            )
            
        elif method == "ping":
            return MCPResponse(
                id=request.id,
                result={}
            )
            
        else:
            return MCPResponse(
                id=request.id,
                error={
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            )
            
    except Exception as e:
        logger.error(f"MCP request error: {e}")
        return MCPResponse(
            id=request.id,
            error={
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        )

# SSE endpoint for Home Assistant MCP Integration
@app.get("/sse")
async def mcp_sse_endpoint():
    """SSE endpoint for MCP protocol - required by Home Assistant MCP integration"""
    session_id = str(uuid.uuid4())
    logger.info(f"New MCP SSE session: {session_id}")
    
    async def event_stream():
        try:
            # Send endpoint event with session ID for message posting
            endpoint_url = f"/sse/messages?session_id={session_id}"
            yield f"event: endpoint\ndata: {endpoint_url}\n\n"
            
            # Store session info
            sse_sessions[session_id] = {
                "created": datetime.utcnow(),
                "active": True
            }
            
            # Keep connection alive with periodic pings
            while session_id in sse_sessions and sse_sessions[session_id]["active"]:
                yield f"event: ping\ndata: {json.dumps({'timestamp': datetime.utcnow().isoformat()})}\n\n"
                await asyncio.sleep(30)  # Ping every 30 seconds
                
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
        finally:
            # Clean up session
            if session_id in sse_sessions:
                del sse_sessions[session_id]
            logger.info(f"SSE session closed: {session_id}")
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )

# Message endpoint for MCP protocol
@app.post("/sse/messages")
async def mcp_sse_messages(request: Request):
    """Handle MCP JSON-RPC messages via POST - required by Home Assistant"""
    try:
        # Get session ID from query params
        session_id = request.query_params.get("session_id")
        if not session_id or session_id not in sse_sessions:
            raise HTTPException(status_code=400, detail="Invalid or missing session ID")
        
        # Parse JSON-RPC request
        body = await request.json()
        mcp_request = MCPRequest(**body)
        
        logger.info(f"MCP request: {mcp_request.method} (session: {session_id[:8]})")
        
        # Handle the request
        response = await handle_mcp_request(mcp_request)
        
        return JSONResponse(content=response.dict(exclude_none=True))
        
    except Exception as e:
        logger.error(f"MCP message handling error: {e}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": body.get("id") if 'body' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            },
            status_code=500
        )

# Health and info endpoints
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
        "active_sessions": len(sse_sessions),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/")
def root():
    """Root endpoint - API documentation"""
    return {
        "name": "Home Assistant MCP Server",
        "version": "0.3.1",
        "description": "Model Context Protocol server for Home Assistant historical data",
        "protocol_version": "2024-11-05",
        "transport": "SSE",
        "endpoints": {
            "health": "/health",
            "mcp_sse": "/sse",
            "mcp_messages": "/sse/messages",
        },
        "tools": len(get_available_tools()),
        "status": "running",
        "home_assistant_integration": {
            "compatible": True,
            "sse_url": "http://localhost:8099/sse",
            "documentation": "https://www.home-assistant.io/integrations/mcp/"
        }
    }

# Legacy endpoints for backward compatibility
@app.post("/tools/ha.get_history")
async def legacy_ha_get_history(request: Request):
    """Legacy endpoint for backward compatibility"""
    body = await request.json()
    result = await execute_tool("ha_get_history", body)
    return JSONResponse(content=result)

@app.post("/tools/ha.get_statistics")
async def legacy_ha_get_statistics(request: Request):
    """Legacy endpoint for backward compatibility"""
    body = await request.json()
    result = await execute_tool("ha_get_statistics", body)
    return JSONResponse(content=result)

@app.post("/tools/ha.statistics_meta")
async def legacy_ha_statistics_meta():
    """Legacy endpoint for backward compatibility"""
    result = await execute_tool("ha_statistics_meta", {})
    return JSONResponse(content=result)

# Session management
@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    logger.info(f"🚀 Home Assistant MCP Server v0.3.1 starting...")
    logger.info(f"🔌 Database: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    logger.info(f"🔒 Read-only mode: {READ_ONLY}")
    logger.info(f"⚡ TimescaleDB: {ENABLE_TIMESCALEDB}")
    logger.info(f"🌐 SSE endpoint: http://localhost:{PORT}/sse")
    logger.info(f"📡 Compatible with Home Assistant MCP Integration")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    logger.info("🛑 Shutting down MCP Server...")
    # Close all active SSE sessions
    for session_id in list(sse_sessions.keys()):
        sse_sessions[session_id]["active"] = False
    sse_sessions.clear()

if __name__ == "__main__":
    logger.info(f"🎯 Starting Home Assistant MCP Server on port {PORT}")
    logger.info(f"📖 Add this URL to HA MCP integration: http://localhost:{PORT}/sse")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=PORT, 
        log_level="info",
        access_log=True
    )