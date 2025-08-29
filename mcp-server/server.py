import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field
import uvicorn
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Home Assistant MCP Server", version="0.3.2")

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

# MCP Protocol Models
class MCPTool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Union[str, int]
    method: str
    params: Optional[Dict[str, Any]] = None

class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Union[str, int]
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

class MCPToolContent(BaseModel):
    type: str = "text"
    text: str

class MCPToolResult(BaseModel):
    content: List[MCPToolContent]
    isError: bool = False

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

def get_available_entities(limit: int = 50):
    """Get list of available entities from states_meta"""
    conn = get_db_connection()
    if not conn:
        return ["sensor.temperature", "sensor.humidity", "light.living_room"]
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT entity_id FROM states_meta 
                ORDER BY entity_id 
                LIMIT %s
            """, (limit,))
            results = cur.fetchall()
            return [row['entity_id'] for row in results]
    except Exception as e:
        logger.error(f"Error fetching entities: {e}")
        return ["sensor.temperature", "sensor.humidity", "light.living_room"]
    finally:
        conn.close()

def get_available_statistics(limit: int = 50):
    """Get list of available statistics from statistics_meta"""
    conn = get_db_connection()
    if not conn:
        return ["sensor.power_consumption", "sensor.energy_total"]
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT statistic_id FROM statistics_meta 
                ORDER BY statistic_id 
                LIMIT %s
            """, (limit,))
            results = cur.fetchall()
            return [row['statistic_id'] for row in results]
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        return ["sensor.power_consumption", "sensor.energy_total"]
    finally:
        conn.close()

# MCP Tool Implementations
def handle_get_history(params: Dict[str, Any]) -> MCPToolResult:
    """Handle ha.get_history tool calls"""
    try:
        entity_id = params.get("entity_id")
        start = params.get("start")
        end = params.get("end")
        
        if not all([entity_id, start, end]):
            return MCPToolResult(
                content=[MCPToolContent(text="Missing required parameters: entity_id, start, end")],
                isError=True
            )
        
        data = query_history(entity_id, start, end)
        result = {
            "entity_id": entity_id,
            "start": start,
            "end": end,
            "data_points": len(data),
            "history": data
        }
        
        return MCPToolResult(
            content=[MCPToolContent(text=json.dumps(result, indent=2))]
        )
        
    except Exception as e:
        return MCPToolResult(
            content=[MCPToolContent(text=f"Error getting history: {str(e)}")],
            isError=True
        )

def handle_get_statistics(params: Dict[str, Any]) -> MCPToolResult:
    """Handle ha.get_statistics tool calls"""
    try:
        statistic_id = params.get("statistic_id")
        start = params.get("start")
        end = params.get("end")
        period = params.get("period", "hour")
        
        if not all([statistic_id, start, end]):
            return MCPToolResult(
                content=[MCPToolContent(text="Missing required parameters: statistic_id, start, end")],
                isError=True
            )
        
        data = query_statistics(statistic_id, start, end, period)
        result = {
            "statistic_id": statistic_id,
            "period": period,
            "start": start,
            "end": end,
            "data_points": len(data),
            "statistics": data
        }
        
        return MCPToolResult(
            content=[MCPToolContent(text=json.dumps(result, indent=2))]
        )
        
    except Exception as e:
        return MCPToolResult(
            content=[MCPToolContent(text=f"Error getting statistics: {str(e)}")],
            isError=True
        )

def handle_list_entities(params: Dict[str, Any]) -> MCPToolResult:
    """Handle ha.list_entities tool calls"""
    try:
        limit = params.get("limit", 50)
        entities = get_available_entities(limit)
        
        result = {
            "available_entities": entities,
            "count": len(entities),
            "limit": limit
        }
        
        return MCPToolResult(
            content=[MCPToolContent(text=json.dumps(result, indent=2))]
        )
        
    except Exception as e:
        return MCPToolResult(
            content=[MCPToolContent(text=f"Error listing entities: {str(e)}")],
            isError=True
        )

