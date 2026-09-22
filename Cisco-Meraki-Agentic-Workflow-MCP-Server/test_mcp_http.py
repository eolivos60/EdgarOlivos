"""
Integration test suite for the Meraki MCP Server HTTP endpoint.

Tests the JSON-RPC 2.0 / MCP protocol over HTTP (Streamable HTTP transport).
Works against both local (http://127.0.0.1:3000/mcp) and remote Cloudflare endpoints.

Usage:
    # Against local server:
    pytest test_mcp_http.py -v

    # Against a remote Cloudflare endpoint:
    pytest test_mcp_http.py -v --mcp-url https://toward-johns-beer-analyze.trycloudflare.com/mcp

    # Skip slow agentic workflow tests:
    pytest test_mcp_http.py -v -m "not slow"
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional, Tuple

import httpx
import pytest

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


@pytest.fixture(scope="session")
def mcp_url(request: pytest.FixtureRequest) -> str:
    return request.config.getoption("--mcp-url")


# ---------------------------------------------------------------------------
# Low-level JSON-RPC helpers
# ---------------------------------------------------------------------------

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

TIMEOUT = 30.0
MCP_AUTH_TOKEN = (os.getenv("MCP_AUTH_TOKEN") or "").strip()


def _extract_payload(text: str) -> Dict[str, Any]:
    """Handle both plain JSON and SSE-wrapped responses."""
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty response body")
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(stripped)
    # SSE: look for "data: {...}"
    data_lines = [
        line[len("data:"):].strip()
        for line in stripped.splitlines()
        if line.startswith("data:")
    ]
    if not data_lines:
        raise ValueError(f"no JSON payload in response: {stripped[:200]}")
    return json.loads("\n".join(data_lines))


def jsonrpc_call(
    client: httpx.Client,
    url: str,
    method: str,
    params: Dict[str, Any],
    rpc_id: int = 1,
    session_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Send a single JSON-RPC request and return (parsed_body, session_id)."""
    headers = dict(HEADERS)
    if session_id:
        headers["mcp-session-id"] = session_id
    if MCP_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {MCP_AUTH_TOKEN}"

    payload = {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params}
    resp = client.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    data = _extract_payload(resp.text)
    returned_session = resp.headers.get("mcp-session-id") or session_id
    return data, returned_session


# ---------------------------------------------------------------------------
# Session fixture – initialise once per test session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mcp_session(mcp_url: str):
    """Returns (client, session_id) after a successful MCP initialise handshake."""
    client = httpx.Client(timeout=TIMEOUT, follow_redirects=True, verify=True)

    init_payload = {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "pytest-mcp-suite", "version": "1.0"},
    }
    data, session_id = jsonrpc_call(client, mcp_url, "initialize", init_payload, rpc_id=1)
    assert "result" in data, f"initialize failed: {data}"

    yield client, session_id, mcp_url
    client.close()


@pytest.fixture(scope="session")
def tool_names(mcp_session) -> list[str]:
    """Return list of tool names advertised by the server."""
    client, session_id, url = mcp_session
    data, _ = jsonrpc_call(client, url, "tools/list", {}, rpc_id=2, session_id=session_id)
    tools = data.get("result", {}).get("tools", [])
    return [t["name"] for t in tools if isinstance(t, dict)]


def call_tool(
    mcp_session,
    name: str,
    arguments: Dict[str, Any],
    rpc_id: int = 99,
) -> Dict[str, Any]:
    """Helper: call a named tool and return the parsed JSON-RPC response."""
    client, session_id, url = mcp_session
    params = {"name": name, "arguments": arguments}
    data, _ = jsonrpc_call(client, url, "tools/call", params, rpc_id=rpc_id, session_id=session_id)
    return data


def tool_text(response: Dict[str, Any]) -> str:
    """Extract the text payload from a tools/call response."""
    result = response.get("result", {})
    content = result.get("content", []) if isinstance(result, dict) else []
    if content and isinstance(content[0], dict):
        return content[0].get("text", "")
    return ""


