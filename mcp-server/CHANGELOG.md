# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.7] - 2025-08-31

### 🛠️ Fixed - MCP SDK Import Error

### Fixed
- **Critical Import Fix**: Fixed `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` error
- **Correct MCP Imports**: Updated to use proper MCP Python SDK imports (`mcp.types`, `mcp.server`)
- **SDK Compatibility**: Implemented server using standard MCP Server class instead of FastMCP
- **Protocol Compliance**: Using official MCP protocol implementation with stdio transport

### Changed  
- **Server Implementation**: Migrated from FastMCP to standard MCP Server class
- **Import Structure**: Updated all MCP imports to use official SDK structure
- **Transport Method**: Using stdio transport as recommended for MCP servers
- **Tool Registration**: Proper tool registration using server decorators

### Technical Details
- Uses `mcp` package version 1.1.2 with correct import paths
- Implemented HAMCPServer class with proper MCP server initialization
- Tools registered using `@server.list_tools()` and `@server.call_tool()` decorators
- Full async implementation with proper database connection pooling
- Comprehensive error handling and logging throughout

### Compatibility
- Maintains all existing functionality (get_history, get_statistics, list_entities, health_check)
- Backward compatible configuration options
- Same database connection and query logic
- Mock data mode still available when database unavailable

## [0.5.0] - 2024-12-19 (Deprecated)

### 🎉 Major Rewrite: Official MCP SDK Implementation

### Changed
- **Complete Rewrite**: Now using the official MCP Python SDK (`mcp` package) instead of custom implementation
- **FastMCP Framework**: Leveraging the high-level FastMCP API for cleaner code
- **Proper Protocol Compliance**: Using official SDK ensures full MCP protocol compatibility
- **Simplified Architecture**: Removed custom SSE/REST endpoints in favor of MCP stdio transport

### Added
- **Official MCP Tools**: Properly registered tools using `@mcp.tool()` decorator
- **Standard MCP Transport**: Using stdio transport as recommended by MCP specification
- **Better Type Safety**: Full type hints with official SDK types

### Fixed
- **Protocol Compatibility**: Should resolve all "Failed to connect" issues with HA MCP Client
- **Tool Discovery**: Proper tool registration and discovery through official SDK
- **Message Format**: Correct MCP message format handled by SDK

### Technical Details
- Uses `mcp` package version 1.1.2 from PyPI
- FastMCP server with stdio transport
- Tools: `get_history`, `get_statistics`, `list_entities`, `health_check`
- Maintains backward compatibility with mock data mode
- Async/await throughout with proper connection pooling

### Breaking Changes
- Removed custom REST API endpoints (use MCP protocol instead)
- Removed SSE endpoint (MCP handles its own transport)
- Server now runs as stdio process (standard for MCP servers)

## [0.4.2] - 2024-12-19

### Added
- **SSE (Server-Sent Events) Support**: Full implementation for MCP protocol communication
- **Interactive Test Interface**: Web-based testing UI at root endpoint
- **SSE Connection Monitor**: Real-time connection status and message logging
- **Local Testing Scripts**: Standalone scripts for testing without Home Assistant
- **Comprehensive Test Suite**: Automated tests for SSE, MCP, and REST endpoints

### Fixed
- **MCP Client Integration**: Resolved "Failed to connect" errors with proper SSE implementation
- **Protocol Compliance**: Correct event stream format with connection, tools, and ping events
- **Content-Type Headers**: Proper `text/event-stream` for SSE responses

### Enhanced
- **Mock Mode**: Server now works without database for testing SSE functionality
- **Debug Logging**: Detailed SSE client tracking and event logging
- **Error Recovery**: Graceful handling of SSE disconnections
- **Keep-Alive**: Periodic ping events to maintain connection

### Testing Tools
- `run_local.py`: Run server locally with mock data
- `test_sse.py`: Comprehensive SSE and MCP protocol testing
- Web interface with SSE connection testing at `http://localhost:8099/`

### Technical Details
- SSE endpoint at `/sse` with proper event streaming
- Connection event with protocol capabilities
- Tools event listing available MCP tools
- Ping events every 30 seconds for keep-alive
- Support for multiple concurrent SSE clients

## [0.4.1] - 2024-12-19

### Added
- **Real PostgreSQL/TimescaleDB Integration**: Complete implementation using asyncpg for async database operations
- **Full MCP Protocol Support**: Comprehensive Model Context Protocol implementation for AI assistant integration
- **Advanced Database Pooling**: Async connection pooling for improved performance and reliability
- **Entity Discovery**: Enhanced endpoint to list available entities and statistics with metadata
- **Time-series Aggregations**: Support for multiple aggregation intervals (5m, 15m, 30m, 1h, 6h, 1d)
- **Bulk Operations**: Efficient bulk querying with pagination support