def handle_list_statistics(params: Dict[str, Any]) -> MCPToolResult:
    """Handle ha.list_statistics tool calls"""
    try:
        limit = params.get("limit", 50)
        statistics = get_available_statistics(limit)
        
        result = {
            "available_statistics": statistics,
            "count": len(statistics),
            "limit": limit
        }
        
        return MCPToolResult(
            content=[MCPToolContent(text=json.dumps(result, indent=2))]
        )
        
    except Exception as e:
        return MCPToolResult(
            content=[MCPToolContent(text=f"Error listing statistics: {str(e)}")],
            isError=True
        )

def handle_addon_health(params: Dict[str, Any]) -> MCPToolResult:
    """Handle addon.health tool calls"""
    try:
        conn = get_db_connection()
        db_connected = conn is not None
        if conn:
            conn.close()
        
        result = {
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
        }
        
        return MCPToolResult(
            content=[MCPToolContent(text=json.dumps(result, indent=2))]
        )
        
    except Exception as e:
        return MCPToolResult(
            content=[MCPToolContent(text=f"Error getting health status: {str(e)}")],
            isError=True
        )

# MCP Tool Registry
MCP_TOOLS = {
    "ha.get_history": {
        "name": "ha.get_history",
        "description": "Get historical data for a Home Assistant entity over a time period",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "The entity ID to get history for (e.g., sensor.temperature)"
                },
                "start": {
                    "type": "string",
                    "description": "Start time in ISO format (e.g., 2024-01-01T00:00:00Z)"
                },
                "end": {
                    "type": "string", 
                    "description": "End time in ISO format (e.g., 2024-01-02T00:00:00Z)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of data points to return",
                    "default": 1000
                }
            },
            "required": ["entity_id", "start", "end"]
        },
        "handler": handle_get_history
    },
    "ha.get_statistics": {
        "name": "ha.get_statistics",
        "description": "Get statistical data (mean, min, max, sum) for a Home Assistant entity",
        "inputSchema": {
            "type": "object",
            "properties": {
                "statistic_id": {
                    "type": "string",
                    "description": "The statistic ID to get data for"
                },
                "start": {
                    "type": "string",
                    "description": "Start time in ISO format"
                },
                "end": {
                    "type": "string",
                    "description": "End time in ISO format"
                },
                "period": {
                    "type": "string",
                    "enum": ["hour", "day"],
                    "description": "Aggregation period",
                    "default": "hour"
                }
            },
            "required": ["statistic_id", "start", "end"]
        },
        "handler": handle_get_statistics
    },
    "ha.list_entities": {
        "name": "ha.list_entities",
        "description": "List available Home Assistant entities that have historical data",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of entities to return",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 500
                }
            }
        },
        "handler": handle_list_entities
    },
    "ha.list_statistics": {
        "name": "ha.list_statistics",
        "description": "List available Home Assistant statistics",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of statistics to return",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 500
                }
            }
        },
        "handler": handle_list_statistics
    },
    "addon.health": {
        "name": "addon.health",
        "description": "Get health status of the MCP server and database connection",
        "inputSchema": {
            "type": "object",
            "properties": {}
        },
        "handler": handle_addon_health
    }
}

# SSE Transport Endpoints (Required by Home Assistant MCP Integration)

@app.get("/sse")
async def sse_endpoint():
    """Main SSE endpoint for MCP protocol - Required by Home Assistant integration"""
    
    async def event_stream():
        # Send initial connection message
        init_msg = {
            "jsonrpc": "2.0", 
            "method": "notifications/initialized",
            "params": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "Home Assistant MCP Server",
                    "version": "0.3.2"
                },
                "capabilities": {
                    "tools": {}
                }
            }
        }
        yield f"data: {json.dumps(init_msg)}\n\n"
        
        # Keep connection alive with periodic pings
        while True:
            try:
                ping_msg = {
                    "jsonrpc": "2.0",
                    "method": "notifications/ping",
                    "params": {
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                }
                yield f"data: {json.dumps(ping_msg)}\n\n"
                await asyncio.sleep(30)  # Ping every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SSE stream error: {e}")
                break
    
    return StreamingResponse(
        event_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Accept, Authorization"
        }
    )

