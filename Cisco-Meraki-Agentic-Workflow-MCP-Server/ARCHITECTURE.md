# Meraki MCP Server - Architecture Documentation

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         User Layer                          │
│  (Network Administrator, Support Engineer, Automation)      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                     AI Assistant Layer                      │
│     (Claude Desktop, Cline, GPT-4, Custom Assistants)       │
│                                                             │
│  • Natural language understanding                           │
│  • Intent recognition                                       │
│  • Multi-turn conversation                                  │
│  • Result synthesis                                         │
└──────────────────────┬──────────────────────────────────────┘
                       │ MCP Protocol
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   MCP Server Layer                          │
│              (Meraki MCP Server)                            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Tool Handler                           │   │
│  │  • 18 Specialized Tools                             │   │
│  │  • Input validation                                 │   │
│  │  • Error handling                                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                       │                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           Agentic Workflow Engine                   │   │
│  │  • Multi-step orchestration                         │   │
│  │  • Context management                               │   │
│  │  • Intelligent decision making                      │   │
│  │  • Progressive diagnosis                            │   │
│  └─────────────────────────────────────────────────────┘   │
│                       │                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              API Client Layer                       │   │
│  │  • HTTP client (httpx)                              │   │
│  │  • Rate limiting                                    │   │
│  │  • Retry logic                                      │   │
│  │  • Response parsing                                 │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS REST API
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Cisco Meraki Cloud                         │
│              Dashboard API v1                               │
│                                                             │
│  • Organization management                                  │
│  • Network configuration                                    │
│  • Device control                                           │
│  • Monitoring & analytics                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                Physical Infrastructure                      │
│  (Meraki MX, MR, MS, MG devices)                            │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. MCP Protocol Layer

**Protocol**: Model Context Protocol (MCP)
**Transport**: stdio (standard input/output)
**Format**: JSON-RPC 2.0

**Key Messages**:
- `initialize` - Server capabilities negotiation
- `tools/list` - Enumerate available tools
- `tools/call` - Execute tool with parameters
- `notifications` - Async status updates

### 2. Tool Architecture

Tools are the primary interface between AI assistants and Meraki APIs.

```python
Tool Structure:
{
  "name": "get_network_devices",
  "description": "User-facing description",
  "inputSchema": {
    "type": "object",
    "properties": {...},
    "required": [...]
  }
}
```

**Tool Categories**:

1. **Discovery Tools** (3 tools)
   - Organization discovery
   - Network enumeration
   - Device inventory

2. **Monitoring Tools** (5 tools)
   - Device status
   - Uplink health
   - Client tracking
   - Alert management
   - Organization-wide status

3. **Client Tools** (2 tools)
   - Client listing
   - Client details

4. **Configuration Tools** (5 tools)
   - Device configuration
   - Network settings
   - Wireless SSID management

5. **Agentic Workflow Tools** (2 tools)
   - Intelligent diagnosis
   - Automated health checks

### 3. Agentic Workflow Engine

The workflow engine enables multi-step, intelligent operations.

**Core Capabilities**:

```python
class WorkflowEngine:
    def __init__(self):
        self.context = {}  # Maintains state
        self.findings = []  # Accumulates discoveries
        self.recommendations = []  # Builds action items
    
    async def execute_step(self, step_name, params):
        """Execute single workflow step"""
        result = await self.api_call(step_name, params)
        self.context[step_name] = result
        return result
    
    async def analyze_results(self):
        """Correlate findings across steps"""
        # Pattern matching
        # Severity classification
        # Root cause analysis
        pass
    
    async def generate_recommendations(self):
        """Create actionable recommendations"""
        # Based on findings
        # Prioritized by impact
        # With implementation steps
        pass
```

**Workflow State Machine**:

```
[Start] → [Discovery] → [Analysis] → [Diagnosis] → [Recommendations] → [End]
            ↓              ↓             ↓
         [Context]    [Findings]   [Actions]
```

### 4. Data Flow

#### Tool Call Flow

```
1. AI Assistant (User request) →
2. MCP Protocol (tools/call message) →
3. Tool Handler (validate input) →
4. Workflow Engine (orchestrate if needed) →
5. API Client (HTTP request) →
6. Meraki Dashboard API →
7. Response Processing →
8. Result Formatting →
9. MCP Protocol (return result) →
10. AI Assistant (synthesize response) →
11. User (natural language response)
```

