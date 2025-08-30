#!/usr/bin/env python3
"""
Simple test runner - just run: python test_now.py
"""
import subprocess
import sys

print("""
╔═══════════════════════════════════════════════════════════╗
║              🧪 MCP Server Quick Test                    ║
╚═══════════════════════════════════════════════════════════╝
""")

# Install pytest if needed
try:
    import pytest
except ImportError:
    print("📦 Installing pytest...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pytest", "pytest-asyncio", "pytest-mock"])

# Run tests
print("🚀 Running tests...\n")
result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"])

if result.returncode == 0:
    print("\n✅ All tests passed!")
else:
    print("\n❌ Some tests failed")
    
sys.exit(result.returncode)
