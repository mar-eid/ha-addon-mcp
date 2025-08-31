@echo off
REM Quick test runner for Windows development

echo ================================
echo MCP Server - Quick Test Runner
echo ================================

REM Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    exit /b 1
)

echo Python found: 
python --version

REM Install test dependencies if needed
python -c "import pytest" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing test dependencies...
    pip install -q pytest pytest-asyncio pytest-mock
)

REM Run tests
echo.
echo Running tests...
python -m pytest tests\ -v --tb=short

if %errorlevel% equ 0 (
    echo.
    echo All tests passed!
) else (
    echo.
    echo Some tests failed
    exit /b 1
)

REM Optional: Run test client
if exist "test_client.py" (
    echo.
    echo Running test client...
    python test_client.py
)

echo.
echo Test run complete!
pause
