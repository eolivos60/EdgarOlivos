# Cisco Meraki MCP Server

A Model Context Protocol (MCP) server for intelligent Cisco Meraki network troubleshooting and configuration with agentic workflow capabilities.

## Features

### 🔍 Discovery & Monitoring
- **Organization Management**: View and manage multiple Meraki organizations
- **Network Discovery**: Automatically discover networks and devices
- **Real-time Status**: Monitor device status, uplinks, and connectivity
- **Health Alerts**: Track and respond to network health alerts

### 🛠️ Troubleshooting Tools
- **Device Diagnostics**: Detailed device status and uplink analysis
- **Client Troubleshooting**: Track and diagnose client connectivity issues
- **Connectivity Diagnosis**: Multi-step intelligent diagnosis of network issues
- **Automated Health Checks**: Comprehensive organization-wide health assessment

### ⚙️ Configuration Management
- **Device Configuration**: Update device names, tags, addresses, and notes
- **Network Settings**: Manage network configurations and settings
- **Wireless Management**: Configure and manage wireless SSIDs
- **Bulk Operations**: Perform operations across multiple devices

### 🤖 Agentic Workflows
- **Intelligent Diagnosis**: AI-driven multi-step troubleshooting workflows
- **Automated Health Checks**: Proactive monitoring with actionable recommendations
- **Context-Aware Suggestions**: Smart recommendations based on network state
- **Workflow Orchestration**: Chain multiple operations for complex tasks

## Installation

### Prerequisites
- Python 3.10 or higher
- Cisco Meraki credentials (API key or dashboard cookie session)
- Approved client path for your org (GitHub Copilot, AWS Bedrock, or CircuIT)

### Setup

1. **Clone or download this repository**

```bash
cd meraki-mcp-server
```

2. **Install dependencies**

```bash
pip install -e .
```

3. **Set up credentials**

Create a `.env` file for API-key auth:
```bash
MERAKI_API_KEY=your_api_key_here
```

Or for dashboard cookie auth (supports GET and PUT when session + CSRF are valid):
```bash
MERAKI_AUTH_METHOD=cookies
MERAKI_DASHBOARD_HOST=n###.dashboard.meraki.com
MERAKI_COOKIES=...
MERAKI_CSRF_TOKEN=...
MERAKI_REFERER=https://n###.dashboard.meraki.com/
```

Or export API key as environment variable:
```bash
export MERAKI_API_KEY=your_api_key_here
```

### Getting Your Meraki API Key

