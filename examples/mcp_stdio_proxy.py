#!/usr/bin/env python3
"""
Stdio proxy for SAM MCP Gateway.
This allows Claude Desktop to connect to the SAM HTTP MCP server via stdio transport.
"""

import asyncio
import json
import sys
import httpx
from typing import Any, Dict

# URL of your running SAM MCP gateway
SAM_MCP_URL = "http://localhost:8080/mcp"

async def forward_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Forward MCP request to SAM HTTP server and return response"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SAM_MCP_URL,
                json=request,
                headers={"Content-Type": "application/json"},
                timeout=30.0
            )
            return response.json()
    except Exception as e:
        # Return JSON-RPC error response
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32603,
                "message": f"Proxy error: {str(e)}"
            }
        }

async def main():
    """Main stdio proxy loop"""
    stdin_reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(stdin_reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
    
    while True:
        try:
            # Read JSON-RPC request from stdin
            line = await stdin_reader.readline()
            if not line:
                break
                
            line = line.decode('utf-8').strip()
            if not line:
                continue
                
            request = json.loads(line)
            
            # Forward to SAM MCP gateway
            response = await forward_request(request)
            
            # Send response to stdout
            print(json.dumps(response), flush=True)
            
        except json.JSONDecodeError:
            # Invalid JSON, send error response
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            }
            print(json.dumps(error_response), flush=True)
        except Exception as e:
            # Other errors
            error_response = {
                "jsonrpc": "2.0", 
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error_response), flush=True)

if __name__ == "__main__":
    asyncio.run(main())