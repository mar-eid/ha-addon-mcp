#!/usr/bin/env python3
"""
MCP Test Client - Simulates MCP protocol communication
Use this to test the server without Home Assistant
"""
import asyncio
import json
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import argparse
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp-test-client")

class MCPTestClient:
    """Test client for MCP Server"""
    
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self.server_process = None
        self.reader = None
        self.writer = None
        
    async def start_server(self, server_path: str = "mcp-server/server.py"):
        """Start the MCP server as a subprocess"""
        logger.info("Starting MCP server...")
        
        # Set environment for mock mode
        env = os.environ.copy()
        if self.mock_mode:
            env['PGHOST'] = 'localhost'
            env['PGPORT'] = '5432'
            env['PGDATABASE'] = 'test'
            env['PGUSER'] = 'test'
            env['PGPASSWORD'] = ''
        
        self.server_process = await asyncio.create_subprocess_exec(
            sys.executable, server_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        logger.info(f"Server started with PID: {self.server_process.pid}")
        return self.server_process
    
    async def send_message(self, message: Dict[str, Any]) -> Optional[Dict]:
        """Send a message to the server and get response"""
        if not self.server_process:
            raise RuntimeError("Server not started")
        
        # Send message
        message_str = json.dumps(message) + "\n"
        self.server_process.stdin.write(message_str.encode())
        await self.server_process.stdin.drain()
        
        # Read response (with timeout)
        try:
            response_line = await asyncio.wait_for(
                self.server_process.stdout.readline(), 
                timeout=5.0
            )
            if response_line:
                return json.loads(response_line.decode())
        except asyncio.TimeoutError:
            logger.warning("Response timeout")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode response: {e}")
        
        return None
    
    async def call_tool(self, tool_name: str, **kwargs) -> Dict:
        """Call an MCP tool"""
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": kwargs
            }
        }
        
        logger.info(f"Calling tool: {tool_name}")
        logger.debug(f"Arguments: {kwargs}")
        
        response = await self.send_message(message)
        
        if response and "result" in response:
            logger.info(f"Tool call successful")
            return response["result"]
        elif response and "error" in response:
            logger.error(f"Tool call failed: {response['error']}")
            return response["error"]
        else:
            logger.error("No response from server")
            return {"error": "No response"}
    
    async def list_tools(self) -> list:
        """List available tools"""
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        response = await self.send_message(message)
        
        if response and "result" in response:
            return response["result"].get("tools", [])
        return []
    
    async def stop_server(self):
        """Stop the MCP server"""
        if self.server_process:
            logger.info("Stopping server...")
            self.server_process.terminate()
            await self.server_process.wait()
            logger.info("Server stopped")

