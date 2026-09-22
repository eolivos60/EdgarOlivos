#!/usr/bin/env python3
"""
Cisco Meraki MCP Server - Agentic Troubleshooting and Configuration Assistant
This MCP server provides intelligent tools for Cisco Meraki network management.
"""

import asyncio
import argparse
import json
import os
import re
import secrets
import uuid
from urllib.parse import urlencode
from typing import Any, Dict, List, Optional, Sequence
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE_PATH = os.path.join(BASE_DIR, ".env")
LOG_DIR_PATH = os.path.join(BASE_DIR, "logs")
LOG_FILE_PATH = os.path.join(LOG_DIR_PATH, "mcp_server.log")
load_dotenv(dotenv_path=ENV_FILE_PATH)

# MCP SDK imports
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
import mcp.types as types

# HTTP client for Meraki API
import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
import uvicorn


class MerakiMCPServer:
    """MCP Server for Cisco Meraki troubleshooting and configuration"""
    MAX_LIST_ITEMS = 100
    MAX_ORG_DEVICES_ITEMS = 5000
    MAX_RECURSION_DEPTH = 12  # Increased from 6 to support nested wireless analytics data
    
    def __init__(self):
        self.server = Server("meraki-assistant")
        self.api_key: Optional[str] = None
        self.cookies: Optional[str] = None
        self.csrf_token: str = ""
        self.auth_method: Optional[str] = None
        self.auth_preference: str = "auto"
        self.dashboard_host: Optional[str] = None
        self.base_url = "https://api.meraki.com/api/v1"
        self.client: Optional[httpx.AsyncClient] = None
        self.env_mtime: Optional[float] = self._get_env_mtime()
        
        # Agentic workflow state
        self.workflow_context: Dict[str, Any] = {}
        
        # Setup handlers
        self.setup_handlers()

    def _log(self, message: str) -> None:
        """Best-effort local logging for MCP troubleshooting without stdout noise."""
        try:
            os.makedirs(LOG_DIR_PATH, exist_ok=True)
            with open(LOG_FILE_PATH, "a", encoding="utf-8") as log_file:
                log_file.write(f"{datetime.now().isoformat()} {message}\n")
        except Exception:
            pass

    def _get_env_mtime(self) -> Optional[float]:
        """Return current .env mtime when available for hot-reload checks."""
        try:
            if os.path.exists(ENV_FILE_PATH):
                return os.path.getmtime(ENV_FILE_PATH)
        except Exception:
            pass
        return None
    
    def setup_handlers(self):
        """Setup MCP protocol handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """List available Meraki troubleshooting and configuration tools"""
            return [
                # Organization Management
                types.Tool(
                    name="get_organizations",
                    description="Get all organizations accessible with the active credentials. First step in workflow.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
                
                # Network Discovery and Status
                types.Tool(
                    name="get_networks",
                    description="Get all networks in an organization. Use after getting organizations.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "organization_id": {
                                "type": "string",
                                "description": "Organization ID"
                            }
                        },
                        "required": ["organization_id"]
                    },
                ),
                
                types.Tool(
                    name="get_network_devices",
                    description="Get all devices in a network with status information",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "network_id": {
                                "type": "string",
                                "description": "Network ID"
                            }
                        },
                        "required": ["network_id"]
                    },
                ),

                types.Tool(
                    name="get_organization_devices",
                    description="List devices assigned to networks in an organization",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "organization_id": {
                                "type": "string",
                                "description": "Organization ID"
                            },
                            "per_page": {
                                "type": "integer",
                                "description": "Number of results per page (3-5000)",
                                "default": 1000
                            },
                            "starting_after": {
                                "type": "string",
                                "description": "Pagination token for next page"
                            },
                            "ending_before": {
                                "type": "string",
                                "description": "Pagination token for previous page"
                            },
                            "auto_paginate": {
                                "type": "boolean",
                                "description": "When true, keeps paging with starting_after until max_records or API end",
                                "default": False
                            },
                            "max_records": {
                                "type": "integer",
                                "description": "Maximum number of devices to return when auto_paginate is true (1-5000)",
                                "default": 5000
                            }
                        },
                        "required": ["organization_id"]
                    },
                ),

                types.Tool(
                    name="find_organization_device_by_serial",
                    description="Find one organization device by serial using internal pagination and return node ID when available",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "organization_id": {
                                "type": "string",
                                "description": "Organization ID"
                            },
                            "serial": {
                                "type": "string",
                                "description": "Device serial to find"
                            },
                            "per_page": {
                                "type": "integer",
                                "description": "Number of results per page (3-5000)",
                                "default": 1000
                            },
                            "max_pages": {
                                "type": "integer",
                                "description": "Maximum pages to scan before stopping",
                                "default": 100
                            }
                        },
                        "required": ["organization_id", "serial"]
                    },
                ),

                types.Tool(
                    name="get_organization_inventory_devices",
                    description="Return inventory devices for an organization",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "organization_id": {
                                "type": "string",
                                "description": "Organization ID"
                            },
                            "per_page": {
                                "type": "integer",
                                "description": "Number of results per page (3-1000)",
                                "default": 1000
                            },
                            "starting_after": {
                                "type": "string",
                                "description": "Pagination token for next page"
                            },
                            "ending_before": {
                                "type": "string",
                                "description": "Pagination token for previous page"
                            }
                        },
                        "required": ["organization_id"]
                    },
                ),

                types.Tool(
                    name="get_organization_devices_statuses",
                    description="List status of devices across an organization",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "organization_id": {
                                "type": "string",
                                "description": "Organization ID"
                            },
                            "per_page": {
                                "type": "integer",
                                "description": "Number of results per page (3-1000)",
                                "default": 1000
                            },
                            "starting_after": {
                                "type": "string",
                                "description": "Pagination token for next page"
                            },
                            "ending_before": {
                                "type": "string",
                                "description": "Pagination token for previous page"
                            }
                        },
                        "required": ["organization_id"]
                    },
                ),
                
                # Device Troubleshooting
                types.Tool(
                    name="get_device_status",
                    description="Get detailed status of a specific device including connectivity, performance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "serial": {
                                "type": "string",
                                "description": "Device serial number"
                            }
                        },
                        "required": ["serial"]
                    },
                ),
                
                types.Tool(
                    name="get_device_uplink_status",
                    description="Troubleshoot device uplink connectivity issues",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "serial": {
                                "type": "string",
                                "description": "Device serial number"
                            }
                        },
                        "required": ["serial"]
                    },
                ),
                
                types.Tool(
                    name="get_device_clients",
                    description="Get clients connected to a device for troubleshooting client issues",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "serial": {
                                "type": "string",
                                "description": "Device serial number"
                            },
                            "timespan": {
                                "type": "integer",
                                "description": "Timespan in seconds (max 2592000 - 30 days)",
                                "default": 86400
                            }
                        },
                        "required": ["serial"]
                    },
                ),
                
                # Network Health and Monitoring
                types.Tool(
                    name="get_network_health_alerts",
                    description="Get active alerts and health issues for a network",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "network_id": {
                                "type": "string",
                                "description": "Network ID"
                            }
                        },
                        "required": ["network_id"]
                    },
                ),

                types.Tool(
                    name="get_network_events",
                    description="List event history for a network",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "network_id": {
                                "type": "string",
                                "description": "Network ID"
                            },
                            "product_type": {
                                "type": "string",
                                "description": "Optional product type filter for mixed-product networks"
                            },
                            "per_page": {
                                "type": "integer",
                                "description": "Number of events per page (3-1000)",
                                "default": 100
                            },
                            "starting_after": {
                                "type": "string",
                                "description": "Pagination token for next page"
                            },
                            "ending_before": {
                                "type": "string",
                                "description": "Pagination token for previous page"
                            }
                        },
                        "required": ["network_id"]
                    },
                ),
                
                types.Tool(
                    name="get_organization_uplink_statuses",
                    description="Get uplink status for all devices across organization",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "organization_id": {
                                "type": "string",
                                "description": "Organization ID"
                            }
                        },
                        "required": ["organization_id"]
                    },
                ),
                
                # Client Troubleshooting
                types.Tool(
                    name="get_network_clients",
                    description="Get all clients in a network for troubleshooting connectivity",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "network_id": {
                                "type": "string",
                                "description": "Network ID"
                            },
                            "timespan": {
                                "type": "integer",
                                "description": "Timespan in seconds",
                                "default": 86400
                            }
                        },
                        "required": ["network_id"]
                    },
                ),
                
                types.Tool(
                    name="get_client_details",
                    description="Get detailed information about a specific client",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "network_id": {
                                "type": "string",
                                "description": "Network ID"
                            },
                            "client_id": {
                                "type": "string",
                                "description": "Client ID or MAC address"
                            }
                        },
                        "required": ["network_id", "client_id"]
                    },
                ),
                
                # Configuration Management
                types.Tool(
                    name="update_device",
                    description="Update device configuration (name, tags, address, notes)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "serial": {
                                "type": "string",
                                "description": "Device serial number"
                            },
                            "name": {
                                "type": "string",
                                "description": "Device name"
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Device tags"
                            },
                            "address": {
                                "type": "string",
                                "description": "Device physical address"
                            },
                            "notes": {
                                "type": "string",
                                "description": "Device notes"
                            }
                        },
                        "required": ["serial"]
                    },
                ),

                types.Tool(
                    name="get_device_internal_details",
                    description="Get internal dashboard device details (includes adminTags) using cookie auth",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "serial": {
                                "type": "string",
                                "description": "Device serial number"
                            },
                            "node_id": {
                                "type": "string",
                                "description": "Internal numeric node ID (from device URL). Providing this fixes 404s on the GET path — obtain it from find_organization_device_by_serial."
                            }
                        },
                        "required": ["serial"]
                    },
                ),

                types.Tool(
                    name="update_device_admin_tags",
                    description="Update internal dashboard adminTags for a device using cookie auth",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "serial": {
                                "type": "string",
                                "description": "Device serial number"
                            },
                            "admin_tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Internal admin tags to set. Use [] to clear all admin tags"
                            }
                        },
                        "required": ["serial", "admin_tags"]
                    },
                ),

                types.Tool(
                    name="clear_device_admin_tags_by_serial",
                    description="Find a device in an organization by serial, then clear its internal adminTags using cookie auth",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "organization_id": {
                                "type": "string",
                                "description": "Organization ID"
                            },
                            "serial": {
                                "type": "string",
                                "description": "Device serial to locate and clear adminTags for"
                            },
                            "per_page": {
                                "type": "integer",
                                "description": "Results per page for serial lookup (3-5000)",
                                "default": 1000
                            },
                            "max_pages": {
                                "type": "integer",
                                "description": "Maximum lookup pages to scan",
                                "default": 100
                            },
                            "verify_after": {
                                "type": "boolean",
                                "description": "Read back internal details after update to confirm adminTags",
                                "default": True
                            }
                        },
                        "required": ["organization_id", "serial"]
                    },
                ),
                
                types.Tool(
                    name="update_network",
                    description="Update network configuration (name, timezone, tags)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "network_id": {
                                "type": "string",
                                "description": "Network ID"
                            },
                            "name": {
                                "type": "string",
                                "description": "Network name"
                            },
                            "timezone": {
                                "type": "string",
                                "description": "Network timezone"
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Network tags"
                            }
                        },
                        "required": ["network_id"]
                    },
                ),
                
                # Wireless Configuration
                types.Tool(
                    name="get_wireless_ssids",
                    description="Get wireless SSIDs configured in a network",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "network_id": {
                                "type": "string",
                                "description": "Network ID"
                            }
                        },
                        "required": ["network_id"]
                    },
                ),
                
                types.Tool(
                    name="update_wireless_ssid",
                    description="Update wireless SSID configuration",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "network_id": {
                                "type": "string",
                                "description": "Network ID"
                            },
                            "number": {
                                "type": "string",
                                "description": "SSID number (0-14)"
                            },
                            "name": {
                                "type": "string",
                                "description": "SSID name"
                            },
                            "enabled": {
                                "type": "boolean",
                                "description": "Enable/disable SSID"
                            },
                            "authMode": {
                                "type": "string",
                                "description": "Authentication mode",
                                "enum": ["open", "psk", "8021x-radius"]
                            }
                        },
                        "required": ["network_id", "number"]
                    },
                ),
                
                # Agentic Workflow Tools
                types.Tool(
                    name="diagnose_connectivity_issue",
                    description="Intelligent diagnosis of connectivity issues using multi-step analysis",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "organization_id": {
                                "type": "string",
                                "description": "Organization ID"
                            },
                            "issue_description": {
                                "type": "string",
                                "description": "Description of the connectivity issue"
                            },
                            "network_id": {
                                "type": "string",
                                "description": "Network ID (optional)"
                            },
                            "device_serial": {
                                "type": "string",
                                "description": "Device serial (optional)"
                            }
                        },
                        "required": ["organization_id", "issue_description"]
                    },
                ),
                
                types.Tool(
                    name="automated_health_check",
                    description="Comprehensive automated health check across organization",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "organization_id": {
                                "type": "string",
                                "description": "Organization ID"
                            },
                            "include_recommendations": {
                                "type": "boolean",
                                "description": "Include configuration recommendations",
                                "default": True
                            }
                        },
                        "required": ["organization_id"]
                    },
                ),

                types.Tool(
                    name="reload_credentials",
                    description="Reload MERAKI_API_KEY or MERAKI_COOKIES from .env without restarting Claude",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    },
                ),

                types.Tool(
                    name="health_check",
                    description="Fast local MCP health check with no Meraki API calls",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "echo": {
                                "type": "string",
                                "description": "Optional value echoed back"
                            }
                        },
                        "required": []
                    },
                ),

                types.Tool(
                    name="investigate_ssid_issue",
                    description="Focused SSID investigation for one network using targeted GET calls",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "organization_id": {
                                "type": "string",
                                "description": "Organization ID"
                            },
                            "network_id": {
                                "type": "string",
                                "description": "Network ID"
                            },
                            "ssid_name": {
                                "type": "string",
                                "description": "SSID name to investigate"
                            },
                            "timespan": {
                                "type": "integer",
                                "description": "Client lookback window in seconds",
                                "default": 7200
                            }
                        },
                        "required": ["organization_id", "network_id", "ssid_name"]
                    },
                ),

                types.Tool(
                    name="get_device_channel_utilization",
                    description="Get wireless device channel utilization statistics (% of time channel was occupied)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "organization_id": {
                                "type": "string",
                                "description": "Organization ID"
                            },
                            "serials": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of AP serial numbers (e.g., [\"Q3AL-84EF-7Z69\"])"
                            },
                            "timespan": {
                                "type": "integer",
                                "description": "Timespan in seconds (default 604800 = 7 days)",
                                "default": 604800
                            },
                            "interval": {
                                "type": "integer",
                                "description": "Interval in seconds for data points (default 3600 = 1 hour)",
                                "default": 3600
                            }
                        },
                        "required": ["organization_id", "serials"]
                    },
                ),

                types.Tool(
                    name="get_wireless_signal_quality_history",
                    description="Get wireless signal quality history for a device (SNR, RSSI, etc.)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "network_id": {
                                "type": "string",
                                "description": "Network ID"
                            },
                            "device_serial": {
                                "type": "string",
                                "description": "Device (AP) serial number"
                            },
                            "timespan": {
                                "type": "integer",
                                "description": "Timespan in seconds (default 604800 = 7 days)",
                                "default": 604800
                            },
                            "resolution": {
                                "type": "integer",
                                "description": "Resolution in seconds (default 3600 = 1 hour)",
                                "default": 3600
                            }
                        },
                        "required": ["network_id", "device_serial"]
                    },
                ),

                types.Tool(
                    name="get_wireless_failed_connections",
                    description="Get failed wireless connection attempts within a time range",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "network_id": {
                                "type": "string",
                                "description": "Network ID"
                            },
                            "t0": {
                                "type": "string",
                                "description": "Start time (ISO 8601 format, e.g., \"2026-06-16T11:45:00Z\")"
                            },
                            "t1": {
                                "type": "string",
                                "description": "End time (ISO 8601 format, e.g., \"2026-06-17T11:45:00Z\")"
                            }
                        },
                        "required": ["network_id", "t0", "t1"]
                    },
                ),

                types.Tool(
                    name="get_wireless_roaming_stats",
                    description="Get wireless roaming statistics for networks in an organization",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "organization_id": {
                                "type": "string",
                                "description": "Organization ID"
                            },
                            "network_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of network IDs to analyze"
                            },
                            "timespan": {
                                "type": "integer",
                                "description": "Timespan in seconds (default 86400 = 1 day)",
                                "default": 86400
                            },
                            "interval": {
                                "type": "integer",
                                "description": "Interval in seconds (default 3600 = 1 hour)",
                                "default": 3600
                            }
                        },
                        "required": ["organization_id", "network_ids"]
                    },
                ),

                types.Tool(
                    name="get_wireless_rf_profiles",
                    description="Get RF (Radio Frequency) profiles configured for a network",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "network_id": {
                                "type": "string",
                                "description": "Network ID"
                            }
                        },
                        "required": ["network_id"]
                    },
                ),
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict
        ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
            """Handle tool execution"""
            arguments = arguments or {}
            self._log(f"tool_call name={name}")

            if name == "reload_credentials":
                result = await self._reload_credentials()
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            if name == "health_check":
                result = await self._health_check(arguments)
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]

            current_env_mtime = self._get_env_mtime()
            if self.client and current_env_mtime and self.env_mtime and current_env_mtime > self.env_mtime:
                self._log("env_changed_detected auto_reloading_credentials")
                await self._reload_credentials()
                self.env_mtime = current_env_mtime
            
            if not self.client:
                auth_method = self._initialize_client_from_env()
                self.env_mtime = current_env_mtime
                if not auth_method:
                    return [types.TextContent(
                        type="text",
                        text="Error: Either MERAKI_API_KEY or MERAKI_COOKIES environment variable must be set"
                    )]
            
            try:
                # Route to appropriate handler
                if name == "get_organizations":
                    result = await self._get_organizations()
                
                elif name == "get_networks":
                    result = await self._get_networks(arguments["organization_id"])
                
                elif name == "get_network_devices":
                    result = await self._get_network_devices(arguments["network_id"])

                elif name == "get_organization_devices":
                    result = await self._get_organization_devices(
                        arguments["organization_id"],
                        arguments.get("per_page", 1000),
                        arguments.get("starting_after"),
                        arguments.get("ending_before"),
                        arguments.get("auto_paginate", False),
                        arguments.get("max_records", 5000),
                    )

                elif name == "get_organization_inventory_devices":
                    result = await self._get_organization_inventory_devices(
                        arguments["organization_id"],
                        arguments.get("per_page", 1000),
                        arguments.get("starting_after"),
                        arguments.get("ending_before"),
                    )

                elif name == "find_organization_device_by_serial":
                    result = await self._find_organization_device_by_serial(
                        arguments["organization_id"],
                        arguments["serial"],
                        arguments.get("per_page", 1000),
                        arguments.get("max_pages", 100),
                    )

                elif name == "get_organization_devices_statuses":
                    result = await self._get_organization_devices_statuses(
                        arguments["organization_id"],
                        arguments.get("per_page", 1000),
                        arguments.get("starting_after"),
                        arguments.get("ending_before"),
                    )
                
                elif name == "get_device_status":
                    result = await self._get_device_status(arguments["serial"])
                
                elif name == "get_device_uplink_status":
                    result = await self._get_device_uplink_status(arguments["serial"])
                
                elif name == "get_device_clients":
                    result = await self._get_device_clients(
                        arguments["serial"],
                        arguments.get("timespan", 86400)
                    )
                
                elif name == "get_network_health_alerts":
                    result = await self._get_network_health_alerts(arguments["network_id"])

                elif name == "get_network_events":
                    result = await self._get_network_events(
                        arguments["network_id"],
                        arguments.get("product_type"),
                        arguments.get("per_page", 100),
                        arguments.get("starting_after"),
                        arguments.get("ending_before"),
                    )
                
                elif name == "get_organization_uplink_statuses":
                    result = await self._get_organization_uplink_statuses(
                        arguments["organization_id"]
                    )
                
                elif name == "get_network_clients":
                    result = await self._get_network_clients(
                        arguments["network_id"],
                        arguments.get("timespan", 86400)
                    )
                
                elif name == "get_client_details":
                    result = await self._get_client_details(
                        arguments["network_id"],
                        arguments["client_id"]
                    )
                
                elif name == "update_device":
                    result = await self._update_device(arguments)

                elif name == "get_device_internal_details":
                    result = await self._get_device_internal_details(arguments["serial"], node_id=arguments.get("node_id"))

                elif name == "update_device_admin_tags":
                    result = await self._update_device_admin_tags(arguments)

                elif name == "clear_device_admin_tags_by_serial":
                    result = await self._clear_device_admin_tags_by_serial(arguments)
                
                elif name == "update_network":
                    result = await self._update_network(arguments)
                
                elif name == "get_wireless_ssids":
                    result = await self._get_wireless_ssids(arguments["network_id"])
                
                elif name == "update_wireless_ssid":
                    result = await self._update_wireless_ssid(arguments)
                
                elif name == "diagnose_connectivity_issue":
                    result = await self._diagnose_connectivity_issue(arguments)
                
                elif name == "automated_health_check":
                    result = await self._automated_health_check(arguments)

                elif name == "investigate_ssid_issue":
                    result = await self._investigate_ssid_issue(arguments)
                
                elif name == "get_device_channel_utilization":
                    result = await self._get_device_channel_utilization(arguments)
                
                elif name == "get_wireless_signal_quality_history":
                    result = await self._get_wireless_signal_quality_history(arguments)
                
                elif name == "get_wireless_failed_connections":
                    result = await self._get_wireless_failed_connections(arguments)
                
                elif name == "get_wireless_roaming_stats":
                    result = await self._get_wireless_roaming_stats(arguments)
                
                elif name == "get_wireless_rf_profiles":
                    result = await self._get_wireless_rf_profiles(arguments)
                
                else:
                    result = {"error": f"Unknown tool: {name}"}

                safe_result = self._truncate_result(
                    result,
                    list_limit=self._tool_result_list_limit(name, arguments),
                    max_depth=self._tool_recursion_depth_limit(name, arguments),
                )
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(safe_result, indent=2)
                )]
                
            except Exception as e:
                self._log(f"tool_error name={name} error={str(e)}")
                return [types.TextContent(
                    type="text",
                    text=f"Error executing {name}: {str(e)}"
                )]

    def _tool_result_list_limit(self, tool_name: str, arguments: Dict[str, Any]) -> int:
        """Allow larger responses for specific tools that require broader discovery."""
        if tool_name != "get_organization_devices":
            return self.MAX_LIST_ITEMS

        if arguments.get("auto_paginate"):
            try:
                requested_max = int(arguments.get("max_records", self.MAX_ORG_DEVICES_ITEMS))
            except Exception:
                requested_max = self.MAX_ORG_DEVICES_ITEMS
            return max(self.MAX_LIST_ITEMS, min(requested_max, self.MAX_ORG_DEVICES_ITEMS))

        try:
            per_page = int(arguments.get("per_page", 1000))
        except Exception:
            per_page = 1000
        return max(self.MAX_LIST_ITEMS, min(per_page, self.MAX_ORG_DEVICES_ITEMS))
    
    def _tool_recursion_depth_limit(self, tool_name: str, arguments: Dict[str, Any]) -> int:
        """Allow deeper nesting for wireless analytics tools with complex nested structures."""
        # Wireless analytics tools have deeply nested data (time-series arrays, bands, etc.)
        wireless_analytics_tools = {
            "get_device_channel_utilization",
            "get_wireless_signal_quality_history",
            "get_wireless_failed_connections",
            "get_wireless_roaming_stats",
            "get_network_events",
            "get_network_health_alerts",
        }
        
        if tool_name in wireless_analytics_tools:
            return 50  # Very deep nesting for wireless time-series data with nested arrays
        
        return self.MAX_RECURSION_DEPTH

    def _truncate_result(self, data: Any, depth: int = 0, list_limit: Optional[int] = None, max_depth: Optional[int] = None) -> Any:
        """Limit oversized responses so MCP clients do not stall on huge JSON payloads."""
        limit = self.MAX_LIST_ITEMS if list_limit is None else list_limit
        depth_limit = max_depth if max_depth is not None else self.MAX_RECURSION_DEPTH

        if depth >= depth_limit:
            return "<truncated: max depth reached>"

        if isinstance(data, list):
            if len(data) > limit:
                return {
                    "_truncated": True,
                    "_original_count": len(data),
                    "_returned_count": limit,
                    "items": [self._truncate_result(item, depth + 1, list_limit=limit, max_depth=max_depth) for item in data[:limit]],
                }
            return [self._truncate_result(item, depth + 1, list_limit=limit, max_depth=max_depth) for item in data]

        if isinstance(data, dict):
            return {k: self._truncate_result(v, depth + 1, list_limit=limit, max_depth=max_depth) for k, v in data.items()}

        return data

    def _initialize_client_from_env(self) -> Optional[str]:
        """Load credentials from env/.env and initialize HTTP client."""
        load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)

        self.api_key = (os.getenv("MERAKI_API_KEY") or "").strip()
        self.cookies = (os.getenv("MERAKI_COOKIES") or "").strip()
        self.auth_preference = (os.getenv("MERAKI_AUTH_METHOD") or "auto").strip().lower()
        self.csrf_token = (os.getenv("MERAKI_CSRF_TOKEN") or "").strip()
        csrf_token = self.csrf_token
        dashboard_host = (os.getenv("MERAKI_DASHBOARD_HOST") or "").strip()
        referer = (os.getenv("MERAKI_REFERER") or "").strip()
        pageload_request_id = (os.getenv("MERAKI_PAGELOAD_REQUEST_ID") or "").strip()
        if self.auth_preference not in {"auto", "api_key", "cookies"}:
            self.auth_preference = "auto"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        }

        def _init_api_key_client() -> Optional[str]:
            if not self.api_key:
                return None
            self.base_url = "https://api.meraki.com/api/v1"
            self.dashboard_host = None
            key_headers = dict(headers)
            key_headers["X-Cisco-Meraki-API-Key"] = self.api_key
            self.client = httpx.AsyncClient(
                headers=key_headers,
                timeout=30.0,
            )
            self.auth_method = "api_key"
            return "api_key"

        def _init_cookie_client() -> Optional[str]:
            if not self.cookies:
                return None
            resolved_dashboard_host = dashboard_host
            cookie_dict: Dict[str, str] = {}
            for cookie in self.cookies.split(";"):
                cookie = cookie.strip()
                if "=" in cookie:
                    key, value = cookie.split("=", 1)
                    cookie_dict[key.strip()] = value.strip()

            # Dashboard cookie sessions are shard-specific: infer n#### host from cookie names.
            if not resolved_dashboard_host:
                session_match = re.search(r"_session_id_for_(n\d+)", self.cookies)
                if session_match:
                    resolved_dashboard_host = f"{session_match.group(1)}.dashboard.meraki.com"

            if resolved_dashboard_host:
                self.base_url = f"https://{resolved_dashboard_host}/api/v1"
                self.dashboard_host = resolved_dashboard_host
            else:
                self.base_url = "https://api.meraki.com/api/v1"
                self.dashboard_host = None

            cookie_headers = dict(headers)
            if csrf_token:
                cookie_headers["x-csrf-token"] = csrf_token
            if referer:
                cookie_headers["referer"] = referer
            elif resolved_dashboard_host:
                cookie_headers["referer"] = f"https://{resolved_dashboard_host}/"
            if resolved_dashboard_host:
                cookie_headers["origin"] = f"https://{resolved_dashboard_host}"
            # Dashboard write paths often check this header on cookie sessions.
            cookie_headers["x-requested-with"] = "XMLHttpRequest"
            # This header is optional in browser calls; generate one if not provided.
            cookie_headers["x-pageload-request-id"] = pageload_request_id or uuid.uuid4().hex

            self.client = httpx.AsyncClient(
                headers=cookie_headers,
                cookies=cookie_dict,
                timeout=30.0,
                follow_redirects=True,
            )
            self.auth_method = "cookies"
            return "cookies"

        # Default behavior remains API key first unless MERAKI_AUTH_METHOD forces cookies.
        if self.auth_preference == "cookies":
            preferred_order = (_init_cookie_client, _init_api_key_client)
        elif self.auth_preference == "api_key":
            preferred_order = (_init_api_key_client, _init_cookie_client)
        else:
            preferred_order = (_init_api_key_client, _init_cookie_client)

        for initializer in preferred_order:
            method = initializer()
            if method:
                return method

        self.auth_method = None
        return None

    async def _reload_credentials(self) -> Dict:
        """Reload credentials from .env and reinitialize HTTP client."""
        try:
            if self.client:
                await self.client.aclose()
                self.client = None

            auth_method = self._initialize_client_from_env()
            self.env_mtime = self._get_env_mtime()
            if not auth_method:
                return {
                    "success": False,
                    "error": "No credentials found. Set MERAKI_API_KEY or MERAKI_COOKIES in .env/environment."
                }

            return {
                "success": True,
                "auth_method": auth_method,
                "message": "Credentials reloaded successfully."
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to reload credentials: {str(e)}"
            }

    async def _health_check(self, args: Optional[Dict] = None) -> Dict:
        """Return immediate local health without external calls."""
        args = args or {}
        self._log("health_check executed")
        return {
            "success": True,
            "status": "ok",
            "server": "meraki-assistant",
            "timestamp": datetime.now().isoformat(),
            "credentials_present": {
                "meraki_cookies": bool(os.getenv("MERAKI_COOKIES")),
                "meraki_api_key": bool(os.getenv("MERAKI_API_KEY"))
            },
            "auth_preference": self.auth_preference,
            "active_auth_method": self.auth_method,
            "echo": args.get("echo")
        }
    
    # API Helper Methods
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None
    ) -> Dict:
        """Make HTTP request to Meraki API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = await self.client.get(url)
            elif method == "POST":
                response = await self.client.post(url, json=data)
            elif method == "PUT":
                response = await self.client.put(url, json=data)
            elif method == "DELETE":
                response = await self.client.delete(url)
            
            response.raise_for_status()
            return response.json() if response.text else {}
            
        except httpx.HTTPStatusError as e:
            response_text = e.response.text
            if e.response.status_code in (401, 403) and self.auth_method == "cookies":
                expired_markers = [
                    "idle_timeout_session_expired",
                    "session_expired",
                    "invalid_csrf",
                    "csrf",
                ]
                is_expired = any(marker in response_text.lower() for marker in expired_markers)
                return {
                    "error": f"HTTP {e.response.status_code}",
                    "message": response_text,
                    "auth_method": "cookies",
                    "hint": (
                        "Meraki browser session cookies are not valid for this call. "
                        "Refresh MERAKI_COOKIES / MERAKI_CSRF_TOKEN from a logged-in dashboard browser session "
                        "and restart this server (or run reload_credentials)."
                        if is_expired else
                        "Cookie-based auth failed for this API call. Refresh MERAKI_COOKIES / MERAKI_CSRF_TOKEN "
                        "from an active Meraki dashboard browser session and restart this server (or run reload_credentials)."
                    )
                }
            return {
                "error": f"HTTP {e.response.status_code}",
                "message": response_text
            }
        except httpx.TimeoutException:
            return {
                "error": "request_timeout",
                "message": f"Request timed out for endpoint: {endpoint}"
            }
        except Exception as e:
            return {"error": str(e)}

    def _resolve_dashboard_host(self) -> Optional[str]:
        """Resolve dashboard host for internal API calls."""
        if self.dashboard_host:
            return self.dashboard_host

        base_match = re.match(r"^https://([^/]+)/", self.base_url)
        if base_match:
            host = base_match.group(1)
            if host.endswith(".dashboard.meraki.com"):
                return host

        cookie_session_match = re.search(r"_session_id_for_(n\d+)", self.cookies or "")
        if cookie_session_match:
            return f"{cookie_session_match.group(1)}.dashboard.meraki.com"

        return None

    async def _make_internal_request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
    ) -> Dict:
        """Make request to Meraki dashboard internal API using cookie auth session."""
        if self.auth_method != "cookies":
            return {
                "error": "cookie_auth_required",
                "message": "This operation requires cookie-based auth. Set MERAKI_AUTH_METHOD=cookies and reload credentials.",
            }

        host = self._resolve_dashboard_host()
        if not host:
            return {
                "error": "missing_dashboard_host",
                "message": "Unable to determine dashboard host for internal API call.",
            }

        url = f"https://{host}{path}"

        try:
            # Always send the latest in-memory CSRF token so rotations are picked up.
            per_req_headers = {"x-csrf-token": self.csrf_token} if self.csrf_token else {}
            if method == "GET":
                response = await self.client.get(url, headers=per_req_headers)
            elif method == "PUT":
                response = await self.client.put(url, json=data, headers=per_req_headers)
            else:
                return {
                    "error": "unsupported_method",
                    "message": f"Unsupported internal method: {method}",
                }

            # Capture rotated CSRF token that Rails returns after every write.
            rotated = response.headers.get("x-csrf-token") or response.headers.get("X-CSRF-Token")
            if rotated and rotated != self.csrf_token:
                self.csrf_token = rotated

            response.raise_for_status()
            return response.json() if response.text else {}

        except httpx.HTTPStatusError as e:
            # Still try to capture a token included with error responses.
            rotated = e.response.headers.get("x-csrf-token") or e.response.headers.get("X-CSRF-Token")
            if rotated and rotated != self.csrf_token:
                self.csrf_token = rotated
            response_text = e.response.text
            return {
                "error": f"HTTP {e.response.status_code}",
                "message": response_text,
                "auth_method": self.auth_method,
                "hint": (
                    "Refresh MERAKI_COOKIES and MERAKI_CSRF_TOKEN from an active dashboard session and run reload_credentials."
                    if e.response.status_code in (401, 403)
                    else "Internal API call failed"
                )
            }
        except httpx.TimeoutException:
            return {
                "error": "request_timeout",
                "message": f"Internal API request timed out for path: {path}",
            }
        except Exception as e:
            return {"error": str(e)}
    
    # Organization Methods
    async def _get_organizations(self) -> Dict:
        """Get all organizations"""
        organizations = await self._make_request("GET", "/organizations")
        if isinstance(organizations, list):
            return [
                {
                    "id": org.get("id"),
                    "name": org.get("name"),
                    "url": org.get("url"),
                }
                for org in organizations
                if isinstance(org, dict)
            ]
        return organizations
    
    # Network Methods
    async def _get_networks(self, org_id: str) -> Dict:
        """Get networks in organization"""
        return await self._make_request("GET", f"/organizations/{org_id}/networks")
    
    async def _get_network_devices(self, network_id: str) -> Dict:
        """Get devices in network"""
        return await self._make_request("GET", f"/networks/{network_id}/devices")

    async def _get_organization_devices(
        self,
        org_id: str,
        per_page: int = 1000,
        starting_after: Optional[str] = None,
        ending_before: Optional[str] = None,
        auto_paginate: bool = False,
        max_records: int = 5000,
    ) -> Dict:
        """List devices assigned to networks in an organization."""
        per_page = max(3, min(int(per_page), 5000))
        max_records = max(1, min(int(max_records), 5000))

        if not auto_paginate:
            query_params: Dict[str, Any] = {"perPage": per_page}
            if starting_after:
                query_params["startingAfter"] = starting_after
            if ending_before:
                query_params["endingBefore"] = ending_before
            query = urlencode(query_params)
            return await self._make_request("GET", f"/organizations/{org_id}/devices?{query}")

        devices: List[Dict[str, Any]] = []
        seen_serials: set[str] = set()
        next_starting_after = starting_after
        pages_fetched = 0
        active_ending_before = ending_before

        while len(devices) < max_records:
            this_page_size = min(per_page, max_records - len(devices))
            query_params = {"perPage": this_page_size}
            if next_starting_after:
                query_params["startingAfter"] = next_starting_after
            elif active_ending_before:
                query_params["endingBefore"] = active_ending_before

            query = urlencode(query_params)
            page = await self._make_request("GET", f"/organizations/{org_id}/devices?{query}")
            if not isinstance(page, list):
                return page

            pages_fetched += 1
            if not page:
                break

            for device in page:
                if not isinstance(device, dict):
                    continue
                serial = str(device.get("serial") or "").strip()
                if serial and serial in seen_serials:
                    continue
                if serial:
                    seen_serials.add(serial)
                devices.append(device)
                if len(devices) >= max_records:
                    break

            if len(page) < this_page_size:
                break

            last_device = page[-1]
            if not isinstance(last_device, dict):
                break
            last_serial = str(last_device.get("serial") or "").strip()
            if not last_serial:
                break

            # Meraki accepts device serial for organizations/{id}/devices startingAfter token.
            if last_serial == next_starting_after:
                break
            next_starting_after = last_serial
            active_ending_before = None

        return {
            "devices": devices,
            "count": len(devices),
            "pages_fetched": pages_fetched,
            "requested_max_records": max_records,
            "auto_paginate": True,
            "next_starting_after": next_starting_after if len(devices) >= max_records else None,
        }

    async def _get_organization_inventory_devices(
        self,
        org_id: str,
        per_page: int = 1000,
        starting_after: Optional[str] = None,
        ending_before: Optional[str] = None,
    ) -> Dict:
        """Get inventory devices for an organization."""
        per_page = max(3, min(int(per_page), 1000))
        query_params: Dict[str, Any] = {"perPage": per_page}
        if starting_after:
            query_params["startingAfter"] = starting_after
        if ending_before:
            query_params["endingBefore"] = ending_before
        query = urlencode(query_params)
        return await self._make_request(
            "GET",
            f"/organizations/{org_id}/inventory/devices?{query}"
        )

    async def _find_organization_device_by_serial(
        self,
        org_id: str,
        serial: str,
        per_page: int = 1000,
        max_pages: int = 100,
    ) -> Dict:
        """Find one organization device by serial using server-side pagination."""
        target_serial = str(serial or "").strip().upper()
        if not target_serial:
            return {"error": "serial is required"}

        per_page = max(3, min(int(per_page), 5000))
        max_pages = max(1, min(int(max_pages), 500))
        starting_after: Optional[str] = None
        scanned = 0

        for page_number in range(1, max_pages + 1):
            query = urlencode({"perPage": per_page, **({"startingAfter": starting_after} if starting_after else {})})
            page = await self._make_request("GET", f"/organizations/{org_id}/devices?{query}")
            if not isinstance(page, list):
                return page

            if not page:
                return {
                    "found": False,
                    "serial": target_serial,
                    "scanned_devices": scanned,
                    "pages_scanned": page_number,
                    "message": "Reached end of device list",
                }

            for device in page:
                if not isinstance(device, dict):
                    continue
                scanned += 1
                current_serial = str(device.get("serial") or "").strip().upper()
                if current_serial == target_serial:
                    node_id = None
                    device_url = str(device.get("url") or "")
                    node_match = re.search(r"/manage/nodes/new_list/(\d+)$", device_url)
                    if node_match:
                        node_id = node_match.group(1)
                    return {
                        "found": True,
                        "serial": target_serial,
                        "node_id": node_id,
                        "device": device,
                        "scanned_devices": scanned,
                        "pages_scanned": page_number,
                    }

            last_device = page[-1]
            if not isinstance(last_device, dict):
                break
            last_serial = str(last_device.get("serial") or "").strip()
            if not last_serial or last_serial == starting_after:
                break
            starting_after = last_serial

            if len(page) < per_page:
                break

        return {
            "found": False,
            "serial": target_serial,
            "scanned_devices": scanned,
            "pages_scanned": max_pages,
            "message": "Stopped at max_pages before finding serial",
            "next_starting_after": starting_after,
        }

    async def _get_organization_devices_statuses(
        self,
        org_id: str,
        per_page: int = 1000,
        starting_after: Optional[str] = None,
        ending_before: Optional[str] = None,
    ) -> Dict:
        """Get status for all organization devices."""
        per_page = max(3, min(int(per_page), 1000))
        query_params: Dict[str, Any] = {"perPage": per_page}
        if starting_after:
            query_params["startingAfter"] = starting_after
        if ending_before:
            query_params["endingBefore"] = ending_before
        query = urlencode(query_params)
        return await self._make_request(
            "GET",
            f"/organizations/{org_id}/devices/statuses?{query}"
        )
    
    async def _update_network(self, args: Dict) -> Dict:
        """Update network configuration"""
        network_id = args.pop("network_id")
        return await self._make_request("PUT", f"/networks/{network_id}", args)
    
    # Device Methods
    async def _get_device_status(self, serial: str) -> Dict:
        """Get device status"""
        return await self._make_request("GET", f"/devices/{serial}/statuses")
    
    async def _get_device_uplink_status(self, serial: str) -> Dict:
        """Get device uplink status"""
        return await self._make_request("GET", f"/devices/{serial}/uplink")
    
    async def _get_device_clients(self, serial: str, timespan: int) -> Dict:
        """Get clients connected to device"""
        return await self._make_request(
            "GET", 
            f"/devices/{serial}/clients?timespan={timespan}"
        )
    
    async def _update_device(self, args: Dict) -> Dict:
        """Update device configuration"""
        serial = args.pop("serial")
        return await self._make_request("PUT", f"/devices/{serial}", args)

    async def _get_device_internal_details(self, serial: str, node_id: Optional[str] = None) -> Dict:
        """Get dashboard internal device details including adminTags when available."""
        cleaned_serial = str(serial or "").strip()
        if not cleaned_serial:
            return {"error": "serial is required"}
        cleaned_node_id = str(node_id or "").strip()
        if cleaned_node_id:
            # Meraki GET uses numeric node_id, not serial; try nodes path first then devices path.
            result = await self._make_internal_request("GET", f"/internalAPI/nodes/{cleaned_node_id}")
            if not (isinstance(result, dict) and str(result.get("error", "")).startswith("HTTP 404")):
                return result
            result = await self._make_internal_request("GET", f"/internalAPI/devices/{cleaned_node_id}")
            if not (isinstance(result, dict) and str(result.get("error", "")).startswith("HTTP 404")):
                return result
        return await self._make_internal_request("GET", f"/internalAPI/devices/{cleaned_serial}")

    async def _update_device_admin_tags(self, args: Dict) -> Dict:
        """Update dashboard internal adminTags for a device."""
        serial = str(args.get("serial") or "").strip()
        if not serial:
            return {"error": "serial is required"}

        admin_tags = args.get("admin_tags")
        if not isinstance(admin_tags, list):
            return {"error": "admin_tags must be an array of strings"}

        cleaned_tags = [str(tag).strip() for tag in admin_tags if str(tag).strip()]
        payload = {"adminTags": cleaned_tags}
        update_result = await self._make_internal_request(
            "PUT",
            f"/internalAPI/devices/{serial}",
            payload,
        )

        if isinstance(update_result, dict) and update_result.get("error"):
            return update_result

        return {
            "success": True,
            "serial": serial,
            "admin_tags": cleaned_tags,
            "updated_via": "internal_api",
            "result": update_result,
        }

    async def _clear_device_admin_tags_by_serial(self, args: Dict) -> Dict:
        """Find device by serial then clear its internal adminTags in one operation."""
        org_id = str(args.get("organization_id") or "").strip()
        requested_serial = str(args.get("serial") or "").strip().upper()
        per_page = args.get("per_page", 1000)
        max_pages = args.get("max_pages", 100)
        verify_after = bool(args.get("verify_after", True))

        if not org_id:
            return {"error": "organization_id is required"}
        if not requested_serial:
            return {"error": "serial is required"}

        lookup_result = await self._find_organization_device_by_serial(
            org_id,
            requested_serial,
            per_page=per_page,
            max_pages=max_pages,
        )
        if not isinstance(lookup_result, dict):
            return {
                "error": "lookup_failed",
                "message": "Unexpected lookup response type",
            }

        if lookup_result.get("error"):
            return {
                "error": "lookup_failed",
                "lookup": lookup_result,
            }

        if not lookup_result.get("found"):
            return {
                "success": False,
                "organization_id": org_id,
                "requested_serial": requested_serial,
                "message": "Serial was not found in organization device list",
                "lookup": {
                    "found": False,
                    "pages_scanned": lookup_result.get("pages_scanned"),
                    "scanned_devices": lookup_result.get("scanned_devices"),
                    "next_starting_after": lookup_result.get("next_starting_after"),
                    "details": lookup_result.get("message"),
                },
            }

        matched_serial = str(lookup_result.get("serial") or requested_serial).strip().upper()
        clear_result = await self._update_device_admin_tags(
            {
                "serial": matched_serial,
                "admin_tags": [],
            }
        )

        if isinstance(clear_result, dict) and clear_result.get("error"):
            return {
                "success": False,
                "organization_id": org_id,
                "requested_serial": requested_serial,
                "matched_serial": matched_serial,
                "lookup": {
                    "pages_scanned": lookup_result.get("pages_scanned"),
                    "scanned_devices": lookup_result.get("scanned_devices"),
                    "node_id": lookup_result.get("node_id"),
                },
                "clear_result": clear_result,
            }

        response = {
            "success": True,
            "organization_id": org_id,
            "requested_serial": requested_serial,
            "matched_serial": matched_serial,
            "node_id": lookup_result.get("node_id"),
            "lookup": {
                "pages_scanned": lookup_result.get("pages_scanned"),
                "scanned_devices": lookup_result.get("scanned_devices"),
            },
            "clear_result": clear_result,
        }

        if verify_after:
            verification = await self._get_device_internal_details(matched_serial, node_id=lookup_result.get("node_id"))
            if isinstance(verification, dict) and not verification.get("error"):
                response["verification"] = {
                    "adminTags": verification.get("adminTags"),
                    "serial": verification.get("serial", matched_serial),
                }
            else:
                response["verification"] = verification

        return response
    
    # Monitoring Methods
    async def _get_network_health_alerts(self, network_id: str) -> Dict:
        """Get network health alerts"""
        return await self._make_request("GET", f"/networks/{network_id}/health/alerts")

    async def _get_network_events(
        self,
        network_id: str,
        product_type: Optional[str] = None,
        per_page: int = 100,
        starting_after: Optional[str] = None,
        ending_before: Optional[str] = None,
    ) -> Dict:
        """Get network events with optional product filter."""
        per_page = max(3, min(int(per_page), 1000))
        query_params: Dict[str, Any] = {"perPage": per_page}
        if product_type:
            query_params["productType"] = product_type
        if starting_after:
            query_params["startingAfter"] = starting_after
        if ending_before:
            query_params["endingBefore"] = ending_before
        query = urlencode(query_params)
        return await self._make_request("GET", f"/networks/{network_id}/events?{query}")
    
    async def _get_organization_uplink_statuses(self, org_id: str) -> Dict:
        """Get organization-wide uplink statuses"""
        return await self._make_request(
            "GET", 
            f"/organizations/{org_id}/uplinks/statuses"
        )
    
    # Client Methods
    async def _get_network_clients(self, network_id: str, timespan: int) -> Dict:
        """Get clients in network"""
        timespan = max(300, min(int(timespan), 86400))
        return await self._make_request(
            "GET",
            f"/networks/{network_id}/clients?timespan={timespan}&perPage=250"
        )
    
    async def _get_client_details(self, network_id: str, client_id: str) -> Dict:
        """Get client details"""
        return await self._make_request(
            "GET",
            f"/networks/{network_id}/clients/{client_id}"
        )
    
    # Wireless Methods
    async def _get_wireless_ssids(self, network_id: str) -> Dict:
        """Get wireless SSIDs"""
        return await self._make_request("GET", f"/networks/{network_id}/wireless/ssids")
    
    async def _update_wireless_ssid(self, args: Dict) -> Dict:
        """Update wireless SSID"""
        network_id = args.pop("network_id")
        number = args.pop("number")
        return await self._make_request(
            "PUT",
            f"/networks/{network_id}/wireless/ssids/{number}",
            args
        )
    
    # Agentic Workflow Methods
    async def _diagnose_connectivity_issue(self, args: Dict) -> Dict:
        """Intelligent multi-step connectivity diagnosis"""
        org_id = args["organization_id"]
        issue_desc = args["issue_description"]
        network_id = args.get("network_id")
        device_serial = args.get("device_serial")
        
        diagnosis = {
            "issue_description": issue_desc,
            "timestamp": datetime.now().isoformat(),
            "steps_performed": [],
            "findings": [],
            "recommendations": []
        }
        
        # Step 1: Check organization-wide uplink status
        diagnosis["steps_performed"].append("Checking organization uplink status")
        uplinks = await self._get_organization_uplink_statuses(org_id)
        
        if isinstance(uplinks, list):
            down_uplinks = [u for u in uplinks if u.get("status") != "active"]
            if down_uplinks:
                diagnosis["findings"].append({
                    "severity": "high",
                    "category": "uplink",
                    "message": f"Found {len(down_uplinks)} devices with inactive uplinks",
                    "devices": down_uplinks
                })
        
        # Step 2: If network specified, check network health
        if network_id:
            diagnosis["steps_performed"].append(f"Checking network health: {network_id}")
            alerts = await self._get_network_health_alerts(network_id)
            
            if isinstance(alerts, list) and len(alerts) > 0:
                diagnosis["findings"].append({
                    "severity": "medium",
                    "category": "alerts",
                    "message": f"Found {len(alerts)} active alerts",
                    "alerts": alerts
                })
            
            # Check network devices
            devices = await self._get_network_devices(network_id)
            if isinstance(devices, list):
                offline_devices = [d for d in devices if d.get("status") != "online"]
                if offline_devices:
                    diagnosis["findings"].append({
                        "severity": "high",
                        "category": "device_status",
                        "message": f"Found {len(offline_devices)} offline devices",
                        "devices": offline_devices
                    })
        
        # Step 3: If device specified, detailed device check
        if device_serial:
            diagnosis["steps_performed"].append(f"Checking device: {device_serial}")
            
            device_status = await self._get_device_status(device_serial)
            device_uplink = await self._get_device_uplink_status(device_serial)
            
            diagnosis["findings"].append({
                "severity": "info",
                "category": "device_details",
                "device_status": device_status,
                "uplink_status": device_uplink
            })
        
        # Generate recommendations
        if any(f["severity"] == "high" for f in diagnosis["findings"]):
            diagnosis["recommendations"].append(
                "Immediate action required: Check devices with inactive uplinks or offline status"
            )
        
        diagnosis["recommendations"].extend([
            "Review device logs for error patterns",
            "Verify physical connections and power",
            "Check for recent configuration changes",
            "Consider firmware updates if available"
        ])
        
        return diagnosis
    
    async def _automated_health_check(self, args: Dict) -> Dict:
        """Comprehensive automated health check"""
        org_id = args["organization_id"]
        include_recommendations = args.get("include_recommendations", True)
        
        health_report = {
            "organization_id": org_id,
            "timestamp": datetime.now().isoformat(),
            "summary": {},
            "network_health": [],
            "device_health": [],
            "recommendations": []
        }
        
        # Get all networks
        networks = await self._get_networks(org_id)
        
        if isinstance(networks, list):
            health_report["summary"]["total_networks"] = len(networks)
            
            for network in networks[:10]:  # Limit to first 10 for demo
                network_id = network["id"]
                
                # Check network alerts
                alerts = await self._get_network_health_alerts(network_id)
                
                # Check devices
                devices = await self._get_network_devices(network_id)
                
                network_health = {
                    "network_id": network_id,
                    "network_name": network.get("name"),
                    "alert_count": len(alerts) if isinstance(alerts, list) else 0,
                    "device_count": len(devices) if isinstance(devices, list) else 0,
                    "offline_devices": 0
                }
                
                if isinstance(devices, list):
                    network_health["offline_devices"] = len(
                        [d for d in devices if d.get("status") != "online"]
                    )
                
                health_report["network_health"].append(network_health)
        
        # Get uplink status
        uplinks = await self._get_organization_uplink_statuses(org_id)
        
        if isinstance(uplinks, list):
            health_report["summary"]["total_uplinks"] = len(uplinks)
            health_report["summary"]["inactive_uplinks"] = len(
                [u for u in uplinks if u.get("status") != "active"]
            )
        
        # Generate recommendations
        if include_recommendations:
            if health_report["summary"].get("inactive_uplinks", 0) > 0:
                health_report["recommendations"].append(
                    "Address inactive uplink connections immediately"
                )
            
            for network in health_report["network_health"]:
                if network["offline_devices"] > 0:
                    health_report["recommendations"].append(
                        f"Network '{network['network_name']}' has {network['offline_devices']} offline devices"
                    )
        
        return health_report

    async def _investigate_ssid_issue(self, args: Dict) -> Dict:
        """Focused SSID analysis for one network."""
        org_id = args["organization_id"]
        network_id = args["network_id"]
        ssid_name = args["ssid_name"]
        timespan = max(300, min(int(args.get("timespan", 7200)), 86400))

        result = {
            "organization_id": org_id,
            "network_id": network_id,
            "ssid_name": ssid_name,
            "timespan_seconds": timespan,
            "timestamp": datetime.now().isoformat(),
            "findings": [],
            "recommendations": []
        }

        ssids = await self._get_wireless_ssids(network_id)
        if not isinstance(ssids, list):
            return {
                "error": "Failed to fetch SSIDs",
                "details": ssids,
                "network_id": network_id,
                "ssid_name": ssid_name
            }

        target_ssid = None
        for ssid in ssids:
            if isinstance(ssid, dict) and str(ssid.get("name", "")).strip().lower() == ssid_name.strip().lower():
                target_ssid = ssid
                break

        if not target_ssid:
            available = [s.get("name") for s in ssids if isinstance(s, dict) and s.get("name")]
            return {
                "error": f"SSID '{ssid_name}' not found in network {network_id}",
                "available_ssids": available
            }

        result["findings"].append({
            "category": "ssid_config",
            "message": "SSID configuration retrieved",
            "ssid": {
                "number": target_ssid.get("number"),
                "name": target_ssid.get("name"),
                "enabled": target_ssid.get("enabled"),
                "authMode": target_ssid.get("authMode")
            }
        })

        if target_ssid.get("enabled") is False:
            result["findings"].append({
                "severity": "high",
                "category": "ssid_state",
                "message": f"SSID '{ssid_name}' is disabled"
            })
            result["recommendations"].append("Enable the SSID if clients are expected to connect.")

        alerts = await self._get_network_health_alerts(network_id)
        if isinstance(alerts, list):
            ssid_alerts = [a for a in alerts if ssid_name.lower() in json.dumps(a).lower()]
            result["findings"].append({
                "category": "health_alerts",
                "message": f"Found {len(ssid_alerts)} SSID-related alerts",
                "alerts": ssid_alerts
            })

        clients = await self._get_network_clients(network_id, timespan)
        if isinstance(clients, list):
            matching_clients = [
                c for c in clients
                if isinstance(c, dict) and str(c.get("ssid", "")).strip().lower() == ssid_name.strip().lower()
            ]
            result["findings"].append({
                "category": "client_summary",
                "message": f"{len(matching_clients)} clients seen on SSID in last {timespan} seconds",
                "client_count": len(matching_clients),
                "sample_clients": matching_clients[:20]
            })

            if len(matching_clients) == 0:
                result["recommendations"].append("No clients are visible on this SSID; verify broadcast, auth, VLAN, and DHCP path.")

        if not result["recommendations"]:
            result["recommendations"].append("No immediate critical issues found; continue monitoring SSID alerts and client experience.")

        return result
    
    async def _get_device_channel_utilization(self, args: Dict) -> Dict:
        """Get wireless device channel utilization statistics with flattened response."""
        org_id = args["organization_id"]
        serials = args.get("serials", [])
        timespan = int(args.get("timespan", 604800))
        interval = int(args.get("interval", 3600))
        
        if not serials:
            return {"error": "No serials provided", "organization_id": org_id}
        
        # Build query parameters
        serial_params = "&".join([f"serials[]={s}" for s in serials])
        endpoint = f"/organizations/{org_id}/wireless/devices/channelUtilization/byDevice?{serial_params}&timespan={timespan}&interval={interval}"
        
        raw_data = await self._make_request("GET", endpoint)
        
        # Flatten response to reduce nesting depth and improve readability
        flattened = {
            "organization_id": org_id,
            "serials": serials,
            "timespan": timespan,
            "interval": interval,
            "timestamp": datetime.now().isoformat(),
            "devices": {}
        }
        
        # Extract and flatten per-device data
        if isinstance(raw_data, list):
            for device in raw_data:
                if isinstance(device, dict):
                    serial = device.get("serial", "unknown")
                    flattened["devices"][serial] = {
                        "serial": serial,
                        "bands": {}
                    }
                    
                    # Flatten band data (2.4 GHz, 5 GHz, etc.)
                    for band_name, band_data in device.items():
                        if band_name == "serial":
                            continue
                        if isinstance(band_data, dict):
                            flattened["devices"][serial]["bands"][band_name] = {
                                "band": band_name,
                                "connection_types": {}
                            }
                            
                            # Flatten connection types (wifi, nonWifi, total)
                            for conn_type, conn_data in band_data.items():
                                if isinstance(conn_data, dict):
                                    percentage = conn_data.get("percentage", [])
                                    # Calculate average utilization for summary
                                    avg_util = 0
                                    if isinstance(percentage, list) and len(percentage) > 0:
                                        utilizations = [p.get("utilization", 0) for p in percentage if isinstance(p, dict)]
                                        if utilizations:
                                            avg_util = sum(utilizations) / len(utilizations)
                                    
                                    flattened["devices"][serial]["bands"][band_name]["connection_types"][conn_type] = {
                                        "type": conn_type,
                                        "average_utilization_percent": round(avg_util, 2),
                                        "data_points": len(percentage) if isinstance(percentage, list) else 0,
                                        "raw_percentage_data": percentage[:10] if isinstance(percentage, list) else []  # Limit to first 10 for brevity
                                    }
        
        return flattened
    
    async def _get_wireless_signal_quality_history(self, args: Dict) -> Dict:
        """Get wireless signal quality history for a device."""
        network_id = args["network_id"]
        device_serial = args["device_serial"]
        timespan = int(args.get("timespan", 604800))
        resolution = int(args.get("resolution", 3600))
        
        endpoint = f"/networks/{network_id}/wireless/signalQualityHistory?deviceSerial={device_serial}&timespan={timespan}&resolution={resolution}&autoResolution=false"
        
        result = await self._make_request("GET", endpoint)
        return {
            "network_id": network_id,
            "device_serial": device_serial,
            "timespan": timespan,
            "resolution": resolution,
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _get_wireless_failed_connections(self, args: Dict) -> Dict:
        """Get failed wireless connection attempts within a time range."""
        network_id = args["network_id"]
        t0 = args["t0"]
        t1 = args["t1"]
        
        endpoint = f"/networks/{network_id}/wireless/failedConnections?t0={t0}&t1={t1}"
        
        result = await self._make_request("GET", endpoint)
        return {
            "network_id": network_id,
            "start_time": t0,
            "end_time": t1,
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _get_wireless_roaming_stats(self, args: Dict) -> Dict:
        """Get wireless roaming statistics for networks."""
        org_id = args["organization_id"]
        network_ids = args.get("network_ids", [])
        timespan = int(args.get("timespan", 86400))
        interval = int(args.get("interval", 3600))
        
        if not network_ids:
            return {"error": "No network IDs provided", "organization_id": org_id}
        
        # Build query parameters
        network_params = "&".join([f"networkIds[]={nid}" for nid in network_ids])
        endpoint = f"/organizations/{org_id}/wireless/roaming/byNetwork/byInterval?{network_params}&timespan={timespan}&interval={interval}"
        
        result = await self._make_request("GET", endpoint)
        return {
            "organization_id": org_id,
            "network_ids": network_ids,
            "timespan": timespan,
            "interval": interval,
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _get_wireless_rf_profiles(self, args: Dict) -> Dict:
        """Get RF (Radio Frequency) profiles configured for a network."""
        network_id = args["network_id"]
        
        endpoint = f"/networks/{network_id}/wireless/rfProfiles/indoor"
        
        result = await self._make_request("GET", endpoint)
        return {
            "network_id": network_id,
            "rf_profiles": result,
            "timestamp": datetime.now().isoformat()
        }
    
    async def run_stdio(self):
        """Run the MCP server over stdio (local desktop clients)."""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="meraki-assistant",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

    async def run_http(self, host: str = "127.0.0.1", port: int = 3000, path: str = "/mcp"):
        """Run the MCP server over streamable HTTP (for remote integrations)."""
        auth_token = (os.getenv("MCP_AUTH_TOKEN") or "").strip()
        if auth_token:
            self._log("http_auth enabled via MCP_AUTH_TOKEN")

        normalized_path = path if path.startswith("/") else f"/{path}"
        session_manager = StreamableHTTPSessionManager(app=self.server, stateless=False)
        normalized_base = normalized_path.rstrip("/") or "/"
        alias_base = "/mc" if normalized_base == "/mcp" else None

        def _is_request_authorized(scope: Dict[str, Any]) -> bool:
            if not auth_token:
                return True

            raw_headers = scope.get("headers", [])
            headers: Dict[str, str] = {}
            for key, value in raw_headers:
                try:
                    headers[key.decode("latin-1").lower()] = value.decode("latin-1")
                except Exception:
                    continue

            x_token = headers.get("x-mcp-auth-token", "").strip()
            if x_token and secrets.compare_digest(x_token, auth_token):
                return True

            auth_header = headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                bearer_token = auth_header[7:].strip()
                if bearer_token and secrets.compare_digest(bearer_token, auth_token):
                    return True

            return False

        class _NormalizeMcpPathMiddleware:
            def __init__(self, app, base_path: str, alias_path: Optional[str] = None):
                self.app = app
                self.base_path = base_path
                self.alias_path = alias_path

            async def __call__(self, scope, receive, send):
                if scope.get("type") == "http" and scope.get("path") == self.base_path:
                    scope = dict(scope)
                    scope["path"] = f"{self.base_path}/"
                elif (
                    self.alias_path
                    and scope.get("type") == "http"
                    and scope.get("path") == self.alias_path
                ):
                    scope = dict(scope)
                    scope["path"] = f"{self.alias_path}/"
                await self.app(scope, receive, send)

        @asynccontextmanager
        async def lifespan(app: Starlette):
            async with session_manager.run():
                yield

        async def mcp_asgi(scope, receive, send):
            if scope.get("type") == "http" and not _is_request_authorized(scope):
                response = JSONResponse(
                    {
                        "error": "unauthorized",
                        "message": "Missing or invalid MCP auth token",
                    },
                    status_code=401,
                )
                await response(scope, receive, send)
                return
            await session_manager.handle_request(scope, receive, send)

        async def mcp_health(_: Any):
            # Some hosted clients probe the endpoint with GET/HEAD/OPTIONS before MCP POST.
            return JSONResponse(
                {
                    "status": "ok",
                    "mcp": True,
                    "path": normalized_base,
                    "transport": "streamable-http",
                }
            )

        routes = [
            Route(normalized_base, endpoint=mcp_health, methods=["GET", "HEAD", "OPTIONS"]),
            Route(f"{normalized_base}/", endpoint=mcp_health, methods=["GET", "HEAD", "OPTIONS"]),
            Mount(f"{normalized_base}/", app=mcp_asgi),
        ]
        if alias_base:
            routes.append(Route(alias_base, endpoint=mcp_health, methods=["GET", "HEAD", "OPTIONS"]))
            routes.append(Route(f"{alias_base}/", endpoint=mcp_health, methods=["GET", "HEAD", "OPTIONS"]))
            routes.append(Mount(f"{alias_base}/", app=mcp_asgi))

        app = Starlette(
            routes=routes,
            lifespan=lifespan,
        )
        app.router.redirect_slashes = False
        app_asgi = _NormalizeMcpPathMiddleware(app, normalized_base, alias_base)

        uvicorn_server = uvicorn.Server(
            uvicorn.Config(app_asgi, host=host, port=port, log_level="info")
        )
        await uvicorn_server.serve()

    async def run(self, transport: str = "stdio", host: str = "127.0.0.1", port: int = 3000, path: str = "/mcp"):
        """Run the MCP server with selectable transport mode."""
        if transport == "http":
            await self.run_http(host=host, port=port, path=path)
            return
        await self.run_stdio()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Cisco Meraki MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport mode: stdio for local clients, http for remote integrations",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HTTP_HOST", "127.0.0.1"),
        help="HTTP bind host (used when --transport http)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_HTTP_PORT", "3000")),
        help="HTTP bind port (used when --transport http)",
    )
    parser.add_argument(
        "--path",
        default=os.getenv("MCP_HTTP_PATH", "/mcp"),
        help="HTTP MCP path (used when --transport http)",
    )
    args = parser.parse_args()

    server = MerakiMCPServer()
    await server.run(
        transport=args.transport,
        host=args.host,
        port=args.port,
        path=args.path,
    )


if __name__ == "__main__":
    asyncio.run(main())
