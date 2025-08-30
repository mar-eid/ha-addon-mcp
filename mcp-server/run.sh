#!/usr/bin/with-contenv bashio
# ==============================================================================
# Home Assistant Community Add-on: MCP Server
# Direct run script (no s6-overlay complexity)
# ==============================================================================

echo "🚀 Starting MCP Server v0.5.0 (Official MCP SDK)..."

# Read configuration from Home Assistant
PG_HOST=$(bashio::config 'pg_host')
PG_PORT=$(bashio::config 'pg_port')
PG_DATABASE=$(bashio::config 'pg_database')
PG_USER=$(bashio::config 'pg_user')
PG_PASSWORD=$(bashio::config 'pg_password')
READ_ONLY=$(bashio::config 'read_only')
ENABLE_TIMESCALEDB=$(bashio::config 'enable_timescaledb')
LOG_LEVEL=$(bashio::config 'log_level')
QUERY_TIMEOUT=$(bashio::config 'query_timeout')
MAX_QUERY_DAYS=$(bashio::config 'max_query_days')

echo "📊 Database: ${PG_USER}@${PG_HOST}:${PG_PORT}/${PG_DATABASE}"
echo "🔒 Read-only mode: ${READ_ONLY}"
echo "⚡ TimescaleDB: ${ENABLE_TIMESCALEDB}"
echo "📝 Log level: ${LOG_LEVEL^^}"

# Export environment variables for the server
export PGHOST="${PG_HOST}"
export PGPORT="${PG_PORT}"
export PGDATABASE="${PG_DATABASE}"
export PGUSER="${PG_USER}"
export PGPASSWORD="${PG_PASSWORD}"
export MCP_READ_ONLY="${READ_ONLY}"
export MCP_ENABLE_TIMESCALEDB="${ENABLE_TIMESCALEDB}"
export MCP_PORT="8099"
export LOG_LEVEL="${LOG_LEVEL^^}"
export MCP_QUERY_TIMEOUT="${QUERY_TIMEOUT}"
export MCP_MAX_QUERY_DAYS="${MAX_QUERY_DAYS}"

# Quick database connectivity test
echo "🔍 Testing database connection..."
timeout 10 python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='${PG_HOST}',
        port=${PG_PORT},
        database='${PG_DATABASE}',
        user='${PG_USER}',
        password='${PG_PASSWORD}',
        connect_timeout=5
    )
    conn.close()
    print('✅ Database connection successful')
except Exception as e:
    print(f'⚠️  Database connection failed: {e}')
    print('🔄 Will use mock data as fallback')
" 2>/dev/null || echo "⚠️  Database test failed - continuing with mock data"

echo "🌐 Starting MCP Server on port 8099..."
echo "🎯 Web UI will be available via Home Assistant Ingress"

# Start the server directly
cd /app
exec python3 server.py
