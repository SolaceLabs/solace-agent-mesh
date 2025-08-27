#!/usr/bin/env python3
"""
Simple Python client to test the OAuth-enabled MCP Gateway
"""

from fastmcp import Client
import asyncio
import json

async def test_mcp_server():
    """Test the MCP server with OAuth authentication"""
    
    # Your MCP Gateway URL
    server_url = "http://localhost:8080/mcp/"
    
    print("🔐 Testing MCP Gateway with OAuth...")
    print(f"📡 Server: {server_url}")
    print("-" * 50)
    
    try:
        # Connect with OAuth authentication
        async with Client(server_url, auth="oauth") as client:
            print("✅ OAuth authentication successful!")
            
            # Test 1: Ping the server
            print("\n1️⃣ Testing ping...")
            try:
                await client.ping()
                print("   ✅ Ping successful")
            except Exception as e:
                print(f"   ❌ Ping failed: {e}")
            
            # Test 2: List available tools
            print("\n2️⃣ Listing available tools...")
            try:
                tools = await client.list_tools()
                if tools:
                    print(f"   ✅ Found {len(tools)} tools:")
                    for i, tool in enumerate(tools, 1):
                        print(f"      {i}. {tool.name}")
                        print(f"         📝 {tool.description}")
                else:
                    print("   ℹ️ No tools available")
                    return
            except Exception as e:
                print(f"   ❌ Failed to list tools: {e}")
                return
            
            # Test 3: List resources (if any)
            print("\n3️⃣ Listing available resources...")
            try:
                resources = await client.list_resources()
                if resources:
                    print(f"   ✅ Found {len(resources)} resources:")
                    for i, resource in enumerate(resources, 1):
                        print(f"      {i}. {resource.uri}")
                        print(f"         📝 {resource.description or 'No description'}")
                else:
                    print("   ℹ️ No resources available")
            except Exception as e:
                print(f"   ❌ Failed to list resources: {e}")
            
            # Test 4: Try calling a tool
            if tools:
                print("\n4️⃣ Testing tool execution...")
                # Test with the first available tool
                tool_to_test = tools[0]
                print(f"   🔧 Testing tool: {tool_to_test.name}")
                
                try:
                    # Try with a simple message parameter
                    result = await client.call_tool(
                        tool_to_test.name, 
                        {"message": "Hello from simple test client!"}
                    )
                    
                    print("   ✅ Tool call successful!")
                    print(f"   📤 Result type: {type(result.data)}")
                    
                    # Pretty print the result
                    if isinstance(result.data, dict):
                        print("   📋 Result data:")
                        for key, value in result.data.items():
                            print(f"      {key}: {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
                    else:
                        result_str = str(result.data)
                        print(f"   📋 Result: {result_str[:200]}{'...' if len(result_str) > 200 else ''}")
                        
                except Exception as e:
                    print(f"   ❌ Tool call failed: {e}")
                    # Try with no parameters
                    try:
                        print("   🔄 Retrying with no parameters...")
                        result = await client.call_tool(tool_to_test.name, {})
                        print("   ✅ Tool call successful (no params)!")
                        print(f"   📤 Result: {str(result.data)[:200]}...")
                    except Exception as e2:
                        print(f"   ❌ Tool call failed again: {e2}")
            
            print("\n🎉 Test completed successfully!")
            
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\n💡 Troubleshooting:")
        print("1. Make sure MCP Gateway is running on port 8080")
        print("2. Verify OAuth is enabled in mcp_gateway_config.yaml")
        print("3. Check Azure App registration settings")
        print("4. Ensure environment variables AZURE_CLIENT_ID and AZURE_CLIENT_SECRET are set")

if __name__ == "__main__":
    print("🚀 Simple MCP Test Client")
    print("=" * 50)
    asyncio.run(test_mcp_server())