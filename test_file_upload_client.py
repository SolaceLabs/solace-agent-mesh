#!/usr/bin/env python3
"""
Test client for MCP Gateway file upload functionality (no OAuth)
"""

from fastmcp import Client
import asyncio
import base64
import json

async def create_test_files():
    """Create test files for upload"""
    
    # Test file 1: Simple text file
    test_content_1 = b"Hello, this is a test file from MCP client!"
    test_filename_1 = "test.txt"
    
    # Test file 2: JSON data
    test_content_2 = json.dumps({
        "message": "This is test data",
        "timestamp": "2024-01-01T00:00:00Z",
        "numbers": [1, 2, 3, 4, 5]
    }, indent=2).encode('utf-8')
    test_filename_2 = "data.json"
    
    # Test file 3: Small binary data
    test_content_3 = bytes([0x48, 0x65, 0x6C, 0x6C, 0x6F, 0x20, 0x42, 0x69, 0x6E, 0x61, 0x72, 0x79])
    test_filename_3 = "binary.dat"
    
    # Test both base64 and raw content to match what Claude might send
    files = [
        {
            "name": test_filename_1,
            "content": base64.b64encode(test_content_1).decode('utf-8')  # Base64 encoded
        },
        {
            "name": test_filename_2,
            "content": test_content_2.decode('utf-8')  # Raw text content (like Claude might send)
        },
        {
            "name": test_filename_3,
            "content": base64.b64encode(test_content_3).decode('utf-8')  # Base64 encoded binary
        }
    ]
    
    print("📁 Created test files:")
    print(f"  1. {test_filename_1} ({len(test_content_1)} bytes)")
    print(f"  2. {test_filename_2} ({len(test_content_2)} bytes)")
    print(f"  3. {test_filename_3} ({len(test_content_3)} bytes)")
    
    return files

async def main():
    # Test server URL (assuming MCP Gateway is running on default port)
    server_url = "http://localhost:8080/mcp/"
    
    print("🚀 Testing MCP Gateway file upload functionality...")
    print(f"📡 Connecting to: {server_url}")
    print("ℹ️  OAuth disabled for this test")
    
    try:
        # Connect without OAuth authentication
        async with Client(server_url) as client:
            print("✅ Connected to MCP Gateway!")
            
            # Test ping
            try:
                await client.ping()
                print("✅ Ping successful!")
            except Exception as e:
                print(f"❌ Ping failed: {e}")
                return
            
            # List available tools
            print("\n📋 Available tools:")
            tools = await client.list_tools()
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
            
            if not tools:
                print("ℹ️  No tools found - make sure agents are registered")
                return
            
            # Find the first agent tool (should end with '_agent')
            agent_tool = None
            for tool in tools:
                if tool.name.endswith('_agent'):
                    agent_tool = tool
                    break
            
            if not agent_tool:
                print("❌ No agent tools found - using first available tool")
                if tools:
                    agent_tool = tools[0]
                else:
                    return
            
            print(f"\n🎯 Testing tool: {agent_tool.name}")
            print("tool:",agent_tool )
            
            # Test 1: Call without files (baseline test)
            print(f"\n🔧 Test 1: Call without files")
            try:
                result = await client.call_tool(agent_tool.name, {
                    "message": "Hello from test client - no files"
                })
                print(f"📤 Response: {result}")
            except Exception as e:
                print(f"❌ Call without files failed: {e}")
            
            # Test 2: Call with files
            print(f"\n🔧 Test 2: Call with files")
            files = await create_test_files()
            
            try:
                result = await client.call_tool(agent_tool.name, {
                    "message": "Hello from test client - processing these files",
                    "files": files
                })
                print(f"📤 Response: {result}")
                print("\n✅ File upload test completed!")
                print("📝 Check the MCP Gateway logs to verify files were received and processed")
                
            except Exception as e:
                print(f"❌ Call with files failed: {e}")
                print("📝 This might be expected if the tool signature hasn't been updated yet")
            
            # Test 3: Call with single file
            print(f"\n🔧 Test 3: Call with single file")
            single_file = [files[0]]  # Just the first file
            
            try:
                result = await client.call_tool(agent_tool.name, {
                    "message": "Processing single file",
                    "files": single_file
                })
                print(f"📤 Response: {result}")
            except Exception as e:
                print(f"❌ Single file test failed: {e}")
                
    except Exception as e:
        print(f"❌ Connection error: {e}")
        print("\n💡 Troubleshooting:")
        print("1. Make sure the MCP Gateway is running")
        print("2. Verify the server is listening on localhost:8080")
        print("3. Check that OAuth is disabled in the gateway config")
        print("4. Ensure at least one agent is registered")

if __name__ == "__main__":
    asyncio.run(main())