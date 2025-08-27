#!/usr/bin/env bash
set -euo pipefail

# Les add-on options (Supervisor skriver til /data/options.json)
jq_get() { jq -r "$1" /data/options.json; }

PGHOST=$(jq_get '.pg_host')
PGPORT=$(jq_get '.pg_port')
PGDATABASE=$(jq_get '.pg_database')
PGUSER=$(jq_get '.pg_user')
PGPASSWORD=$(jq_get '.pg_password // empty')
READ_ONLY=$(jq_get '.read_only')
ENABLE_TS=$(jq_get '.enable_timescaledb')

export PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD
export MCP_READ_ONLY="$READ_ONLY"
export MCP_ENABLE_TS="$ENABLE_TS"
export MCP_PORT="${MCP_PORT:-8099}"

echo "[mcp] starting on port ${MCP_PORT} (read_only=${MCP_READ_ONLY}, enable_ts=${MCP_ENABLE_TS})"

exec python3 /opt/mcp/server.py

