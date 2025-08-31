# 🔧 Home Assistant MCP Server Troubleshooting

## SSL/TLS Connection Issues

### ❌ Common Error
```
WARNING (MainThread) [homeassistant.util.loop] Detected blocking call to load_verify_locations 
with args (<ssl.SSLContext object>, '/usr/local/lib/python3.13/site-packages/certifi/cacert.pem', None, None) 
inside the event loop by integration 'mcp' at homeassistant/components/mcp/coordinator.py, line 49
```

### ✅ Solution: Use HTTP (Not HTTPS)

The error occurs when the Home Assistant MCP Client tries to connect using HTTPS and encounters SSL certificate validation issues.

**Fix**: Configure MCP Client to use **HTTP** endpoints:

### 🔗 Correct MCP Client Configuration

When setting up the MCP Client integration in Home Assistant:

```
Server URL: http://localhost:8099/sse
```

**NOT:**
- ~~https://localhost:8099/sse~~ ❌
- ~~https://addon_mcp_server:8099/sse~~ ❌

### 📝 Alternative URLs to Try

If `localhost` doesn't work, try these HTTP URLs:

1. `http://localhost:8099/sse`
2. `http://addon_mcp_server:8099/sse`  
3. `http://a0d7b954-mcp-server:8099/sse` (replace with your actual add-on hostname)
4. `http://homeassistant.local:8099/sse`

### 🧪 Test Connectivity First

Before configuring the MCP Client, test the connection:

```bash
# Test basic connectivity
curl http://localhost:8099/mcp-test

# Test SSE endpoint
curl -N -H "Accept: text/event-stream" http://localhost:8099/sse
```

### 🔍 Debugging Steps

1. **Check Add-on Status**
   - Ensure MCP Server add-on is running
   - Check add-on logs for errors

2. **Verify Web UI**
   - Open add-on Web UI from Home Assistant
   - Confirm server is responding

3. **Test Endpoints**
   - Use `/mcp-test` endpoint to verify basic connectivity
   - Use browser to test `http://homeassistant.local:8099/`

4. **Check Network**
   - Ensure port 8099 is accessible
   - Verify no firewall blocking

### 📊 Expected Log Messages

When working correctly, you should see:
```
🔗 HA MCP Client connected via /sse: [client-id]
🌍 Client headers: {...}
🔄 Sent initialization event to HA MCP Client
🛠️ Sent 4 tools to HA MCP Client
🏓 Ping [n] sent to HA MCP Client [client-id]
```

### ⚡ Quick Fix Checklist

- [ ] Using HTTP (not HTTPS) in MCP Client config
- [ ] MCP Server add-on is running
- [ ] Web UI accessible at add-on URL
- [ ] `/mcp-test` endpoint returns success
- [ ] No firewall blocking port 8099
- [ ] Using correct hostname for your setup

### 🆘 Still Not Working?

1. **Check Add-on Logs**: Settings → Add-ons → MCP Server → Logs
2. **Enable Debug Logging**: Set `log_level: debug` in add-on configuration
3. **Try Different URLs**: Test all the alternative URLs listed above
4. **Restart Add-on**: Sometimes a restart helps clear connection issues
5. **Check HA Core Logs**: Look for MCP-related errors in Home Assistant logs

### 💡 Why HTTP Instead of HTTPS?

- **Local Communication**: Add-ons communicate locally within Home Assistant
- **No Internet Traffic**: No external network exposure
- **Ingress Protection**: Home Assistant's Ingress provides authentication
- **SSL Unnecessary**: TLS/SSL not needed for localhost communication
- **Avoids Certificate Issues**: Eliminates SSL certificate validation problems

### ✅ Success Indicators

You'll know it's working when:
- MCP Client integration setup completes without errors
- Add-on logs show successful client connections
- Tools appear in AI assistant conversations
- You can ask AI about your Home Assistant historical data
