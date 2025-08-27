#!/usr/bin/env python3
"""
Test script for MCP Gateway OAuth authentication
"""

from fastmcp import Client
import asyncio

async def main():
    # Your MCP gateway URL (note the port 8080, not 8000)
    gateway_url = "http://localhost:8080/mcp/"
    
    print("🔐 Testing MCP Gateway OAuth Authentication...")
    print(f"📡 Connecting to: {gateway_url}")
    
    try:
        # The client will automatically handle OAuth flow
        async with Client(gateway_url, auth="oauth") as client:
            print("✅ OAuth authentication successful!")
            
            # Try to extract and display the bearer token for MCP Inspector
            try:
                # Check if we can access the transport's auth headers
                if hasattr(client, 'transport') and hasattr(client.transport, '_auth'):
                    auth_obj = client.transport._auth
                    if hasattr(auth_obj, 'token'):
                        print(f"\n🔑 Bearer Token for MCP Inspector:")
                        print(f"   {auth_obj.token}")
                        print(f"   Copy this token to the MCP Inspector 'Bearer Token' field")
                elif hasattr(client, '_session') and hasattr(client._session, 'headers'):
                    auth_header = client._session.headers.get('Authorization', '')
                    if auth_header.startswith('Bearer '):
                        token = auth_header[7:]  # Remove 'Bearer ' prefix
                        print(f"\n🔑 Bearer Token for MCP Inspector:")
                        print(f"   {token}")
                        print(f"   Copy this token to the MCP Inspector 'Bearer Token' field")
                else:
                    print("\n🔑 Could not extract bearer token from client (auth may be handled internally)")
            except Exception as e:
                print(f"\n🔑 Could not extract bearer token: {e}")
            
            # List available tools (these are your discovered agents)
            print("\n📋 Available agent tools:")
            tools = await client.list_tools()
            
            if not tools:
                print("ℹ️  No agent tools available yet")
                print("   Make sure some agents are running and discovered")
                return
            
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
            
            # Test calling the first available agent tool
            if tools:
                tool_name = tools[0].name
                print(f"\n🔧 Testing tool: {tool_name}")
                
                # Call the agent tool (this will go through your OAuth-authenticated A2A flow)
                result = await client.call_tool(tool_name, {"message": "Hello from OAuth authenticated client!"})
                print(f"📤 Agent response: {result}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Troubleshooting:")
        print("1. Make sure MCP Gateway is running with enable_authentication: true")
        print("2. Verify Azure App registration redirect URI: http://localhost:8080/mcp/auth/callback")
        print("3. Check environment variables AZURE_CLIENT_ID and AZURE_CLIENT_SECRET are set")
        print("4. Ensure some agents are running for the gateway to discover")

if __name__ == "__main__":
    asyncio.run(main())