### Changed
- **Complete Server Rewrite**: Migrated from mock data to real PostgreSQL queries
- **Async Architecture**: Full async/await implementation for better concurrency
- **Enhanced Error Handling**: Comprehensive error handling with detailed logging
- **Query Optimization**: Improved SQL queries with proper indexing and time-based partitioning support
- **Response Format**: Standardized MCP-compliant response format across all endpoints

### Fixed
- **Database Connectivity**: Robust connection management with proper error recovery
- **Read-only Enforcement**: Correctly applies read-only transaction mode when configured
- **TimescaleDB Support**: Proper detection and utilization of TimescaleDB features
- **Memory Management**: Fixed potential memory leaks in connection pooling

### Technical Improvements
- Implemented asyncpg for high-performance async PostgreSQL operations
- Added comprehensive input validation using Pydantic models
- Support for both short-term and long-term statistics tables
- Query timeout enforcement to prevent long-running queries
- Maximum query day limits to prevent excessive data retrieval
- Proper handling of numeric and non-numeric state values
- Support for JSON attributes in state data

### MCP Tools Available
- `ha.get_history`: Query historical state data with flexible aggregations
- `ha.get_statistics`: Retrieve statistical summaries from recorder
- `ha.get_statistics_bulk`: Bulk query multiple statistics efficiently
- `ha.list_entities`: Discover entities with recent data and metadata

### Performance
- Async database operations for non-blocking I/O
- Connection pooling with configurable min/max connections
- Efficient SQL queries optimized for Home Assistant's schema
- Support for TimescaleDB continuous aggregates when available

## [0.3.9] - 2025-08-29

### Added
- **📡 Full SSE Compliance**: Added Server-Sent Events endpoint (GET /mcp) for MCP protocol
- **🔄 Real-time Streaming**: Proper SSE implementation with initialization and tools notifications
- **🔔 Ping System**: Periodic keep-alive pings every 30 seconds for connection stability
- **⚙️ Dual Protocol Support**: Both SSE (GET /mcp) and JSON-RPC (POST /mcp) endpoints
- **🌐 Enhanced Headers**: Proper SSE headers with CORS and anti-buffering support

### Fixed
- **⚠️ SSE Protocol Compliance**: Now fully compliant with MCP Server-Sent Events specification
- **🔗 Home Assistant Integration**: Should resolve "Failed to connect" errors with MCP Client
- **📋 Connection Stability**: Proper SSE stream management with graceful error handling
- **🔍 Debug Logging**: Enhanced SSE connection and streaming debug information

### Technical Details
- **GET /mcp**: SSE endpoint for real-time MCP protocol communication
- **POST /mcp**: JSON-RPC endpoint for tool calls and commands
- **Auto-discovery**: SSE stream sends server info and available tools on connection
- **Error Handling**: Graceful SSE disconnection and error event broadcasting
- **Performance**: Optimized streaming with proper Content-Type and cache headers

### SSE Protocol Implementation
- **notifications/initialized**: Server capabilities and protocol version
- **notifications/tools/list**: Available tools broadcast to connected clients
- **notifications/ping**: Periodic heartbeat with timestamp and sequence
- **notifications/error**: Error events with graceful connection termination

### Usage
Home Assistant MCP Client can now connect to:
```
SSE URL: http://addon_mcp_server:8099/mcp (GET)
JSON-RPC URL: http://addon_mcp_server:8099/mcp (POST)
```

## [0.3.8] - 2025-08-29

### Documentation
- **📚 Troubleshooting Guide**: Added comprehensive MCP Client integration troubleshooting
- **🔍 Debug Instructions**: Detailed debugging steps for official HA MCP Client integration
- **⚙️ Configuration Examples**: Common setup scenarios and error solutions
- **🌐 Network Connectivity**: Add-on to integration communication guide

### Added
- **📋 Integration Support**: Enhanced compatibility with official Home Assistant MCP Client
- **🔧 Debug Commands**: Quick troubleshooting commands and tests
- **📄 Error Reference**: Common error messages and their solutions
- **🏗️ Setup Examples**: Multiple configuration approaches and alternatives

### Technical Details
- Documented official MCP Client integration troubleshooting workflow
- Added network connectivity testing procedures
- Provided alternative integration methods when MCP Client unavailable
- Enhanced server compliance verification steps

## [0.3.7] - 2025-08-29

### Fixed
- **⚠️ Critical JavaScript Errors**: Fixed undefined `timestamp` variable causing web interface crashes
- **🌐 Web Server Crashes**: Resolved server crashes when accessing root endpoint (`/`)
- **💻 HTML Template Issues**: Fixed malformed JavaScript in web interface template
- **🔧 String Formatting**: Corrected Python f-string formatting issues in HTML responses

### Enhanced
- **🌐 Stable Web Interface**: Complete rewrite of HTML template with proper JavaScript
- **🧨 Error Handling**: Improved error handling for web interface rendering
- **📱 Responsive Design**: Better mobile-friendly web interface
- **⚙️ Simplified Core**: Streamlined to essential MCP tools for better stability

