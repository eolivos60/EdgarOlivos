"""
Test suite for Meraki MCP Server
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
from urllib.parse import parse_qs, urlparse

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server import MerakiMCPServer


@pytest.fixture
def server():
    """Create server instance for testing"""
    return MerakiMCPServer()


@pytest.fixture
def mock_client():
    """Create mock HTTP client"""
    client = MagicMock()
    response = MagicMock()
    response.text = ""
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value={})
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    client.put = AsyncMock(return_value=response)
    client.delete = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_get_organizations(server, mock_client):
    """Test getting organizations"""
    server.client = mock_client
    server.api_key = "test_key"
    
    mock_response = [
        {"id": "123", "name": "Test Org 1"},
        {"id": "456", "name": "Test Org 2"}
    ]
    
    mock_client.get.return_value.json.return_value = mock_response
    mock_client.get.return_value.text = "response"
    mock_client.get.return_value.raise_for_status = MagicMock()
    
    result = await server._get_organizations()
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_diagnose_connectivity_issue(server, mock_client):
    """Test agentic connectivity diagnosis"""
    server.client = mock_client
    server.api_key = "test_key"
    
    # Mock API responses
    mock_client.get.return_value.json.return_value = []
    mock_client.get.return_value.text = "response"
    mock_client.get.return_value.raise_for_status = MagicMock()
    
    args = {
        "organization_id": "123",
        "issue_description": "Network slow",
        "network_id": "net123"
    }
    
    result = await server._diagnose_connectivity_issue(args)
    
    assert "issue_description" in result
    assert "findings" in result
    assert "recommendations" in result
    assert "steps_performed" in result


@pytest.mark.asyncio
async def test_automated_health_check(server, mock_client):
    """Test automated health check workflow"""
    server.client = mock_client
    server.api_key = "test_key"
    
    mock_networks = [
        {"id": "net1", "name": "Network 1"},
        {"id": "net2", "name": "Network 2"}
    ]
    
    mock_client.get.return_value.json.return_value = mock_networks
    mock_client.get.return_value.text = "response"
    mock_client.get.return_value.raise_for_status = MagicMock()
    
    args = {
        "organization_id": "123",
        "include_recommendations": True
    }
    
    result = await server._automated_health_check(args)
    
    assert "organization_id" in result
    assert "summary" in result
    assert "network_health" in result
    assert "recommendations" in result


@pytest.mark.asyncio
async def test_make_request_error_handling(server, mock_client):
    """Test error handling in API requests"""
    server.client = mock_client
    server.api_key = "test_key"
    
    # Simulate HTTP error
    from httpx import HTTPStatusError, Response, Request
    
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    
    mock_request = MagicMock(spec=Request)
    
    mock_client.get.side_effect = HTTPStatusError(
        "Not Found", 
        request=mock_request,
        response=mock_response
    )
    
    result = await server._make_request("GET", "/test")
    
    assert "error" in result
    assert "HTTP 404" in result["error"]


@pytest.mark.asyncio
async def test_get_organization_devices_query_and_clamp(server):
    """New helper should include perPage and pagination query params."""
    server._make_request = AsyncMock(return_value=[])

    await server._get_organization_devices(
        "123",
        per_page=99999,
        starting_after="tokenA",
        ending_before="tokenB",
    )

    server._make_request.assert_awaited_once()
    method, endpoint = server._make_request.await_args.args
    assert method == "GET"
    assert endpoint.startswith("/organizations/123/devices?")
    query = parse_qs(urlparse(endpoint).query)
    assert query.get("perPage") == ["5000"]
    assert query.get("startingAfter") == ["tokenA"]
    assert query.get("endingBefore") == ["tokenB"]


@pytest.mark.asyncio
async def test_get_organization_inventory_devices_query_and_clamp(server):
    """Inventory helper should clamp perPage and include page tokens."""
    server._make_request = AsyncMock(return_value=[])

    await server._get_organization_inventory_devices(
        "123",
        per_page=1,
        starting_after="token1",
    )

    method, endpoint = server._make_request.await_args.args
    assert method == "GET"
    assert endpoint.startswith("/organizations/123/inventory/devices?")
    query = parse_qs(urlparse(endpoint).query)
    assert query.get("perPage") == ["3"]
    assert query.get("startingAfter") == ["token1"]
    assert "endingBefore" not in query


@pytest.mark.asyncio
async def test_get_organization_devices_statuses_query_and_clamp(server):
    """Statuses helper should clamp perPage and include endingBefore when provided."""
    server._make_request = AsyncMock(return_value=[])

    await server._get_organization_devices_statuses(
        "123",
        per_page=1200,
        ending_before="tokenEnd",
    )

    method, endpoint = server._make_request.await_args.args
    assert method == "GET"
    assert endpoint.startswith("/organizations/123/devices/statuses?")
    query = parse_qs(urlparse(endpoint).query)
    assert query.get("perPage") == ["1000"]
    assert query.get("endingBefore") == ["tokenEnd"]
    assert "startingAfter" not in query


@pytest.mark.asyncio
async def test_get_network_events_query_and_clamp(server):
    """Network events helper should build query params correctly."""
    server._make_request = AsyncMock(return_value={"events": []})

    await server._get_network_events(
        "N_1",
        product_type="wireless",
        per_page=0,
        starting_after="s1",
        ending_before="e1",
    )

    method, endpoint = server._make_request.await_args.args
    assert method == "GET"
    assert endpoint.startswith("/networks/N_1/events?")
    query = parse_qs(urlparse(endpoint).query)
    assert query.get("perPage") == ["3"]
    assert query.get("productType") == ["wireless"]
    assert query.get("startingAfter") == ["s1"]
    assert query.get("endingBefore") == ["e1"]


@pytest.mark.asyncio
async def test_get_organization_devices_auto_paginate_max_records(server):
    """Auto-pagination should chain by last serial and stop at max_records."""
    page_1 = [
        {"serial": "Q2XX-AAAA-0001"},
        {"serial": "Q2XX-AAAA-0002"},
        {"serial": "Q2XX-AAAA-0003"},
    ]
    page_2 = [
        {"serial": "Q2XX-AAAA-0004"},
        {"serial": "Q2XX-AAAA-0005"},
        {"serial": "Q2XX-AAAA-0006"},
    ]

    server._make_request = AsyncMock(side_effect=[page_1, page_2])

    result = await server._get_organization_devices(
        "123",
        per_page=3,
        auto_paginate=True,
        max_records=5,
    )

    assert isinstance(result, dict)
    assert result["count"] == 5
    assert result["pages_fetched"] == 2
    assert result["requested_max_records"] == 5
    assert len(result["devices"]) == 5
    assert result["devices"][-1]["serial"] == "Q2XX-AAAA-0005"
    assert result["next_starting_after"] == "Q2XX-AAAA-0006"

    first_call = server._make_request.await_args_list[0].args
    second_call = server._make_request.await_args_list[1].args
    assert first_call[1].startswith("/organizations/123/devices?perPage=3")
    assert "startingAfter=Q2XX-AAAA-0003" in second_call[1]


def test_tool_result_list_limit_for_org_devices(server):
    """Organization device listings should allow larger result payloads."""
    assert server._tool_result_list_limit("get_networks", {}) == 100
    assert server._tool_result_list_limit("get_organization_devices", {"per_page": 5000}) == 5000
    assert (
        server._tool_result_list_limit(
            "get_organization_devices",
            {"auto_paginate": True, "max_records": 4500},
        )
        == 4500
    )


def test_initialize_client_prefers_cookies_when_forced(server):
    """MERAKI_AUTH_METHOD=cookies should use cookie auth even when API key exists."""
    with patch.dict(
        os.environ,
        {
            "MERAKI_AUTH_METHOD": "cookies",
            "MERAKI_API_KEY": "api-key-should-not-be-selected",
            "MERAKI_COOKIES": "dash_auth=abc123; _session_id_for_n999=xyz",
            "MERAKI_DASHBOARD_HOST": "n999.dashboard.meraki.com",
            "MERAKI_CSRF_TOKEN": "csrf-token",
        },
        clear=False,
    ):
        with patch("server.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = MagicMock()
            selected = server._initialize_client_from_env()

    assert selected == "cookies"
    kwargs = mock_async_client.call_args.kwargs
    headers = kwargs["headers"]
    assert headers.get("x-requested-with") == "XMLHttpRequest"
    assert headers.get("x-csrf-token")
    assert kwargs.get("follow_redirects") is True


@pytest.mark.asyncio
async def test_find_organization_device_by_serial_found(server):
    """Finder should page and return device + node_id when serial is discovered."""
    page_1 = [
        {"serial": "Q2XX-AAAA-0001", "url": "https://n1.dashboard.meraki.com/manage/nodes/new_list/111"},
        {"serial": "Q2XX-AAAA-0002", "url": "https://n1.dashboard.meraki.com/manage/nodes/new_list/222"},
        {"serial": "Q2XX-AAAA-0003", "url": "https://n1.dashboard.meraki.com/manage/nodes/new_list/333"},
    ]
    page_2 = [
        {"serial": "Q3AC-WY9C-4STT", "url": "https://n1.dashboard.meraki.com/manage/nodes/new_list/567444484311"},
        {"serial": "Q2XX-AAAA-0004", "url": "https://n1.dashboard.meraki.com/manage/nodes/new_list/444"},
        {"serial": "Q2XX-AAAA-0005", "url": "https://n1.dashboard.meraki.com/manage/nodes/new_list/555"},
    ]
    server._make_request = AsyncMock(side_effect=[page_1, page_2])

    result = await server._find_organization_device_by_serial(
        "123",
        "q3ac-wy9c-4stt",
        per_page=3,
        max_pages=10,
    )

    assert result["found"] is True
    assert result["serial"] == "Q3AC-WY9C-4STT"
    assert result["node_id"] == "567444484311"
    assert result["pages_scanned"] == 2


@pytest.mark.asyncio
async def test_find_organization_device_by_serial_not_found(server):
    """Finder should return not found summary when max_pages is reached."""
    page = [
        {"serial": "Q2XX-AAAA-0001"},
        {"serial": "Q2XX-AAAA-0002"},
        {"serial": "Q2XX-AAAA-0003"},
    ]
    server._make_request = AsyncMock(side_effect=[page, page])

    result = await server._find_organization_device_by_serial(
        "123",
        "Q3AC-WY9C-4STT",
        per_page=3,
        max_pages=2,
    )

    assert result["found"] is False
    assert result["serial"] == "Q3AC-WY9C-4STT"
    assert result["pages_scanned"] == 2


def test_resolve_dashboard_host_prefers_explicit_field(server):
    """Host resolution should use stored dashboard host first."""
    server.dashboard_host = "n986.dashboard.meraki.com"
    assert server._resolve_dashboard_host() == "n986.dashboard.meraki.com"


@pytest.mark.asyncio
async def test_make_internal_request_requires_cookie_auth(server):
    """Internal operations should reject API-key auth mode."""
    server.auth_method = "api_key"
    result = await server._make_internal_request("GET", "/internalAPI/devices/Q3AC-WY9C-4STT")
    assert result.get("error") == "cookie_auth_required"


@pytest.mark.asyncio
async def test_get_device_internal_details_calls_internal_api(server, mock_client):
    """Internal details helper should call /internalAPI/devices/{serial}."""
    server.client = mock_client
    server.auth_method = "cookies"
    server.dashboard_host = "n986.dashboard.meraki.com"
    mock_client.get.return_value.text = "{\"adminTags\":[\"admin\"]}"
    mock_client.get.return_value.json.return_value = {"adminTags": ["admin"]}

    result = await server._get_device_internal_details("Q3AC-WY9C-4STT")

    assert result.get("adminTags") == ["admin"]
    mock_client.get.assert_awaited_once()
    called_url = mock_client.get.await_args.args[0]
    assert called_url == "https://n986.dashboard.meraki.com/internalAPI/devices/Q3AC-WY9C-4STT"


@pytest.mark.asyncio
async def test_update_device_admin_tags_puts_internal_payload(server, mock_client):
    """Admin tags updater should send adminTags payload to internal endpoint."""
    server.client = mock_client
    server.auth_method = "cookies"
    server.dashboard_host = "n986.dashboard.meraki.com"
    mock_client.put.return_value.text = "{}"
    mock_client.put.return_value.json.return_value = {}

    result = await server._update_device_admin_tags(
        {
            "serial": "Q3AC-KGYE-MZKY",
            "admin_tags": [],
        }
    )

    assert result.get("success") is True
    assert result.get("serial") == "Q3AC-KGYE-MZKY"
    assert result.get("admin_tags") == []
    mock_client.put.assert_awaited_once()
    called_url = mock_client.put.await_args.args[0]
    called_payload = mock_client.put.await_args.kwargs.get("json")
    assert called_url == "https://n986.dashboard.meraki.com/internalAPI/devices/Q3AC-KGYE-MZKY"
    assert called_payload == {"adminTags": []}


@pytest.mark.asyncio
async def test_clear_device_admin_tags_by_serial_success(server):
    """Convenience helper should lookup serial, clear admin tags, and verify when requested."""
    server._find_organization_device_by_serial = AsyncMock(
        return_value={
            "found": True,
            "serial": "Q3AC-KGYE-MZKY",
            "node_id": "251056543930133",
            "pages_scanned": 3,
            "scanned_devices": 2245,
        }
    )
    server._update_device_admin_tags = AsyncMock(
        return_value={
            "success": True,
            "serial": "Q3AC-KGYE-MZKY",
            "admin_tags": [],
            "updated_via": "internal_api",
            "result": {},
        }
    )
    server._get_device_internal_details = AsyncMock(
        return_value={
            "serial": "Q3AC-KGYE-MZKY",
            "adminTags": [],
        }
    )

    result = await server._clear_device_admin_tags_by_serial(
        {
            "organization_id": "622622648484233674",
            "serial": "q3ac-kgye-mzky",
            "verify_after": True,
        }
    )

    assert result.get("success") is True
    assert result.get("matched_serial") == "Q3AC-KGYE-MZKY"
    assert result.get("node_id") == "251056543930133"
    assert result.get("verification", {}).get("adminTags") == []
    server._find_organization_device_by_serial.assert_awaited_once()
    server._update_device_admin_tags.assert_awaited_once_with(
        {"serial": "Q3AC-KGYE-MZKY", "admin_tags": []}
    )


@pytest.mark.asyncio
async def test_clear_device_admin_tags_by_serial_not_found(server):
    """Convenience helper should stop and report not found without calling update."""
    server._find_organization_device_by_serial = AsyncMock(
        return_value={
            "found": False,
            "pages_scanned": 100,
            "scanned_devices": 5000,
            "message": "Stopped at max_pages before finding serial",
            "next_starting_after": "Q3AC-XXXX-YYYY",
        }
    )
    server._update_device_admin_tags = AsyncMock()

    result = await server._clear_device_admin_tags_by_serial(
        {
            "organization_id": "622622648484233674",
            "serial": "Q3AC-UNKNOWN-0000",
        }
    )

    assert result.get("success") is False
    assert result.get("requested_serial") == "Q3AC-UNKNOWN-0000"
    assert result.get("lookup", {}).get("pages_scanned") == 100
    server._update_device_admin_tags.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