1. Log into the [Meraki Dashboard](https://dashboard.meraki.com)
2. Navigate to **Organization > Settings**
3. Scroll to **Dashboard API access**
4. Enable API access
5. Generate and copy your API key

## Configuration

### Approved MCP Client Configuration

Use your approved Cisco channel (GitHub Copilot, AWS Bedrock integration, or CircuIT) and register this server with your client's MCP settings:

```json
{
  "meraki-assistant": {
    "command": "python",
    "args": ["/path/to/meraki-mcp-server/server.py"],
    "env": {
      "MERAKI_API_KEY": "your_api_key_here",
      "MERAKI_AUTH_METHOD": "auto"
    }
  }
}
```

### Large Organization Device Retrieval (Up To 5000)

Use `get_organization_devices` with `auto_paginate` for large organizations:

```json
{
  "organization_id": "123456",
  "per_page": 1000,
  "auto_paginate": true,
  "max_records": 5000
}
```

For manual paging, keep `auto_paginate` false and pass `starting_after` with the last serial from the prior batch.

### Find One Device Serial (Recommended For Large Orgs)

Use `find_organization_device_by_serial` to scan pages server-side and return a match in one tool call:

```json
{
  "organization_id": "123456",
  "serial": "Q3AC-WY9C-4STT",
  "per_page": 1000,
  "max_pages": 100
}
```

When found, response includes `device` and `node_id` (parsed from `device.url` when present).

## Usage Examples

### Basic Discovery Workflow

```
User: "Show me all my Meraki organizations"
Agent: [Uses get_organizations tool]

User: "Get the networks in organization XYZ"
Agent: [Uses get_networks with org_id]

User: "Show me all devices in network ABC"
Agent: [Uses get_network_devices]
```

### Troubleshooting Workflow

```
User: "I'm having connectivity issues in my Seattle office network"
Agent: [Uses diagnose_connectivity_issue tool]
- Checks organization-wide uplink status
- Analyzes network health alerts
- Identifies offline devices
- Provides actionable recommendations
```

### Automated Health Check

```
User: "Run a health check on my entire organization"
Agent: [Uses automated_health_check tool]
- Scans all networks
- Checks device status
- Reviews uplink connectivity
- Generates comprehensive report with recommendations
```

### Configuration Management

```
User: "Update the name of device with serial Q2XX-XXXX-XXXX to 'Seattle-AP-01'"
Agent: [Uses update_device tool]

User: "Enable SSID 1 in network ABC and set the name to 'Corporate-WiFi'"
Agent: [Uses update_wireless_ssid tool]

User: "Clear internal adminTags for serial Q3AC-KGYE-MZKY"
Agent: [Uses update_device_admin_tags with admin_tags=[]]

User: "Find serial Q3AC-KGYE-MZKY and clear adminTags in one step"
Agent: [Uses clear_device_admin_tags_by_serial]
```

## Available Tools

### Discovery Tools
- `get_organizations` - List all accessible organizations
- `get_networks` - Get networks in an organization
- `get_network_devices` - List devices in a network
- `get_organization_devices` - List organization devices with pagination (`starting_after`, `ending_before`) and optional auto-pagination up to 5000 records
- `find_organization_device_by_serial` - Search organization devices across pages and return the matching device plus node ID
- `get_device_internal_details` - Read internal dashboard device details (cookie auth), including adminTags when available

### Monitoring Tools
- `get_device_status` - Detailed device status
- `get_device_uplink_status` - Uplink connectivity status
- `get_device_clients` - Clients connected to a device
- `get_network_health_alerts` - Active alerts for a network
- `get_organization_uplink_statuses` - Organization-wide uplink status

### Client Tools
- `get_network_clients` - All clients in a network
- `get_client_details` - Detailed client information

### Configuration Tools
- `update_device` - Update device configuration
- `update_device_admin_tags` - Update internal adminTags field through dashboard internal API (cookie auth)
- `clear_device_admin_tags_by_serial` - Find by serial in org and clear adminTags in one call (cookie auth)
- `update_network` - Update network settings
- `get_wireless_ssids` - List wireless SSIDs
- `update_wireless_ssid` - Update SSID configuration

### Admin Tags Through Internal API

Use cookie auth for these operations:

```bash
MERAKI_AUTH_METHOD=cookies
MERAKI_DASHBOARD_HOST=n###.dashboard.meraki.com
MERAKI_COOKIES=...
MERAKI_CSRF_TOKEN=...
```

Read current internal details:

```json
{
  "serial": "Q3AC-KGYE-MZKY"
}
```

Clear admin tags:

```json
{
  "serial": "Q3AC-KGYE-MZKY",
  "admin_tags": []
}
```

Convenience one-call flow (find + clear + optional verification):

```json
{
  "organization_id": "622622648484233674",
  "serial": "Q3AC-KGYE-MZKY",
  "per_page": 1000,
  "max_pages": 100,
  "verify_after": true
}
```

### Agentic Workflow Tools
- `diagnose_connectivity_issue` - Intelligent multi-step diagnosis
- `automated_health_check` - Comprehensive health assessment

## Agentic Workflow Architecture

The server implements intelligent workflows that:

1. **Contextual Analysis**: Understands the problem from user description
2. **Multi-Step Execution**: Performs sequential diagnostic steps
3. **Data Correlation**: Connects information across multiple API calls
4. **Smart Recommendations**: Provides actionable next steps
5. **State Management**: Maintains context across workflow steps

### Example: Connectivity Diagnosis Flow

```
User Issue: "Office WiFi is slow"
    ↓
1. Check Organization Uplinks → Identify WAN issues
    ↓
2. Check Network Alerts → Identify configuration issues
    ↓
3. Check Device Status → Identify offline devices
    ↓
4. Analyze Client Connections → Identify congestion
    ↓
5. Generate Report → Prioritized recommendations
```

## API Rate Limiting

The Meraki API has rate limits:
- **10 requests per second** per organization
- The server implements automatic retry logic
- Use bulk operations when possible

## Error Handling

The server provides detailed error messages:
- **Authentication errors**: Check API key validity
- **404 errors**: Verify resource IDs
- **Rate limiting**: Automatic backoff and retry
- **Network errors**: Connection timeout handling

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black server.py
ruff check server.py
```

### Adding New Tools

1. Add tool definition in `handle_list_tools()`
2. Add handler method (e.g., `_handle_new_tool()`)
3. Add routing in `handle_call_tool()`
4. Update documentation

## Troubleshooting

### "API Key Not Set" Error
- Ensure `MERAKI_API_KEY` is set in environment or config
- Verify API key is valid and has proper permissions

### "Connection Timeout" Errors
- Check internet connectivity
- Verify Meraki Dashboard is accessible
- Increase timeout in `httpx.AsyncClient`

### "404 Not Found" Errors
- Verify organization/network/device IDs
- Check API key has access to the resource
- Ensure resource exists in Dashboard

### Tool Not Appearing in Client
- Restart your approved MCP-capable client
- Check MCP server logs for errors
- Verify configuration file syntax

### Compliance Guardrails
- Do not use native Anthropic API routes or Anthropic-native products for this workflow
- Use only approved channels: GitHub Copilot, AWS Bedrock, or CircuIT
- See COMPLIANCE.md for policy mapping and verification steps

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use environment variables** for sensitive data
3. **Limit API key permissions** to minimum required
4. **Rotate API keys** periodically
5. **Monitor API usage** via Meraki Dashboard

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## Resources

- [Cisco Meraki API Documentation](https://developer.cisco.com/meraki/api-v1/)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Meraki Community](https://community.meraki.com/)

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
- Create an issue in this repository
- Check [Meraki DevNet Community](https://community.cisco.com/t5/devnet/ct-p/4421j-devnet-home)
- Review [MCP Documentation](https://modelcontextprotocol.io/)

## Changelog

### v1.0.0 (2026-01-16)
- Initial release
- 18 tools covering discovery, monitoring, troubleshooting, and configuration
- Agentic workflow capabilities
- Intelligent diagnosis and automated health checks
- Full MCP protocol support