### Technical Details
- Fixed JavaScript `NameError: name 'timestamp' is not defined` on line 968
- Rewrote all JavaScript functions with proper variable declarations
- Cleaned up HTML template string formatting to prevent parsing errors
- Added proper DOM manipulation with error handling
- Simplified MCP tool registry to core functionality

### Web Interface
- **Working Test Buttons**: All test functions now work properly
- **Clean Output Display**: Properly formatted test results
- **Safe JavaScript**: No undefined variables or syntax errors
- **Mobile Responsive**: Better display on mobile devices

## [0.3.6] - 2025-08-29

### Added
- **🔍 Enhanced Debug Logging**: Comprehensive debug logging when `log_level: debug` is set
- **📊 Full Stack Traces**: Complete error tracebacks in debug mode for all exceptions
- **🔧 Request/Response Logging**: Detailed logging of MCP protocol messages and timing
- **📋 Database Query Debugging**: SQL query logging, timing, and result analysis
- **🌐 Client Connection Info**: Log client IP, headers, and request details
- **🚀 Enhanced Startup Logging**: Environment variables, versions, and configuration details

### Enhanced
- **Database Connection**: Detailed connection timing and database metadata logging
- **Tool Execution**: Per-tool execution timing and parameter logging
- **Error Handling**: Full stack traces for all error conditions when in debug mode
- **Query Analysis**: Entity existence checks and data availability diagnostics
- **MCP Protocol**: Request/response debugging with full JSON message logging

### Debug Features
- **Query Performance**: Database query execution timing and optimization hints
- **Environment Inspection**: All MCP_* and PG* environment variables logged (passwords masked)
- **Tool Registry**: Available tools and their schemas logged at startup
- **Connection Diagnostics**: Database version, user, available tables logged
- **Request Tracking**: Full request lifecycle from client connection to response

### Usage
Set `log_level: debug` in add-on configuration to enable comprehensive debugging:
```yaml
log_level: debug
```

This will provide:
- Full stack traces for all errors
- Database query logging and timing
- MCP protocol message debugging  
- Tool execution performance metrics
- Environment and configuration inspection
- Client connection and request details

## [0.3.5] - 2025-08-29

### Fixed
- **🔧 Container Caching Issue**: Bumped version to force rebuild and prevent cached container usage
- **📦 Docker Image Update**: Ensured latest code is used instead of cached v0.3.0 image

### Technical Details
- Fixed issue where Home Assistant was using old cached Docker images
- Updated all version references to 0.3.5 to force container rebuild
- Resolved persistent "SyntaxError: 'break' outside loop" from cached code

## [0.3.4] - 2025-08-29

### Fixed
- **⚠️ Critical Syntax Error**: Resolved Python syntax error causing "'break' outside loop" crash on startup
- **🔧 Enhanced Error Handling**: Improved database connection error handling and fallback logic
- **📊 Better Mock Data**: Enhanced mock data generation for more realistic testing when DB unavailable
- **🔍 Query Robustness**: Added better validation and error handling for database queries
- **📝 Improved Logging**: Enhanced logging throughout application for better debugging

### Changed
- **🏗️ Complete Code Refactor**: Cleaned up entire server.py for better maintainability
- **📋 Enhanced Web UI**: Improved testing interface with better error handling
- **🎯 Better Tool Descriptions**: More detailed descriptions for all MCP tools
- **⚙️ Container Configuration**: Fixed startup settings in config.yaml (services, init: true)

### Added
- **🧪 Enhanced Testing**: Better test interface with more comprehensive tool testing
- **📊 Database Status**: More detailed health reporting for database connectivity
- **🔄 Graceful Fallbacks**: Better handling when database is unavailable
- **📖 Setup Instructions**: Enhanced setup documentation in web interface

### Technical Details
- Fixed Python syntax errors that prevented server startup
- Enhanced database connection pooling and error recovery
- Improved MCP protocol compliance and error responses
- Better handling of edge cases in data queries
- Enhanced configuration validation

## [0.3.3] - 2025-08-29

### Fixed
- **🔧 Protocol Compliance**: Implemented correct single `/mcp` endpoint per MCP specification
- **📡 SSE Transport**: Fixed SSE client connection issues with Home Assistant MCP integration
- **🔗 Endpoint Detection**: Added proper `endpoint` event emission for transport auto-detection
- **⚙️ Message Handling**: Corrected JSON-RPC 2.0 request/response format

### Changed
- **🎯 Single Endpoint Architecture**: Replaced separate `/sse` and `/message` with unified `/mcp`
- **📋 Enhanced Testing**: Updated Web UI with corrected endpoint testing
- **🔍 Protocol Validation**: Stricter adherence to MCP 2024-11-05 specification

### Technical Details
- Fixed `sse_client` connection failures in Home Assistant MCP integration
- Proper `text/event-stream` content type for SSE responses
- Enhanced CORS headers for cross-origin requests
- Correct endpoint announcement for transport negotiation

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