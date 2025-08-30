#!/bin/bash
# Quick test runner for development

echo "================================"
echo "MCP Server - Quick Test Runner"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python 3 found: $(python3 --version)${NC}"

# Install test dependencies if needed
if ! python3 -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}📦 Installing test dependencies...${NC}"
    pip install -q pytest pytest-asyncio pytest-mock
fi

# Run tests
echo -e "\n${GREEN}🧪 Running tests...${NC}"
python3 -m pytest tests/ -v --tb=short

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✅ All tests passed!${NC}"
else
    echo -e "\n${RED}❌ Some tests failed${NC}"
    exit 1
fi

# Optional: Run test client
if [ -f "test_client.py" ]; then
    echo -e "\n${GREEN}🔧 Running test client...${NC}"
    python3 test_client.py
fi

echo -e "\n${GREEN}✨ Test run complete!${NC}"