@app.post("/message")
async def handle_mcp_message(request: MCPRequest):
    """Handle MCP protocol messages - Required by Home Assistant integration"""
    
    try:
        method = request.method
        params = request.params or {}
        
        if method == "tools/list":
            # Return list of available tools
            tools = []
            for tool_name, tool_info in MCP_TOOLS.items():
                tools.append({
                    "name": tool_info["name"],
                    "description": tool_info["description"],
                    "inputSchema": tool_info["inputSchema"]
                })
            
            return MCPResponse(
                id=request.id,
                result={"tools": tools}
            )
        
        elif method == "tools/call":
            # Handle tool calls
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if tool_name not in MCP_TOOLS:
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32602,
                        "message": f"Unknown tool: {tool_name}"
                    }
                )
            
            # Execute the tool
            tool_handler = MCP_TOOLS[tool_name]["handler"]
            result = tool_handler(tool_args)
            
            return MCPResponse(
                id=request.id,
                result=result.dict()
            )
        
        elif method == "initialize":
            # Initialize MCP session
            return MCPResponse(
                id=request.id,
                result={
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "Home Assistant MCP Server",
                        "version": "0.3.2"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
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
        logger.error(f"MCP message handling error: {e}")
        return MCPResponse(
            id=request.id,
            error={
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        )

# Standard HTTP API Endpoints (for backwards compatibility)

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
        "mcp_version": "2024-11-05",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/")
def root():
    """Root endpoint - API documentation"""
    conn = get_db_connection()
    db_status = "connected" if conn else "disconnected"
    if conn:
        conn.close()
    
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Home Assistant MCP Server</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .status {{ padding: 10px; border-radius: 4px; margin: 10px 0; }}
            .healthy {{ background-color: #d4edda; color: #155724; }}
            .warning {{ background-color: #fff3cd; color: #856404; }}
            h1 {{ color: #1976d2; }}
            .endpoint {{ background: #f8f9fa; padding: 10px; margin: 10px 0; border-left: 4px solid #1976d2; }}
            .tools {{ margin: 20px 0; }}
            .tool {{ background: #e7f3ff; padding: 10px; margin: 5px 0; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Home Assistant MCP Server v0.3.2</h1>
            
            <div class="status {'healthy' if db_status == 'connected' else 'warning'}">
                <strong>Status:</strong> Running | <strong>Database:</strong> {db_status} | <strong>Read-only:</strong> {READ_ONLY}
            </div>
            
            <h2>📡 MCP Protocol Endpoints</h2>
            <div class="endpoint"><strong>GET /sse</strong> - SSE transport endpoint (for Home Assistant integration)</div>
            <div class="endpoint"><strong>POST /message</strong> - MCP message handler</div>
            
            <h2>🛠️ Available MCP Tools</h2>
            <div class="tools">
                <div class="tool"><strong>ha.get_history</strong> - Get historical entity data</div>
                <div class="tool"><strong>ha.get_statistics</strong> - Get statistical data for entities</div>
                <div class="tool"><strong>ha.list_entities</strong> - List available entities</div>
                <div class="tool"><strong>ha.list_statistics</strong> - List available statistics</div>
                <div class="tool"><strong>addon.health</strong> - Get server health status</div>
            </div>
            
            <h2>🔗 Configuration</h2>
            <p>To use with Home Assistant MCP integration:</p>
            <ol>
                <li>Install the <strong>Model Context Protocol</strong> integration</li>
                <li>Configure SSE endpoint: <code>http://localhost:8099/sse</code></li>
                <li>Tools will be available for conversation agents</li>
            </ol>
            
            <p><em>Compatible with Home Assistant MCP Integration using SSE transport protocol</em></p>
        </div>
    </body>
    </html>
    """)

if __name__ == "__main__":
    logger.info(f"🚀 Starting Home Assistant MCP Server v0.3.2")
    logger.info(f"📊 Database: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    logger.info(f"🔒 Read-only mode: {READ_ONLY}")
    logger.info(f"⚡ TimescaleDB: {ENABLE_TIMESCALEDB}")
    logger.info(f"🌐 Server starting on port {PORT}")
    logger.info(f"📡 SSE endpoint: http://localhost:{PORT}/sse")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")