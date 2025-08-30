# Home Assistant Add-on: MCP Server

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]

[![GitHub Sponsors][sponsors-shield]][sponsors]

Model Context Protocol (MCP) server for querying Home Assistant historical data from PostgreSQL/TimescaleDB.

## About

This add-on runs an MCP server that provides AI assistants (like those using OpenAI through Home Assistant Assist) with access to your historical sensor data. It connects to your Home Assistant's PostgreSQL/TimescaleDB recorder database and exposes the data through standardized MCP tools.

## Installation

1. Navigate in your Home Assistant frontend to **Settings** → **Add-ons** → **Add-on Store**
2. Click the 3-dots menu at the top right and select **Repositories**
3. Add this repository URL: `https://github.com/mar-eid/ha-addon-mcp`
4. Search for "MCP Server" and install the add-on
5. Start the add-on

## Configuration

Add-on configuration:

```yaml
pg_host: "a0d7b954-postgresql"
pg_port: 5432
pg_database: "homeassistant"
pg_user: "homeassistant"
pg_password: "your_password"
read_only: true
enable_timescaledb: false
log_level: "info"
query_timeout: 30
max_query_days: 90
```

### Option: `pg_host`

The hostname or IP address of your PostgreSQL server.

### Option: `pg_port`

The port number of your PostgreSQL server (default: 5432).

### Option: `pg_database`

The name of your Home Assistant database (default: homeassistant).

### Option: `pg_user`

Username for database connection.

### Option: `pg_password`

Password for database connection (leave empty if using trust authentication).

### Option: `read_only`

Enable read-only mode to prevent any database modifications (recommended: true).

### Option: `enable_timescaledb`

Enable TimescaleDB-specific features if your database supports it.

### Option: `log_level`

Controls the level of log output (debug, info, warning, error).

### Option: `query_timeout`

Maximum time in seconds for database queries (5-300).

### Option: `max_query_days`

Maximum number of days that can be queried in a single request (1-365).

## Usage

After installation and configuration:

1. Start the add-on
2. Check the logs to ensure database connection is successful
3. Open the Web UI to test the API endpoints
4. Configure Home Assistant's MCP Client integration to use this server

## Home Assistant MCP Integration Setup

To enable AI assistants to use this server:

1. **Install MCP Integration**: Go to Settings → Devices & Services → Add Integration
2. **Search for**: "Model Context Protocol"
3. **Configure Server URL**: Use your add-on's URL:
   ```
   http://localhost:8099/mcp
   ```
   Or if using Ingress: use the internal add-on URL
4. **Test Connection**: The integration will automatically discover available tools
5. **Use with Assist**: Ask questions like:
   - "What was the temperature yesterday?"
   - "Show me energy consumption for the past week"
   - "List all sensors with historical data"

## MCP Protocol Support

### **Transport Methods**

This server supports multiple MCP transport methods:

#### **1. JSON-RPC over HTTP (Primary)**
```bash
# Endpoint: POST /mcp
# Content-Type: application/json
# Protocol: JSON-RPC 2.0

# Example request:
curl -X POST http://localhost:8099/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tools/list"
  }'
```

#### **2. Server-Sent Events (SSE) - Alternative Transport**
```bash
# SSE Endpoint: GET /mcp (for streaming)
# Used by some MCP clients for real-time communication
# Provides bidirectional communication over HTTP

# SSE Connection:
curl -N -H "Accept: text/event-stream" http://localhost:8099/mcp

# SSE Events:
# - endpoint: Announces available endpoints
# - initialized: Server initialization complete
# - ping: Keep-alive messages (every 30s)
```

#### **3. WebSocket Support (Future)**
```bash
# WebSocket endpoint: ws://localhost:8099/ws
# Not yet implemented - use HTTP/SSE for now
```

### **MCP Protocol Compliance**

This server implements **MCP Protocol 2024-11-05** with:

- ✅ **Initialize handshake**: Capability negotiation
- ✅ **Tool discovery**: `tools/list` method
- ✅ **Tool execution**: `tools/call` method  
- ✅ **Error handling**: Standard JSON-RPC error codes
- ✅ **Request/Response**: Full JSON-RPC 2.0 compliance
- ✅ **SSE Transport**: Real-time event streaming
- ✅ **Batch requests**: Multiple operations in one request

### **Client Compatibility**

