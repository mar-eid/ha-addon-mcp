# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.2] - 2025-08-29

### 🎯 Major Update: Home Assistant MCP Integration Compatibility

### Fixed
- **⚠️ Critical Protocol Fix**: Resolved Home Assistant MCP integration connection errors
- **🔧 Single Endpoint**: Implemented correct MCP specification with single `/mcp` endpoint
- **📡 SSE Transport**: Fixed SSE transport implementation per MCP 2024-11-05 specification
- **🔗 Protocol Compliance**: Corrected JSON-RPC message handling and endpoint detection

### Added
- **📡 SSE Transport Protocol**: Full Server-Sent Events implementation required by HA MCP integration
- **🔧 MCP Protocol Compliance**: Complete Model Context Protocol 2024-11-05 implementation
- **📜 MCP Message Handler**: `/message` endpoint for proper MCP client communication
- **🔍 Tool Discovery**: Dynamic tool listing via `tools/list` method
- **🎯 Enhanced Tool Set**: 5 comprehensive tools for Home Assistant data access
- **📊 Real-time SSE Stream**: `/sse` endpoint with connection management and keep-alive
- **🔄 Protocol Initialization**: Proper MCP session setup with capability negotiation
- **🧪 Live SSE Testing**: Interactive web interface to test SSE endpoint in real-time
- **📋 Integration Instructions**: Step-by-step setup guide in Web UI

### Changed
- **🚀 Complete Server Rewrite**: Full compatibility with official Home Assistant MCP integration
- **📝 MCP-Standard Responses**: All tool responses now follow MCP content format
- **🔎 Tool Schema**: Comprehensive JSON schemas for all available tools
- **💱 Web Interface**: Enhanced root endpoint with integration instructions
- **🗺️ Tool Organization**: Structured tool registry with proper handlers

### Tools Available for AI Assistants
- **`ha.get_history`**: Get historical entity data over time periods
- **`ha.get_statistics`**: Get statistical summaries (mean, min, max, sum)
- **`ha.list_entities`**: Discover available entities with historical data
- **`ha.list_statistics`**: List available statistical data sources
- **`addon.health`**: Monitor server and database connection status

### Integration Instructions
1. Install **Model Context Protocol** integration in Home Assistant
2. Configure SSE endpoint: `http://localhost:8099/sse`
3. Tools automatically available for conversation agents (OpenAI, Anthropic, etc.)
4. Ask AI assistants questions about your Home Assistant historical data!

### Technical Details
- Implements MCP Protocol version 2024-11-05
- SSE transport with proper connection management
- JSON-RPC 2.0 compliant message handling
- Backward compatible with previous REST API endpoints
- Enhanced error handling and logging
- Real-time connection status monitoring

### Migration Notes
- **Fully backward compatible** - existing integrations continue to work
- **New primary integration path**: Use Home Assistant MCP integration
- **Enhanced AI capabilities**: Ask natural language questions about your data
- **Tool-based interaction**: AI can now directly query your historical data

### Fixed
- **🔧 Critical Container Fix**: Resolved "s6-overlay-suexec: fatal: can only run as pid 1" error
- **Simplified Startup**: Changed from `startup: services` to `startup: application`
- **Container Init**: Set `init: false` and use direct `run.sh` script instead of s6-overlay
- **Build Process**: Streamlined Docker container startup process

### Technical Details
- Replaced complex s6-overlay service management with simple run script
- Fixed container execution to avoid PID 1 conflicts
- Maintained all functionality while simplifying container architecture

## [0.3.0] - 2025-08-29

### 🎉 Major Milestone: Working Home Assistant Add-on Store Integration

### Added
- **Full PostgreSQL Database Integration**: Real database queries replace mock data
- **Complete MCP Protocol Support**: Added `/mcp/call_tool` endpoint for AI assistants
- **Enhanced API Endpoints**: Comprehensive tool set for historical data access
- **Proper Error Handling**: Robust database connection management with fallbacks
- **Health Monitoring**: Detailed health checks and status reporting
- **Repository Compatibility**: Added `repository.json` for better HA store integration

