#!/usr/bin/with-contenv bashio
# ==============================================================================
# Home Assistant Community Add-on: MCP Server
# Simple startup script that avoids s6-overlay complexity
# ==============================================================================

bashio::log.info "🚀 Starting MCP Server v0.3.0..."

# Read configuration from add-on options
pg_host=$(bashio::config 'pg_host')
pg_port=$(bashio::config 'pg_port')
pg_database=$(bashio::config 'pg_database')
pg_user=$(bashio::config 'pg_user')
pg_password=$(bashio::config 'pg_password')
read_only=$(bashio::config 'read_only')
enable_timescaledb=$(bashio::config 'enable_timescaledb')
log_level=$(bashio::config 'log_level')

# Export environment variables for Python app
export PGHOST="${pg_host}"
export PGPORT="${pg_port}"
export PGDATABASE="${pg_database}"
export PGUSER="${pg_user}"
export PGPASSWORD="${pg_password}"
export MCP_READ_ONLY="${read_only}"
export MCP_ENABLE_TIMESCALEDB="${enable_timescaledb}"
export MCP_PORT="8099"

bashio::log.info "📊 Database: ${pg_user}@${pg_host}:${pg_port}/${pg_database}"
bashio::log.info "🔒 Read-only mode: ${read_only}"
bashio::log.info "⚡ TimescaleDB: ${enable_timescaledb}"

# Quick database connectivity test
bashio::log.info "🔍 Testing database connection..."
if timeout 5 python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='${pg_host}',
        port=${pg_port},
        database='${pg_database}',
        user='${pg_user}',
        password='${pg_password}',
        connect_timeout=3
    )
    conn.close()
    print('✅ Database connection successful')
except Exception as e:
    print(f'⚠️ Database connection failed: {e}')
    print('📝 Will use mock data as fallback')
" 2>&1; then
    bashio::log.info "✅ Database connectivity verified"
else
    bashio::log.warning "⚠️ Database not available - using mock data"
fi

bashio::log.info "🌐 Starting HTTP server on port ${MCP_PORT}..."
bashio::log.info "🎯 Web UI available via Home Assistant Ingress"

# Change to app directory and start the server
cd /app

# Run the Python server (exec replaces shell process)
exec python3 server.py