Tested and compatible with:
- **Home Assistant MCP Integration** (Primary target)
- **Claude Desktop MCP Client**
- **OpenAI Custom Actions** (via HTTP)
- **Generic MCP Clients** (JSON-RPC 2.0)
- **SSE-compatible clients** (real-time streaming)

### **SSE Connection Details**

For clients that prefer Server-Sent Events:

```javascript
// JavaScript SSE client example
const eventSource = new EventSource('http://localhost:8099/mcp');

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('MCP Event:', data);
  
  // Handle different event types
  switch(data.method) {
    case 'endpoint':
      console.log('Available endpoint:', data.params.endpoint);
      break;
    case 'notifications/initialized':
      console.log('Server initialized:', data.params.serverInfo);
      break;
    case 'notifications/ping':
      console.log('Keep-alive ping');
      break;
  }
};

eventSource.onerror = function(event) {
  console.error('SSE connection error');
};
```

```python
# Python SSE client example
import sseclient
import json

def connect_sse():
    response = requests.get('http://localhost:8099/mcp', 
                          headers={'Accept': 'text/event-stream'},
                          stream=True)
    
    client = sseclient.SSEClient(response)
    for event in client.events():
        data = json.loads(event.data)
        print(f"SSE Event: {data}")
```

### **Protocol Selection**

Most MCP clients will auto-detect the best transport:

1. **HTTP POST** (Recommended): Simple, reliable, works everywhere
2. **SSE** (Alternative): Real-time events, better for streaming
3. **WebSocket** (Future): Full bidirectional, lowest latency

### **Advanced Configuration**

For advanced MCP client configurations:

```yaml
# Home Assistant MCP Integration Config
server_url: "http://localhost:8099/mcp"
transport: "http"              # or "sse"
timeout: 30                    # seconds
keep_alive: true              # for SSE connections
max_retries: 3                # connection retries
```

## Available MCP Tools

The add-on provides 5 MCP tools for AI assistants:

- `ha.get_history` - Get historical state data for entities over time periods
- `ha.get_statistics` - Get statistical summaries (mean, min, max, sum) for entities  
- `ha.list_entities` - List available entities that have historical data
- `ha.list_statistics` - List available statistics in the database
- `addon.health` - Get server health status and database connectivity

## API Endpoints

- `POST /mcp` - Main MCP protocol endpoint (JSON-RPC 2.0)
- `GET /health` - Health check and status
- `GET /` - Web interface for testing and setup instructions

## Security

- Uses Home Assistant's built-in authentication via Ingress
- Supports read-only database access
- Configurable query limits to prevent abuse
- No external ports exposed

## Database Setup

For enhanced security, create a dedicated read-only user:

```sql
CREATE USER ha_mcp_readonly WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE homeassistant TO ha_mcp_readonly;
GRANT USAGE ON SCHEMA public TO ha_mcp_readonly;
GRANT SELECT ON states, states_meta, statistics, statistics_meta TO ha_mcp_readonly;
```

## Support

Got questions?

You have several options to get them answered:

- The Home Assistant [Community Forum][forum]
- Open an issue on our [GitHub][issue]

## Contributing

This is an active open-source project. We are always open to people who want to
use the code or contribute to it.

We have set up a separate document containing our
[contribution guidelines](CONTRIBUTING.md).

Thank you for being involved! :heart_eyes:

## Authors & contributors

This repository is owned and maintained by [mar-eid][mar-eid].

For a full list of all authors and contributors,
check [the contributor's page][contributors].

## License

MIT License

Copyright (c) 2024 mar-eid

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[commits-shield]: https://img.shields.io/github/commit-activity/y/mar-eid/ha-addon-mcp.svg
[commits]: https://github.com/mar-eid/ha-addon-mcp/commits/main
[contributors]: https://github.com/mar-eid/ha-addon-mcp/graphs/contributors
[forum]: https://community.home-assistant.io
[issue]: https://github.com/mar-eid/ha-addon-mcp/issues
[license]: https://github.com/mar-eid/ha-addon-mcp/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/mar-eid/ha-addon-mcp.svg
[mar-eid]: https://github.com/mar-eid
[releases-shield]: https://img.shields.io/github/release/mar-eid/ha-addon-mcp.svg
[releases]: https://github.com/mar-eid/ha-addon-mcp/releases
[sponsors]: https://github.com/sponsors/mar-eid
[sponsors-shield]: https://img.shields.io/github/sponsors/mar-eid?label=Sponsors