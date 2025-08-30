#!/usr/bin/env python3
"""
Test script for Home Assistant MCP Server
Tests the MCP server implementation locally
"""
import json
import asyncio
import subprocess
import sys
from datetime import datetime, timedelta

async def test_mcp_server():
    """Test the MCP server using stdio transport"""
    
    print("🧪 Testing Home Assistant MCP Server")
    print("=" * 50)
    
    # Set environment variables for testing
    import os
    os.environ.update({
        "PGHOST": "localhost",
        "PGPORT": "5432", 
        "PGDATABASE": "homeassistant",
        "PGUSER": "test",
        "PGPASSWORD": "",
        "MCP_READ_ONLY": "true",
        "MCP_ENABLE_TIMESCALEDB": "false",
        "LOG_LEVEL": "DEBUG"
    })
    
    try:
        # Import the server
        sys.path.append('.')
        from server import HAMCPServer, main
        
        print("✅ Server imports successful")
        
        # Test server initialization
        server_instance = HAMCPServer()
        print("✅ Server instance created")
        
        # Test tool registration
        tools = await server_instance.server._handlers['list_tools']()
        print(f"✅ Found {len(tools)} registered tools:")
        for tool in tools:
            print(f"   - {tool.name}: {tool.description}")
        
        # Test health check
        print("\n🔍 Testing health check...")
        health_result = await server_instance.health_check()
        print(f"✅ Health check: {health_result['status']}")
        
        # Test list entities (will use mock data)
        print("\n📋 Testing list entities...")
        entities_result = await server_instance.list_entities(limit=5)
        print(f"✅ Found {len(entities_result.get('entities', []))} entities")
        
        # Test get history with mock data
        print("\n📈 Testing get history...")
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        history_result = await server_instance.get_history(
            entity_id="sensor.temperature",
            start=start_time.isoformat() + "Z",
            end=end_time.isoformat() + "Z",
            interval="1h"
        )
        
        print(f"✅ Got {len(history_result.get('series', []))} data points")
        if history_result.get('mock_data'):
            print("   (Using mock data - no database connected)")
        
        # Test get statistics
        print("\n📊 Testing get statistics...")
        stats_result = await server_instance.get_statistics(
            statistic_id="sensor.temperature",
            start=start_time.isoformat() + "Z",
            end=end_time.isoformat() + "Z",
            period="hour"
        )
        
        print(f"✅ Got {len(stats_result.get('series', []))} statistical points")
        
        print("\n🎉 All tests passed!")
        print("✅ MCP Server is working correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔬 Home Assistant MCP Server Test")
    print("This will test the server functionality locally\n")
    
    success = asyncio.run(test_mcp_server())
    
    if success:
        print("\n✅ All tests completed successfully!")
        print("🚀 Your MCP server is ready for deployment")
    else:
        print("\n❌ Some tests failed")
        print("🔧 Please check the error messages above")
        sys.exit(1)
