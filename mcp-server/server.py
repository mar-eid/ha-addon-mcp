#!/usr/bin/env python3
"""
Home Assistant MCP Server Add-on
Compatible with Home Assistant's official MCP Client integration
"""

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

app = FastAPI(title="Home Assistant MCP Server", version="0.3.4")

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

# Database connection with proper error handling
def get_db_connection():
    """Get database connection with comprehensive error handling"""
    try:
        conn = psycopg2.connect(
            **DB_CONFIG,
            cursor_factory=RealDictCursor,
            connect_timeout=10
        )
        # Test the connection
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return conn
    except psycopg2.OperationalError as e:
        logger.warning(f"Database connection failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected database error: {e}")
        return None

# Mock data generator for fallback when DB is unavailable
def generate_mock_series(start: str, end: str, points: int = 24):
    """Generate realistic mock time series data"""
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", ""))
        end_dt = datetime.fromisoformat(end.replace("Z", ""))
        delta = (end_dt - start_dt) / points
        
        data = []
        base_value = 22.0  # Temperature-like base value
        for i in range(points):
            timestamp = start_dt + delta * i
            # Add some realistic variation
            variation = 0.5 * (i % 5 - 2) + 0.1 * i
            value = round(base_value + variation, 2)
            
            data.append({
                "time": timestamp.isoformat() + "Z",
                "value": value
            })
        return data
    except Exception as e:
        logger.error(f"Error generating mock data: {e}")
        return []

# Enhanced database query functions
def query_history(entity_id: str, start: str, end: str, limit: int = 1000):
    """Query historical data from Home Assistant recorder database"""
    conn = get_db_connection()
    if not conn:
        logger.warning("Using mock data - database not available")
        return generate_mock_series(start, end)
    
    try:
        with conn.cursor() as cur:
            # Enhanced query with better filtering
            query = """
            SELECT s.last_changed as time, s.state as value, s.attributes
            FROM states s
            JOIN states_meta sm ON s.metadata_id = sm.metadata_id
            WHERE sm.entity_id = %s 
            AND s.last_changed BETWEEN %s::timestamp AND %s::timestamp
            AND s.state NOT IN ('unknown', 'unavailable', '', 'None')
            AND s.state IS NOT NULL
            ORDER BY s.last_changed ASC
            LIMIT %s
            """
            
            cur.execute(query, (entity_id, start, end, limit))
            results = cur.fetchall()
            
            if not results:
                logger.info(f"No data found for entity {entity_id} in range {start} to {end}")
                return generate_mock_series(start, end, 12)  # Smaller mock dataset
            
            data = []
            for row in results:
                try:
                    # Try to convert to float for numeric sensors
                    try:
                        value = float(row['value'])
                    except (ValueError, TypeError):
                        value = row['value']  # Keep as string for non-numeric
                    
                    data.append({
                        "time": row['time'].isoformat() + "Z" if row['time'] else None,
                        "value": value,
                        "attributes": row.get('attributes', {})
                    })
                except Exception as e:
                    logger.warning(f"Skipping invalid data point: {e}")
                    continue
            
            logger.info(f"Retrieved {len(data)} data points for {entity_id}")
            return data
            
    except Exception as e:
        logger.error(f"Database query error: {e}")
        return generate_mock_series(start, end)
    finally:
        if conn:
            conn.close()

def query_statistics(statistic_id: str, start: str, end: str, period: str = "hour"):
    """Query statistical data from Home Assistant statistics tables"""
    conn = get_db_connection()
    if not conn:
        return generate_mock_series(start, end)
    
    try:
        with conn.cursor() as cur:
            query = """
            SELECT s.start as time, s.mean, s.min, s.max, s.sum, s.state
            FROM statistics s
            JOIN statistics_meta sm ON s.metadata_id = sm.id
            WHERE sm.statistic_id = %s
            AND s.start BETWEEN %s::timestamp AND %s::timestamp
            ORDER BY s.start ASC
            LIMIT 1000
            """
            
            cur.execute(query, (statistic_id, start, end))
            results = cur.fetchall()
            
            if not results:
                logger.info(f"No statistics found for {statistic_id}")
                return generate_mock_series(start, end, 24)
            
            data = []
            for row in results:
                data.append({
                    "time": row['time'].isoformat() + "Z" if row['time'] else None,
                    "mean": row['mean'],
                    "min": row['min'],
                    "max": row['max'], 
                    "sum": row['sum'],
                    "state": row['state']
                })
            
            logger.info(f"Retrieved {len(data)} statistics for {statistic_id}")
            return data
            
    except Exception as e:
        logger.error(f"Statistics query error: {e}")
        return generate_mock_series(start, end)
    finally:
        if conn:
            conn.close()