class TestScenarios:
    """Collection of test scenarios"""
    
    def __init__(self, client: MCPTestClient):
        self.client = client
    
    async def test_health_check(self):
        """Test health check"""
        logger.info("\n=== Testing Health Check ===")
        result = await self.client.call_tool("health_check")
        
        assert result.get("status") == "ok", "Health check failed"
        assert "version" in result, "Missing version"
        assert "database" in result, "Missing database status"
        
        logger.info(f"✓ Health check passed: {result}")
        return True
    
    async def test_list_entities(self):
        """Test listing entities"""
        logger.info("\n=== Testing List Entities ===")
        result = await self.client.call_tool("list_entities", limit=10)
        
        assert "entities" in result, "Missing entities"
        assert "statistics" in result, "Missing statistics"
        assert isinstance(result["entities"], list), "Entities should be a list"
        
        logger.info(f"✓ Found {len(result['entities'])} entities and {len(result['statistics'])} statistics")
        return True
    
    async def test_get_history(self):
        """Test getting history data"""
        logger.info("\n=== Testing Get History ===")
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=6)
        
        result = await self.client.call_tool(
            "get_history",
            entity_id="sensor.temperature",
            start=start_time.isoformat() + "Z",
            end=end_time.isoformat() + "Z",
            interval="1h",
            aggregation="mean"
        )
        
        assert "series" in result, "Missing series data"
        assert isinstance(result["series"], list), "Series should be a list"
        assert result.get("entity_id") == "sensor.temperature", "Wrong entity_id"
        
        logger.info(f"✓ Got {len(result['series'])} data points")
        return True
    
    async def test_get_statistics(self):
        """Test getting statistics"""
        logger.info("\n=== Testing Get Statistics ===")
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        result = await self.client.call_tool(
            "get_statistics",
            statistic_id="sensor.temperature",
            start=start_time.isoformat() + "Z",
            end=end_time.isoformat() + "Z",
            period="hour"
        )
        
        assert "series" in result, "Missing series data"
        assert isinstance(result["series"], list), "Series should be a list"
        
        logger.info(f"✓ Got {len(result['series'])} statistical points")
        return True
    
    async def test_error_handling(self):
        """Test error handling"""
        logger.info("\n=== Testing Error Handling ===")
        
        # Test with invalid date range (exceeds max days)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=365)  # Way too long
        
        result = await self.client.call_tool(
            "get_history",
            entity_id="sensor.test",
            start=start_time.isoformat() + "Z",
            end=end_time.isoformat() + "Z"
        )
        
        # Should get an error
        if "error" in result or (isinstance(result, dict) and "message" in result):
            logger.info("✓ Error handling works correctly")
            return True
        else:
            logger.error("Expected error for invalid date range")
            return False
    
    async def run_all_tests(self):
        """Run all test scenarios"""
        tests = [
            self.test_health_check,
            self.test_list_entities,
            self.test_get_history,
            self.test_get_statistics,
            self.test_error_handling
        ]
        
        results = []
        for test in tests:
            try:
                result = await test()
                results.append((test.__name__, result))
            except Exception as e:
                logger.error(f"Test {test.__name__} failed: {e}")
                results.append((test.__name__, False))
        
        # Summary
        logger.info("\n" + "="*50)
        logger.info("TEST SUMMARY")
        logger.info("="*50)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✓ PASSED" if result else "✗ FAILED"
            logger.info(f"{test_name}: {status}")
        
        logger.info(f"\nTotal: {passed}/{total} tests passed")
        
        return passed == total

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="MCP Server Test Client")
    parser.add_argument("--server-path", default="mcp-server/server.py", 
                       help="Path to server.py")
    parser.add_argument("--mock", action="store_true", default=True,
                       help="Use mock data (no database required)")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create client
    client = MCPTestClient(mock_mode=args.mock)
    
    try:
        # Note: In real MCP, the server runs as stdio subprocess
        # For testing, we simulate the protocol
        logger.info("="*50)
        logger.info("MCP SERVER TEST CLIENT")
        logger.info("="*50)
        logger.info(f"Mock mode: {args.mock}")
        logger.info(f"Server path: {args.server_path}")
        
        # For this test, we'll import and test the functions directly
        # since MCP stdio protocol requires more complex setup
        
        # Import server module
        sys.path.insert(0, os.path.dirname(args.server_path))
        import server
        
        # Set to mock mode
        server.db_pool = None
        
        # Create test scenarios
        logger.info("\nRunning test scenarios...")
        
        # Test functions directly
        tests_passed = 0
        tests_total = 5
        
        # Test 1: Health check
        logger.info("\n=== Test 1: Health Check ===")
        result = await server.health_check()
        if result["status"] == "ok":
            logger.info("✓ Health check passed")
            tests_passed += 1
        
        # Test 2: List entities
        logger.info("\n=== Test 2: List Entities ===")
        result = await server.list_entities(limit=5)
        if "entities" in result and "statistics" in result:
            logger.info(f"✓ Listed {len(result['entities'])} entities")
            tests_passed += 1
        
        # Test 3: Get history
        logger.info("\n=== Test 3: Get History ===")
        result = await server.get_history(
            entity_id="sensor.test",
            start="2024-12-19T00:00:00Z",
            end="2024-12-19T06:00:00Z",
            interval="1h",
            aggregation="mean"
        )
        if result["series"] and len(result["series"]) == 6:
            logger.info(f"✓ Got {len(result['series'])} history points")
            tests_passed += 1
        
        # Test 4: Get statistics
        logger.info("\n=== Test 4: Get Statistics ===")
        result = await server.get_statistics(
            statistic_id="sensor.test",
            start="2024-12-19T00:00:00Z",
            end="2024-12-19T12:00:00Z",
            period="hour"
        )
        if "series" in result:
            logger.info(f"✓ Got {len(result['series'])} statistics points")
            tests_passed += 1
        
        # Test 5: Error handling
        logger.info("\n=== Test 5: Error Handling ===")
        try:
            await server.get_history(
                entity_id="sensor.test",
                start="2024-01-01T00:00:00Z",
                end="2024-12-31T00:00:00Z"  # Exceeds max days
            )
            logger.error("✗ Should have raised error for date range")
        except ValueError as e:
            logger.info(f"✓ Error handling works: {e}")
            tests_passed += 1
        
        # Summary
        logger.info("\n" + "="*50)
        logger.info(f"TEST RESULTS: {tests_passed}/{tests_total} passed")
        logger.info("="*50)
        
        if tests_passed == tests_total:
            logger.info("✓ All tests passed!")
            return 0
        else:
            logger.error(f"✗ {tests_total - tests_passed} tests failed")
            return 1
        
    except Exception as e:
        logger.error(f"Test client error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