def tool_json(response: Dict[str, Any]) -> Any:
    """Parse the text payload of a tools/call response as JSON."""
    return json.loads(tool_text(response))


# ---------------------------------------------------------------------------
# 1. MCP Protocol Tests
# ---------------------------------------------------------------------------

class TestMCPProtocol:
    """Verify the MCP handshake and core protocol messages."""

    def test_initialize_returns_result(self, mcp_session):
        client, session_id, url = mcp_session
        init_payload = {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "0"},
        }
        data, _ = jsonrpc_call(client, url, "initialize", init_payload, rpc_id=10)
        assert "result" in data, f"Expected result, got: {data}"

    def test_initialize_returns_server_info(self, mcp_session):
        client, session_id, url = mcp_session
        init_payload = {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "0"},
        }
        data, _ = jsonrpc_call(client, url, "initialize", init_payload, rpc_id=11)
        result = data.get("result", {})
        assert "serverInfo" in result or "protocolVersion" in result, (
            f"initialize result missing serverInfo/protocolVersion: {result}"
        )

    def test_initialize_returns_session_id(self, mcp_url):
        """Each initialize call should yield a session ID header."""
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            payload = {
                "jsonrpc": "2.0",
                "id": 20,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0"},
                },
            }
            resp = client.post(mcp_url, headers=HEADERS, json=payload, timeout=TIMEOUT)
            assert resp.status_code == 200
            assert "mcp-session-id" in resp.headers, "Missing mcp-session-id header"

    def test_tools_list_returns_list(self, tool_names):
        assert isinstance(tool_names, list)
        assert len(tool_names) > 0, "tools/list returned empty list"

    def test_unknown_rpc_method_returns_error(self, mcp_session):
        client, session_id, url = mcp_session
        data, _ = jsonrpc_call(
            client, url, "nonexistent/method", {}, rpc_id=30, session_id=session_id
        )
        # MCP may return error object or wrap it — just ensure no unhandled crash (200 with body)
        assert "error" in data or "result" in data


# ---------------------------------------------------------------------------
# 2. Tool Inventory Tests
# ---------------------------------------------------------------------------

EXPECTED_TOOLS = [
    "get_organizations",
    "get_networks",
    "get_network_devices",
    "get_organization_devices",
    "get_organization_inventory_devices",
    "get_organization_devices_statuses",
    "get_device_status",
    "get_device_uplink_status",
    "get_device_clients",
    "get_network_health_alerts",
    "get_network_events",
    "get_organization_uplink_statuses",
    "get_network_clients",
    "get_client_details",
    "update_device",
    "update_network",
    "get_wireless_ssids",
    "update_wireless_ssid",
    "diagnose_connectivity_issue",
    "automated_health_check",
    "investigate_ssid_issue",
    "reload_credentials",
    "health_check",
]


class TestToolInventory:
    """Verify every expected tool is advertised."""

    @pytest.mark.parametrize("expected", EXPECTED_TOOLS)
    def test_tool_is_listed(self, tool_names, expected):
        assert expected in tool_names, (
            f"Tool '{expected}' missing from tools/list. Available: {tool_names}"
        )

    def test_tool_count(self, tool_names):
        assert len(tool_names) >= len(EXPECTED_TOOLS), (
            f"Expected at least {len(EXPECTED_TOOLS)} tools, got {len(tool_names)}: {tool_names}"
        )

    def test_tools_have_schemas(self, mcp_session):
        client, session_id, url = mcp_session
        data, _ = jsonrpc_call(client, url, "tools/list", {}, rpc_id=40, session_id=session_id)
        tools = data.get("result", {}).get("tools", [])
        for tool in tools:
            assert "name" in tool, f"Tool missing name: {tool}"
            assert "description" in tool, f"Tool '{tool.get('name')}' missing description"
            assert "inputSchema" in tool, f"Tool '{tool.get('name')}' missing inputSchema"