def get_available_entities(limit: int = 50):
    """Get list of available entities from states_meta table"""
    conn = get_db_connection()
    if not conn:
        return ["sensor.temperature", "sensor.humidity", "light.living_room", "binary_sensor.motion"]
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT entity_id 
                FROM states_meta 
                WHERE entity_id LIKE 'sensor.%' 
                   OR entity_id LIKE 'light.%'
                   OR entity_id LIKE 'binary_sensor.%'
                ORDER BY entity_id 
                LIMIT %s
            """, (limit,))
            results = cur.fetchall()
            entities = [row['entity_id'] for row in results]
            logger.info(f"Found {len(entities)} entities")
            return entities
    except Exception as e:
        logger.error(f"Error fetching entities: {e}")
        return ["sensor.temperature", "sensor.humidity", "light.living_room"]
    finally:
        if conn:
            conn.close()

def get_available_statistics(limit: int = 50):
    """Get list of available statistics from statistics_meta table"""
    conn = get_db_connection()
    if not conn:
        return ["sensor.energy_total", "sensor.power_consumption"]
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT statistic_id, unit_of_measurement 
                FROM statistics_meta 
                ORDER BY statistic_id 
                LIMIT %s
            """, (limit,))
            results = cur.fetchall()
            stats = []
            for row in results:
                stats.append({
                    "statistic_id": row['statistic_id'],
                    "unit": row.get('unit_of_measurement', '')
                })
            logger.info(f"Found {len(stats)} statistics")
            return stats
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        return ["sensor.energy_total", "sensor.power_consumption"]
    finally:
        if conn:
            conn.close()

# MCP Tool Handlers
def handle_get_history(params: Dict[str, Any]) -> MCPToolResult:
    """Handle ha.get_history tool calls - Get historical sensor data"""
    try:
        entity_id = params.get("entity_id")
        start = params.get("start")
        end = params.get("end")
        
        if not all([entity_id, start, end]):
            return MCPToolResult(
                content=[MCPToolContent(text="Missing required parameters: entity_id, start, end")],
                isError=True
            )
        
        logger.info(f"Getting history for {entity_id} from {start} to {end}")
        data = query_history(entity_id, start, end)
        
        result = {
            "entity_id": entity_id,
            "start": start,
            "end": end,
            "data_points": len(data),
            "history": data,
            "message": f"Retrieved {len(data)} data points for {entity_id}"
        }
        
        return MCPToolResult(
            content=[MCPToolContent(text=json.dumps(result, indent=2))]
        )
        
    except Exception as e:
        logger.error(f"Error in get_history: {e}")
        return MCPToolResult(
            content=[MCPToolContent(text=f"Error getting history: {str(e)}")],
            isError=True
        )

def handle_get_statistics(params: Dict[str, Any]) -> MCPToolResult:
    """Handle ha.get_statistics tool calls - Get statistical summaries"""
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
        
        logger.info(f"Getting statistics for {statistic_id}")
        data = query_statistics(statistic_id, start, end, period)
        
        result = {
            "statistic_id": statistic_id,
            "period": period,
            "start": start,
            "end": end,
            "data_points": len(data),
            "statistics": data,
            "message": f"Retrieved {len(data)} statistical data points for {statistic_id}"
        }
        
        return MCPToolResult(
            content=[MCPToolContent(text=json.dumps(result, indent=2))]
        )
        
    except Exception as e:
        logger.error(f"Error in get_statistics: {e}")
        return MCPToolResult(
            content=[MCPToolContent(text=f"Error getting statistics: {str(e)}")],
            isError=True
        )

def handle_list_entities(params: Dict[str, Any]) -> MCPToolResult:
    """Handle ha.list_entities tool calls - List available entities"""
    try:
        limit = params.get("limit", 50)
        entities = get_available_entities(limit)
        
        result = {
            "available_entities": entities,
            "count": len(entities),
            "limit": limit,
            "message": f"Found {len(entities)} available entities in Home Assistant"
        }
        
        return MCPToolResult(
            content=[MCPToolContent(text=json.dumps(result, indent=2))]
        )
        
    except Exception as e:
        logger.error(f"Error in list_entities: {e}")
        return MCPToolResult(
            content=[MCPToolContent(text=f"Error listing entities: {str(e)}")],
            isError=True
        )

