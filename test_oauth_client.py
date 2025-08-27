#!/usr/bin/env python3
"""
Test client for the standalone OAuth server
"""

from fastmcp import Client
import asyncio

async def main():
    # Test server URL (port 3001 to avoid conflicts)
    server_url = "http://localhost:8080/mcp/"
    
    print("🔐 Testing standalone OAuth server...")
    print(f"📡 Connecting to: {server_url}")
    
    try:
        # Use OAuth authentication
        async with Client(server_url, auth="oauth") as client:
            print("✅ OAuth authentication successful!")
            
            # Test ping
            try:
                await client.ping()
                print("✅ Ping successful!")
            except Exception as e:
                print(f"❌ Ping failed: {e}")
            
            # List available tools
            print("\n📋 Available tools:")
            tools = await client.list_tools()
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
            
            if not tools:
                print("ℹ️  No tools found")
                return
            
            # Test the simple tool
            print(f"\n🔧 Testing 'test_tool':")
            try:
                result = await client.call_tool("test_tool", {"message": "Hello from test client!"})
                print(f"📤 Response: {result}")
            except Exception as e:
                print(f"❌ test_tool failed: {e}")
            
            # Test user info tool
            print(f"\n🔧 Testing 'get_user_info':")
            try:
                result = await client.call_tool("get_user_info", {})
                print(f"📤 User info: {result}")
            except Exception as e:
                print(f"❌ get_user_info failed: {e}")
            
            # Test bearer token tool for MCP Inspector
            print(f"\n🔧 Testing 'get_bearer_token':")
            try:
                result = await client.call_tool("get_bearer_token", {})
                print(f"📤 Bearer token result: {result}")
                # Try to extract the token from the response
                if hasattr(result, 'data') and isinstance(result.data, dict):
                    bearer_token = result.data.get('bearer_token')
                    if bearer_token:
                        print(f"\n🔑 Bearer Token for MCP Inspector:")
                        print(f"   {bearer_token}")
                        print(f"   Copy this token to the MCP Inspector 'Bearer Token' field")
            except Exception as e:
                print(f"❌ get_bearer_token failed: {e}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Troubleshooting:")
        print("1. Make sure test_oauth_server.py is running")
        print("2. Verify Azure App has redirect URI: http://localhost:3001/mcp/auth/callback")
        print("3. Check AZURE_CLIENT_ID and AZURE_CLIENT_SECRET are set")

if __name__ == "__main__":
    asyncio.run(main())