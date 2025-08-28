# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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