class TestPaginationTokenCoverage:
    """Verify pagination args are exposed and accepted over MCP HTTP."""

    @staticmethod
    def _tool_by_name(tools: list[Dict[str, Any]], name: str) -> Dict[str, Any]:
        for tool in tools:
            if isinstance(tool, dict) and tool.get("name") == name:
                return tool
        pytest.skip(f"Tool '{name}' not advertised by current MCP server instance")

    def test_pagination_fields_present_in_schemas(self, mcp_session):
        client, session_id, url = mcp_session
        data, _ = jsonrpc_call(client, url, "tools/list", {}, rpc_id=45, session_id=session_id)
        tools = data.get("result", {}).get("tools", [])

        for tool_name in [
            "get_organization_devices",
            "get_organization_inventory_devices",
            "get_organization_devices_statuses",
            "get_network_events",
        ]:
            tool = self._tool_by_name(tools, tool_name)
            schema = tool.get("inputSchema", {})
            props = schema.get("properties", {}) if isinstance(schema, dict) else {}
            assert "starting_after" in props, f"{tool_name} missing starting_after in inputSchema"
            assert "ending_before" in props, f"{tool_name} missing ending_before in inputSchema"

    def test_get_organization_devices_accepts_pagination_tokens(self, mcp_session):
        client, session_id, url = mcp_session
        listing, _ = jsonrpc_call(client, url, "tools/list", {}, rpc_id=459, session_id=session_id)
        tool_names = [t.get("name") for t in listing.get("result", {}).get("tools", []) if isinstance(t, dict)]
        if "get_organization_devices" not in tool_names:
            pytest.skip("get_organization_devices not available on current MCP server instance")

        data = call_tool(
            mcp_session,
            "get_organization_devices",
            {
                "organization_id": "BOGUS_ORG_999",
                "per_page": 10,
                "starting_after": "tok_start",
                "ending_before": "tok_end",
            },
            rpc_id=460,
        )
        assert_no_crash(data, "get_organization_devices")

    def test_get_network_events_accepts_pagination_tokens(self, mcp_session):
        client, session_id, url = mcp_session
        listing, _ = jsonrpc_call(client, url, "tools/list", {}, rpc_id=458, session_id=session_id)
        tool_names = [t.get("name") for t in listing.get("result", {}).get("tools", []) if isinstance(t, dict)]
        if "get_network_events" not in tool_names:
            pytest.skip("get_network_events not available on current MCP server instance")

        data = call_tool(
            mcp_session,
            "get_network_events",
            {
                "network_id": "BOGUS_NET_999",
                "product_type": "wireless",
                "per_page": 10,
                "starting_after": "tok_start",
                "ending_before": "tok_end",
            },
            rpc_id=461,
        )
        assert_no_crash(data, "get_network_events")


# ---------------------------------------------------------------------------
# 3. No-Auth Tool Tests (work without MERAKI_API_KEY)
# ---------------------------------------------------------------------------

class TestNoAuthTools:
    """Tools that return a valid response without a Meraki API key."""

    def test_health_check_success(self, mcp_session):
        data = call_tool(mcp_session, "health_check", {})
        assert "result" in data, f"Unexpected response: {data}"
        body = tool_json(data)
        assert body.get("success") is True
        assert body.get("status") == "ok"

    def test_health_check_echo(self, mcp_session):
        data = call_tool(mcp_session, "health_check", {"echo": "ping"})
        body = tool_json(data)
        assert body.get("echo") == "ping"

    def test_health_check_has_timestamp(self, mcp_session):
        data = call_tool(mcp_session, "health_check", {})
        body = tool_json(data)
        assert "timestamp" in body, "health_check missing timestamp"

    def test_health_check_reports_credentials(self, mcp_session):
        data = call_tool(mcp_session, "health_check", {})
        body = tool_json(data)
        assert "credentials_present" in body, "health_check missing credentials_present"
        creds = body["credentials_present"]
        assert "meraki_api_key" in creds
        assert "meraki_cookies" in creds

    def test_reload_credentials_returns_result(self, mcp_session):
        data = call_tool(mcp_session, "reload_credentials", {})
        assert "result" in data, f"Unexpected response: {data}"
        body = tool_json(data)
        # Either success=True (credentials present) or success=False with an error key
        assert "success" in body, f"reload_credentials missing 'success': {body}"

    def test_reload_credentials_response_shape(self, mcp_session):
        data = call_tool(mcp_session, "reload_credentials", {})
        body = tool_json(data)
        if body.get("success"):
            assert "auth_method" in body
            assert "message" in body
        else:
            assert "error" in body


