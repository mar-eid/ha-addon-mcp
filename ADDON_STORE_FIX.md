# 🔧 Add-on Store Visibility Troubleshooting Guide

## Problem
After build succeeded, the MCP Server add-on is not visible in the Home Assistant Add-on Store.

## ✅ Fixes Applied (v0.5.3)

### 1. **Fixed Invalid Service Dependency**
- **Problem**: `services: - postgresql:want` caused validation errors
- **Solution**: Removed invalid PostgreSQL service dependency
- **Impact**: Allows HA to properly parse the configuration

### 2. **Added Missing Repository Files**
- **Problem**: Missing `repository.yaml` file
- **Solution**: Added proper repository configuration files:
  - ✅ `repository.json` (already existed)
  - ✅ `repository.yaml` (added)

### 3. **Corrected Version Numbering**
- **Problem**: Version numbering confusion
- **Solution**: Set correct incremental version `0.5.3`
- **Files Updated**: `config.yaml`, `server.py`, `run.sh`, `CHANGELOG.md`, `README.md`

## 🔄 How to Make Add-on Visible Again

### Step 1: Push Changes and Trigger Build
```bash
git add .
git commit -m "v0.5.3: Fix add-on store visibility issues"
git push
```

### Step 2: Wait for GitHub Actions Build
- Check: https://github.com/mar-eid/ha-addon-mcp/actions
- Ensure both `amd64` and `aarch64` builds succeed
- New images should be pushed to `ghcr.io/mar-eid/ha-addon-mcp-{arch}:0.5.3`

### Step 3: Refresh Home Assistant Add-on Store
1. In Home Assistant: **Settings** → **Add-ons** → **Add-on Store**
2. Click ⋮ menu → **Reload**
3. Wait 30-60 seconds for cache refresh
4. Check if "MCP Server" appears in the add-on list

### Step 4: Clear Browser Cache (if needed)
- Clear browser cache for Home Assistant
- Hard refresh (Ctrl+F5 / Cmd+Shift+R)
- Try incognito/private mode

### Step 5: Force Repository Refresh
If still not visible, remove and re-add the repository:

1. **Settings** → **Add-ons** → **Add-on Store**
2. Click ⋮ → **Repositories**
3. **Remove** `https://github.com/mar-eid/ha-addon-mcp`
4. Wait 30 seconds
5. **Add** `https://github.com/mar-eid/ha-addon-mcp` again
6. **Reload** the add-on store

## 🏗️ Configuration Validation

The add-on now has a clean, valid configuration:

```yaml
name: MCP Server
version: "0.5.3"
slug: mcp_server
description: Model Context Protocol server for querying Home Assistant historical data
url: https://github.com/mar-eid/ha-addon-mcp
arch:
  - aarch64
  - amd64
startup: application
boot: auto
init: false
stage: experimental
hassio_api: true
hassio_role: default
auth_api: true
ingress: true
ingress_port: 8099
panel_icon: mdi:database-search
panel_title: MCP Server
homeassistant: 2024.1.0

image: ghcr.io/mar-eid/ha-addon-mcp-{arch}

ports:
  8099/tcp: 8099

map:
  - config:rw

# No invalid service dependencies
options:
  pg_host: a0d7b954-postgresql
  pg_port: 5432
  pg_database: homeassistant
  pg_user: homeassistant
  pg_password: ""
  read_only: true
  enable_timescaledb: false
  log_level: info
  query_timeout: 30
  max_query_days: 90
```

## 🔍 Troubleshooting Steps

### Check Build Status
```bash
# Check if images were built successfully
curl -s https://api.github.com/repos/mar-eid/ha-addon-mcp/actions/runs | jq '.workflow_runs[0] | {status, conclusion}'
```

### Check Container Registry
- Visit: https://github.com/mar-eid/ha-addon-mcp/pkgs/container/ha-addon-mcp-amd64
- Verify version `0.5.3` exists

### Check Repository Files
Ensure these files exist in the root of your repo:
- ✅ `repository.json` 
- ✅ `repository.yaml`
- ✅ `mcp-server/config.yaml`
- ✅ `mcp-server/Dockerfile`

### Check HA Logs
If still not visible, check Home Assistant logs:
1. **Settings** → **System** → **Logs**
2. Look for add-on store parsing errors
3. Check for validation failures

## 🚀 Expected Result

After these fixes, you should see:
- ✅ MCP Server appears in Home Assistant Add-on Store
- ✅ Version shows as 0.5.3
- ✅ Installation works without errors
- ✅ Add-on starts successfully with MCP SDK

## 📞 If Still Not Visible

If the add-on is still not visible after following all steps:

1. **Check GitHub Actions**: Ensure all builds completed successfully
2. **Wait Longer**: Sometimes HA cache takes 5-10 minutes to refresh
3. **Restart Home Assistant**: Full restart may clear repository cache
4. **Check Configuration**: Validate `config.yaml` syntax is correct
5. **Check Repository**: Ensure all required files are present

The most common cause is caching - give it some time and try the repository refresh method above.

---

**Status**: ✅ All configuration issues fixed in version 0.5.3
**Next**: Push changes and wait for GitHub Actions build to complete