### Fixed
- **⚠️ Critical**: Removed invalid `postgresql:want` service that prevented add-on detection
- **Container Build**: Fixed Docker health check using `curl` instead of missing dependencies
- **Configuration Schema**: Corrected port mapping and ingress configuration
- **File Structure**: Moved `build.yaml` to correct location inside add-on folder
- **Logging**: Added comprehensive logging throughout the application

### Changed
- **Database Queries**: Implemented real Home Assistant recorder table queries
- **Response Format**: Standardized MCP-compatible JSON responses
- **Configuration**: Simplified and validated all config options
- **Documentation**: Updated README with proper installation instructions

### Technical Details
- Now properly queries `states`, `states_meta`, `statistics`, and `statistics_meta` tables
- Graceful fallback to mock data when database is unavailable
- Full MCP protocol compliance for AI assistant integration
- Enhanced container labels and build arguments
- Proper Home Assistant Ingress integration

### Migration Notes
- This version requires PostgreSQL database access configured in options
- Add-on is now visible in Home Assistant Add-on Store
- Compatible with official Home Assistant MCP Client integration


---

## [0.2.4] - 2024-08-28

### Fixed
- **Build System**: Removed Alpine package version pinning that caused multi-arch build failures
- **Dependencies**: Added missing `psycopg2-binary` for PostgreSQL database connectivity
- **Container**: Fixed s6-overlay configuration with `init: true` in config.yaml
- **Dockerfile**: Simplified Python package installation approach for better compatibility

### Changed
- Updated Dockerfile to use latest compatible Alpine packages without version constraints
- Improved error handling in container build process
- Streamlined s6 service structure for better reliability

### Technical Details
- Fixed exit code 5 errors during Docker build on both amd64 and aarch64 architectures
- Resolved "s6-overlay-suexec: fatal: can only run as pid 1" startup errors
- Cleaned up conflicting service management files

## [0.2.3] - 2024-08-28

### Added
- Enhanced Home Assistant add-on compliance following official guidelines
- Comprehensive configuration schema validation
- Professional README with installation and configuration instructions
- Multi-architecture support (amd64, aarch64)

### Improved
- Security model using Home Assistant Ingress authentication
- Service dependency management for PostgreSQL integration
- Logging and error handling throughout the application

## [0.1.0] - 2024-08-28

### Added
- Initial release with basic MCP server functionality
- **Core Features**:
  - Home Assistant Ingress integration for secure access
  - Three MCP tools: `ha.get_history`, `ha.get_statistics`, `ha.get_statistics_bulk`
  - Mock data endpoints for development and testing
  - Health check endpoint for monitoring
- **Configuration Options**:
  - PostgreSQL/TimescaleDB connection settings
  - Read-only mode for database security
  - Configurable query limits and timeouts
- **Container Support**:
  - Docker containerization with Home Assistant base images
  - S6-overlay service management
  - Multi-stage build process
- **Development Infrastructure**:
  - GitHub Actions CI/CD pipeline
  - Multi-architecture container builds
  - Automated container registry publishing

### Technical Implementation
- FastAPI-based REST API server
- Pydantic models for request validation
- Environment-based configuration management
- Prepared database integration points (PostgreSQL/TimescaleDB)

---

## Planned Features

### [0.3.0] - Upcoming
- **Real Database Integration**: Replace mock data with actual PostgreSQL queries
- **MCP Protocol Implementation**: Full Model Context Protocol support for AI assistants
- **Enhanced Query Capabilities**: Advanced filtering and aggregation options
- **TimescaleDB Optimization**: Native time-series database features

### [0.4.0] - Future
- **AI Assistant Integration**: Direct integration with Home Assistant Assist
- **Query Caching**: Performance improvements for frequently requested data
- **Advanced Statistics**: More sophisticated data analysis capabilities
- **User Interface**: Web-based query builder and data visualization

---

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to submit pull requests, report issues, and suggest improvements.

## Support

- **Documentation**: [README.md](README.md)
- **Issues**: [GitHub Issues](https://github.com/mar-eid/ha-addon-mcp/issues)
- **Community**: [Home Assistant Community Forum](https://community.home-assistant.io)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for d