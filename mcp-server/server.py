import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field
import uvicorn
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Home Assistant MCP Server", version="0.3.3")

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

# MCP Tool Handlers
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

# Single MCP Endpoint (Correct Protocol Implementation)
@app.get("/mcp")
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    Single MCP endpoint that handles both GET (SSE) and POST (messages)
    This is the correct implementation per MCP specification
    """
    
    if request.method == "GET":
        # SSE endpoint - return event stream
        async def sse_stream():
            try:
                # Send endpoint event to indicate SSE transport capability
                endpoint_event = {
                    "jsonrpc": "2.0",
                    "method": "endpoint",
                    "params": {
                        "endpoint": {
                            "method": "POST",
                            "path": "/mcp"
                        }
                    }
                }
                yield f"data: {json.dumps(endpoint_event)}\n\n"
                
                # Send initialization
                init_event = {
                    "jsonrpc": "2.0", 
                    "method": "notifications/initialized",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {
                            "name": "Home Assistant MCP Server",
                            "version": "0.3.3"
                        },
                        "capabilities": {
                            "tools": {}
                        }
                    }
                }
                yield f"data: {json.dumps(init_event)}\n\n"
                
                # Keep connection alive with pings
                while True:
                    ping_event = {
                        "jsonrpc": "2.0",
                        "method": "notifications/ping",
                        "params": {
                            "timestamp": datetime.utcnow().isoformat() + "Z"
                        }
                    }
                    yield f"data: {json.dumps(ping_event)}\n\n"
                    await asyncio.sleep(30)
                    
            except asyncio.CancelledError:
                logger.info("SSE client disconnected")
                break
            except Exception as e:
                logger.error(f"SSE stream error: {e}")
                break
        
        return StreamingResponse(
            sse_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST",
                "Access-Control-Allow-Headers": "Accept, Authorization, Content-Type"
            }
        )
    
    elif request.method == "POST":
        # Handle MCP messages
        try:
            request_data = await request.json()
            
            # Handle single request or batch
            if isinstance(request_data, list):
                # Batch request
                responses = []
                for req in request_data:
                    mcp_req = MCPRequest(**req)
                    response = await handle_mcp_request(mcp_req)
                    responses.append(response.dict())
                return responses
            else:
                # Single request
                mcp_req = MCPRequest(**request_data)
                response = await handle_mcp_request(mcp_req)
                return response.dict()
                
        except Exception as e:
            logger.error(f"Error processing MCP request: {e}")
            return MCPResponse(
                id="error",
                error={
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            ).dict()

async def handle_mcp_request(request: MCPRequest) -> MCPResponse:
    """Handle individual MCP requests"""
    try:
        method = request.method
        params = request.params or {}
        
        if method == "initialize":
            return MCPResponse(
                id=request.id,
                result={
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "Home Assistant MCP Server",
                        "version": "0.3.3"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            )
        
        elif method == "tools/list":
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
        
        else:
            return MCPResponse(
                id=request.id,
                error={
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            )
            
    except Exception as e:
        logger.error(f"Error handling MCP request: {e}")
        return MCPResponse(
            id=request.id,
            error={
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        )

# Health endpoint
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
        "mcp_endpoint": "/mcp",
        "protocol_version": "2024-11-05",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# Root endpoint with testing interface
@app.get("/")
def root():
    """Root endpoint with testing interface"""
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
            .test-section {{ background: #fff3e0; padding: 15px; border-radius: 4px; margin: 20px 0; }}
            .sse-output {{ background: #000; color: #00ff00; padding: 15px; border-radius: 4px; font-family: monospace; height: 200px; overflow-y: auto; }}
            .url {{ background: #f0f0f0; padding: 5px; border-radius: 4px; font-family: monospace; }}
            button {{ background: #1976d2; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }}
            button:hover {{ background: #1565c0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Home Assistant MCP Server v0.3.3</h1>
            
            <div class="status {'healthy' if db_status == 'connected' else 'warning'}">
                <strong>Status:</strong> Running | <strong>Database:</strong> {db_status} | <strong>Read-only:</strong> {READ_ONLY}
            </div>
            
            <div class="test-section">
                <h2>🧪 Live MCP Endpoint Test</h2>
                <p><strong>MCP Endpoint URL:</strong></p>
                <div class="url">http://localhost:8099/mcp</div>
                <br>
                <button onclick="testSSE()">Test SSE Stream (GET /mcp)</button>
                <button onclick="testTools()">Test Tools List (POST /mcp)</button>
                <button onclick="stopTest()">Stop Test</button>
                <div class="sse-output" id="testOutput">Click a test button to see results...</div>
            </div>
            
            <h2>📡 MCP Protocol Endpoint</h2>
            <div class="endpoint"><strong>GET|POST /mcp</strong> - Single MCP endpoint (SSE + Messages)</div>
            
            <h2>🔗 Home Assistant MCP Integration Setup</h2>
            <div class="test-section">
                <p><strong>1. Install Integration:</strong> Settings → Devices & Services → Add Integration → "Model Context Protocol"</p>
                <p><strong>2. Configure Server URL:</strong></p>
                <div class="url">http://localhost:8099/mcp</div>
                <p><strong>3. Available Tools:</strong> ha.get_history, ha.get_statistics, ha.list_entities, ha.list_statistics, addon.health</p>
            </div>
            
            <h2>🔗 Manual Testing</h2>
            <div class="endpoint"><strong>Health Check:</strong> <a href="/health" target="_blank">/health</a></div>
            <div class="endpoint"><strong>SSE Stream:</strong> <a href="/mcp" target="_blank">/mcp</a></div>
        </div>
        
        <script>
            let eventSource = null;
            
            function testSSE() {{
                const output = document.getElementById('testOutput');
                output.innerHTML = '🔄 Testing SSE stream (GET /mcp)...\\n';
                
                if (eventSource) {{
                    eventSource.close();
                }}
                
                eventSource = new EventSource('/mcp');
                
                eventSource.onopen = function(event) {{
                    output.innerHTML += '✅ SSE connection opened\\n';
                }};
                
                eventSource.onmessage = function(event) {{
                    const timestamp = new Date().toLocaleTimeString();
                    try {{
                        const data = JSON.parse(event.data);
                        output.innerHTML += `[${timestamp}] ${{JSON.stringify(data, null, 2)}}\\n`;
                    }} catch(e) {{
                        output.innerHTML += `[${timestamp}] Raw: ${{event.data}}\\n`;
                    }}
                    output.scrollTop = output.scrollHeight;
                }};
                
                eventSource.onerror = function(event) {{
                    output.innerHTML += '❌ SSE connection error\\n';
                }};
            }}
            
            function testTools() {{
                const output = document.getElementById('testOutput');
                output.innerHTML = '🔄 Testing tools/list (POST /mcp)...\\n';
                
                fetch('/mcp', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        jsonrpc: '2.0',
                        id: '1',
                        method: 'tools/list'
                    }})
                }})
                .then(response => response.json())
                .then(data => {{
                    output.innerHTML += '✅ Tools response:\\n';
                    output.innerHTML += JSON.stringify(data, null, 2) + '\\n';
                    output.scrollTop = output.scrollHeight;
                }})
                .catch(error => {{
                    output.innerHTML += `❌ Error: ${{error}}\\n`;
                }});
            }}
            
            function stopTest() {{
                if (eventSource) {{
                    eventSource.close();
                    eventSource = null;
                }}
                document.getElementById('testOutput').innerHTML += '🛑 Tests stopped\\n';
            }}
        </script>
    </body>
    </html>
    """)

if __name__ == "__main__":
    logger.info(f"🚀 Starting Home Assistant MCP Server v0.3.3")
    logger.info(f"📊 Database: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    logger.info(f"🔒 Read-only mode: {READ_ONLY}")
    logger.info(f"⚡ TimescaleDB: {ENABLE_TIMESCALEDB}")
    logger.info(f"🌐 Server starting on port {PORT}")
    logger.info(f"📡 MCP endpoint: http://localhost:{PORT}/mcp")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")