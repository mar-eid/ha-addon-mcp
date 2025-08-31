# 🛠️ Home Assistant MCP Server Add-on

[![Build & Push](https://github.com/mar-eid/ha-addon-mcp/actions/workflows/build.yml/badge.svg)](https://github.com/mar-eid/ha-addon-mcp/actions/workflows/build.yml)
[![Version](https://img.shields.io/badge/version-0.5.3-blue)](https://github.com/mar-eid/ha-addon-mcp/releases)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A [Home Assistant](https://www.home-assistant.io/) add-on that runs a **Model Context Protocol (MCP) server** for querying historical data from PostgreSQL/TimescaleDB. This enables AI assistants (like OpenAI through Home Assistant Assist) to access and analyze your home automation data.

🛠️ **Version 0.5.3 Update**: Fixed add-on store visibility issues - now properly appears in Home Assistant Add-on Store!

---

## ✨ Features

- 🎯 **Official MCP SDK**: Built with the official `mcp` Python package for guaranteed compatibility
- 🤖 **MCP Protocol Support**: Full compliance with MCP specification through official SDK
- 📊 **Historical Data Access**: Query entity states and statistics over time
- 🔒 **Security First**: Read-only database access with configurable restrictions
- ⚡ **High Performance**: Async database operations with connection pooling
- 🌐 **Ingress Support**: Access through Home Assistant UI without port exposure
- 📈 **TimescaleDB Ready**: Optional support for advanced time-series features

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

### Using with MCP Client Integration

1. Install the **Model Context Protocol** integration in Home Assistant
2. Configure the MCP Client to connect to the add-on
3. The add-on provides MCP tools via stdio transport
4. Tools are automatically discovered and available to AI assistants

### Testing the Server

You can test the MCP server functionality:

```python
# Run the test script
python test_mcp_server.py
```

This will verify:
- ✅ Server initialization
- ✅ Tool registration  
- ✅ Database connectivity (or mock mode)
- ✅ All MCP tools functionality

---

## 🛡️ Security

- **Read-only mode**: Enforces SELECT-only queries when enabled
- **Query limits**: Configurable timeout and date range restrictions
- **Connection security**: Uses Home Assistant's authentication via Ingress
- **No port exposure**: Runs internally, accessible only through HA

---

## 🚀 Development

### Testing Locally

```bash
# Clone the repository
git clone https://github.com/mar-eid/ha-addon-mcp.git
cd ha-addon-mcp

# Install dependencies
pip install -r mcp-server/requirements.txt

# Run the test script
python test_mcp_server.py
```

### Building the Add-on

```bash
# Build the Docker image
docker build -t ha-addon-mcp ./mcp-server

# The add-on uses stdio transport, so it's managed by the MCP Client
```

---

## 🐛 Troubleshooting

### ✅ Version 0.5.3 Fixes

This version fixes add-on store visibility:
- ✅ **Fixed**: Add-on now appears in Home Assistant Add-on Store
- ✅ **Removed**: Invalid PostgreSQL service dependency causing validation errors
- ✅ **Added**: Missing repository.yaml for proper store integration
- ✅ **Uses**: Correct MCP SDK imports (`mcp.types`, `mcp.server`)

### Testing the Fix

Run the test script to verify everything works:

```bash
cd ha-addon-mcp
python test_mcp_server.py
```

You should see:
```
🧪 Testing Home Assistant MCP Server
✅ Server imports successful
✅ Server instance created  
✅ Found 4 registered tools
✅ Health check: ok
🎉 All tests passed!
```

### Database Connection

The server gracefully falls back to mock data if database isn't available:
- ✅ Database connected: Real data from Home Assistant
- ⚠️ Database unavailable: Mock data for testing

### MCP Client Integration

If the MCP Client has issues:
1. Check add-on logs: `ha addon logs mcp_server`
2. Verify configuration is correct
3. Ensure PostgreSQL add-on is running (if using real data)
4. Check that the add-on started successfully

---

## 📜 Changelog

### v0.5.3 (2025-08-31) - 🔧 Store Visibility Fix
- **Fixed**: Add-on store visibility issues preventing installation
- **Removed**: Invalid PostgreSQL service dependency causing validation errors
- **Added**: Missing repository.yaml for proper HA store integration
- **Maintained**: All MCP functionality with official SDK

See [CHANGELOG.md](mcp-server/CHANGELOG.md) for complete version history.

---

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test your changes with the test script
4. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Home Assistant Community for the amazing platform
- MCP Protocol team for the excellent SDK
- PostgreSQL and TimescaleDB teams for excellent databases
- Contributors and testers who help improve this add-on

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/mar-eid/ha-addon-mcp/issues)
- **Discussions**: [Home Assistant Community Forum](https://community.home-assistant.io)
- **Testing**: Use `test_mcp_server.py` for local verification

---

Made with ❤️ for the Home Assistant community
