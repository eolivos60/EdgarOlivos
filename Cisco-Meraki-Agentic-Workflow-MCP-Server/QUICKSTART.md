# Quick Start Guide - Meraki MCP Server

This guide will get you up and running with the Meraki MCP Server in under 5 minutes.

## Prerequisites Checklist

- [ ] Python 3.10+ installed
- [ ] Meraki Dashboard account with API access
- [ ] MCP-compatible client (Claude Desktop, Cline, etc.)

## Step 1: Get Your Meraki API Key (2 minutes)

1. Log into [Meraki Dashboard](https://dashboard.meraki.com)
2. Click your profile (top right) → **My Profile**
3. Scroll to **API access**
4. Click **Generate new API key**
5. Copy the key (you won't see it again!)

## Step 2: Install the Server (1 minute)

```bash
# Navigate to the server directory
cd meraki-mcp-server

# Install dependencies
pip install -e .
```

## Step 3: Configure Your Client (2 minutes)

### For Claude Desktop

**MacOS**: Edit `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows**: Edit `%APPDATA%\Claude\claude_desktop_config.json`

Add this configuration:

```json
{
  "mcpServers": {
    "meraki-assistant": {
      "command": "python",
      "args": ["/FULL/PATH/TO/meraki-mcp-server/server.py"],
      "env": {
        "MERAKI_API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

**Important**: Replace `/FULL/PATH/TO/` with the actual absolute path!

### For Cline (VS Code)

1. Open VS Code
2. Install Cline extension if not already installed
3. Open Cline settings
4. Add MCP server configuration:

```json
{
  "meraki-assistant": {
    "command": "python",
    "args": ["/FULL/PATH/TO/meraki-mcp-server/server.py"],
    "env": {
      "MERAKI_API_KEY": "YOUR_API_KEY_HERE"
    }
  }
}
```

## Step 4: Test It! (30 seconds)

1. **Restart your MCP client** (important!)
2. Open a new chat
3. Try this command:

```
Show me all my Meraki organizations
```

You should see your Meraki organizations listed!

## Quick Test Commands

Try these to verify everything works:

```
# Discovery
Show me all networks in organization [ORG_ID]

# Device Status
What's the status of all devices in network [NETWORK_ID]?

# Health Check
Run a health check on my organization [ORG_ID]

# Troubleshooting
Diagnose connectivity issues in network [NETWORK_ID]
```

## Common Issues & Fixes

### "Tool not found" or "No MCP servers"
**Fix**: Restart your MCP client after adding configuration

### "API Key not set" error
**Fix**: Check that `MERAKI_API_KEY` is correctly set in config file

### "404 Not Found" errors
**Fix**: Verify your API key has access to the organization/network

### Server not starting
**Fix**: 
1. Check Python version: `python --version` (needs 3.10+)
2. Verify path to server.py is absolute
3. Check server.py has execute permissions

## Next Steps

Now that it's working, explore the capabilities:

1. **Read WORKFLOWS.md** - Learn about agentic workflows
2. **Try complex queries** - "Diagnose why my WiFi is slow"
3. **Automate tasks** - "Update all AP names to include floor numbers"
4. **Monitor health** - "Give me a weekly health report"

## Getting Help

- Check [README.md](README.md) for full documentation
- Review [WORKFLOWS.md](WORKFLOWS.md) for workflow examples
- Visit [Cisco DevNet](https://developer.cisco.com/meraki/) for API docs
- Check [MCP Documentation](https://modelcontextprotocol.io/)

## Security Reminder

🔒 **Never commit your API key to version control!**

Always use:
- Environment variables
- Config files (in .gitignore)
- Secret management systems

## Success!

If you've gotten this far, you now have an intelligent Meraki assistant at your fingertips! 🎉

Try asking it: "What can you help me with?" and explore its capabilities.

---

**Tip**: The more context you provide, the better the agent can help. Instead of "Check the network", try "Our Seattle office network has been slow since yesterday, can you diagnose the issue?"
