"""
MCP Server for Home Assistant Historical Data
Version: 0.4.2
"""
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Literal, AsyncGenerator
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field
import uvicorn
import logging
import asyncpg
from asyncpg.pool import Pool
from sse_starlette.sse import EventSourceResponse
import uuid

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
    version="0.4.2",
    description="Model Context Protocol server for Home Assistant historical data"
)

# Database connection pool
db_pool: Optional[Pool] = None

# SSE client management
sse_clients: Dict[str, Any] = {}

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
# MCP Tool Implementations (Mock for testing)
# =============================================================================

async def get_history_data(params: HistoryRequest) -> Dict[str, Any]:
    """Fetch historical state data from recorder (mock for testing)"""
    # For testing, return mock data
    start_dt = datetime.fromisoformat(params.start.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(params.end.replace("Z", "+00:00"))
    
    # Generate mock time series
    series = []
    current = start_dt
    value = 20.0
    while current < end_dt:
        series.append({
            "t": current.isoformat() + "Z",
            "v": round(value + (hash(str(current)) % 10) - 5, 2)
        })
        current += timedelta(hours=1)
        value += 0.1
    
    return {
        "entity_id": params.entity_id,
        "series": series,
        "count": len(series),
        "interval": params.interval,
        "aggregation": params.agg
    }

async def get_statistics_data(params: StatisticsRequest) -> Dict[str, Any]:
    """Fetch statistics data (mock for testing)"""
    start_dt = datetime.fromisoformat(params.start.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(params.end.replace("Z", "+00:00"))
    
    series = []
    current = start_dt
    base_value = 22.0
    while current < end_dt:
        item = {"t": current.isoformat() + "Z"}
        for field in params.fields:
            if field == "mean":
                item[field] = round(base_value, 2)
            elif field == "min":
                item[field] = round(base_value - 2, 2)
            elif field == "max":
                item[field] = round(base_value + 2, 2)
            elif field == "sum":
                item[field] = round(base_value * 24, 2)
        series.append(item)
        current += timedelta(hours=1 if params.period == "hour" else 24)
        base_value += 0.05
    
    return {
        "statistic_id": params.statistic_id,
        "source": "recorder",
        "unit": "°C",
        "series": series,
        "count": len(series),
        "period": params.period
    }

async def list_entities() -> Dict[str, Any]:
    """List available entities (mock for testing)"""
    mock_entities = [
        {"entity_id": "sensor.temperature", "state_count": 1440, "last_seen": datetime.utcnow().isoformat() + "Z"},
        {"entity_id": "sensor.humidity", "state_count": 1440, "last_seen": datetime.utcnow().isoformat() + "Z"},
        {"entity_id": "sensor.pressure", "state_count": 720, "last_seen": datetime.utcnow().isoformat() + "Z"},
    ]
    
    mock_statistics = [
        {"statistic_id": "sensor.temperature", "source": "recorder", "unit": "°C", "has_mean": True, "has_sum": False},
        {"statistic_id": "sensor.humidity", "source": "recorder", "unit": "%", "has_mean": True, "has_sum": False},
    ]
    
    return {
        "entities": mock_entities,
        "statistics": mock_statistics,
        "entity_count": len(mock_entities),
        "statistic_count": len(mock_statistics)
    }

# =============================================================================
# SSE (Server-Sent Events) Implementation for MCP
# =============================================================================

async def sse_generator(request: Request) -> AsyncGenerator:
    """Generate SSE events for MCP protocol"""
    client_id = str(uuid.uuid4())
    sse_clients[client_id] = {"connected": datetime.utcnow()}
    
    logger.info(f"SSE client connected: {client_id}")
    
    try:
        # Send initial connection event
        yield {
            "event": "connection",
            "data": json.dumps({
                "protocol": "mcp",
                "version": "0.1.0",
                "capabilities": {
                    "tools": True,
                    "prompts": False,
                    "resources": False,
                    "logging": False,
                    "sampling": False
                }
            })
        }
        
        # Send available tools
        yield {
            "event": "tools",
            "data": json.dumps({
                "tools": [
                    {
                        "name": "ha.get_history",
                        "description": "Query historical state data from Home Assistant recorder",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "entity_id": {"type": "string"},
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "interval": {"type": "string"},
                                "agg": {"type": "string"}
                            },
                            "required": ["entity_id", "start", "end"]
                        }
                    },
                    {
                        "name": "ha.get_statistics",
                        "description": "Query aggregated statistics data",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "statistic_id": {"type": "string"},
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "period": {"type": "string"},
                                "fields": {"type": "array", "items": {"type": "string"}}
                            },
                            "required": ["statistic_id", "start", "end"]
                        }
                    },
                    {
                        "name": "ha.list_entities",
                        "description": "List available entities with recent data",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                ]
            })
        }
        
        # Keep connection alive with periodic pings
        ping_count = 0
        while True:
            if await request.is_disconnected():
                break
                
            await asyncio.sleep(30)  # Send ping every 30 seconds
            ping_count += 1
            yield {
                "event": "ping",
                "data": json.dumps({
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "sequence": ping_count
                })
            }
            
    except asyncio.CancelledError:
        logger.info(f"SSE client disconnected: {client_id}")
    finally:
        if client_id in sse_clients:
            del sse_clients[client_id]