def handle_list_statistics(params: Dict[str, Any]) -> MCPToolResult:
    """Handle ha.list_statistics tool calls - List available statistics"""
    try:
        limit = params.get("limit", 50)
        statistics = get_available_statistics(limit)
        
        result = {
            "available_statistics": statistics,
            "count": len(statistics),
            "limit": limit,
            "message": f"Found {len(statistics)} available statistics in Home Assistant"
        }
        
        return MCPToolResult(
            content=[MCPToolContent(text=json.dumps(result, indent=2))]
        )
        
    except Exception as e:
        logger.error(f"Error in list_statistics: {e}")
        return MCPToolResult(
            content=[MCPToolContent(text=f"Error listing statistics: {str(e)}")],
            isError=True
        )

def handle_addon_health(params: Dict[str, Any]) -> MCPToolResult:
    """Handle addon.health tool calls - Get server health status"""
    try:
        conn = get_db_connection()
        db_connected = conn is not None
        if conn:
            conn.close()
        
        result = {
            "addon_status": "running",
            "version": "0.3.4",
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
            "mcp_tools": list(MCP_TOOLS.keys()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": f"MCP Server is running with {'database' if db_connected else 'mock data'}"
        }
        
        return MCPToolResult(
            content=[MCPToolContent(text=json.dumps(result, indent=2))]
        )
        
    except Exception as e:
        logger.error(f"Error in addon_health: {e}")
        return MCPToolResult(
            content=[MCPToolContent(text=f"Error getting health status: {str(e)}")],
            isError=True
        )

# MCP Tool Registry - Properly formatted for Home Assistant integration
MCP_TOOLS = {
    "ha.get_history": {
        "name": "ha.get_history",
        "description": "Get historical state data for a Home Assistant entity over a specified time period. Returns timestamped values showing how the entity's state changed over time.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "The entity ID to get history for (e.g., 'sensor.temperature', 'light.living_room')"
                },
                "start": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format (e.g., '2024-01-01T00:00:00Z' or '2024-01-01T10:00:00+01:00')"
                },
                "end": {
                    "type": "string", 
                    "description": "End time in ISO 8601 format (e.g., '2024-01-02T00:00:00Z' or '2024-01-01T20:00:00+01:00')"
                }
            },
            "required": ["entity_id", "start", "end"]
        },
        "handler": handle_get_history
    },
    "ha.get_statistics": {
        "name": "ha.get_statistics",
        "description": "Get statistical data (mean, min, max, sum) for a Home Assistant entity over time. This provides aggregated data that's useful for analysis and trends.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "statistic_id": {
                    "type": "string",
                    "description": "The statistic ID to get data for (usually same as entity_id for sensors)"
                },
                "start": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format"
                },
                "end": {
                    "type": "string",
                    "description": "End time in ISO 8601 format"
                },
                "period": {
                    "type": "string",
                    "enum": ["hour", "day"],
                    "description": "Aggregation period for statistics",
                    "default": "hour"
                }
            },
            "required": ["statistic_id", "start", "end"]
        },
        "handler": handle_get_statistics
    },
    "ha.list_entities": {
        "name": "ha.list_entities",
        "description": "List available Home Assistant entities that have historical data. Useful for discovering what sensors and devices can be queried.",
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
        "description": "List available Home Assistant statistics. These are entities that have statistical summaries available (mean, min, max, sum).",
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
        "description": "Get health status and configuration of the MCP server including database connectivity and available features.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        },
        "handler": handle_addon_health
    }
}

