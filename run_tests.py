#!/usr/bin/env python3
"""
Run all tests for MCP Server
This script can be run without any setup - it handles everything
"""
import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description, cwd=None):
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    print(f"Command: {cmd}")
    
    result = subprocess.run(cmd, shell=True, cwd=cwd)
    
    if result.returncode == 0:
        print(f"✅ {description} - SUCCESS")
    else:
        print(f"❌ {description} - FAILED")
    
    return result.returncode == 0

def main():
    """Run all tests"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║           MCP Server - Automated Test Suite              ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Check if we're in the right directory
    if not Path("mcp-server").exists():
        print("❌ Error: mcp-server directory not found")
        print("   Please run this script from the project root")
        sys.exit(1)
    
    results = []
    
    # 1. Install test dependencies
    print("\n📦 Installing dependencies...")
    if not Path("test-requirements.txt").exists():
        print("⚠️  test-requirements.txt not found, skipping dependency installation")
    else:
        cmd = f"{sys.executable} -m pip install -q -r test-requirements.txt"
        subprocess.run(cmd, shell=True, capture_output=True)
        print("✅ Dependencies installed")
    
    # 2. Check code formatting
    try:
        import black
        results.append(run_command(
            f"{sys.executable} -m black --check mcp-server/ tests/ 2>/dev/null",
            "Code Formatting Check"
        ))
    except ImportError:
        print("⚠️  Black not installed, skipping format check")
    
    # 3. Run linting
    try:
        import flake8
        results.append(run_command(
            f"{sys.executable} -m flake8 mcp-server/ tests/ --max-line-length=120 --count --statistics 2>/dev/null",
            "Code Linting"
        ))
    except ImportError:
        print("⚠️  Flake8 not installed, skipping linting")
    
    # 4. Run unit tests
    try:
        import pytest
        results.append(run_command(
            f"{sys.executable} -m pytest tests/ -v -m 'not integration' --tb=short",
            "Unit Tests"
        ))
    except ImportError:
        print("❌ Pytest not installed! Install with: pip install pytest pytest-asyncio")
        results.append(False)
    
    # 5. Run integration tests
    if Path("tests/test_mcp_protocol.py").exists():
        results.append(run_command(
            f"{sys.executable} -m pytest tests/test_mcp_protocol.py -v --tb=short",
            "Integration Tests"
        ))
    
    # 6. Test with test client
    if Path("test_client.py").exists():
        results.append(run_command(
            f"{sys.executable} test_client.py",
            "Test Client Validation"
        ))
    
    # 7. Coverage report
    try:
        import pytest_cov
        run_command(
            f"{sys.executable} -m pytest tests/ --cov=mcp-server --cov-report=term --cov-report=html --quiet",
            "Coverage Report"
        )
        print("\n📊 Coverage report generated in htmlcov/index.html")
    except ImportError:
        print("⚠️  pytest-cov not installed, skipping coverage")
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    test_names = [
        "Code Formatting",
        "Code Linting",
        "Unit Tests",
        "Integration Tests",
        "Test Client"
    ]
    
    for i, (name, result) in enumerate(zip(test_names[:len(results)], results)):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name:.<40} {status}")
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The code is ready for deployment.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test suite(s) failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
