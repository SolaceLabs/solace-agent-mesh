#!/usr/bin/env python3
"""
FastMCP proxy server for SAM MCP Gateway.
This allows Claude Desktop to connect to the SAM HTTP MCP server via stdio.
"""

from fastmcp import FastMCP

# Create a proxy to the running SAM MCP gateway
proxy = FastMCP.as_proxy(
    "http://localhost:8080/mcp", 
    name="SAM Agent Mesh Proxy"
)

if __name__ == "__main__":
    proxy.run()  # Runs via STDIO for Claude Desktop