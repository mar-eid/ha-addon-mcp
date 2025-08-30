#!/usr/bin/env python3
"""
Run MCP Server locally for testing
This script sets up the environment and runs the server without Home Assistant
"""

import os
import sys
import subprocess

def main():
    print("🚀 Starting MCP Server locally for testing...")
    print("=" * 60)
    
    # Set environment variables for local testing
    env = os.environ.copy()
    env.update({
        "PGHOST": os.getenv("PGHOST", "localhost"),
        "PGPORT": os.getenv("PGPORT", "5432"),
        "PGDATABASE": os.getenv("PGDATABASE", "homeassistant"),
        "PGUSER": os.getenv("PGUSER", "homeassistant"),
        "PGPASSWORD": os.getenv("PGPASSWORD", ""),
        "MCP_READ_ONLY": "true",
        "MCP_ENABLE_TIMESCALEDB": "false",
        "MCP_PORT": "8099",
        "MCP_QUERY_TIMEOUT": "30",
        "MCP_MAX_QUERY_DAYS": "90"
    })
    
    print("📋 Configuration:")
    print(f"   Database: {env['PGUSER']}@{env['PGHOST']}:{env['PGPORT']}/{env['PGDATABASE']}")
    print(f"   Server Port: {env['MCP_PORT']}")
    print(f"   Read-only: {env['MCP_READ_ONLY']}")
    print("=" * 60)
    print("")
    print("🌐 Server will be available at:")
    print(f"   Web Interface: http://localhost:{env['MCP_PORT']}/")
    print(f"   SSE Endpoint:  http://localhost:{env['MCP_PORT']}/sse")
    print(f"   MCP Endpoint:  http://localhost:{env['MCP_PORT']}/mcp")
    print("")
    print("💡 Open another terminal and run: python test_sse.py")
    print("=" * 60)
    print("")
    
    # Change to mcp-server directory if we're not already there
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_dir = os.path.join(script_dir, 'mcp-server')
    if os.path.exists(server_dir):
        os.chdir(server_dir)
    
    # Check if server.py exists
    if not os.path.exists('server.py'):
        print("❌ Error: server.py not found!")
        print(f"   Current directory: {os.getcwd()}")
        sys.exit(1)
    
    # Install requirements if needed
    print("📦 Checking dependencies...")
    try:
        import fastapi
        import sse_starlette
        import asyncpg
        print("✅ All dependencies installed")
    except ImportError:
        print("📦 Installing dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    print("\n🚀 Starting server...\n")
    
    # Run the server
    try:
        subprocess.run([sys.executable, "server.py"], env=env)
    except KeyboardInterrupt:
        print("\n\n⏹️ Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