#### Agentic Workflow Flow

```
1. User: "My WiFi is slow"
   ↓
2. AI Assistant: Interpret intent → Connectivity Issue
   ↓
3. MCP Call: diagnose_connectivity_issue
   ↓
4. Workflow Engine Orchestrates:
   Step 1: Get org uplinks → [3 inactive]
   Step 2: Get network alerts → [High channel util]
   Step 3: Get device status → [2 offline APs]
   Step 4: Analyze findings → [Capacity + Hardware issues]
   Step 5: Generate recommendations → [Prioritized actions]
   ↓
5. Return comprehensive report
   ↓
6. AI Assistant: Format for user
   ↓
7. User: Sees actionable diagnosis
```

## Key Design Patterns

### 1. Progressive Disclosure

Start broad, then narrow based on findings:

```python
async def diagnose():
    # Level 1: Organization-wide scan
    uplinks = await get_all_uplinks()
    if issues_found(uplinks):
        # Level 2: Network-specific analysis
        alerts = await get_network_alerts()
        if issues_found(alerts):
            # Level 3: Device-specific inspection
            status = await get_device_status()
```

### 2. Context Accumulation

Build knowledge graph during execution:

```python
workflow_context = {
    "organization": {...},
    "networks": [...],
    "devices": [...],
    "issues": [
        {
            "severity": "high",
            "type": "connectivity",
            "devices": [...],
            "impact": "50 clients affected"
        }
    ]
}
```

### 3. Smart Recommendations

Generate prioritized, actionable advice:

```python
def generate_recommendations(findings):
    recommendations = []
    
    # Severity-based prioritization
    for finding in sorted(findings, key=lambda x: x['severity']):
        recommendations.append({
            "priority": severity_to_priority(finding['severity']),
            "action": determine_action(finding),
            "steps": implementation_steps(finding),
            "estimated_time": time_estimate(finding)
        })
    
    return recommendations
```

## Security Architecture

### API Key Management

```
Environment Variable → Server Process Memory
                    ↓
              Request Headers
                    ↓
         HTTPS (TLS 1.3) → Meraki Cloud
```

**Never**:
- Log API keys
- Store in version control
- Transmit unencrypted

### Principle of Least Privilege

API keys should have minimum required permissions:
- Read-only for monitoring tools
- Write access only when configuration needed
- Organization-scoped, not account-wide

### Rate Limiting

```python
class RateLimiter:
    def __init__(self):
        self.max_per_second = 10  # Meraki limit
        self.requests = []
    
    async def wait_if_needed(self):
        now = time.time()
        # Remove requests older than 1 second
        self.requests = [r for r in self.requests if r > now - 1]
        
        if len(self.requests) >= self.max_per_second:
            await asyncio.sleep(1)
        
        self.requests.append(now)
```

## Performance Optimization

### 1. Parallel Requests

Where possible, execute independent API calls in parallel:

```python
async def health_check(org_id):
    # Execute in parallel
    networks, uplinks, devices = await asyncio.gather(
        get_networks(org_id),
        get_uplinks(org_id),
        get_devices(org_id)
    )
```

### 2. Caching Strategy

Cache stable data with TTL:

```python
cache = {
    "organizations": (data, expiry),  # 1 hour
    "networks": (data, expiry),       # 5 minutes
    "devices": (data, expiry),        # 1 minute
}
```

### 3. Lazy Loading

Only fetch data when needed:

```python
async def diagnose(org_id, network_id=None):
    # Always needed
    uplinks = await get_uplinks(org_id)
    
    # Only if network specified
    if network_id:
        alerts = await get_alerts(network_id)
    
    # Only if issues found
    if has_issues(uplinks):
        devices = await get_devices(network_id)
```

## Error Handling Strategy

### Graceful Degradation

```python
async def multi_step_workflow():
    results = {}
    
    try:
        results['step1'] = await step1()
    except Exception as e:
        log_error(e)
        results['step1'] = {"error": str(e)}
    
    # Continue with available data
    if 'step1' in results and not results['step1'].get('error'):
        try:
            results['step2'] = await step2(results['step1'])
        except Exception as e:
            log_error(e)
    
    # Return partial results
    return results
```

### User-Friendly Error Messages

```python
def format_error(error):
    if "401" in str(error):
        return "Authentication failed. Please check your API key."
    elif "404" in str(error):
        return "Resource not found. Please verify the ID."
    elif "429" in str(error):
        return "Rate limit exceeded. Please wait and try again."
    else:
        return f"An error occurred: {error}"
```