@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSE endpoint for MCP protocol"""
    return EventSourceResponse(sse_generator(request))

# =============================================================================
# MCP Protocol Endpoints
# =============================================================================

@app.post("/mcp")
async def mcp_handler(request: Request):
    """Main MCP protocol handler for tool calls"""
    try:
        body = await request.json()
        mcp_request = MCPRequest(**body)
        
        logger.info(f"MCP request: {mcp_request.method}")
        
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
                        "name": "ha.list_entities",
                        "description": "List available entities with recent data",
                        "inputSchema": {}
                    }
                ]
            }
        elif mcp_request.method == "tools/call":
            tool_name = mcp_request.params.get("name")
            tool_params = mcp_request.params.get("arguments", {})
            
            logger.info(f"Calling tool: {tool_name}")
            
            if tool_name == "ha.get_history":
                result = await get_history_data(HistoryRequest(**tool_params))
            elif tool_name == "ha.get_statistics":
                result = await get_statistics_data(StatisticsRequest(**tool_params))
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
# Test Interface
# =============================================================================

@app.get("/")
async def root():
    """Serve test interface"""
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>MCP Server - Test Interface</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .status {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 5px;
            font-weight: bold;
            margin-left: 10px;
        }
        .status.online { background: #10b981; color: white; }
        .status.offline { background: #ef4444; color: white; }
        .section {
            margin: 30px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .button {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            margin: 5px;
            transition: all 0.3s;
        }
        .button:hover {
            background: #764ba2;
            transform: translateY(-2px);
        }
        .button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        #output {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 15px;
            border-radius: 6px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            max-height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .test-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 10px;
            margin: 20px 0;
        }
        .info-box {
            background: #e0f2fe;
            border-left: 4px solid #0284c7;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }
        .error-box {
            background: #fee2e2;
            border-left: 4px solid #dc2626;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }
        .sse-status {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 10px 15px;
            background: #f3f4f6;
            border-radius: 6px;
            margin: 10px 0;
        }
        .sse-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #ef4444;
            animation: pulse 2s infinite;
        }
        .sse-indicator.connected {
            background: #10b981;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏠 MCP Server <span class="status online">v0.4.2</span></h1>
        <p>Model Context Protocol server for Home Assistant historical data</p>
        
        <div class="section">
            <h2>🔌 SSE Connection Test</h2>
            <div class="sse-status">
                <div id="sseIndicator" class="sse-indicator"></div>
                <span id="sseStatus">Disconnected</span>
            </div>
            <div class="test-grid">
                <button class="button" onclick="testSSE()">Test SSE Connection</button>
                <button class="button" onclick="stopSSE()">Stop SSE</button>
                <button class="button" onclick="testMCPTools()">Test MCP Tools</button>
            </div>
            <div id="sseMessages" style="display:none;" class="info-box">
                <strong>SSE Messages:</strong>
                <div id="sseLog" style="max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 12px;"></div>
            </div>
        </div>

        <div class="section">
            <h2>🧪 API Tests</h2>
            <div class="test-grid">
                <button class="button" onclick="testHealth()">Test Health</button>
                <button class="button" onclick="testHistory()">Test History</button>
                <button class="button" onclick="testStatistics()">Test Statistics</button>
                <button class="button" onclick="testEntities()">Test List Entities</button>
                <button class="button" onclick="testMCPProtocol()">Test MCP Protocol</button>
            </div>
        </div>

        <div class="section">
            <h2>📋 Output</h2>
            <div id="output">Ready for testing...</div>
        </div>

        <div class="info-box">
            <h3>🔧 Integration Setup</h3>
            <p><strong>For Home Assistant MCP Client:</strong></p>
            <ul>
                <li>SSE URL: <code>http://localhost:8099/sse</code></li>
                <li>MCP URL: <code>http://localhost:8099/mcp</code></li>
                <li>Transport: Server-Sent Events (SSE)</li>
            </ul>
        </div>
    </div>

    <script>
        let eventSource = null;
        
        function log(message, isError = false) {
            const output = document.getElementById('output');
            const timestamp = new Date().toISOString();
            const prefix = isError ? '❌ ERROR' : '✅';
            output.textContent += `\\n[${timestamp}] ${prefix} ${message}`;
            output.scrollTop = output.scrollHeight;
        }

        function logSSE(message) {
            const sseLog = document.getElementById('sseLog');
            const timestamp = new Date().toTimeString().split(' ')[0];
            sseLog.innerHTML += `[${timestamp}] ${message}<br>`;
            sseLog.scrollTop = sseLog.scrollHeight;
        }

        async function testSSE() {
            log('Testing SSE connection...');
            
            if (eventSource) {
                eventSource.close();
            }
            
            document.getElementById('sseMessages').style.display = 'block';
            document.getElementById('sseLog').innerHTML = '';
            
            eventSource = new EventSource('/sse');
            
            eventSource.onopen = () => {
                log('SSE connection opened');
                document.getElementById('sseStatus').textContent = 'Connected';
                document.getElementById('sseIndicator').classList.add('connected');
                logSSE('Connection established');
            };
            
            eventSource.onerror = (error) => {
                log('SSE connection error', true);
                document.getElementById('sseStatus').textContent = 'Error';
                document.getElementById('sseIndicator').classList.remove('connected');
                logSSE('Connection error');
            };
            
            eventSource.addEventListener('connection', (event) => {
                const data = JSON.parse(event.data);
                log('Received connection event: ' + JSON.stringify(data, null, 2));
                logSSE('Connection: ' + data.protocol + ' v' + data.version);
            });
            
            eventSource.addEventListener('tools', (event) => {
                const data = JSON.parse(event.data);
                log('Received tools event with ' + data.tools.length + ' tools');
                logSSE('Tools: ' + data.tools.map(t => t.name).join(', '));
            });
            
            eventSource.addEventListener('ping', (event) => {
                const data = JSON.parse(event.data);
                logSSE('Ping #' + data.sequence);
            });
            
            eventSource.onmessage = (event) => {
                logSSE('Message: ' + event.data);
            };
        }

        function stopSSE() {
            if (eventSource) {
                eventSource.close();
                eventSource = null;
                log('SSE connection closed');
                document.getElementById('sseStatus').textContent = 'Disconnected';
                document.getElementById('sseIndicator').classList.remove('connected');
            }
        }

        async function testHealth() {
            try {
                const response = await fetch('/health');
                const data = await response.json();
                log('Health check: ' + JSON.stringify(data, null, 2));
            } catch (error) {
                log('Health check failed: ' + error, true);
            }
        }

        async function testHistory() {
            try {
                const response = await fetch('/tools/ha.get_history', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        entity_id: 'sensor.temperature',
                        start: new Date(Date.now() - 24*60*60*1000).toISOString(),
                        end: new Date().toISOString(),
                        interval: '1h',
                        agg: 'mean'
                    })
                });
                const data = await response.json();
                log('History data: ' + JSON.stringify(data, null, 2));
            } catch (error) {
                log('History test failed: ' + error, true);
            }
        }

        async function testStatistics() {
            try {
                const response = await fetch('/tools/ha.get_statistics', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        statistic_id: 'sensor.temperature',
                        start: new Date(Date.now() - 24*60*60*1000).toISOString(),
                        end: new Date().toISOString(),
                        period: 'hour',
                        fields: ['mean', 'min', 'max']
                    })
                });
                const data = await response.json();
                log('Statistics data: ' + JSON.stringify(data, null, 2));
            } catch (error) {
                log('Statistics test failed: ' + error, true);
            }
        }

        async function testEntities() {
            try {
                const response = await fetch('/tools/ha.list_entities');
                const data = await response.json();
                log('Entities: ' + JSON.stringify(data, null, 2));
            } catch (error) {
                log('Entities test failed: ' + error, true);
            }
        }

        async function testMCPProtocol() {
            try {
                const response = await fetch('/mcp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        id: 1,
                        method: 'tools/list',
                        params: {}
                    })
                });
                const data = await response.json();
                log('MCP tools/list: ' + JSON.stringify(data, null, 2));
            } catch (error) {
                log('MCP protocol test failed: ' + error, true);
            }
        }

        async function testMCPTools() {
            try {
                log('Testing MCP tool call...');
                const response = await fetch('/mcp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        id: 2,
                        method: 'tools/call',
                        params: {
                            name: 'ha.list_entities',
                            arguments: {}
                        }
                    })
                });
                const data = await response.json();
                log('MCP tool call result: ' + JSON.stringify(data, null, 2));
            } catch (error) {
                log('MCP tool call failed: ' + error, true);
            }
        }

        // Auto-test health on load
        window.onload = () => {
            testHealth();
        };
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

# =============================================================================
# REST API Endpoints (for compatibility and testing)
# =============================================================================

@app.get("/health")
async def health():
    """Health check endpoint"""
    db_status = "connected" if db_pool else "mock_mode"
    
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                db_status = "healthy"
        except:
            db_status = "unhealthy"
    
    return {
        "status": "ok",
        "version": "0.4.2",
        "database": db_status,
        "read_only": READ_ONLY,
        "timescaledb": ENABLE_TIMESCALE,
        "sse_clients": len(sse_clients),
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

@app.get("/tools/ha.list_entities")
async def rest_list_entities():
    """REST endpoint to list entities"""
    return await list_entities()

# =============================================================================
# Application Lifecycle
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Starting MCP Server v0.4.2")
    logger.info(f"SSE endpoint available at: http://localhost:{PORT}/sse")
    logger.info(f"MCP endpoint available at: http://localhost:{PORT}/mcp")
    logger.info(f"Test interface available at: http://localhost:{PORT}/")
    
    success = await init_db_pool()
    if not success:
        logger.warning("⚠️ Running in mock mode - database not connected")
        logger.info("Using mock data for testing SSE functionality")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down MCP Server")
    
    # Close all SSE connections
    for client_id in list(sse_clients.keys()):
        logger.info(f"Closing SSE client: {client_id}")
    sse_clients.clear()
    
    await close_db_pool()

# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    try:
        logger.info(f"Starting server on port {PORT}")
        logger.info(f"Test interface: http://localhost:{PORT}/")
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