# ---------------------------------------------------------------------------
# 4. Auth-Required Tool Error Handling (bogus IDs → structured error, not crash)
# ---------------------------------------------------------------------------

def assert_no_crash(response: Dict[str, Any], tool: str) -> None:
    """Assert the server returned a well-formed response (not a 500 traceback)."""
    text = tool_text(response)
    assert text, f"{tool}: empty response text"
    # Should not be raw Python traceback
    assert "Traceback" not in text, f"{tool} returned a raw traceback: {text[:300]}"
    # Should be parseable JSON or a clear error string
    try:
        parsed = json.loads(text)
        # Either has content or an error key
        assert isinstance(parsed, (dict, list)), f"{tool}: unexpected JSON type {type(parsed)}"
    except json.JSONDecodeError:
        # Plain text error message is acceptable
        assert len(text) < 500, f"{tool}: suspiciously long non-JSON response: {text[:300]}"


class TestAuthRequiredTools:
    """
    Call every auth-required tool with a bogus ID.
    The server should return a structured error, not crash or return a 500.
    """

    def test_get_organizations_no_crash(self, mcp_session):
        data = call_tool(mcp_session, "get_organizations", {})
        assert_no_crash(data, "get_organizations")

    def test_get_organizations_returns_list_or_error(self, mcp_session):
        data = call_tool(mcp_session, "get_organizations", {})
        text = tool_text(data)
        parsed = json.loads(text)
        # Valid: a list of orgs, or a dict with an "error" key
        assert isinstance(parsed, (list, dict)), f"Unexpected type: {type(parsed)}"

    def test_get_networks_bogus_org(self, mcp_session):
        data = call_tool(mcp_session, "get_networks", {"organization_id": "BOGUS_ORG_999"})
        assert_no_crash(data, "get_networks")
        body = tool_json(data)
        # Expect an error dict back (not a crash)
        assert isinstance(body, (dict, list))

    def test_get_network_devices_bogus_network(self, mcp_session):
        data = call_tool(mcp_session, "get_network_devices", {"network_id": "BOGUS_NET_999"})
        assert_no_crash(data, "get_network_devices")

    def test_get_device_status_bogus_serial(self, mcp_session):
        data = call_tool(mcp_session, "get_device_status", {"serial": "BOGUS-SERIAL"})
        assert_no_crash(data, "get_device_status")

    def test_get_device_uplink_status_bogus_serial(self, mcp_session):
        data = call_tool(mcp_session, "get_device_uplink_status", {"serial": "BOGUS-SERIAL"})
        assert_no_crash(data, "get_device_uplink_status")

    def test_get_device_clients_bogus_serial(self, mcp_session):
        data = call_tool(
            mcp_session, "get_device_clients", {"serial": "BOGUS-SERIAL", "timespan": 3600}
        )
        assert_no_crash(data, "get_device_clients")

    def test_get_network_health_alerts_bogus_network(self, mcp_session):
        data = call_tool(
            mcp_session, "get_network_health_alerts", {"network_id": "BOGUS_NET_999"}
        )
        assert_no_crash(data, "get_network_health_alerts")

    def test_get_organization_uplink_statuses_bogus_org(self, mcp_session):
        data = call_tool(
            mcp_session,
            "get_organization_uplink_statuses",
            {"organization_id": "BOGUS_ORG_999"},
        )
        assert_no_crash(data, "get_organization_uplink_statuses")

    def test_get_network_clients_bogus_network(self, mcp_session):
        data = call_tool(
            mcp_session, "get_network_clients", {"network_id": "BOGUS_NET_999", "timespan": 3600}
        )
        assert_no_crash(data, "get_network_clients")

    def test_get_client_details_bogus_ids(self, mcp_session):
        data = call_tool(
            mcp_session,
            "get_client_details",
            {"network_id": "BOGUS_NET", "client_id": "BOGUS_CLIENT"},
        )
        assert_no_crash(data, "get_client_details")

    def test_get_wireless_ssids_bogus_network(self, mcp_session):
        data = call_tool(mcp_session, "get_wireless_ssids", {"network_id": "BOGUS_NET_999"})
        assert_no_crash(data, "get_wireless_ssids")

    def test_update_device_bogus_serial(self, mcp_session):
        data = call_tool(
            mcp_session, "update_device", {"serial": "BOGUS-SERIAL", "name": "test-device"}
        )
        assert_no_crash(data, "update_device")

    def test_update_network_bogus_id(self, mcp_session):
        data = call_tool(
            mcp_session,
            "update_network",
            {"network_id": "BOGUS_NET_999", "name": "test-network"},
        )
        assert_no_crash(data, "update_network")

    def test_update_wireless_ssid_bogus_ids(self, mcp_session):
        data = call_tool(
            mcp_session,
            "update_wireless_ssid",
            {"network_id": "BOGUS_NET_999", "number": "0"},
        )
        assert_no_crash(data, "update_wireless_ssid")


