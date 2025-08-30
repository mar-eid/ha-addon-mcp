# Testing SSE Functionality

This guide helps you test the SSE (Server-Sent Events) functionality of the MCP Server locally to diagnose connection issues with the Home Assistant MCP Client integration.

## Quick Start

### 1. Install Dependencies

```bash
cd ha-addon-mcp

# Install server dependencies
pip install -r mcp-server/requirements.txt

# Install test script dependencies
pip install -r test_requirements.txt
```

### 2. Run the Server Locally

```bash
# Option 1: Using the convenience script
python run_local.py

# Option 2: Direct run with custom database settings
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=homeassistant
export PGUSER=homeassistant
export PGPASSWORD=yourpassword
cd mcp-server
python server.py
```

The server will start with mock data if it can't connect to the database, which is fine for testing SSE.

### 3. Test SSE Connection

Open a new terminal and run:

```bash
python test_sse.py
```

This will:
- Test the health endpoint
- Connect to the SSE stream
- Display received events
- Test MCP protocol endpoints
- Provide a summary of results

### 4. Interactive Web Testing

Open your browser and go to:
```
http://localhost:8099/
```

You'll see an interactive test interface where you can:
- Test SSE connection with visual feedback
- Monitor SSE messages in real-time
- Test individual API endpoints
- View connection status indicators

## What Should Happen

When SSE is working correctly, you should see:

1. **Connection Event**: Immediately after connecting
```json
{
  "protocol": "mcp",
  "version": "0.1.0",
  "capabilities": {
    "tools": true,
    "prompts": false,
    "resources": false,
    "logging": false,
    "sampling": false
  }
}
```

2. **Tools Event**: List of available tools
```json
{
  "tools": [
    {
      "name": "ha.get_history",
      "description": "Query historical state data from Home Assistant recorder",
      "inputSchema": {...}
    },
    ...
  ]
}
```

3. **Ping Events**: Every 30 seconds
```json
{
  "timestamp": "2024-12-19T10:30:00.000Z",
  "sequence": 1
}
```

## Troubleshooting

### SSE Connection Fails

If the SSE connection fails, check:

1. **Server is running**: Should see logs in the server terminal
2. **Port 8099 is free**: `netstat -an | grep 8099`
3. **Firewall**: Ensure port 8099 is not blocked

### No Events Received

If connected but no events:

1. Check server logs for errors
2. Verify content-type header is `text/event-stream`
3. Test with curl:
```bash
curl -N http://localhost:8099/sse
```

### Home Assistant Integration Still Fails

If local tests work but HA integration fails:

1. **Check add-on logs**:
```bash
ha addon logs mcp_server
```

2. **Verify internal networking**:
- The MCP Client should use: `http://localhost:8099/sse`
- Or try: `http://addon_mcp_server:8099/sse`

3. **Check Ingress configuration**:
- Ingress might interfere with SSE
- Try disabling Ingress temporarily in config.yaml

4. **Test from within Home Assistant**:
```bash
# SSH into Home Assistant
docker exec -it addon_mcp_server /bin/sh
# Test SSE from inside the container
curl -N http://localhost:8099/sse
```

## Expected Test Output

### Successful test_sse.py output:
```
🚀 MCP Server Test Suite
📍 Testing server at: http://localhost:8099
============================================================

📋 Testing Health Endpoint...
✅ Health check passed
{
  "status": "ok",
  "version": "0.4.2",
  "database": "mock_mode",
  "sse_clients": 0,
  ...
}

📡 Testing SSE Connection (listening for 30 seconds)...
✅ SSE connection established
✅ Correct content-type: text/event-stream

📨 Event: connection
{
  "protocol": "mcp",
  "version": "0.1.0",
  ...
}

📨 Event: tools
{
  "tools": [...]
}

📨 Event: ping
{
  "timestamp": "...",
  "sequence": 1
}

✅ Test completed. Received 3 events in 30 seconds

📊 Test Summary
============================================================
✅ Health Check: PASSED
✅ SSE Connection: PASSED

🎉 All tests passed!
```

## Configuration for Home Assistant MCP Client

Once SSE is confirmed working locally, configure the MCP Client integration with:

```yaml
# For add-on running locally
URL: http://localhost:8099/sse
Transport: SSE (Server-Sent Events)

# For add-on in Home Assistant
URL: http://addon_mcp_server:8099/sse
Transport: SSE (Server-Sent Events)
```

## Advanced Testing

### Test with specific parameters:
```bash
# Test against remote server
python test_sse.py --host 192.168.1.100 --port 8099

# Longer SSE test duration
python test_sse.py --duration 60

# Skip SSE test (only test other endpoints)
python test_sse.py --skip-sse
```

### Monitor SSE stream with curl:
```bash
# Basic SSE stream
curl -N -H "Accept: text/event-stream" http://localhost:8099/sse

# With headers
curl -N -H "Accept: text/event-stream" -v http://localhost:8099/sse 2>&1
```

### Test MCP protocol directly:
```bash
# List tools
curl -X POST http://localhost:8099/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Call a tool
curl -X POST http://localhost:8099/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ha.list_entities","arguments":{}}}'
```

## Need Help?

If SSE tests pass locally but Home Assistant integration still fails:

1. Check GitHub Issues: https://github.com/mar-eid/ha-addon-mcp/issues
2. Review add-on logs carefully
3. Try the alternative REST API approach instead of SSE
4. Consider network/firewall issues between containers

The SSE implementation follows the MCP specification exactly, so if local tests pass, the issue is likely with container networking or configuration rather than the SSE implementation itself.
