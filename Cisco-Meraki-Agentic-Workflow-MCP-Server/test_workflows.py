"""
Example usage scripts for testing the Meraki MCP Server
Run these after setting up your API key
"""

import asyncio
import json
from server import MerakiMCPServer


async def test_basic_discovery():
    """Test basic discovery workflow"""
    print("=== Testing Basic Discovery ===\n")
    
    server = MerakiMCPServer()
    
    # Note: In actual MCP usage, the server runs via stdio
    # This is for testing the internal methods directly
    
    # Get organizations
    print("1. Getting organizations...")
    orgs = await server._get_organizations()
    print(json.dumps(orgs, indent=2))
    
    if isinstance(orgs, list) and len(orgs) > 0:
        org_id = orgs[0]["id"]
        print(f"\n2. Getting networks for org {org_id}...")
        networks = await server._get_networks(org_id)
        print(json.dumps(networks, indent=2))
        
        if isinstance(networks, list) and len(networks) > 0:
            network_id = networks[0]["id"]
            print(f"\n3. Getting devices for network {network_id}...")
            devices = await server._get_network_devices(network_id)
            print(json.dumps(devices, indent=2))


async def test_health_check():
    """Test automated health check"""
    print("\n=== Testing Automated Health Check ===\n")
    
    server = MerakiMCPServer()
    
    # Get first organization
    orgs = await server._get_organizations()
    
    if isinstance(orgs, list) and len(orgs) > 0:
        org_id = orgs[0]["id"]
        
        print(f"Running health check for organization {org_id}...")
        
        result = await server._automated_health_check({
            "organization_id": org_id,
            "include_recommendations": True
        })
        
        print(json.dumps(result, indent=2))


async def test_connectivity_diagnosis():
    """Test connectivity diagnosis workflow"""
    print("\n=== Testing Connectivity Diagnosis ===\n")
    
    server = MerakiMCPServer()
    
    # Get first organization
    orgs = await server._get_organizations()
    
    if isinstance(orgs, list) and len(orgs) > 0:
        org_id = orgs[0]["id"]
        
        # Get first network
        networks = await server._get_networks(org_id)
        
        if isinstance(networks, list) and len(networks) > 0:
            network_id = networks[0]["id"]
            
            print(f"Diagnosing connectivity for network {network_id}...")
            
            result = await server._diagnose_connectivity_issue({
                "organization_id": org_id,
                "network_id": network_id,
                "issue_description": "Users reporting slow WiFi performance"
            })
            
            print(json.dumps(result, indent=2))


async def test_device_troubleshooting():
    """Test device-specific troubleshooting"""
    print("\n=== Testing Device Troubleshooting ===\n")
    
    server = MerakiMCPServer()
    
    # Get organizations
    orgs = await server._get_organizations()
    
    if isinstance(orgs, list) and len(orgs) > 0:
        org_id = orgs[0]["id"]
        
        # Get networks
        networks = await server._get_networks(org_id)
        
        if isinstance(networks, list) and len(networks) > 0:
            network_id = networks[0]["id"]
            
            # Get devices
            devices = await server._get_network_devices(network_id)
            
            if isinstance(devices, list) and len(devices) > 0:
                serial = devices[0]["serial"]
                
                print(f"Checking device {serial}...")
                
                # Get device status
                status = await server._get_device_status(serial)
                print("\nDevice Status:")
                print(json.dumps(status, indent=2))
                
                # Get uplink status
                uplink = await server._get_device_uplink_status(serial)
                print("\nUplink Status:")
                print(json.dumps(uplink, indent=2))
                
                # Get connected clients
                clients = await server._get_device_clients(serial, 3600)
                print(f"\nConnected Clients (last hour):")
                print(json.dumps(clients, indent=2))


async def main():
    """Run all tests"""
    import os
    
    # Check for API key
    if not os.getenv("MERAKI_API_KEY"):
        print("ERROR: MERAKI_API_KEY environment variable not set!")
        print("Set it with: export MERAKI_API_KEY=your_key_here")
        return
    
    try:
        await test_basic_discovery()
        await test_health_check()
        await test_connectivity_diagnosis()
        await test_device_troubleshooting()
        
        print("\n=== All Tests Complete ===")
        
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
