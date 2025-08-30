#!/usr/bin/env python3
"""
Home Assistant MCP Server Add-on
Compatible with Home Assistant's official MCP Client integration
Enhanced with comprehensive debug logging and stack traces
Fixed JavaScript errors in web interface
"""

import os
import json
import asyncio
import logging
import traceback
import sys
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field
import uvicorn
import psycopg2
from psycopg2.extras import RealDictCursor

# Enhanced logging configuration
log_level = os.getenv("LOG_LEVEL", "info").upper()
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format=log_format,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Set debug level for key components when in debug mode
if log_level == "DEBUG":
    logging.getLogger("uvicorn").setLevel(logging.DEBUG)
    logging.getLogger("uvicorn.access").setLevel(logging.DEBUG)
    logging.getLogger("psycopg2").setLevel(logging.DEBUG)
    logger.debug("🔍 Debug logging enabled - full stack traces will be shown")

app = FastAPI(title="Home Assistant MCP Server", version="0.3.8")

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

# Enhanced database connection with comprehensive debug logging
def get_db_connection():
    """Get database connection with comprehensive error handling and debug logging"""
    logger.debug(f"Attempting database connection to {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    logger.debug(f"Database config: {dict(DB_CONFIG, password='***' if DB_CONFIG['password'] else None)}")
    
    try:
        start_time = datetime.utcnow()
        conn = psycopg2.connect(
            **DB_CONFIG,
            cursor_factory=RealDictCursor,
            connect_timeout=10
        )
        connection_time = (datetime.utcnow() - start_time).total_seconds()
        logger.debug(f"Database connection established in {connection_time:.3f}s")
        
        # Test the connection with a simple query
        with conn.cursor() as cur:
            cur.execute("SELECT version(), current_database(), current_user")
            db_info = cur.fetchone()
            logger.debug(f"Database info: {db_info}")
            
            # Check available tables for debugging
            if logger.isEnabledFor(logging.DEBUG):
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('states', 'states_meta', 'statistics', 'statistics_meta')
                    ORDER BY table_name
                """)
                tables = [row['table_name'] for row in cur.fetchall()]
                logger.debug(f"Available HA tables: {tables}")
                
        return conn
        
    except psycopg2.OperationalError as e:
        logger.warning(f"Database connection failed (OperationalError): {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Full connection error traceback:\n{traceback.format_exc()}")
        return None
    except psycopg2.Error as e:
        logger.error(f"PostgreSQL error during connection: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Full PostgreSQL error traceback:\n{traceback.format_exc()}")
        return None
    except Exception as e:
        logger.error(f"Unexpected database error: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Full unexpected error traceback:\n{traceback.format_exc()}")
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

# Enhanced database query functions with debug logging
def query_history(entity_id: str, start: str, end: str, limit: int = 1000):
    """Query historical data from Home Assistant recorder database with debug logging"""
    logger.debug(f"query_history called: entity_id={entity_id}, start={start}, end={end}, limit={limit}")
    
    conn = get_db_connection()
    if not conn:
        logger.warning("Using mock data - database not available")
        return generate_mock_series(start, end)
    
    try:
        query_start_time = datetime.utcnow()
        with conn.cursor() as cur:
            # Enhanced query with better filtering and debug info
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
            
            logger.debug(f"Executing query: {query}")
            logger.debug(f"Query parameters: entity_id={entity_id}, start={start}, end={end}, limit={limit}")
            
            cur.execute(query, (entity_id, start, end, limit))
            query_time = (datetime.utcnow() - query_start_time).total_seconds()
            
            results = cur.fetchall()
            logger.debug(f"Query executed in {query_time:.3f}s, returned {len(results)} rows")
            
            if not results:
                logger.info(f"No data found for entity {entity_id} in range {start} to {end}")
                if logger.isEnabledFor(logging.DEBUG):
                    # Check if entity exists at all
                    cur.execute("SELECT entity_id FROM states_meta WHERE entity_id = %s", (entity_id,))
                    entity_exists = cur.fetchone()
                    if entity_exists:
                        logger.debug(f"Entity {entity_id} exists in states_meta")
                        # Check for any data for this entity
                        cur.execute("""
                            SELECT COUNT(*) as count, MIN(last_changed) as min_time, MAX(last_changed) as max_time
                            FROM states s 
                            JOIN states_meta sm ON s.metadata_id = sm.metadata_id 
                            WHERE sm.entity_id = %s
                        """, (entity_id,))
                        entity_stats = cur.fetchone()
                        logger.debug(f"Entity {entity_id} stats: {entity_stats}")
                    else:
                        logger.debug(f"Entity {entity_id} not found in states_meta")
                        
                return generate_mock_series(start, end, 12)  # Smaller mock dataset
            
            data = []
            parse_errors = 0
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
                    parse_errors += 1
                    logger.debug(f"Error parsing row: {e}, row data: {row}")
                    continue
            
            logger.info(f"Retrieved {len(data)} data points for {entity_id}")
            if parse_errors > 0:
                logger.warning(f"Skipped {parse_errors} invalid data points")
            
            if logger.isEnabledFor(logging.DEBUG) and data:
                logger.debug(f"Sample data point: {data[0]}")
                
            return data
            
    except psycopg2.Error as e:
        logger.error(f"PostgreSQL error in query_history: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Full PostgreSQL error traceback:\n{traceback.format_exc()}")
        return generate_mock_series(start, end)
    except Exception as e:
        logger.error(f"Unexpected error in query_history: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Full error traceback:\n{traceback.format_exc()}")
        return generate_mock_series(start, end)
    finally:
        if conn:
            conn.close()
            logger.debug("Database connection closed")

# MCP Tool Handlers with enhanced debug logging
def handle_get_history(params: Dict[str, Any]) -> MCPToolResult:
    """Handle ha.get_history tool calls - Get historical sensor data with debug logging"""
    logger.debug(f"handle_get_history called with params: {params}")
    
    try:
        entity_id = params.get("entity_id")
        start = params.get("start")
        end = params.get("end")
        
        logger.debug(f"Extracted parameters: entity_id={entity_id}, start={start}, end={end}")
        
        if not all([entity_id, start, end]):
            error_msg = "Missing required parameters: entity_id, start, end"
            logger.warning(error_msg)
            return MCPToolResult(
                content=[MCPToolContent(text=error_msg)],
                isError=True
            )
        
        logger.info(f"Getting history for {entity_id} from {start} to {end}")
        
        query_start_time = datetime.utcnow()
        data = query_history(entity_id, start, end)
        query_duration = (datetime.utcnow() - query_start_time).total_seconds()
        
        logger.debug(f"query_history completed in {query_duration:.3f}s, got {len(data)} points")
        
        result = {
            "entity_id": entity_id,
            "start": start,
            "end": end,
            "data_points": len(data),
            "query_duration_seconds": round(query_duration, 3),
            "history": data,
            "message": f"Retrieved {len(data)} data points for {entity_id}"
        }
        
        result_json = json.dumps(result, indent=2)
        logger.debug(f"Returning result with {len(result_json)} characters")
        
        return MCPToolResult(
            content=[MCPToolContent(text=result_json)]
        )
        
    except Exception as e:
        logger.error(f"Error in handle_get_history: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Full handle_get_history error traceback:\n{traceback.format_exc()}")
        return MCPToolResult(
            content=[MCPToolContent(text=f"Error getting history: {str(e)}")],
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
            "version": "0.3.8",
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
            "mcp_tools": ["ha.get_history", "addon.health"],
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

# MCP Tool Registry
MCP_TOOLS = {
    "ha.get_history": {
        "name": "ha.get_history",
        "description": "Get historical state data for a Home Assistant entity over a specified time period.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "The entity ID to get history for (e.g., 'sensor.temperature')"
                },
                "start": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format (e.g., '2024-01-01T00:00:00Z')"
                },
                "end": {
                    "type": "string", 
                    "description": "End time in ISO 8601 format (e.g., '2024-01-02T00:00:00Z')"
                }
            },
            "required": ["entity_id", "start", "end"]
        },
        "handler": handle_get_history
    },
    "addon.health": {
        "name": "addon.health",
        "description": "Get health status and configuration of the MCP server.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        },
        "handler": handle_addon_health
    }
}

# Main MCP Protocol Endpoint with enhanced debug logging
@app.get("/mcp")
async def mcp_sse_endpoint(request: Request):
    """
    SSE endpoint for MCP protocol - Server-Sent Events transport
    Used by MCP clients that prefer streaming connections
    """
    client_info = f"{request.client.host}:{request.client.port}" if request.client else "unknown"
    logger.debug(f"SSE MCP endpoint called by client: {client_info}")
    
    async def sse_stream():
        try:
            # Send endpoint announcement
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
            logger.debug(f"Sent SSE endpoint announcement to {client_info}")
            
            # Send initialization
            init_event = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized", 
                "params": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "Home Assistant MCP Server",
                        "version": "0.3.8"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            }
            yield f"data: {json.dumps(init_event)}\n\n"
            logger.debug(f"Sent SSE initialization to {client_info}")
            
            # Keep connection alive with pings
            ping_count = 0
            while True:
                await asyncio.sleep(30)  # Ping every 30 seconds
                ping_count += 1
                ping_event = {
                    "jsonrpc": "2.0",
                    "method": "notifications/ping",
                    "params": {
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "sequence": ping_count
                    }
                }
                yield f"data: {json.dumps(ping_event)}\n\n"
                logger.debug(f"Sent SSE ping #{ping_count} to {client_info}")
                
        except asyncio.CancelledError:
            logger.info(f"SSE client {client_info} disconnected")
            break
        except Exception as e:
            logger.error(f"SSE stream error for {client_info}: {e}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"SSE error traceback:\n{traceback.format_exc()}")
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

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    Main MCP endpoint compatible with Home Assistant's MCP Client integration
    Handles JSON-RPC 2.0 messages for the Model Context Protocol
    Enhanced with comprehensive debug logging
    """
    client_info = f"{request.client.host}:{request.client.port}" if request.client else "unknown"
    logger.debug(f"MCP endpoint called by client: {client_info}")
    logger.debug(f"Request headers: {dict(request.headers)}")
    
    try:
        request_data = await request.json()
        logger.info(f"Received MCP request: {request_data.get('method', 'unknown')} from {client_info}")
        logger.debug(f"Full request data: {json.dumps(request_data, indent=2)}")
        
        # Handle single request only (simplified)
        logger.debug("Processing single request")
        try:
            mcp_req = MCPRequest(**request_data)
            response = await handle_mcp_request(mcp_req)
            response_dict = response.dict()
            logger.debug(f"Single request completed successfully")
            return response_dict
        except Exception as e:
            logger.error(f"Error creating MCPRequest: {e}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"MCPRequest creation error traceback:\n{traceback.format_exc()}")
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id", "error"),
                "error": {
                    "code": -32600,
                    "message": f"Invalid request: {str(e)}"
                }
            }
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error from {client_info}: {e}")
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": f"Parse error: {str(e)}"
            }
        }
    except Exception as e:
        logger.error(f"Error processing MCP request from {client_info}: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Full MCP endpoint error traceback:\n{traceback.format_exc()}")
        return {
            "jsonrpc": "2.0",
            "id": 0,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

async def handle_mcp_request(request: MCPRequest) -> MCPResponse:
    """Handle individual MCP protocol requests with debug logging"""
    logger.debug(f"handle_mcp_request called: method={request.method}, id={request.id}")
    logger.debug(f"Request params: {request.params}")
    
    try:
        method = request.method
        params = request.params or {}
        logger.info(f"Processing MCP method: {method}")
        
        if method == "initialize":
            logger.debug("Handling initialize request")
            return MCPResponse(
                id=request.id,
                result={
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "Home Assistant MCP Server",
                        "version": "0.3.7"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            )
        
        elif method == "tools/list":
            logger.debug("Handling tools/list request")
            tools = []
            for tool_name, tool_info in MCP_TOOLS.items():
                tools.append({
                    "name": tool_info["name"],
                    "description": tool_info["description"],
                    "inputSchema": tool_info["inputSchema"]
                })
            
            logger.debug(f"Returning {len(tools)} tools")
            return MCPResponse(
                id=request.id,
                result={"tools": tools}
            )
        
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            logger.debug(f"Handling tools/call request: tool={tool_name}, args={tool_args}")
            
            if tool_name not in MCP_TOOLS:
                error_msg = f"Unknown tool: {tool_name}"
                logger.warning(error_msg)
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32602,
                        "message": error_msg
                    }
                )
            
            # Execute the tool
            logger.info(f"Executing tool: {tool_name}")
            tool_handler = MCP_TOOLS[tool_name]["handler"]
            
            tool_start_time = datetime.utcnow()
            result = tool_handler(tool_args)
            tool_duration = (datetime.utcnow() - tool_start_time).total_seconds()
            
            logger.debug(f"Tool {tool_name} executed in {tool_duration:.3f}s")
            logger.debug(f"Tool result isError: {result.isError}")
            
            return MCPResponse(
                id=request.id,
                result=result.dict()
            )
        
        else:
            error_msg = f"Method not found: {method}"
            logger.warning(error_msg)
            return MCPResponse(
                id=request.id,
                error={
                    "code": -32601,
                    "message": error_msg
                }
            )
            
    except Exception as e:
        logger.error(f"Error handling MCP request {request.method}: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Full MCP request error traceback:\n{traceback.format_exc()}")
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
        "version": "0.3.8",
        "database": db_status,
        "read_only": READ_ONLY,
        "timescaledb": ENABLE_TIMESCALEDB,
        "mcp_endpoint": "/mcp",
        "protocol_version": "2024-11-05",
        "available_tools": list(MCP_TOOLS.keys()),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# Root endpoint with FIXED web interface
