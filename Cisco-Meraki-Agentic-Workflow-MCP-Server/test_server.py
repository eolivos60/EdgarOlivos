"""
Test suite for Meraki MCP Server
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

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
    client = AsyncMock()
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
