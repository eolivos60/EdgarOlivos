# Wireless Analytics Tools

These 5 new tools provide deep insights into wireless network performance and troubleshooting capabilities.

## Tools Overview

### 1. `get_device_channel_utilization`
**Purpose:** Analyze how much time APs spend on different WiFi channels.

**Use Cases:**
- Identify channel congestion or co-channel interference
- Validate channel efficiency and load distribution
- Plan channel optimization

**Parameters:**
- `organization_id` (required): Your Meraki organization ID
- `serials` (required): Array of AP serial numbers (e.g., `["Q3AL-84EF-7Z69", "Q3AJ-7XRH-W9DW"]`)
- `timespan` (optional): Time period in seconds (default: 604800 = 7 days)
- `interval` (optional): Data point granularity in seconds (default: 3600 = 1 hour)

**Example Claude Prompt:**
```
"Check channel utilization for APs Q3AL-84EF-7Z69 and Q3AJ-7XRH-W9DW 
in org 703687441776644559 over the last 7 days, showing hourly breakdown"
```

---

### 2. `get_wireless_signal_quality_history`
**Purpose:** Track signal strength (RSSI), signal-to-noise ratio (SNR), and other RF metrics over time.

**Use Cases:**
- Diagnose poor RF coverage or interference issues
- Identify signal degradation patterns
- Correlate signal quality with client experience problems

**Parameters:**
- `network_id` (required): Your Meraki network ID
- `device_serial` (required): AP serial number
- `timespan` (optional): Time period in seconds (default: 604800 = 7 days)
- `resolution` (optional): Data point granularity in seconds (default: 3600 = 1 hour)

**Example Claude Prompt:**
```
"Show me the signal quality history for AP Q3AJ-7XRH-W9DW 
in network L_642888846807149407 for the last 7 days"
```

---

### 3. `get_wireless_failed_connections`
**Purpose:** Identify and analyze failed WiFi connection attempts (authentication, DHCP failures, etc.).

**Use Cases:**
- Troubleshoot authentication or DHCP issues
- Find patterns in failed connections (specific times, SSIDs, clients)
- Diagnose security policy or certificate problems

**Parameters:**
- `network_id` (required): Your Meraki network ID
- `t0` (required): Start time (ISO 8601 format, e.g., `"2026-06-16T11:45:00Z"`)
- `t1` (required): End time (ISO 8601 format, e.g., `"2026-06-17T11:45:00Z"`)

**Example Claude Prompt:**
```
"Show failed wireless connections in network L_691865492754805981 
between 2026-06-16T11:45:00Z and 2026-06-17T11:45:00Z"
```

---

### 4. `get_wireless_roaming_stats`
**Purpose:** Measure how often and how successfully clients roam between APs.

**Use Cases:**
- Optimize roaming behavior (fast roaming, seamless handoff)
- Identify roaming problems or excessive client movement
- Validate band steering and load balancing

**Parameters:**
- `organization_id` (required): Your Meraki organization ID
- `network_ids` (required): Array of network IDs (e.g., `["L_784752235069318648"]`)
- `timespan` (optional): Time period in seconds (default: 86400 = 1 day)
- `interval` (optional): Data granularity in seconds (default: 3600 = 1 hour)

**Example Claude Prompt:**
```
"Get roaming statistics for network L_784752235069318648 
in org 1243866 over the last 24 hours, hourly intervals"
```

---

### 5. `get_wireless_rf_profiles`
**Purpose:** Retrieve RF (Radio Frequency) configuration profiles applied to a network.

**Use Cases:**
- Review current RF settings (power, rates, channels, TX power limits)
- Troubleshoot why certain RF settings are not taking effect
- Document RF configuration for compliance or audits

**Parameters:**
- `network_id` (required): Your Meraki network ID

**Example Claude Prompt:**
```
"Show the RF profiles configured for network N_799951883811695119"
```

---

## How to Use with Claude

Once these tools are deployed, you can ask Claude natural language questions:

### Example Troubleshooting Workflow

**Problem:** Clients are experiencing poor WiFi performance.

**Questions to Ask Claude:**
1. "Check channel utilization for my APs to see if we have congestion"
2. "Show me signal quality history for the problematic AP" 
3. "Are there failed connection attempts in the last 24 hours?"
4. "How's the roaming situation? Are clients bouncing between APs?"
5. "What RF settings are currently active for this network?"

Claude will call these tools in sequence and provide a comprehensive analysis with recommendations.

---

## API Endpoint Reference

These tools map directly to Meraki Dashboard API v1 endpoints:

| Tool | Endpoint |
|------|----------|
| `get_device_channel_utilization` | `GET /organizations/{id}/wireless/devices/channelUtilization/byDevice` |
| `get_wireless_signal_quality_history` | `GET /networks/{id}/wireless/signalQualityHistory` |
| `get_wireless_failed_connections` | `GET /networks/{id}/wireless/failedConnections` |
| `get_wireless_roaming_stats` | `GET /organizations/{id}/wireless/roaming/byNetwork/byInterval` |
| `get_wireless_rf_profiles` | `GET /networks/{id}/wireless/rfProfiles/indoor` |

---

## Data Format Tips

### Time Ranges
- Use **ISO 8601 format** for `t0` and `t1`: `YYYY-MM-DDTHH:MM:SSZ`
- Example: `2026-06-16T11:45:00Z` (UTC timezone)

### Serial Numbers
- AP serials are found in the Meraki Dashboard under Device Details
- Always include the full serial (e.g., `Q3AL-84EF-7Z69`, not just `Q3AL`)

### Organization vs Network IDs
- **Organization ID**: Your top-level Meraki account (e.g., `703687441776644559`)
- **Network ID**: A specific network within an org (e.g., `L_642888846807149407`)
- Both are available in the Dashboard URL or via the `get_organizations` and `get_networks` tools

---

## Performance Notes

- **Channel Utilization**: Best queried for multiple APs at once; supports bulk operations
- **Signal Quality History**: Can return large datasets; Claude will automatically truncate for readability
- **Failed Connections**: Time range is critical—narrow windows (<24h) return faster results
- **Roaming Stats**: More meaningful with 24h+ timespan; hourly intervals provide good granularity
- **RF Profiles**: Lightweight query; safe to call frequently

---

## Troubleshooting

### "No data returned"
- Verify organization/network IDs are correct
- Check that time range (t0/t1) is in the past and not too narrow
- Ensure APs have active client traffic during the queried period

### "Invalid serial"
- Confirm AP serial is spelled correctly (case-sensitive)
- Use the `get_organization_devices` or `get_network_devices` tools to find correct serials

### "Unauthorized"
- Verify your Meraki API key is set in the `.env` file
- Check that your account has access to these networks/organizations