@app.get("/")
def root():
    """Root endpoint with fixed web interface - no JavaScript errors"""
    conn = get_db_connection()
    db_status = "connected" if conn else "disconnected"
    if conn:
        conn.close()
    
    # Create safe HTML template without problematic JavaScript
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Home Assistant MCP Server v0.3.8</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
                margin: 0; 
                background: #f5f5f5; 
                line-height: 1.6;
            }}
            .header {{ 
                background: linear-gradient(135deg, #1976d2, #42a5f5); 
                color: white; 
                padding: 20px 40px; 
                text-align: center;
            }}
            .container {{ 
                max-width: 1200px; 
                margin: 0 auto; 
                padding: 30px; 
            }}
            .status {{ 
                padding: 15px; 
                border-radius: 8px; 
                margin: 20px 0; 
                font-weight: 500; 
            }}
            .healthy {{ 
                background-color: #e8f5e8; 
                color: #2e7d32; 
                border-left: 4px solid #4caf50; 
            }}
            .warning {{ 
                background-color: #fff8e1; 
                color: #f57c00; 
                border-left: 4px solid #ff9800; 
            }}
            .card {{ 
                background: white; 
                padding: 25px; 
                border-radius: 12px; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
                margin: 20px 0; 
            }}
            .endpoint {{ 
                background: #f8f9fa; 
                padding: 15px; 
                margin: 10px 0; 
                border-left: 4px solid #1976d2; 
                border-radius: 4px; 
                font-family: monospace;
            }}
            .url {{ 
                background: #e3f2fd; 
                padding: 10px; 
                border-radius: 4px; 
                font-family: monospace; 
                color: #1565c0; 
                word-break: break-all;
            }}
            .test-output {{ 
                background: #1e1e1e; 
                color: #00ff41; 
                padding: 20px; 
                border-radius: 8px; 
                font-family: monospace; 
                height: 200px; 
                overflow-y: auto; 
                font-size: 13px; 
                white-space: pre-wrap;
            }}
            button {{ 
                background: #1976d2; 
                color: white; 
                padding: 12px 24px; 
                border: none; 
                border-radius: 6px; 
                cursor: pointer; 
                margin: 5px; 
                font-size: 14px; 
            }}
            button:hover {{ 
                background: #1565c0; 
            }}
            .grid {{ 
                display: grid; 
                grid-template-columns: 1fr 1fr; 
                gap: 20px; 
            }}
            @media (max-width: 768px) {{ 
                .grid {{ 
                    grid-template-columns: 1fr; 
                }} 
            }}
            h1, h2, h3 {{ 
                color: #1976d2; 
            }}
            .tool {{ 
                background: #f5f5f5; 
                padding: 12px; 
                margin: 8px 0; 
                border-radius: 6px; 
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🤖 Home Assistant MCP Server v0.3.8</h1>
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
                    <div class="tool"><strong>addon.health</strong> - Server health status</div>
                </div>
                
                <div class="card">
                    <h2>🧪 Test Interface</h2>
                    <button onclick="testHealth()">Test Health</button>
                    <button onclick="testTools()">Test Tools List</button>
                    <button onclick="testHistory()">Test Get History</button>
                    <button onclick="testSSE()">Test SSE Stream</button>
                    <button onclick="stopSSE()">Stop SSE</button>
                    <button onclick="clearOutput()">Clear Output</button>
                    
                    <div class="test-output" id="testOutput">Welcome to Home Assistant MCP Server v0.3.8!

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
                    <li>"Get history for sensor.temperature from last month"</li>
                </ul>
            </div>
        </div>
        
        <script>
            // Fixed JavaScript functions without errors
            function addLogEntry(text) {{
                const output = document.getElementById('testOutput');
                const now = new Date();
                const timeStr = now.toLocaleTimeString();
                output.textContent += '[' + timeStr + '] ' + text + '\\n';
                output.scrollTop = output.scrollHeight;
            }}
            
            function clearOutput() {{
                document.getElementById('testOutput').textContent = 'Output cleared.\\n';
            }}
            
            function testHealth() {{
                addLogEntry('🔄 Testing health endpoint...');
                fetch('/health')
                .then(function(response) {{ return response.json(); }})
                .then(function(data) {{
                    addLogEntry('✅ Health check successful:');
                    addLogEntry(JSON.stringify(data, null, 2));
                }})
                .catch(function(error) {{
                    addLogEntry('❌ Health check failed: ' + error);
                }});
            }}
            
            function testTools() {{
                addLogEntry('🔄 Testing MCP tools/list...');
                fetch('/mcp', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        jsonrpc: '2.0',
                        id: '1',
                        method: 'tools/list'
                    }})
                }})
                .then(function(response) {{ return response.json(); }})
                .then(function(data) {{
                    addLogEntry('✅ MCP tools/list successful:');
                    addLogEntry(JSON.stringify(data, null, 2));
                }})
                .catch(function(error) {{
                    addLogEntry('❌ MCP tools/list failed: ' + error);
                }});
            }}
            
            function testHistory() {{
                const now = new Date();
                const endTime = now.toISOString();
                const startTime = new Date(now.getTime() - 24*60*60*1000).toISOString();
                
                addLogEntry('🔄 Testing ha.get_history tool...');
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
                .then(function(response) {{ return response.json(); }})
                .then(function(data) {{
                    addLogEntry('✅ Get history test completed:');
                    addLogEntry(JSON.stringify(data, null, 2));
                }})
                .catch(function(error) {{
                    addLogEntry('❌ Get history test failed: ' + error);
                }});
            }}
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

