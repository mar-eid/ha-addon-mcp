#!/usr/bin/env python3
"""
Simple import test for MCP server dependencies
"""
import sys
import os

def test_imports():
    """Test all required imports for the MCP server"""
    print("🧪 Testing MCP Server Dependencies")
    print("=" * 50)
    
    # Test basic Python modules
    try:
        import asyncio
        print("✅ asyncio")
    except ImportError as e:
        print(f"❌ asyncio: {e}")
        return False
        
    try:
        import logging
        print("✅ logging")
    except ImportError as e:
        print(f"❌ logging: {e}")
        return False
    
    try:
        from datetime import datetime, timedelta
        print("✅ datetime")
    except ImportError as e:
        print(f"❌ datetime: {e}")
        return False
    
    try:
        from typing import Optional, Dict, Any, List, Union
        print("✅ typing")
    except ImportError as e:
        print(f"❌ typing: {e}")
        return False
    
    # Test database modules
    try:
        import asyncpg
        print("✅ asyncpg")
    except ImportError as e:
        print(f"❌ asyncpg: {e}")
        print("   Install with: pip install asyncpg")
        return False
    
    # Test MCP modules (the critical ones that were failing)
    try:
        import mcp.types as types
        print("✅ mcp.types")
    except ImportError as e:
        print(f"❌ mcp.types: {e}")
        print("   Install with: pip install mcp")
        return False
    
    try:
        from mcp.server import NotificationOptions, Server
        print("✅ mcp.server (Server, NotificationOptions)")
    except ImportError as e:
        print(f"❌ mcp.server: {e}")
        print("   Install with: pip install mcp")
        return False
    
    try:
        from mcp.server.models import InitializationOptions
        print("✅ mcp.server.models (InitializationOptions)")
    except ImportError as e:
        print(f"❌ mcp.server.models: {e}")
        print("   Install with: pip install mcp")
        return False
    
    try:
        import mcp.server.stdio
        print("✅ mcp.server.stdio")
    except ImportError as e:
        print(f"❌ mcp.server.stdio: {e}")
        print("   Install with: pip install mcp")
        return False
    
    print("\n🎉 All imports successful!")
    print("✅ Your MCP server dependencies are correctly installed")
    return True

def test_mcp_version():
    """Check the MCP version"""
    try:
        import mcp
        if hasattr(mcp, '__version__'):
            print(f"📦 MCP Version: {mcp.__version__}")
        else:
            print("📦 MCP Version: Unknown (package installed)")
    except ImportError:
        print("❌ MCP package not installed")

if __name__ == "__main__":
    print("🔍 MCP Server Import Test")
    print("Testing all required dependencies...\n")
    
    success = test_imports()
    
    if success:
        print("\n📊 Version Information:")
        test_mcp_version()
        
        print(f"🐍 Python: {sys.version}")
        
        print("\n✅ Your environment is ready!")
        print("🚀 The MCP server should work without import errors")
    else:
        print("\n❌ Some dependencies are missing")
        print("🔧 Please install the missing packages and try again")
        sys.exit(1)
