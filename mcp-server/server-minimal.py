"""
Home Assistant MCP Server - Minimal Version
Model Context Protocol server for Home Assistant historical data
Version: 0.5.4-minimal
"""
import os
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import threading
import time

# Only essential imports - no FastAPI to avoid build issues
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    print("Warning: asyncpg not available, using mock data only")

try:
    import mcp.types as types
    from mcp.server import Server
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("Warning: MCP SDK not available, using basic HTTP server")

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

# Global variables
db_pool = None
connected_clients = set()

class HAMCPServer:
    """Minimal Home Assistant MCP Server Implementation"""
    
    def __init__(self):
        self.tools = [
            {
                "name": "get_history",
                "description": "Query historical state data from Home Assistant recorder"
            },
            {
                "name": "get_statistics", 
                "description": "Query aggregated statistics data from Home Assistant"
            },
            {
                "name": "list_entities",
                "description": "List available entities and statistics for querying"
            },
            {
                "name": "health_check",
                "description": "Check server and database health status"
            }
        ]
    
    async def get_history(self, entity_id: str, start: str, end: str, **kwargs) -> Dict[str, Any]:
        """Query historical state data"""
        logger.info(f"get_history: {entity_id} from {start} to {end}")
        
        # Always use mock data in minimal version
        return {
            "entity_id": entity_id,
            "series": self.generate_mock_series(start, end),
            "mock_data": True,
            "message": "Using mock data - install full version for database access"
        }
    
    async def get_statistics(self, statistic_id: str, start: str, end: str, **kwargs) -> Dict[str, Any]:
        """Query aggregated statistics data"""
        logger.info(f"get_statistics: {statistic_id}")
        
        series = self.generate_mock_series(start, end)
        for item in series:
            value = item["v"]
            item.update({
                "mean": value,
                "min": value - 2,
                "max": value + 2
            })
            del item["v"]
        
        return {
            "statistic_id": statistic_id,
            "series": series,
            "mock_data": True
        }
    
    async def list_entities(self, limit: int = 100, **kwargs) -> Dict[str, Any]:
        """List available entities and statistics"""
        return {
            "entities": [
                {"entity_id": "sensor.temperature", "last_seen": datetime.utcnow().isoformat() + "Z"},
                {"entity_id": "sensor.humidity", "last_seen": datetime.utcnow().isoformat() + "Z"}
            ],
            "statistics": [
                {"statistic_id": "sensor.temperature", "unit": "°C", "source": "recorder"}
            ],
            "mock_data": True
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check server and database health"""
        return {
            "status": "ok",
            "version": "0.5.4-minimal",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "database": {"status": "mock"},
            "transport": "HTTP",
            "connected_clients": len(connected_clients),
            "message": "Minimal version - using mock data only"
        }
    
    def generate_mock_series(self, start: str, end: str, interval: str = "1h") -> List[Dict]:
        """Generate mock time series data"""
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except:
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(hours=24)
        
        series = []
        current = start_dt
        value = 20.0
        
        while current < end_dt and len(series) < 100:
            series.append({
                "t": current.isoformat() + "Z",
                "v": round(value + (hash(str(current)) % 10) - 5, 2)
            })
            current += timedelta(hours=1)
            value += 0.1
        
        return series

# HTTP Server Implementation
class MCPRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, mcp_server=None, **kwargs):
        self.mcp_server = mcp_server
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = f"""
            <!DOCTYPE html>
            <html>
            <head><title>MCP Server v0.5.4-minimal</title></head>
            <body style="font-family: sans-serif; margin: 2rem;">
                <h1>🛠️ Home Assistant MCP Server</h1>
                <p><strong>Version:</strong> 0.5.4-minimal</p>
                <p><strong>Status:</strong> Running (Mock Mode)</p>
                <h2>Available Tools:</h2>
                <ul>
                    <li>get_history - Query historical state data</li>
                    <li>get_statistics - Query aggregated statistics</li> 
                    <li>list_entities - List available entities</li>
                    <li>health_check - Server health status</li>
                </ul>
                <h2>Endpoints:</h2>
                <ul>
                    <li><a href="/health">GET /health</a> - Health check</li>
                    <li>POST /mcp/call - Tool calls</li>
                </ul>
                <p><em>This is the minimal version using mock data only.</em></p>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
            
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            if hasattr(self, 'mcp_server') and self.mcp_server:
                health = asyncio.run(self.mcp_server.health_check())
            else:
                health = {"status": "ok", "version": "0.5.4-minimal"}
            self.wfile.write(json.dumps(health, indent=2).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/mcp/call':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                request_data = json.loads(post_data.decode())
                method = request_data.get("method", "")
                params = request_data.get("params", {})
                
                if hasattr(self, 'mcp_server') and self.mcp_server:
                    if method == "tools/call":
                        tool_name = params.get("name")
                        arguments = params.get("arguments", {})
                        
                        if tool_name == "get_history":
                            result = asyncio.run(self.mcp_server.get_history(**arguments))
                        elif tool_name == "get_statistics":
                            result = asyncio.run(self.mcp_server.get_statistics(**arguments))
                        elif tool_name == "list_entities":
                            result = asyncio.run(self.mcp_server.list_entities(**arguments))
                        elif tool_name == "health_check":
                            result = asyncio.run(self.mcp_server.health_check())
                        else:
                            result = {"error": f"Unknown tool: {tool_name}"}
                        
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_data.get("id"),
                            "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
                        }
                    else:
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_data.get("id"),
                            "error": {"code": -32601, "message": f"Unknown method: {method}"}
                        }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_data.get("id"),
                        "error": {"code": -32603, "message": "Server not initialized"}
                    }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response, indent=2).encode())
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32603, "message": str(e)}
                }
                self.wfile.write(json.dumps(error_response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        logger.info(f"HTTP: {format % args}")

def create_handler_with_server(mcp_server):
    """Create request handler with MCP server instance"""
    def handler(*args, **kwargs):
        return MCPRequestHandler(*args, mcp_server=mcp_server, **kwargs)
    return handler

def main():
    """Main entry point"""
    logger.info("🚀 Starting Home Assistant MCP Server (Minimal)")
    logger.info("📦 Version: 0.5.4-minimal")
    logger.info("🔧 Using minimal HTTP server (no external dependencies)")
    
    # Create MCP server instance
    mcp_server = HAMCPServer()
    logger.info("🌐 MCP server initialized")
    
    # Create HTTP server
    handler = create_handler_with_server(mcp_server)
    httpd = HTTPServer(('0.0.0.0', MCP_PORT), handler)
    
    logger.info(f"🌐 Starting HTTP server on port {MCP_PORT}")
    logger.info(f"🔗 Web interface: http://localhost:{MCP_PORT}/")
    logger.info(f"🔗 Health check: http://localhost:{MCP_PORT}/health")
    logger.info(f"🔗 MCP calls: POST http://localhost:{MCP_PORT}/mcp/call")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("⏹️ Server stopped by user")
    finally:
        httpd.server_close()
        logger.info("🛑 Server shutdown complete")

if __name__ == "__main__":
    main()