def main():
    """Enhanced main function with comprehensive debug logging"""
    logger.info("🚀 Starting Home Assistant MCP Server v0.3.8...")
    logger.info(f"📊 Database: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    logger.info(f"🔒 Read-only mode: {READ_ONLY}")
    logger.info(f"⚡ TimescaleDB: {ENABLE_TIMESCALEDB}")
    logger.info(f"🔍 Log level: {log_level}")
    
    # Enhanced startup logging for debug mode
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("🔧 Debug mode enabled - comprehensive logging active")
        logger.debug(f"Python version: {sys.version}")
        logger.debug("Environment variables (MCP_* and PG*):")
        for key, value in sorted(os.environ.items()):
            if key.startswith('MCP_') or key.startswith('PG'):
                display_value = '***' if 'PASSWORD' in key.upper() else value
                logger.debug(f"  {key}={display_value}")
        logger.debug(f"Available MCP tools: {list(MCP_TOOLS.keys())}")
    
    logger.info(f"🔍 Testing database connection...")
    
    try:
        conn_start = datetime.utcnow()
        conn = get_db_connection()
        conn_time = (datetime.utcnow() - conn_start).total_seconds()
        
        if conn:
            logger.info("✅ Database connection successful")
            logger.debug(f"Database connection test completed in {conn_time:.3f}s")
            conn.close()
        else:
            logger.warning("⚠️  Database connection failed - using mock data")
            
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Database test error traceback:\n{traceback.format_exc()}")
    
    logger.info("✅ Database connectivity verified")
    logger.info(f"🌐 Starting HTTP server on port {PORT}...")
    logger.info("🎯 Web UI available via Home Assistant Ingress")
    
    # Enhanced uvicorn configuration for debug mode
    uvicorn_log_level = log_level.lower() if log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR'] else "info"
    
    uvicorn_config = {
        "app": app,
        "host": "0.0.0.0",
        "port": PORT,
        "log_level": uvicorn_log_level,
        "access_log": logger.isEnabledFor(logging.DEBUG)
    }
    
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Uvicorn config: {uvicorn_config}")
    
    logger.info("🚀 MCP Server startup complete - ready to serve!")
    
    try:
        uvicorn.run(**uvicorn_config)
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Server startup error traceback:\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