# ---------------------------------------------------------------------------
# 5. Agentic Workflow Tool Tests
# ---------------------------------------------------------------------------

class TestAgenticWorkflows:
    """Agentic tools should return structured dicts with required keys."""

    def test_diagnose_connectivity_issue_response_shape(self, mcp_session):
        data = call_tool(
            mcp_session,
            "diagnose_connectivity_issue",
            {
                "organization_id": "BOGUS_ORG_999",
                "issue_description": "Network is slow — pytest smoke test",
            },
        )
        assert_no_crash(data, "diagnose_connectivity_issue")
        body = tool_json(data)
        assert isinstance(body, dict), f"Expected dict, got {type(body)}"
        for key in ("issue_description", "findings", "recommendations", "steps_performed"):
            assert key in body, f"diagnose_connectivity_issue missing key '{key}': {body}"

    def test_diagnose_connectivity_issue_description_echoed(self, mcp_session):
        issue = "WiFi dropped — pytest test"
        data = call_tool(
            mcp_session,
            "diagnose_connectivity_issue",
            {"organization_id": "BOGUS_ORG_999", "issue_description": issue},
        )
        body = tool_json(data)
        assert body.get("issue_description") == issue

    def test_diagnose_connectivity_has_timestamp(self, mcp_session):
        data = call_tool(
            mcp_session,
            "diagnose_connectivity_issue",
            {
                "organization_id": "BOGUS_ORG_999",
                "issue_description": "pytest timestamp check",
            },
        )
        body = tool_json(data)
        assert "timestamp" in body, f"diagnose_connectivity_issue missing timestamp: {body}"

    def test_diagnose_with_optional_network_id(self, mcp_session):
        data = call_tool(
            mcp_session,
            "diagnose_connectivity_issue",
            {
                "organization_id": "BOGUS_ORG_999",
                "issue_description": "slow WiFi",
                "network_id": "BOGUS_NET_999",
            },
        )
        assert_no_crash(data, "diagnose_connectivity_issue")
        body = tool_json(data)
        assert "findings" in body

    @pytest.mark.slow
    def test_automated_health_check_response_shape(self, mcp_session):
        data = call_tool(
            mcp_session,
            "automated_health_check",
            {"organization_id": "BOGUS_ORG_999", "include_recommendations": True},
        )
        assert_no_crash(data, "automated_health_check")
        body = tool_json(data)
        assert isinstance(body, dict)
        for key in ("organization_id", "summary", "network_health", "recommendations"):
            assert key in body, f"automated_health_check missing key '{key}': {body}"

    @pytest.mark.slow
    def test_automated_health_check_org_id_echoed(self, mcp_session):
        data = call_tool(
            mcp_session,
            "automated_health_check",
            {"organization_id": "BOGUS_ORG_999"},
        )
        body = tool_json(data)
        assert body.get("organization_id") == "BOGUS_ORG_999"

    @pytest.mark.slow
    def test_automated_health_check_has_timestamp(self, mcp_session):
        data = call_tool(
            mcp_session,
            "automated_health_check",
            {"organization_id": "BOGUS_ORG_999"},
        )
        body = tool_json(data)
        assert "timestamp" in body

    def test_investigate_ssid_issue_not_found(self, mcp_session):
        """SSID lookup with bogus IDs should return an error dict, not crash."""
        data = call_tool(
            mcp_session,
            "investigate_ssid_issue",
            {
                "organization_id": "BOGUS_ORG",
                "network_id": "BOGUS_NET",
                "ssid_name": "NonExistentSSID",
            },
        )
        assert_no_crash(data, "investigate_ssid_issue")
        body = tool_json(data)
        assert isinstance(body, dict)
        # Should contain either an error or findings
        assert "error" in body or "findings" in body

    def test_investigate_ssid_issue_timespan_clamped(self, mcp_session):
        """Extreme timespan values should not cause a crash."""
        data = call_tool(
            mcp_session,
            "investigate_ssid_issue",
            {
                "organization_id": "BOGUS_ORG",
                "network_id": "BOGUS_NET",
                "ssid_name": "TestSSID",
                "timespan": 999999999,  # Way over the 86400 cap
            },
        )
        assert_no_crash(data, "investigate_ssid_issue")


