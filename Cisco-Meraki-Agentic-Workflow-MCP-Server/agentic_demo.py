"""
Interactive example demonstrating agentic workflow with the Meraki MCP Server
This simulates how an AI assistant would use the tools
"""

import asyncio
import json
from datetime import datetime


class AgenticAssistant:
    """Simulates an AI assistant using the MCP server"""
    
    def __init__(self, server):
        self.server = server
        self.context = {}
    
    async def handle_user_request(self, user_input: str):
        """Process user request and execute appropriate workflow"""
        
        print(f"\n{'='*60}")
        print(f"USER: {user_input}")
        print(f"{'='*60}\n")
        
        # Simulate intent understanding and tool selection
        if "slow" in user_input.lower() or "connectivity" in user_input.lower():
            await self._handle_connectivity_issue(user_input)
        
        elif "health check" in user_input.lower() or "status" in user_input.lower():
            await self._handle_health_check()
        
        elif "show" in user_input.lower() or "list" in user_input.lower():
            await self._handle_discovery()
        
        else:
            print("ASSISTANT: I can help you with:")
            print("- Network discovery and device listing")
            print("- Connectivity troubleshooting")
            print("- Health checks and monitoring")
            print("- Configuration management")
    
    async def _handle_discovery(self):
        """Handle discovery requests"""
        print("ASSISTANT: Let me discover your Meraki infrastructure...\n")
        
        # Step 1: Get organizations
        print("🔍 Step 1: Discovering organizations...")
        orgs = await self.server._get_organizations()
        
        if isinstance(orgs, list):
            print(f"   ✓ Found {len(orgs)} organization(s)")
            for org in orgs:
                print(f"     - {org['name']} (ID: {org['id']})")
            
            # Store in context
            self.context["organizations"] = orgs
            
            # Step 2: Get networks for first org
            if len(orgs) > 0:
                org_id = orgs[0]["id"]
                print(f"\n🔍 Step 2: Discovering networks in {orgs[0]['name']}...")
                
                networks = await self.server._get_networks(org_id)
                
                if isinstance(networks, list):
                    print(f"   ✓ Found {len(networks)} network(s)")
                    for net in networks[:5]:  # Show first 5
                        print(f"     - {net['name']} (ID: {net['id']})")
                    
                    self.context["networks"] = networks
                    
                    # Step 3: Show devices in first network
                    if len(networks) > 0:
                        network_id = networks[0]["id"]
                        print(f"\n🔍 Step 3: Discovering devices in {networks[0]['name']}...")
                        
                        devices = await self.server._get_network_devices(network_id)
                        
                        if isinstance(devices, list):
                            print(f"   ✓ Found {len(devices)} device(s)")
                            for device in devices:
                                status_icon = "🟢" if device.get("status") == "online" else "🔴"
                                print(f"     {status_icon} {device.get('name', 'Unnamed')} "
                                      f"({device.get('model', 'Unknown')}) - {device.get('serial')}")
        
        print("\nASSISTANT: Discovery complete! What would you like to do next?")
    
    async def _handle_connectivity_issue(self, issue_description: str):
        """Handle connectivity troubleshooting"""
        print("ASSISTANT: I'll help you diagnose this connectivity issue.\n")
        print("This is a multi-step intelligent workflow:\n")
        
        # Get organization from context or discover it
        if "organizations" not in self.context:
            orgs = await self.server._get_organizations()
            if isinstance(orgs, list) and len(orgs) > 0:
                self.context["organizations"] = orgs
        
        if "organizations" in self.context and len(self.context["organizations"]) > 0:
            org = self.context["organizations"][0]
            org_id = org["id"]
            
            # Get network from context or use first available
            network_id = None
            if "networks" in self.context and len(self.context["networks"]) > 0:
                network_id = self.context["networks"][0]["id"]
            
            print("🔧 Running diagnostic workflow...")
            print("   This will check:")
            print("   - Organization-wide uplink status")
            print("   - Network health alerts")
            print("   - Device connectivity")
            print("   - Client connections")
            print()
            
            # Run diagnosis
            result = await self.server._diagnose_connectivity_issue({
                "organization_id": org_id,
                "issue_description": issue_description,
                "network_id": network_id
            })
            
            # Present results in user-friendly format
            print("="*60)
            print("DIAGNOSTIC REPORT")
            print("="*60)
            print(f"\nIssue: {result.get('issue_description')}")
            print(f"Analyzed at: {result.get('timestamp')}")
            print(f"\nSteps Performed:")
            for step in result.get('steps_performed', []):
                print(f"  ✓ {step}")
            
            print(f"\nFindings ({len(result.get('findings', []))}):")
            for finding in result.get('findings', []):
                severity = finding.get('severity', 'info').upper()
                icon = "🔴" if severity == "HIGH" else "🟡" if severity == "MEDIUM" else "🔵"
                print(f"\n{icon} {severity}: {finding.get('message', finding.get('category'))}")
            
            print(f"\nRecommendations:")
            for i, rec in enumerate(result.get('recommendations', []), 1):
                print(f"  {i}. {rec}")
            
            print("\n" + "="*60)
            
            print("\nASSISTANT: I've completed the diagnosis. Would you like me to:")
            print("- Investigate any specific finding in more detail")
            print("- Help implement one of the recommendations")
            print("- Run additional diagnostics")
    
    async def _handle_health_check(self):
        """Handle health check request"""
        print("ASSISTANT: I'll run a comprehensive health check on your infrastructure.\n")
        
        # Get organization
        if "organizations" not in self.context:
            orgs = await self.server._get_organizations()
            if isinstance(orgs, list) and len(orgs) > 0:
                self.context["organizations"] = orgs
        
        if "organizations" in self.context and len(self.context["organizations"]) > 0:
            org = self.context["organizations"][0]
            org_id = org["id"]
            
            print(f"🏥 Running health check for: {org['name']}")
            print("   This comprehensive scan will check:")
            print("   - All networks")
            print("   - All devices")
            print("   - Uplink connectivity")
            print("   - Active alerts")
            print()
            
            result = await self.server._automated_health_check({
                "organization_id": org_id,
                "include_recommendations": True
            })
            
            # Present results
            print("="*60)
            print("HEALTH CHECK REPORT")
            print("="*60)
            print(f"\nOrganization: {org['name']}")
            print(f"Generated: {result.get('timestamp')}")
            
            summary = result.get('summary', {})
            print(f"\nSUMMARY:")
            print(f"  Networks: {summary.get('total_networks', 0)}")
            print(f"  Uplinks: {summary.get('total_uplinks', 0)}")
            print(f"  Inactive Uplinks: {summary.get('inactive_uplinks', 0)}")
            
            print(f"\nNETWORK HEALTH:")
            for net_health in result.get('network_health', [])[:5]:
                status_icon = "🟢" if net_health.get('offline_devices', 0) == 0 else "🔴"
                print(f"  {status_icon} {net_health.get('network_name')}")
                print(f"     Devices: {net_health.get('device_count')}, "
                      f"Offline: {net_health.get('offline_devices')}, "
                      f"Alerts: {net_health.get('alert_count')}")
            
            if result.get('recommendations'):
                print(f"\nRECOMMENDATIONS:")
                for i, rec in enumerate(result.get('recommendations', []), 1):
                    print(f"  {i}. {rec}")
            
            print("\n" + "="*60)
            
            print("\nASSISTANT: Health check complete! I can help you:")
            print("- Address any issues found")
            print("- Schedule regular health checks")
            print("- Set up monitoring alerts")


async def demo():
    """Run interactive demo"""
    from server import MerakiMCPServer
    import os
    
    if not os.getenv("MERAKI_API_KEY"):
        print("ERROR: Please set MERAKI_API_KEY environment variable")
        return
    
    print("="*60)
    print("MERAKI MCP SERVER - AGENTIC WORKFLOW DEMO")
    print("="*60)
    print("\nThis demo simulates how an AI assistant uses the MCP server")
    print("to help customers with network management.\n")
    
    server = MerakiMCPServer()
    assistant = AgenticAssistant(server)
    
    # Simulate conversation flow
    conversations = [
        "Show me my Meraki networks",
        "Our office WiFi has been slow since this morning",
        "Run a health check on my organization"
    ]
    
    for user_input in conversations:
        await assistant.handle_user_request(user_input)
        await asyncio.sleep(1)  # Pause between requests
        print("\n" + "-"*60 + "\n")
    
    print("="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print("\nThis demonstrates how the agentic workflows:")
    print("✓ Understand user intent")
    print("✓ Execute multi-step diagnostics")
    print("✓ Provide actionable recommendations")
    print("✓ Maintain context across conversations")
    print("\nTry it yourself with your MCP client!")


if __name__ == "__main__":
    asyncio.run(demo())
