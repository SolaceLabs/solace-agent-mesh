"""
MCP Gateway Adapter - Exposes SAM as an MCP Server.

This adapter uses FastMCP to create a Model Context Protocol server that dynamically
exposes SAM agents and their skills as MCP tools.
"""

from .adapter import McpAdapter

__all__ = ["McpAdapter"]
