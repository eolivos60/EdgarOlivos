# Official Meraki MCP - Integration Opportunities

## 5 Concrete Improvements to Adopt

### 1. **Rate Limit Handling with Exponential Backoff** ⭐ High Priority
**Official MCP Pattern:**
- Respects 10 req/sec per org limit
- Auto-retries with exponential backoff on `429 Too Many Requests`
- Per-org isolation (multi-org sessions don't share rate limit bucket)

**Your Current Gap:**
- Basic error handling in `_make_request()` but no 429 handling
- No retry logic for rate-limited requests
- Can cascade failures on large device queries

**Implementation:**
```python
# In _make_request(), add before response.raise_for_status():
async def _make_request_with_backoff(
    self, 
    method: str, 
    endpoint: str, 
    data: Optional[Dict] = None,
    max_retries: int = 5
) -> Dict:
    """Make HTTP request with exponential backoff on 429."""
    for attempt in range(max_retries):
        try:
            response = await self.client.request(method, url, json=data)
            if response.status_code == 429:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                self._log(f"Rate limited. Retrying in {wait_time:.1f}s (attempt {attempt+1}/{max_retries})")
                await asyncio.sleep(wait_time)
                continue
            response.raise_for_status()
            return response.json() if response.text else {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 429:
                raise
    raise Exception(f"Rate limited after {max_retries} retries")
```

**Impact:**
- Prevents cascading failures on org-wide queries
- Handles traffic spikes gracefully
- Aligns with official MCP reliability model

---

### 2. **Generic API Execution Tool (Fallback)** ⭐ High Priority
**Official MCP Pattern:**
- `execute_api` tool accepts capability_id + params
- Forward-compatible: works with future Meraki API additions
- Complements semantic_search for discovery

**Your Current Gap:**
- 18 hardcoded tools cover current needs
- New Meraki API features require code deployment
- No way for agents to call undocumented capabilities

**Implementation:**
```python
types.Tool(
    name="execute_custom_meraki_api",
    description="Execute a Meraki Dashboard API call for capabilities not in built-in tools. Use when you need to call an endpoint outside the 18 standard tools.",
    inputSchema={
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["GET", "PUT", "POST"],
                "description": "HTTP method"
            },
            "endpoint": {
                "type": "string",
                "description": "API endpoint (e.g., '/organizations/{id}/networks' or '/devices/{serial}/firmware')"
            },
            "params": {
                "type": "object",
                "description": "Query parameters or request body"
            },
            "org_id": {
                "type": "string",
                "description": "Organization ID for rate-limit isolation"
            }
        },
        "required": ["method", "endpoint", "org_id"]
    },
)
```

**Impact:**
- Future-proof: no redeployment needed for new Meraki APIs
- Reduces maintenance burden
- Agents can discover and use new capabilities

---

### 3. **Semantic Search for API Discovery** ⭐ Medium Priority
**Official MCP Pattern:**
- `semantic_search` accepts natural language query
- Returns ranked `capability_id` results
- Helps agents reason about which tool to use

**Your Current Gap:**
- Agent must guess which of 18 tools to call
- No discovery for undocumented or new capabilities
- Requires explicit prompting for obscure endpoints

**Implementation:**
```python
# Add a local capability registry + search
CAPABILITY_REGISTRY = {
    "get_networks": ["networks", "list networks", "organization networks"],
    "get_device_clients": ["clients", "connected devices", "wireless clients"],
    "get_device_uplink": ["uplink", "wan", "connectivity", "internet"],
    # ... 18 tools mapped to keywords
}

types.Tool(
    name="search_api_capabilities",
    description="Search Meraki API capabilities by natural language. Returns ranked tool recommendations.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language query (e.g., 'Find wireless clients', 'WAN uplink status')"
            },
            "org_id": {
                "type": "string",
                "description": "Organization ID (optional, for context)"
            }
        },
        "required": ["query"]
    },
)

async def handle_search_api_capabilities(query: str, org_id: Optional[str] = None):
    """Semantic search over your tool registry."""
    # Rank tools by keyword similarity
    # Return top 3 with descriptions + example usage
```

**Impact:**
- Improves tool discoverability for agents
- Reduces trial-and-error tool selection
- Makes debugging agent workflows easier

---

### 4. **Structured Error Responses** ⭐ Medium Priority
**Official MCP Pattern:**
- Consistent error format with error codes
- Includes diagnostic hints and retry recommendations
- Machine-parseable error context

**Your Current Gap:**
- Mixed error response formats
- Some errors return strings, others dicts
- Agents can't reliably parse error types

**Implementation:**
```python
# Define standard error types
class MerakiAPIError:
    def __init__(self, error_code: str, message: str, retry_after: Optional[int] = None, hint: str = ""):
        self.error_code = error_code
        self.message = message
        self.retry_after = retry_after
        self.hint = hint
    
    def to_dict(self):
        return {
            "error": self.error_code,
            "message": self.message,
            "retry_after_seconds": self.retry_after,
            "diagnostic_hint": self.hint
        }

# Use in responses:
# - "rate_limit_exceeded" → include retry_after from 429 header
# - "invalid_org_id" → suggest get_organizations
# - "session_expired" → suggest refreshing MERAKI_COOKIES
# - "device_not_found" → suggest get_organization_devices
```

**Impact:**
- Agents can handle errors programmatically
- Reduces manual debugging
- Improves resilience of agentic workflows

---

### 5. **Pagination Strategy from Official MCP** ⭐ Low Priority
**Official MCP Pattern:**
- Handles pagination transparently
- Supports large datasets without blocking
- Respects per_page limits and cursor tokens

**Your Current Gap:**
- You have pagination (`starting_after`, `ending_before`, `auto_paginate`)
- But inconsistent application across 18 tools
- Some tools hardcode limits

**Review:**
- `get_organization_devices` has `auto_paginate` and `max_records` ✅ Good pattern
- Ensure all list-returning tools follow same pattern
- Consider adding pagination helper:

```python
async def paginate_api(
    self,
    endpoint_template: str,  # e.g., "/organizations/{org_id}/devices"
    per_page: int = 1000,
    max_records: Optional[int] = None,
    **kwargs
) -> List[Dict]:
    """Generic pagination handler."""
    results = []
    starting_after = None
    while True:
        endpoint = endpoint_template.format(**kwargs)
        params = {"per_page": per_page}
        if starting_after:
            params["starting_after"] = starting_after
        
        data = await self._make_request("GET", f"{endpoint}?{urlencode(params)}")
        results.extend(data if isinstance(data, list) else [data])
        
        if len(results) >= (max_records or 999999):
            break
        if len(data) < per_page:  # Last page
            break
        
        starting_after = data[-1].get("id") if data else None
    
    return results[:max_records] if max_records else results
```

---

## Implementation Roadmap

| Improvement | Priority | Effort | Impact | Timeline |
|-------------|----------|--------|--------|----------|
| Rate limit backoff | High | 4h | Prevents cascading failures | Week 1 |
| Custom API exec tool | High | 2h | Future-proof tool surface | Week 1 |
| Semantic search | Medium | 6h | Better tool discovery | Week 2 |
| Structured errors | Medium | 3h | Better agent handling | Week 2 |
| Pagination refactor | Low | 2h | Code consistency | Week 3 |

---

## Testing Strategy

### Rate Limit Backoff
```python
# test_rate_limit.py
@pytest.mark.asyncio
async def test_429_retry_with_backoff():
    """Verify exponential backoff on 429 responses."""
    # Mock httpx to return 429 twice, then 200
    # Assert retry count and backoff timing
```

### Custom API Execution
```python
@pytest.mark.asyncio
async def test_execute_custom_api():
    """Test fallback execution of arbitrary endpoints."""
    result = await server.handle_execute_custom_meraki_api(
        method="GET",
        endpoint="/organizations/{org_id}/license/state",
        org_id=test_org_id
    )
    assert result["status"] in ["ok", "expired"]
```

### Semantic Search
```python
@pytest.mark.asyncio
async def test_semantic_search_ranking():
    """Verify tool rankings for various queries."""
    queries = [
        ("find wireless clients", "get_device_clients"),
        ("wan health", "get_device_uplink_status"),
        ("network health check", "diagnose_network_health"),
    ]
    for query, expected_top_tool in queries:
        results = await server.handle_search_api_capabilities(query)
        assert results[0]["tool_name"] == expected_top_tool
```

---

## NOT Adopting from Official MCP (Why)

### ❌ Replacing 18 Tools with 2 Generic Tools
Your curated tool surface is a **strength**, not a limitation:
- Agents reason better with 18 focused tools than 2 generic ones
- Keep this architectural choice
- Use semantic_search as *supplement*, not replacement

### ❌ Removing Write Capabilities
Official MCP is read-only (beta limitation). Your write support is competitive advantage:
- Device tagging, SSID changes, config updates
- Keep PUT/POST support in your custom_api tool (with read-only safeguards)
- Warn agents: "This endpoint allows config changes; request confirmation first"

### ❌ OAuth Instead of Bearer Token
Official MCP is moving toward OAuth eventually. For now:
- Keep bearer token (API key) auth
- Your cookie auth fallback is superior for compliance scenarios
- No need to change authentication model

---

## Success Metrics

After implementing these improvements:
1. ✅ **No cascading failures** on org-wide queries (rate limit backoff)
2. ✅ **Forward-compatibility**: New Meraki APIs usable via custom_api tool
3. ✅ **Faster agent reasoning**: Semantic search helps tool selection
4. ✅ **Better error recovery**: Structured errors enable automatic retry logic
5. ✅ **Consistency**: All pagination follows same pattern

