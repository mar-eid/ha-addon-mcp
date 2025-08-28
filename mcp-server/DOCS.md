# Home Assistant Add-on: MCP Server

Model Context Protocol server for querying Home Assistant historical data from PostgreSQL/TimescaleDB.

## Installation

The installation of this add-on is pretty straightforward and not different in comparison to installing any other Home Assistant add-on.

1. Search for the "MCP Server" add-on in the Home Assistant add-on store and install it.
2. Configure the add-on with your database connection details.
3. Start the "MCP Server" add-on.
4. Check the logs of the "MCP Server" to see if everything went well.
5. Open the Web UI to test the endpoints.

## Configuration

**Note**: _Remember to restart the add-on when the configuration is changed._

Example add-on configuration:

```yaml
pg_host: a0d7b954-postgresql
pg_port: 5432
pg_database: homeassistant
pg_user: homeassistant
pg_password: your_secure_password
read_only: true
enable_timescaledb: false
log_level: info
query_timeout: 30
max_query_days: 90
```

**Note**: _This is just an example, don't copy and paste it! Create your own configuration._

### Option: `pg_host`

The hostname or IP address of your PostgreSQL server. If you're using the PostgreSQL add-on, this is typically the add-on name (e.g., `a0d7b954-postgresql`).

### Option: `pg_port`

The port number your PostgreSQL server is running on. Default is `5432`.

### Option: `pg_database`

The name of the database containing your Home Assistant data. Default is `homeassistant`.

### Option: `pg_user`

Username for the database connection. Should have read access to the recorder tables.

### Option: `pg_password`

Password for the database user. Leave empty if using trust authentication.

### Option: `read_only`

When enabled, enforces read-only mode to prevent any database modifications. Highly recommended for security.

### Option: `enable_timescaledb`

Enable TimescaleDB-specific query optimizations if your database supports it.

### Option: `log_level`

The log level for the add-on. Options: `debug`, `info`, `warning`, `error`.

### Option: `query_timeout`

Maximum time in seconds to wait for database queries to complete (5-300).

### Option: `max_query_days`

Maximum number of days that can be queried in a single request (1-365).

## Usage

1. Ensure your PostgreSQL database contains Home Assistant recorder data
2. Configure the add-on with your database connection details
3. Start the add-on and check the logs for successful database connection
4. Access the Web UI through Home Assistant's Ingress system
5. Test the API endpoints or integrate with MCP clients

## Database Setup

For enhanced security, create a dedicated read-only user:

```sql
-- Connect to your PostgreSQL database as a superuser
CREATE USER ha_mcp_readonly WITH PASSWORD 'secure_random_password';

-- Grant necessary permissions
GRANT CONNECT ON DATABASE homeassistant TO ha_mcp_readonly;
GRANT USAGE ON SCHEMA public TO ha_mcp_readonly;
GRANT SELECT ON states TO ha_mcp_readonly;
GRANT SELECT ON states_meta TO ha_mcp_readonly;
GRANT SELECT ON statistics TO ha_mcp_readonly;
GRANT SELECT ON statistics_meta TO ha_mcp_readonly;
```

## API Endpoints

The add-on provides several REST API endpoints:

- `GET /health` - Health check and status
- `POST /tools/ha.get_history` - Query historical sensor data
- `POST /tools/ha.get_statistics` - Get statistical summaries  
- `POST /tools/ha.get_statistics_bulk` - Bulk statistics queries

## Changelog & releases

This repository keeps a change log using [GitHub's releases][releases] functionality.

Releases are based on [Semantic Versioning][semver], and use the format of `MAJOR.MINOR.PATCH`. In a nutshell, the version will be incremented based on the following:

- `MAJOR`: Incompatible or major changes.
- `MINOR`: Backwards-compatible new features and enhancements.
- `PATCH`: Backwards-compatible bugfixes and package updates.

## Support

Got questions?

You have several options to get them answered:

- The Home Assistant [Community Forum][forum].
- Open an issue on our [GitHub][issue].

In case you've found a bug, please [open an issue on our GitHub][issue].

[forum]: https://community.home-assistant.io
[issue]: https://github.com/mar-eid/ha-addon-mcp/issues
[releases]: https://github.com/mar-eid/ha-addon-mcp/releases
[semver]: http://semver.org/spec/v2.0.0.html