"""
Custom MCP Session Manager with SSL configuration support.

This module provides a custom MCPSessionManager subclass that allows
configuring SSL/TLS settings for remote MCP connections (SSE and Streamable HTTP).
"""

import logging
from datetime import timedelta

from google.adk.tools.mcp_tool.mcp_session_manager import (
    MCPSessionManager,
    SseConnectionParams,
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from mcp import StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from .mcp_ssl_config import SslConfig, create_ssl_httpx_client_factory

log = logging.getLogger(__name__)


class SslConfigurableMCPSessionManager(MCPSessionManager):
    """MCP Session Manager with SSL configuration support.

    This class extends MCPSessionManager to support custom SSL settings
    for SSE and Streamable HTTP connections, allowing connections to
    MCP servers with self-signed certificates or custom CA bundles.

    Attributes:
        ssl_config: Optional SSL configuration for the connection.
    """

    def __init__(
        self,
        connection_params: StdioServerParameters | StdioConnectionParams | SseConnectionParams | StreamableHTTPConnectionParams,
        ssl_config: SslConfig | None = None,
        errlog=None,
    ):
        """Initialize the SSL-configurable MCP session manager.

        Args:
            connection_params: Parameters for the MCP connection (Stdio, SSE,
                or Streamable HTTP).
            ssl_config: Optional SSL configuration. If not provided, default
                SSL behavior is used.
            errlog: Optional TextIO stream for error logging (stdio only).
        """
        import sys

        super().__init__(
            connection_params=connection_params,
            errlog=errlog if errlog is not None else sys.stderr,
        )
        self._ssl_config = ssl_config

    def _create_client(self, merged_headers: dict[str, str] | None = None):
        """Create an MCP client with SSL configuration support.

        Overrides the parent class method to inject a custom httpx client factory
        with SSL settings for SSE and Streamable HTTP connections.

        Args:
            merged_headers: Optional headers to include in the connection.
                Only applicable for SSE and StreamableHTTP connections.

        Returns:
            The appropriate MCP client instance.

        Raises:
            ValueError: If the connection parameters are not supported.
        """
        # For stdio connections, use parent implementation
        if isinstance(self._connection_params, StdioConnectionParams):
            return stdio_client(
                server=self._connection_params.server_params,
                errlog=self._errlog,
            )

        # For remote connections, use custom httpx factory if SSL config provided
        httpx_factory = None
        if self._ssl_config is not None:
            httpx_factory = create_ssl_httpx_client_factory(self._ssl_config)

        if isinstance(self._connection_params, SseConnectionParams):
            kwargs = {
                "url": self._connection_params.url,
                "headers": merged_headers,
                "timeout": self._connection_params.timeout,
                "sse_read_timeout": self._connection_params.sse_read_timeout,
            }
            if httpx_factory is not None:
                kwargs["httpx_client_factory"] = httpx_factory
            return sse_client(**kwargs)

        elif isinstance(self._connection_params, StreamableHTTPConnectionParams):
            kwargs = {
                "url": self._connection_params.url,
                "headers": merged_headers,
                "timeout": timedelta(seconds=self._connection_params.timeout),
                "sse_read_timeout": timedelta(
                    seconds=self._connection_params.sse_read_timeout
                ),
                "terminate_on_close": self._connection_params.terminate_on_close,
            }
            if httpx_factory is not None:
                kwargs["httpx_client_factory"] = httpx_factory
            return streamablehttp_client(**kwargs)

        else:
            raise ValueError(
                "Unable to initialize connection. Connection should be "
                "StdioServerParameters or SseServerParams, but got "
                f"{self._connection_params}"
            )
