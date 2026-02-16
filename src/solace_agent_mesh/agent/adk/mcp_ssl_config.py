"""
SSL/TLS configuration support for MCP connections.

This module provides SSL configuration for remote MCP connections (SSE and Streamable HTTP)
to allow connecting to MCP servers with self-signed certificates or custom CA bundles.
"""

import logging
import os
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)


@dataclass
class SslConfig:
    """SSL configuration for MCP connections.

    Attributes:
        verify: Whether to verify SSL certificates. Defaults to True.
                Set to False to disable SSL verification (development only).
        ca_bundle: Optional path to a custom CA certificate bundle file.
                   When provided, this takes precedence over the verify setting.
    """

    verify: bool = True
    ca_bundle: str | None = None

    def __post_init__(self):
        """Validate the SSL configuration after initialization."""
        if self.ca_bundle is not None and not os.path.isfile(self.ca_bundle):
            raise ValueError(
                f"SSL ca_bundle path does not exist or is not a file: {self.ca_bundle}"
            )


def create_ssl_httpx_client_factory(ssl_config: SslConfig):
    """Create an httpx client factory with SSL configuration.

    This factory creates httpx.AsyncClient instances with custom SSL settings,
    following the MCP library's expected factory signature.

    Args:
        ssl_config: SSL configuration specifying verification settings.

    Returns:
        A factory function that creates configured httpx.AsyncClient instances.
    """
    # MCP default timeouts
    MCP_DEFAULT_TIMEOUT = 30.0
    MCP_DEFAULT_SSE_READ_TIMEOUT = 300.0

    def factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        """Create an httpx.AsyncClient with SSL configuration.

        Args:
            headers: Optional headers to include with all requests.
            timeout: Request timeout as httpx.Timeout object.
            auth: Optional authentication handler.

        Returns:
            Configured httpx.AsyncClient instance.
        """
        # Determine SSL verification setting
        # ca_bundle takes precedence if provided
        verify: bool | str = (
            ssl_config.ca_bundle if ssl_config.ca_bundle else ssl_config.verify
        )

        # Build kwargs following MCP defaults
        kwargs: dict = {
            "follow_redirects": True,
            "verify": verify,
        }

        # Handle timeout
        if timeout is None:
            kwargs["timeout"] = httpx.Timeout(
                MCP_DEFAULT_TIMEOUT, read=MCP_DEFAULT_SSE_READ_TIMEOUT
            )
        else:
            kwargs["timeout"] = timeout

        # Handle headers
        if headers is not None:
            kwargs["headers"] = headers

        # Handle authentication
        if auth is not None:
            kwargs["auth"] = auth

        return httpx.AsyncClient(**kwargs)

    return factory