## Scalability Considerations

### Multi-Organization Support

```python
async def cross_org_health_check(org_ids):
    """Check health across multiple organizations"""
    
    # Parallel execution per org
    results = await asyncio.gather(*[
        health_check(org_id) for org_id in org_ids
    ])
    
    # Aggregate results
    return aggregate_health_reports(results)
```

### Batch Operations

```python
async def bulk_device_update(updates):
    """Update multiple devices efficiently"""
    
    # Group by network to optimize API calls
    by_network = group_by_network(updates)
    
    # Execute in controlled batches
    for network_id, device_updates in by_network.items():
        # Respect rate limits
        await rate_limiter.wait_if_needed()
        
        # Parallel updates within rate limit
        await asyncio.gather(*[
            update_device(serial, config) 
            for serial, config in device_updates
        ])
```

## Extensibility

### Adding New Tools

```python
# 1. Define tool schema
new_tool = types.Tool(
    name="custom_diagnostic",
    description="Custom diagnostic workflow",
    inputSchema={...}
)

# 2. Implement handler
async def _handle_custom_diagnostic(self, args):
    # Implementation
    pass

# 3. Register in router
if name == "custom_diagnostic":
    result = await self._handle_custom_diagnostic(arguments)
```

### Custom Workflows

```python
class CustomWorkflow:
    """Extend with custom workflow logic"""
    
    async def execute(self, context):
        # Custom multi-step logic
        step1 = await self.custom_step_1(context)
        step2 = await self.custom_step_2(step1)
        return self.synthesize_results(step1, step2)
```

## Monitoring & Observability

### Logging Strategy

```python
import logging

logger = logging.getLogger("meraki_mcp")

# Log levels:
# DEBUG: API calls, data flows
# INFO: Workflow steps, user actions
# WARNING: Rate limits, retries
# ERROR: API failures, exceptions
# CRITICAL: System failures
```

### Metrics to Track

- API call latency
- Error rates by endpoint
- Workflow completion rates
- Tool usage frequency
- User satisfaction indicators

### Health Checks

```python
async def server_health():
    """Check MCP server health"""
    checks = {
        "api_connectivity": await check_meraki_api(),
        "rate_limit_status": get_rate_limit_status(),
        "memory_usage": get_memory_usage(),
        "active_workflows": count_active_workflows()
    }
    return checks
```

## Deployment Patterns

### Development

```bash
# Local development with hot reload
python server.py

# With debug logging
export LOG_LEVEL=DEBUG
python server.py
```

### Production

```bash
# Systemd service
[Unit]
Description=Meraki MCP Server
After=network.target

[Service]
Type=simple
User=mcpserver
WorkingDirectory=/opt/meraki-mcp-server
Environment="MERAKI_API_KEY=xxx"
ExecStart=/usr/bin/python3 server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Container Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -e .

ENV MERAKI_API_KEY=""
CMD ["python", "server.py"]
```

## Testing Strategy

### Unit Tests

Test individual tools and methods:

```python
@pytest.mark.asyncio
async def test_get_organizations():
    server = MerakiMCPServer()
    result = await server._get_organizations()
    assert isinstance(result, list)
```

### Integration Tests

Test workflow orchestration:

```python
@pytest.mark.asyncio
async def test_diagnosis_workflow():
    server = MerakiMCPServer()
    result = await server._diagnose_connectivity_issue({
        "organization_id": "test_org",
        "issue_description": "test"
    })
    assert "findings" in result
    assert "recommendations" in result
```

### End-to-End Tests

Test full MCP protocol interaction:

```python
async def test_mcp_protocol():
    # Simulate MCP client
    async with stdio_server() as (read, write):
        # Send initialize
        # Send tools/list
        # Send tools/call
        # Verify responses
        pass
```

## Conclusion

This architecture provides:

✅ **Modularity**: Clear separation of concerns
✅ **Scalability**: Parallel execution, batch operations
✅ **Reliability**: Error handling, graceful degradation
✅ **Extensibility**: Easy to add new tools and workflows
✅ **Security**: API key management, rate limiting
✅ **Intelligence**: Agentic workflows with context

The Meraki MCP Server transforms raw API access into an intelligent assistant that understands user needs and orchestrates complex multi-step operations automatically.
