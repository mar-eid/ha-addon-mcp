#!/usr/bin/env python3
"""
Local test script for MCP Server SSE functionality
Run this to test the server locally without Home Assistant
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime
import argparse

# ANSI color codes for terminal output
COLORS = {
    'GREEN': '\033[92m',
    'YELLOW': '\033[93m',
    'RED': '\033[91m',
    'BLUE': '\033[94m',
    'MAGENTA': '\033[95m',
    'CYAN': '\033[96m',
    'RESET': '\033[0m',
    'BOLD': '\033[1m'
}

def print_colored(message, color='RESET', bold=False):
    """Print colored message to terminal"""
    prefix = COLORS.get(color, '')
    if bold:
        prefix += COLORS['BOLD']
    print(f"{prefix}{message}{COLORS['RESET']}")

async def test_health(base_url):
    """Test health endpoint"""
    print_colored("\n📋 Testing Health Endpoint...", 'CYAN', bold=True)
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{base_url}/health") as response:
                data = await response.json()
                print_colored(f"✅ Health check passed", 'GREEN')
                print(json.dumps(data, indent=2))
                return True
        except Exception as e:
            print_colored(f"❌ Health check failed: {e}", 'RED')
            return False

async def test_sse_connection(base_url, duration=30):
    """Test SSE connection and receive events"""
    print_colored(f"\n📡 Testing SSE Connection (listening for {duration} seconds)...", 'CYAN', bold=True)
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{base_url}/sse") as response:
                print_colored(f"✅ SSE connection established", 'GREEN')
                print_colored(f"Response headers: {dict(response.headers)}", 'BLUE')
                
                # Check content-type
                content_type = response.headers.get('content-type', '')
                if 'text/event-stream' in content_type:
                    print_colored(f"✅ Correct content-type: {content_type}", 'GREEN')
                else:
                    print_colored(f"⚠️ Unexpected content-type: {content_type}", 'YELLOW')
                
                # Read SSE stream
                start_time = asyncio.get_event_loop().time()
                event_count = 0
                
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    
                    if not line:
                        continue
                    
                    if line.startswith('event:'):
                        event_type = line[6:].strip()
                        print_colored(f"\n📨 Event: {event_type}", 'MAGENTA')
                        event_count += 1
                    elif line.startswith('data:'):
                        data = line[5:].strip()
                        try:
                            parsed = json.loads(data)
                            print(json.dumps(parsed, indent=2))
                        except:
                            print(data)
                    
                    # Check if we've listened long enough
                    if asyncio.get_event_loop().time() - start_time > duration:
                        print_colored(f"\n✅ Test completed. Received {event_count} events in {duration} seconds", 'GREEN')
                        break
                        
        except Exception as e:
            print_colored(f"❌ SSE connection failed: {e}", 'RED')
            return False
    
    return True

async def test_mcp_protocol(base_url):
    """Test MCP protocol endpoints"""
    print_colored("\n🔧 Testing MCP Protocol...", 'CYAN', bold=True)
    
    async with aiohttp.ClientSession() as session:
        # Test tools/list
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
            async with session.post(f"{base_url}/mcp", json=payload) as response:
                data = await response.json()
                print_colored(f"✅ MCP tools/list successful", 'GREEN')
                print(f"Available tools: {len(data.get('result', {}).get('tools', []))}")
                for tool in data.get('result', {}).get('tools', []):
                    print(f"  - {tool['name']}: {tool['description']}")
        except Exception as e:
            print_colored(f"❌ MCP tools/list failed: {e}", 'RED')
        
        # Test tool call
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "ha.list_entities",
                    "arguments": {}
                }
            }
            async with session.post(f"{base_url}/mcp", json=payload) as response:
                data = await response.json()
                if 'result' in data:
                    print_colored(f"✅ MCP tool call successful", 'GREEN')
                    entities = data['result'].get('entities', [])
                    print(f"Found {len(entities)} entities")
                else:
                    print_colored(f"⚠️ MCP tool call returned error: {data.get('error')}", 'YELLOW')
        except Exception as e:
            print_colored(f"❌ MCP tool call failed: {e}", 'RED')

async def test_rest_endpoints(base_url):
    """Test REST API endpoints"""
    print_colored("\n🔌 Testing REST Endpoints...", 'CYAN', bold=True)
    
    async with aiohttp.ClientSession() as session:
        # Test history endpoint
        try:
            payload = {
                "entity_id": "sensor.test",
                "start": "2024-12-18T00:00:00Z",
                "end": "2024-12-19T00:00:00Z",
                "interval": "1h",
                "agg": "mean"
            }
            async with session.post(f"{base_url}/tools/ha.get_history", json=payload) as response:
                data = await response.json()
                print_colored(f"✅ History endpoint working", 'GREEN')
                print(f"  Returned {data.get('count', 0)} data points")
        except Exception as e:
            print_colored(f"❌ History endpoint failed: {e}", 'RED')
        
        # Test entities list
        try:
            async with session.get(f"{base_url}/tools/ha.list_entities") as response:
                data = await response.json()
                print_colored(f"✅ List entities endpoint working", 'GREEN')
                print(f"  Found {data.get('entity_count', 0)} entities")
        except Exception as e:
            print_colored(f"❌ List entities failed: {e}", 'RED')

async def main():
    parser = argparse.ArgumentParser(description='Test MCP Server SSE functionality')
    parser.add_argument('--host', default='localhost', help='Server host')
    parser.add_argument('--port', default=8099, type=int, help='Server port')
    parser.add_argument('--duration', default=30, type=int, help='SSE test duration in seconds')
    parser.add_argument('--skip-sse', action='store_true', help='Skip SSE test')
    
    args = parser.parse_args()
    base_url = f"http://{args.host}:{args.port}"
    
    print_colored("=" * 60, 'CYAN')
    print_colored("🚀 MCP Server Test Suite", 'CYAN', bold=True)
    print_colored(f"📍 Testing server at: {base_url}", 'BLUE')
    print_colored("=" * 60, 'CYAN')
    
    # Run tests
    results = []
    
    # Test health
    results.append(("Health Check", await test_health(base_url)))
    
    # Test REST endpoints
    await test_rest_endpoints(base_url)
    
    # Test MCP protocol
    await test_mcp_protocol(base_url)
    
    # Test SSE (unless skipped)
    if not args.skip_sse:
        results.append(("SSE Connection", await test_sse_connection(base_url, args.duration)))
    
    # Summary
    print_colored("\n" + "=" * 60, 'CYAN')
    print_colored("📊 Test Summary", 'CYAN', bold=True)
    print_colored("=" * 60, 'CYAN')
    
    all_passed = True
    for test_name, passed in results:
        if passed:
            print_colored(f"✅ {test_name}: PASSED", 'GREEN')
        else:
            print_colored(f"❌ {test_name}: FAILED", 'RED')
            all_passed = False
    
    if all_passed:
        print_colored("\n🎉 All tests passed!", 'GREEN', bold=True)
    else:
        print_colored("\n⚠️ Some tests failed. Check the output above.", 'YELLOW', bold=True)
    
    print_colored("\n💡 To use with Home Assistant MCP Client:", 'BLUE')
    print_colored(f"   SSE URL: http://{args.host}:{args.port}/sse", 'BLUE')
    print_colored(f"   MCP URL: http://{args.host}:{args.port}/mcp", 'BLUE')

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_colored("\n\n⏹️ Test interrupted by user", 'YELLOW')
    except Exception as e:
        print_colored(f"\n❌ Test failed with error: {e}", 'RED')
        sys.exit(1)
