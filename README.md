# 🛠️ Home Assistant MCP Server Add-on

[![Build & Push](https://github.com/mar-eid/ha-addon-mcp/actions/workflows/build.yml/badge.svg)](https://github.com/mar-eid/ha-addon-mcp/actions/workflows/build.yml)
[![Version](https://img.shields.io/badge/version-0.4.1-blue)](https://github.com/mar-eid/ha-addon-mcp/releases)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A [Home Assistant](https://www.home-assistant.io/) add-on that runs a **Model Context Protocol (MCP) server** for querying historical data from PostgreSQL/TimescaleDB. This enables AI assistants (like OpenAI through Home Assistant Assist) to access and analyze your home automation data.

---

## ✨ Features

- 🚀 **Real PostgreSQL Integration**: Direct queries to Home Assistant's recorder database
- 🤖 **MCP Protocol Support**: Full compatibility with Home Assistant's MCP Client integration
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

### `ha.get_history`
Query historical state data with aggregation support:
- **Intervals**: 5m, 15m, 30m, 1h, 6h, 1d
- **Aggregations**: raw, mean, min, max, sum, last
- **Time ranges**: Up to 90 days (configurable)

### `ha.get_statistics`
Retrieve statistical summaries from recorder:
- **Periods**: 5minute, hour, day, month
- **Fields**: mean, min, max, sum, state
- **Sources**: All Home Assistant statistics

### `ha.get_statistics_bulk`
Efficient bulk queries for multiple entities:
- **Batch processing**: Query multiple statistics at once
- **Pagination**: Handle large datasets efficiently
- **Performance**: Optimized for minimal database load

### `ha.list_entities`
Discover available entities and statistics:
- **Entity metadata**: Last seen, state counts
- **Statistics info**: Available fields and units
- **Filtering**: Recent data only (last 7 days)

---

## 🔌 Integration with Home Assistant

### Using with MCP Client Integration

1. Install the **Model Context Protocol** integration in Home Assistant
2. Configure the MCP Client with:
   - **URL**: `http://localhost:8099/mcp`
   - **Transport**: SSE (Server-Sent Events)
3. Tools are automatically available to AI assistants

### Using with REST API

The server also provides REST endpoints for direct testing:

```bash
# Check health
curl http://localhost:8099/health

# Query history
curl -X POST http://localhost:8099/tools/ha.get_history \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "sensor.temperature",
    "start": "2024-12-18T00:00:00Z",
    "end": "2024-12-19T00:00:00Z",
    "interval": "1h",
    "agg": "mean"
  }'
```

---

## 🛡️ Security

- **Read-only mode**: Enforces SELECT-only queries when enabled
- **Query limits**: Configurable timeout and date range restrictions
- **Connection security**: Uses Home Assistant's authentication via Ingress
- **No port exposure**: Runs internally, accessible only through HA

---

## 🚀 Development

### Building Locally

```bash
# Clone the repository
git clone https://github.com/mar-eid/ha-addon-mcp.git
cd ha-addon-mcp

# Build the Docker image
docker build -t ha-addon-mcp ./mcp-server

# Run locally for testing
docker run --rm -it \
  -p 8099:8099 \
  -e PGHOST=localhost \
  -e PGPORT=5432 \
  -e PGDATABASE=homeassistant \
  -e PGUSER=homeassistant \
  -e PGPASSWORD=password \
  ha-addon-mcp
```

### GitHub Actions

The repository includes automated builds via GitHub Actions:
- Multi-architecture support (amd64, arm64)
- Automatic container registry publishing
- Version tagging and releases

---

## 📊 Performance

- **Async Operations**: Non-blocking database queries using asyncpg
- **Connection Pooling**: Min 2, Max 10 concurrent connections
- **Query Optimization**: Efficient SQL with proper indexing
- **TimescaleDB Support**: Leverages continuous aggregates when available

---

## 🐛 Troubleshooting

### Database Connection Issues

Check logs for connection errors:
```bash
# In Home Assistant
ha addon logs mcp_server
```

Common issues:
- Wrong hostname (use add-on name for internal connections)
- Missing database permissions
- PostgreSQL add-on not running

### MCP Client Integration

If the MCP Client can't connect:
1. Ensure the add-on is running
2. Check the endpoint URL is correct
3. Verify Ingress is enabled in configuration
4. Review logs for SSE connection errors

---

## 📜 Changelog

See [CHANGELOG.md](mcp-server/CHANGELOG.md) for detailed version history.

### Latest: v0.4.1 (2024-12-19)
- Real PostgreSQL/TimescaleDB integration
- Full MCP protocol support
- Async database operations
- Enhanced error handling
- Query optimization

---

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

For major changes, please open an issue first to discuss.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Home Assistant Community for the amazing platform
- PostgreSQL and TimescaleDB teams for excellent databases
- Contributors and testers who help improve this add-on

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/mar-eid/ha-addon-mcp/issues)
- **Discussions**: [Home Assistant Community Forum](https://community.home-assistant.io)
- **Documentation**: [Wiki](https://github.com/mar-eid/ha-addon-mcp/wiki)

---

Made with ❤️ for the Home Assistant community