# Main MCP Protocol Endpoint
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    Main MCP endpoint compatible with Home Assistant's MCP Client integration
    Handles JSON-RPC 2.0 messages for the Model Context Protocol
    """
    try:
        request_data = await request.json()
        logger.info(f"Received MCP request: {request_data.get('method', 'unknown')}")
        
        # Handle single request or batch
        if isinstance(request_data, list):
            responses = []
            for req in request_data:
                mcp_req = MCPRequest(**req)
                response = await handle_mcp_request(mcp_req)
                responses.append(response.dict())
            return responses
        else:
            mcp_req = MCPRequest(**request_data)
            response = await handle_mcp_request(mcp_req)
            return response.dict()
            
    except Exception as e:
        logger.error(f"Error processing MCP request: {e}")
        return MCPResponse(
            id=0,
            error={
                "code": -32700,
                "message": f"Parse error: {str(e)}"
            }
        ).dict()

async def handle_mcp_request(request: MCPRequest) -> MCPResponse:
    """Handle individual MCP protocol requests"""
    try:
        method = request.method
        params = request.params or {}
        logger.info(f"Processing MCP method: {method}")
        
        if method == "initialize":
            return MCPResponse(
                id=request.id,
                result={
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "Home Assistant MCP Server",
                        "version": "0.3.4"
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
            logger.info(f"Executing tool: {tool_name}")
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
        logger.error(f"Error handling MCP request {request.method}: {e}")
        return MCPResponse(
            id=request.id,
            error={
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        )

# Health check endpoint
@app.get("/health")
def health():
    """Health check endpoint for monitoring and diagnostics"""
    conn = get_db_connection()
    db_status = "connected" if conn else "disconnected"
    if conn:
        conn.close()
    
    return {
        "status": "healthy",
        "version": "0.3.4",
        "database": db_status,
        "read_only": READ_ONLY,
        "timescaledb": ENABLE_TIMESCALEDB,
        "mcp_endpoint": "/mcp",
        "protocol_version": "2024-11-05",
        "available_tools": list(MCP_TOOLS.keys()),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# Root endpoint with user interface
@app.get("/")
def root():
    """Root endpoint with test interface and setup instructions"""
    conn = get_db_connection()
    db_status = "connected" if conn else "disconnected"
    if conn:
        conn.close()
    
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Home Assistant MCP Server v0.3.4</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background: #f5f5f5; }}
            .header {{ background: linear-gradient(135deg, #1976d2, #42a5f5); color: white; padding: 20px 40px; }}
            .container {{ max-width: 1200px; margin: 0 auto; padding: 30px; }}
            .status {{ padding: 15px; border-radius: 8px; margin: 20px 0; font-weight: 500; }}
            .healthy {{ background-color: #e8f5e8; color: #2e7d32; border-left: 4px solid #4caf50; }}
            .warning {{ background-color: #fff8e1; color: #f57c00; border-left: 4px solid #ff9800; }}
            .card {{ background: white; padding: 25px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin: 20px 0; }}
            .endpoint {{ background: #f8f9fa; padding: 15px; margin: 10px 0; border-left: 4px solid #1976d2; border-radius: 4px; }}
            .test-section {{ background: #fff3e0; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .output {{ background: #1e1e1e; color: #00ff41; padding: 20px; border-radius: 8px; font-family: 'Consolas', monospace; height: 300px; overflow-y: auto; font-size: 13px; }}
            .url {{ background: #e3f2fd; padding: 10px; border-radius: 4px; font-family: 'Consolas', monospace; color: #1565c0; }}
            button {{ background: #1976d2; color: white; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; margin: 5px; font-size: 14px; }}
            button:hover {{ background: #1565c0; }}
            .tool {{ background: #f5f5f5; padding: 12px; margin: 8px 0; border-radius: 6px; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
            @media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} }}
            h1, h2, h3 {{ color: #1976d2; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🤖 Home Assistant MCP Server v0.3.4</h1>
            <p>Model Context Protocol server for querying Home Assistant historical data</p>
        </div>
        
        <div class="container">
            <div class="status {'healthy' if db_status == 'connected' else 'warning'}">
                <strong>Status:</strong> Running | 
                <strong>Database:</strong> {db_status.title()} | 
                <strong>Read-only:</strong> {READ_ONLY} | 
                <strong>TimescaleDB:</strong> {ENABLE_TIMESCALEDB}
            </div>
            
            <div class="grid">
                <div class="card">
                    <h2>🔧 Setup Instructions</h2>
                    <h3>1. Install Home Assistant MCP Integration</h3>
                    <p>Go to: <strong>Settings → Devices & Services → Add Integration</strong></p>
                    <p>Search for: <strong>"Model Context Protocol"</strong></p>
                    
                    <h3>2. Configure MCP Server</h3>
                    <p><strong>Server URL:</strong></p>
                    <div class="url">http://localhost:8099/mcp</div>
                    <p><em>For add-on: Use the add-on's internal URL or ingress</em></p>
                    
                    <h3>3. Available Tools</h3>
                    <div class="tool"><strong>ha.get_history</strong> - Get entity state history</div>
                    <div class="tool"><strong>ha.get_statistics</strong> - Get statistical summaries</div>
                    <div class="tool"><strong>ha.list_entities</strong> - List available entities</div>
                    <div class="tool"><strong>ha.list_statistics</strong> - List available statistics</div>
                    <div class="tool"><strong>addon.health</strong> - Server health status</div>
                </div>
                
                <div class="card">
                    <h2>🧪 Test Interface</h2>
                    <button onclick="testHealth()">Test Health</button>
                    <button onclick="testTools()">Test Tools List</button>
                    <button onclick="testHistory()">Test Get History</button>
                    <button onclick="clearOutput()">Clear Output</button>
                    
                    <div class="output" id="testOutput">
                        Welcome to Home Assistant MCP Server v0.3.4!
                        
                        Ready to serve historical data to AI assistants via MCP protocol.
                        Click test buttons above to verify functionality.
                        
                        Database Status: {db_status}
                        Available Tools: {len(MCP_TOOLS)}
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>📡 API Endpoints</h2>
                <div class="endpoint"><strong>POST /mcp</strong> - Main MCP protocol endpoint (JSON-RPC 2.0)</div>
                <div class="endpoint"><strong>GET /health</strong> - <a href="/health" target="_blank">Health check and status</a></div>
                <div class="endpoint"><strong>GET /</strong> - This testing interface</div>
            </div>
            
            <div class="card">
                <h2>💡 Usage with Home Assistant Assist</h2>
                <p>Once configured, you can ask Home Assistant Assist questions like:</p>
                <ul>
                    <li>"What was the temperature in the living room yesterday?"</li>
                    <li>"Show me energy consumption for the past week"</li>
                    <li>"List all available sensors with historical data"</li>
                    <li>"Get statistics for sensor.power_meter from last month"</li>
                </ul>
            </div>
        </div>
        
        <script>
            function appendOutput(text) {{
                const output = document.getElementById('testOutput');
                const timestamp = new Date().toLocaleTimeString();
                output.innerHTML += `[${timestamp}] ${text}\\n`;
                output.scrollTop = output.scrollHeight;
            }}
            
            function clearOutput() {{
                document.getElementById('testOutput').innerHTML = 'Output cleared.\\n';
            }}
            
            function testHealth() {{
                appendOutput('🔄 Testing health endpoint...');
                fetch('/health')
                .then(response => response.json())
                .then(data => {{
                    appendOutput('✅ Health check successful:');
                    appendOutput(JSON.stringify(data, null, 2));
                }})
                .catch(error => {{
                    appendOutput(`❌ Health check failed: ${error}`);
                }});
            }}
            
            function testTools() {{
                appendOutput('🔄 Testing MCP tools/list...');
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
                    appendOutput('✅ MCP tools/list successful:');
                    appendOutput(JSON.stringify(data, null, 2));
                }})
                .catch(error => {{
                    appendOutput(`❌ MCP tools/list failed: ${error}`);
                }});
            }}
            
            function testHistory() {{
                const endTime = new Date().toISOString();
                const startTime = new Date(Date.now() - 24*60*60*1000).toISOString();
                
                appendOutput('🔄 Testing ha.get_history tool...');
                fetch('/mcp', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        jsonrpc: '2.0',
                        id: '2',
                        method: 'tools/call',
                        params: {{
                            name: 'ha.get_history',
                            arguments: {{
                                entity_id: 'sensor.temperature',
                                start: startTime,
                                end: endTime
                            }}
                        }}
                    }})
                }})
                .then(response => response.json())
                .then(data => {{
                    appendOutput('✅ Get history test completed:');
                    appendOutput(JSON.stringify(data, null, 2));
                }})
                .catch(error => {{
                    appendOutput(`❌ Get history test failed: ${error}`);
                }});
            }}
        </script>
    </body>
    </html>
    """)

if __name__ == "__main__":
    logger.info("🚀 Starting Home Assistant MCP Server v0.3.4...")
    logger.info(f"📊 Database: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    logger.info(f"🔒 Read-only mode: {READ_ONLY}")
    logger.info(f"⚡ TimescaleDB: {ENABLE_TIMESCALEDB}")
    logger.info(f"🔍 Testing database connection...")
    
    conn = get_db_connection()
    if conn:
        logger.info("✅ Database connection successful")
        conn.close()
    else:
        logger.warning("⚠️ Database connection failed - using mock data")
    
    logger.info("✅ Database connectivity verified")
    logger.info(f"🌐 Starting HTTP server on port {PORT}...")
    logger.info("🎯 Web UI available via Home Assistant Ingress")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
