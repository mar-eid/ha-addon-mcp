# 🛠️ Home Assistant MCP Server Add-on

[![Build & Push](https://github.com/mar-eid/ha-addon-mcp/actions/workflows/build.yml/badge.svg)](https://github.com/mar-eid/ha-addon-mcp/actions/workflows/build.yml)
[![Version](https://img.shields.io/badge/version-6.2-blue)](https://github.com/mar-eid/ha-addon-mcp/releases)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A [Home Assistant](https://www.home-assistant.io/) add-on that runs a **Model Context Protocol (MCP) server** for querying historical data from PostgreSQL/TimescaleDB. This enables AI assistants (like OpenAI through Home Assistant Assist) to access and analyze your home automation data.

🎉 **Version 6.2 - ENHANCED COMPATIBILITY**: Improved Home Assistant MCP Client compatibility with better SSE formatting and enhanced debugging.

---

## ✨ What's Working in v6.2

- ✅ **Home Assistant MCP Client**: Connects via `http://homeassistant.local:8099/sse`
- ✅ **External MCP Clients**: Connect via `http://homeassistant.local:8099/mcp` 
- ✅ **Claude Desktop**: Tested and working connection
- ✅ **Database Integration**: Real Home Assistant data or graceful mock fallback
- ✅ **All MCP Tools**: get_history, get_statistics, list_entities, health_check
- ✅ **Web Interface**: Rich monitoring and testing interface
- ✅ **Container Build**: Reliable multi-architecture builds
- ✅ **Add-on Store**: Visible and installable in Home Assistant

---

## 📈 Latest Updates (6.1 → 6.2)

### 🔧 Enhanced v6.2 Features
- **Better SSE Formatting**: Fixed event stream formatting for improved HA MCP Client compatibility
- **Enhanced Logging**: More detailed tool execution logging and debugging information
- **Improved Mock Data**: More realistic Home Assistant entity examples for testing
- **Better Error Handling**: Enhanced error responses and debugging capabilities
- **Test Endpoint**: Added `/test-tool` endpoint for easier development and testing

## 📈 Major Version Jump (0.5.x → 6.1+)

This represents the transition from **experimental** to **stable working version**:
- **Before v6.1**: Server crashed immediately with stdio transport issues
- **After v6.1**: Stable server with working HA integration and external client support

### 🎯 Technical Achievements v6.1+
- **Official MCP SDK**: Using `mcp==1.1.2` for guaranteed protocol compliance
- **FastAPI + SSE**: Hybrid architecture combining web server with MCP SDK
- **Async Database**: Full asyncpg implementation with connection pooling
- **CORS Compliance**: Proper headers for cross-origin requests
- **Dual Transport**: SSE for web clients + stdio support in SDK
- **Enhanced Logging**: Comprehensive debugging and monitoring
- **Error Recovery**: Graceful fallbacks and robust error handling

---

## 🔌 Integration URLs

### For Home Assistant MCP Client:
- **Primary**: `http://homeassistant.local:8099/sse`
- **Alternative**: `http://localhost:8099/sse`
- **Internal**: `http://addon_mcp_server:8099/sse`

### For External MCP Clients:
- **Claude Desktop**: `http://homeassistant.local:8099/mcp`
- **Generic MCP**: `http://localhost:8099/mcp`

---

## 📦 Installation

### Via Home Assistant Add-on Store

1. Open **Settings** → **Add-ons** → **Add-on Store** in Home Assistant
2. Click the ⋮ menu → **Repositories**
3. Add this repository URL:
   ```
   https://github.com/mar-eid/ha-addon-mcp
   ```
4. Find **MCP Server** in the add-on list and click **Install**
5. Configure the add-on (see Configuration section)
6. Start the add-on
7. Open **Web UI** to test functionality

---

## ⚙️ Configuration

### Basic Configuration

```yaml
pg_host: a0d7b954-postgresql  # Your PostgreSQL add-on hostname
pg_port: 5432
pg_database: homeassistant
pg_user: homeassistant
pg_password: "your_password"
read_only: true                # Enforce read-only mode (recommended)
enable_timescaledb: false      # Enable if using TimescaleDB
log_level: info
query_timeout: 30              # Max query time in seconds
max_query_days: 90             # Max days per query
```

### Database Setup (Recommended)

For enhanced security, create a dedicated read-only user:

```sql
-- Connect as postgres superuser
CREATE USER ha_mcp_readonly WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE homeassistant TO ha_mcp_readonly;
GRANT USAGE ON SCHEMA public TO ha_mcp_readonly;
GRANT SELECT ON states, states_meta, statistics, statistics_meta TO ha_mcp_readonly;
```

---

## 🧰 Available MCP Tools

### `get_history`
Query historical state data with aggregation support:
- **Intervals**: raw, 5m, 15m, 30m, 1h, 6h, 1d
- **Aggregations**: mean, min, max, sum, last, first
- **Time ranges**: Up to 90 days (configurable)

### `get_statistics`  
Retrieve statistical summaries from recorder:
- **Periods**: 5minute, hour, day, month
- **Fields**: mean, min, max, sum
- **Sources**: All Home Assistant statistics

### `list_entities`
Discover available entities and statistics:
- **Entity metadata**: Recent activity filtering
- **Type filtering**: Filter by entity domain (sensor, binary_sensor, etc.)
- **Statistics info**: Available fields and units

### `health_check`
Monitor server and database status:
- **Connection status**: Database connectivity
- **Configuration**: Current settings
- **TimescaleDB**: Extension availability

---

## 🔌 Integration with Home Assistant

### Using with Home Assistant MCP Client

1. Install the **Model Context Protocol** integration in Home Assistant
2. Configure the MCP Client SSE endpoint: `http://localhost:8099/sse`
3. The add-on provides MCP tools via SSE transport
4. Tools are automatically discovered and available to AI assistants

### Using with External MCP Clients (Claude Desktop, etc.)

1. Configure client to connect to: `http://homeassistant.local:8099/mcp`
2. Use SSE transport mode
3. All MCP tools will be automatically discovered
4. Test via the Web UI at `http://homeassistant.local:8099/`

---

## 🧪 Testing the Server

### Web Interface Testing
1. Open the add-on **Web UI** in Home Assistant
2. Use the interactive interface to test all endpoints
3. Test SSE connections in real-time
4. Monitor connected clients and server status

### Manual SSE Testing
```bash
# Test HA MCP Client endpoint
curl -N http://localhost:8099/sse

# Test generic MCP endpoint  
curl -N http://localhost:8099/mcp
```

---

## 🛡️ Security

- **Read-only mode**: Enforces SELECT-only queries when enabled
- **Query limits**: Configurable timeout and date range restrictions
- **Connection security**: Uses Home Assistant's authentication via Ingress
- **No port exposure**: Runs internally, accessible only through HA
- **CORS compliance**: Proper headers for secure cross-origin requests

---

## 🚀 Development

### Testing Locally

```bash
# Clone the repository
git clone https://github.com/mar-eid/ha-addon-mcp.git
cd ha-addon-mcp

# Install dependencies
pip install -r mcp-server/requirements.txt

# Run the server locally
cd mcp-server
python server.py
```

### Building the Add-on

```bash
# Build the Docker image
docker build -t ha-addon-mcp ./mcp-server

# Test container
docker run -p 8099:8099 ha-addon-mcp
```

---

## ✅ What's Fixed in v6.1

### 🔧 From Broken to Working
- **Before**: Server crashed immediately with stdio transport issues
- **After**: Stable server with working HA integration

### 🎉 Major Accomplishments  
- ✅ **Critical /sse Endpoint**: Added required endpoint for HA MCP Client integration
- ✅ **Dual Endpoint Support**: Both `/sse` (HA MCP Client) and `/mcp` (general clients) working
- ✅ **SSE Transport Fixed**: No more stdio transport shutdown issues
- ✅ **Build System Robust**: Multi-arch builds (amd64, arm64) working reliably
- ✅ **Container Stability**: Server runs continuously without crashes
- ✅ **Protocol Compliance**: Full MCP 2024-11-05 specification compliance

### 🎯 Integration Ready
This version is production-ready for:
- ✅ **Home Assistant Assist**: AI queries on historical data
- ✅ **Claude Desktop**: External MCP client integration  
- ✅ **Custom Applications**: Any MCP-compatible client
- ✅ **Development**: Full API and web interface for testing

---

## 🐛 Troubleshooting

### Database Connection

The server gracefully falls back to mock data if database isn't available:
- ✅ Database connected: Real data from Home Assistant
- ⚠️ Database unavailable: Mock data for testing

### MCP Client Integration

If the MCP Client has issues:
1. Check add-on logs: `ha addon logs mcp_server`
2. Use correct endpoints:
   - **HA MCP Client**: `http://localhost:8099/sse`
   - **External clients**: `http://localhost:8099/mcp`
3. Verify add-on is running and accessible
4. Test via Web UI first

### SSE Connection Testing

```bash
# Test SSE endpoints
curl -N -H "Accept: text/event-stream" http://localhost:8099/sse
curl -N -H "Accept: text/event-stream" http://localhost:8099/mcp
```

---

## 📜 Changelog

### v6.2 (2025-08-31) - 🔧 Enhanced Compatibility 
- **🔧 Better SSE Formatting**: Fixed event stream formatting for improved HA MCP Client compatibility
- **📝 Enhanced Logging**: More detailed tool execution logging and debugging information  
- **📊 Improved Mock Data**: More realistic Home Assistant entity examples for testing
- **🚫 Better Error Handling**: Enhanced error responses and debugging capabilities
- **🧪 Test Endpoint**: Added `/test-tool` endpoint for easier development and testing

### v6.1 (2025-08-31) - 🎉 Major Milestone
- **🎉 Complete Working MCP Server**: First fully functional version
- **✅ HA MCP Client Integration**: Working `/sse` endpoint
- **✅ External Client Support**: Working `/mcp` endpoint for Claude Desktop, etc.
- **✅ Protocol Compliance**: Full MCP 2024-11-05 specification
- **✅ Stable Architecture**: FastAPI + SSE + Official MCP SDK
- **✅ Production Ready**: All integrations tested and working

See [CHANGELOG.md](mcp-server/CHANGELOG.md) for complete version history.

---

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test your changes with the Web UI
4. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Home Assistant Community for the amazing platform
- MCP Protocol team for the excellent SDK
- PostgreSQL and TimescaleDB teams for excellent databases
- Contributors and testers who helped achieve this working milestone

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/mar-eid/ha-addon-mcp/issues)
- **Discussions**: [Home Assistant Community Forum](https://community.home-assistant.io)
- **Testing**: Use the built-in Web UI for testing and monitoring

---

Made with ❤️ for the Home Assistant community

**🎉 Milestone Achievement: World's First Working Home Assistant MCP Server Add-on!**
