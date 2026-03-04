"""Tests for SSL-configurable MCP Session Manager."""

from unittest.mock import patch, MagicMock

import pytest
from google.adk.tools.mcp_tool.mcp_session_manager import (
    SseConnectionParams,
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from mcp import StdioServerParameters

from solace_agent_mesh.agent.adk.mcp_ssl_config import SslConfig
from solace_agent_mesh.agent.adk.ssl_mcp_session_manager import (
    SslConfigurableMCPSessionManager,
)


class TestSslConfigurableMCPSessionManager:
    """Tests for SslConfigurableMCPSessionManager class."""

    def test_init_stores_ssl_config(self):
        """Test that SSL config is stored during initialization."""
        ssl_config = SslConfig(verify=False)
        connection_params = SseConnectionParams(
            url="https://example.com/sse",
            timeout=30,
            sse_read_timeout=300,
        )

        manager = SslConfigurableMCPSessionManager(
            connection_params=connection_params,
            ssl_config=ssl_config,
        )

        assert manager._ssl_config is ssl_config

    def test_init_without_ssl_config(self):
        """Test initialization without SSL config uses None."""
        connection_params = SseConnectionParams(
            url="https://example.com/sse",
            timeout=30,
            sse_read_timeout=300,
        )

        manager = SslConfigurableMCPSessionManager(
            connection_params=connection_params,
        )

        assert manager._ssl_config is None

    @patch("solace_agent_mesh.agent.adk.ssl_mcp_session_manager.sse_client")
    def test_create_client_sse_without_ssl_config(self, mock_sse_client):
        """Test _create_client for SSE connection without SSL config."""
        mock_sse_client.return_value = MagicMock()
        connection_params = SseConnectionParams(
            url="https://example.com/sse",
            timeout=30,
            sse_read_timeout=300,
        )

        manager = SslConfigurableMCPSessionManager(
            connection_params=connection_params,
            ssl_config=None,
        )
        manager._create_client(merged_headers={"Authorization": "Bearer token"})

        mock_sse_client.assert_called_once_with(
            url="https://example.com/sse",
            headers={"Authorization": "Bearer token"},
            timeout=30,
            sse_read_timeout=300,
        )

    @patch("solace_agent_mesh.agent.adk.ssl_mcp_session_manager.sse_client")
    @patch("solace_agent_mesh.agent.adk.ssl_mcp_session_manager.create_ssl_httpx_client_factory")
    def test_create_client_sse_with_ssl_config(self, mock_factory, mock_sse_client):
        """Test _create_client for SSE connection with SSL config."""
        mock_sse_client.return_value = MagicMock()
        mock_httpx_factory = MagicMock()
        mock_factory.return_value = mock_httpx_factory

        ssl_config = SslConfig(verify=False)
        connection_params = SseConnectionParams(
            url="https://example.com/sse",
            timeout=30,
            sse_read_timeout=300,
        )

        manager = SslConfigurableMCPSessionManager(
            connection_params=connection_params,
            ssl_config=ssl_config,
        )
        manager._create_client()

        mock_factory.assert_called_once_with(ssl_config)
        mock_sse_client.assert_called_once_with(
            url="https://example.com/sse",
            headers=None,
            timeout=30,
            sse_read_timeout=300,
            httpx_client_factory=mock_httpx_factory,
        )

    @patch("solace_agent_mesh.agent.adk.ssl_mcp_session_manager.streamablehttp_client")
    def test_create_client_streamable_http_without_ssl_config(self, mock_http_client):
        """Test _create_client for Streamable HTTP connection without SSL config."""
        mock_http_client.return_value = MagicMock()
        connection_params = StreamableHTTPConnectionParams(
            url="https://example.com/mcp",
            timeout=30,
            sse_read_timeout=300,
            terminate_on_close=True,
        )

        manager = SslConfigurableMCPSessionManager(
            connection_params=connection_params,
            ssl_config=None,
        )
        manager._create_client(merged_headers={"X-Custom": "header"})

        mock_http_client.assert_called_once()
        call_kwargs = mock_http_client.call_args.kwargs
        assert call_kwargs["url"] == "https://example.com/mcp"
        assert call_kwargs["headers"] == {"X-Custom": "header"}
        assert call_kwargs["terminate_on_close"] is True
        assert "httpx_client_factory" not in call_kwargs

    @patch("solace_agent_mesh.agent.adk.ssl_mcp_session_manager.streamablehttp_client")
    @patch("solace_agent_mesh.agent.adk.ssl_mcp_session_manager.create_ssl_httpx_client_factory")
    def test_create_client_streamable_http_with_ssl_config(self, mock_factory, mock_http_client):
        """Test _create_client for Streamable HTTP connection with SSL config."""
        mock_http_client.return_value = MagicMock()
        mock_httpx_factory = MagicMock()
        mock_factory.return_value = mock_httpx_factory

        ssl_config = SslConfig(verify=False)
        connection_params = StreamableHTTPConnectionParams(
            url="https://example.com/mcp",
            timeout=30,
            sse_read_timeout=300,
            terminate_on_close=False,
        )

        manager = SslConfigurableMCPSessionManager(
            connection_params=connection_params,
            ssl_config=ssl_config,
        )
        manager._create_client()

        mock_factory.assert_called_once_with(ssl_config)
        call_kwargs = mock_http_client.call_args.kwargs
        assert call_kwargs["httpx_client_factory"] is mock_httpx_factory

    @patch("solace_agent_mesh.agent.adk.ssl_mcp_session_manager.stdio_client")
    def test_create_client_stdio(self, mock_stdio_client):
        """Test _create_client for Stdio connection."""
        mock_stdio_client.return_value = MagicMock()
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "mcp_server"],
        )
        connection_params = StdioConnectionParams(server_params=server_params)

        manager = SslConfigurableMCPSessionManager(
            connection_params=connection_params,
            ssl_config=SslConfig(verify=False),  # SSL config ignored for stdio
        )
        manager._create_client()

        mock_stdio_client.assert_called_once()
        call_kwargs = mock_stdio_client.call_args.kwargs
        assert call_kwargs["server"] is server_params

    def test_create_client_unsupported_params_raises_error(self):
        """Test that unsupported connection params raise ValueError."""
        # Create a mock unsupported connection params type
        unsupported_params = MagicMock()
        unsupported_params.__class__.__name__ = "UnsupportedParams"

        # We need to bypass the parent __init__ validation
        manager = SslConfigurableMCPSessionManager.__new__(SslConfigurableMCPSessionManager)
        manager._connection_params = unsupported_params
        manager._ssl_config = None
        manager._errlog = None

        with pytest.raises(ValueError) as exc_info:
            manager._create_client()

        assert "Unable to initialize connection" in str(exc_info.value)
