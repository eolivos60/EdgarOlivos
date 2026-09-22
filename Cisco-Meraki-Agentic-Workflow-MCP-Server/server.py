#!/usr/bin/env python3
"""
Cisco Meraki MCP Server - Agentic Troubleshooting and Configuration Assistant
This MCP server provides intelligent tools for Cisco Meraki network management.
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Sequence
from datetime import datetime, timedelta

# MCP SDK imports
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# HTTP client for Meraki API
import httpx


class MerakiMCPServer:
    """MCP Server for Cisco Meraki troubleshooting and configuration"""
    
    def __init__(self):
        self.server = Server("meraki-assistant")
        self.api_key: Optional[str] = None
        self.base_url = "https://api.meraki.com/api/v1"
        self.client: Optional[httpx.AsyncClient] = None
        
        # Agentic workflow state
        self.workflow_context: Dict[str, Any] = {}
        
        # Setup handlers
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup MCP protocol handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """List available Meraki troubleshooting and configuration tools"""
            return [
                # Organization Management
                types.Tool(
                    name="get_organizations",
                    description="Get all organizations accessible with the API key. First step in workflow.",
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
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict
        ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
            """Handle tool execution"""
            
            if not self.client:
                self.api_key = os.getenv("MERAKI_API_KEY")
                if not self.api_key:
                    return [types.TextContent(
                        type="text",
                        text="Error: MERAKI_API_KEY environment variable not set"
                    )]
                
                self.client = httpx.AsyncClient(
                    headers={
                        "X-Cisco-Meraki-API-Key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    timeout=30.0
                )
            
            try:
                # Route to appropriate handler
                if name == "get_organizations":
                    result = await self._get_organizations()
                
                elif name == "get_networks":
                    result = await self._get_networks(arguments["organization_id"])
                
                elif name == "get_network_devices":
                    result = await self._get_network_devices(arguments["network_id"])
                
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
                
                else:
                    result = {"error": f"Unknown tool: {name}"}
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
                
            except Exception as e:
                return [types.TextContent(
                    type="text",
                    text=f"Error executing {name}: {str(e)}"
                )]
    
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
            return {
                "error": f"HTTP {e.response.status_code}",
                "message": e.response.text
            }
        except Exception as e:
            return {"error": str(e)}
    
    # Organization Methods
    async def _get_organizations(self) -> Dict:
        """Get all organizations"""
        return await self._make_request("GET", "/organizations")
    
    # Network Methods
    async def _get_networks(self, org_id: str) -> Dict:
        """Get networks in organization"""
        return await self._make_request("GET", f"/organizations/{org_id}/networks")
    
    async def _get_network_devices(self, network_id: str) -> Dict:
        """Get devices in network"""
        return await self._make_request("GET", f"/networks/{network_id}/devices")
    
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
    
    # Monitoring Methods
    async def _get_network_health_alerts(self, network_id: str) -> Dict:
        """Get network health alerts"""
        return await self._make_request("GET", f"/networks/{network_id}/health/alerts")
    
    async def _get_organization_uplink_statuses(self, org_id: str) -> Dict:
        """Get organization-wide uplink statuses"""
        return await self._make_request(
            "GET", 
            f"/organizations/{org_id}/uplinks/statuses"
        )
    
    # Client Methods
    async def _get_network_clients(self, network_id: str, timespan: int) -> Dict:
        """Get clients in network"""
        return await self._make_request(
            "GET",
            f"/networks/{network_id}/clients?timespan={timespan}"
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
    
    async def run(self):
        """Run the MCP server"""
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


async def main():
    """Main entry point"""
    server = MerakiMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
