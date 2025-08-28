#!/usr/bin/env python3
"""
Test script for MCP Gateway file upload functionality.
This script demonstrates how to structure file data for MCP tool calls.
"""

import base64
import json

def create_test_files():
    """Create test files in the format expected by MCP gateway"""
    
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
    
    # Encode as base64 (as required by MCP protocol)
    files = [
        {
            "name": test_filename_1,
            "content": base64.b64encode(test_content_1).decode('utf-8')
        },
        {
            "name": test_filename_2,
            "content": base64.b64encode(test_content_2).decode('utf-8')
        }
    ]
    
    print("Created test files for MCP upload:")
    print(f"1. {test_filename_1} ({len(test_content_1)} bytes)")
    print(f"2. {test_filename_2} ({len(test_content_2)} bytes)")
    print()
    print("Files structure:")
    for i, file_info in enumerate(files, 1):
        print(f"File {i}:")
        print(f"  name: {file_info['name']}")
        print(f"  content (base64): {file_info['content'][:50]}...")
        print()
    
    return files

def example_mcp_tool_call():
    """Example of what the MCP tool call would look like"""
    files = create_test_files()
    
    # This represents the structure that would be sent to the MCP gateway
    mcp_call_example = {
        "message": "Please process these files",
        "files": files
    }
    
    print("Example MCP tool call structure:")
    print(json.dumps(mcp_call_example, indent=2))
    
    return mcp_call_example

if __name__ == "__main__":
    print("=== MCP Gateway File Upload Test ===")
    print()
    
    example_call = example_mcp_tool_call()
    
    print()
    print("=== Expected Log Output ===")
    print("When this structure is sent to the MCP gateway, you should see logs like:")
    print()
    print("[CallAgent:test_agent] Received 2 files from MCP client:")
    print("[CallAgent:test_agent] File 1: test.txt (43 bytes)")
    print("[CallAgent:test_agent] File 2: data.json (XX bytes)")
    print("[CallAgent:test_agent] File 1 content preview: b'Hello, this is a test file from MCP client!'")
    print()
    print("This confirms that:")
    print("1. Files are properly received by the MCP gateway")
    print("2. Base64 decoding works correctly")
    print("3. File metadata (name, size) is extracted properly")
    print("4. File content is accessible for further processing")