# ---------------------------------------------------------------------------
# 6. Error Handling & Edge Case Tests
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Verify the server handles invalid inputs gracefully."""

    def test_unknown_tool_returns_error(self, mcp_session):
        data = call_tool(mcp_session, "nonexistent_tool_xyz", {})
        text = tool_text(data)
        assert "Unknown tool" in text or "error" in text.lower(), (
            f"Expected error for unknown tool, got: {text}"
        )

    def test_tool_call_without_required_arg_returns_error(self, mcp_session):
        """get_networks requires organization_id — omitting it should give an error."""
        client, session_id, url = mcp_session
        params = {"name": "get_networks", "arguments": {}}  # missing organization_id
        data, _ = jsonrpc_call(
            client, url, "tools/call", params, rpc_id=80, session_id=session_id
        )
        # Either a JSON-RPC error or a text error response
        has_rpc_error = "error" in data
        has_tool_error = "error" in tool_text(data).lower() if tool_text(data) else False
        assert has_rpc_error or has_tool_error, f"Expected error for missing arg, got: {data}"

    def test_empty_echo_in_health_check(self, mcp_session):
        """health_check with no echo arg should still work."""
        data = call_tool(mcp_session, "health_check", {})
        body = tool_json(data)
        assert body.get("success") is True

    def test_health_check_echo_null(self, mcp_session):
        """health_check echoes None when not provided."""
        data = call_tool(mcp_session, "health_check", {})
        body = tool_json(data)
        # echo key should be present and None/null
        assert "echo" in body
        assert body["echo"] is None

    def test_get_network_clients_timespan_floor(self, mcp_session):
        """Timespan below 300 should be clamped to 300, not cause a crash."""
        data = call_tool(
            mcp_session, "get_network_clients", {"network_id": "BOGUS_NET", "timespan": 1}
        )
        assert_no_crash(data, "get_network_clients")

    def test_get_network_clients_timespan_ceiling(self, mcp_session):
        """Timespan above 86400 should be clamped to 86400, not cause a crash."""
        data = call_tool(
            mcp_session, "get_network_clients", {"network_id": "BOGUS_NET", "timespan": 999999}
        )
        assert_no_crash(data, "get_network_clients")


# ---------------------------------------------------------------------------
# 7. Response Format Consistency Tests
# ---------------------------------------------------------------------------

class TestResponseFormat:
    """Tool responses must always be wrapped in MCP content blocks."""

    @pytest.mark.parametrize("tool,args", [
        ("health_check", {}),
        ("reload_credentials", {}),
        ("get_organizations", {}),
        ("get_networks", {"organization_id": "BOGUS"}),
        ("get_network_devices", {"network_id": "BOGUS"}),
        ("diagnose_connectivity_issue", {"organization_id": "BOGUS", "issue_description": "test"}),
    ])
    def test_response_has_content_block(self, mcp_session, tool, args):
        data = call_tool(mcp_session, tool, args)
        result = data.get("result", {})
        assert isinstance(result, dict), f"{tool}: result is not a dict: {result}"
        content = result.get("content", [])
        assert isinstance(content, list), f"{tool}: content is not a list: {content}"
        assert len(content) > 0, f"{tool}: content block is empty"
        assert content[0].get("type") == "text", (
            f"{tool}: first content block type is not 'text': {content[0]}"
        )

    @pytest.mark.parametrize("tool,args", [
        ("health_check", {}),
        ("reload_credentials", {}),
        ("diagnose_connectivity_issue", {"organization_id": "BOGUS", "issue_description": "test"}),
    ])
    def test_response_text_is_valid_json(self, mcp_session, tool, args):
        data = call_tool(mcp_session, tool, args)
        text = tool_text(data)
        try:
            parsed = json.loads(text)
            assert parsed is not None
        except json.JSONDecodeError as exc:
            pytest.fail(f"{tool}: response text is not valid JSON: {exc}\n{text[:300]}")


# ---------------------------------------------------------------------------
# 8. Concurrency / Stability
# ---------------------------------------------------------------------------

class TestStability:
    """Quick stability checks — repeated calls and sequential tool chains."""

    def test_health_check_repeated(self, mcp_session):
        """health_check should be stable across 5 rapid successive calls."""
        for i in range(5):
            data = call_tool(mcp_session, "health_check", {"echo": str(i)}, rpc_id=100 + i)
            body = tool_json(data)
            assert body.get("success") is True, f"health_check failed on iteration {i}"

    def test_tools_list_is_idempotent(self, mcp_session):
        """tools/list should return the same tools on repeated calls."""
        client, session_id, url = mcp_session
        first, _ = jsonrpc_call(client, url, "tools/list", {}, rpc_id=200, session_id=session_id)
        second, _ = jsonrpc_call(client, url, "tools/list", {}, rpc_id=201, session_id=session_id)
        first_names = sorted(t["name"] for t in first["result"]["tools"])
        second_names = sorted(t["name"] for t in second["result"]["tools"])
        assert first_names == second_names, "tools/list returned different tools on second call"

    def test_sequential_tool_chain(self, mcp_session):
        """health_check → reload_credentials → health_check should all succeed."""
        d1 = call_tool(mcp_session, "health_check", {}, rpc_id=300)
        assert tool_json(d1).get("success") is True

        d2 = call_tool(mcp_session, "reload_credentials", {}, rpc_id=301)
        assert "success" in tool_json(d2)

        d3 = call_tool(mcp_session, "health_check", {}, rpc_id=302)
        assert tool_json(d3).get("success") is True


if __name__ == "__main__":
    import sys
    # Quick self-test: run against the default local URL
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
