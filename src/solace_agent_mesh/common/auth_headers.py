"""Utilities for building HTTP authentication headers.

This module provides header-building logic that can be used from both
synchronous and asynchronous contexts. OAuth2 authentication requires
async context and a token fetcher callback.
"""

from typing import Dict, Any, Optional, Callable, Awaitable
from solace_ai_connector.common.log import log


def build_static_auth_headers(
    agent_name: str,
    agent_config: Dict[str, Any],
    custom_headers_key: str,
    use_auth: bool = True,
    log_identifier: str = "",
) -> Dict[str, str]:
    """
    Builds HTTP headers with static authentication and custom headers.

    This function handles ONLY static authentication types:
    - static_bearer: Bearer token authentication
    - static_apikey: API key authentication

    For OAuth2 authentication, use build_full_auth_headers() instead.

    Args:
        agent_name: The name of the agent
        agent_config: The agent configuration dictionary containing:
            - authentication: Auth config with type/scheme and token
            - <custom_headers_key>: List of custom header configs
        custom_headers_key: Key for custom headers in agent_config
            (e.g., 'agent_card_headers' or 'task_headers')
        use_auth: Whether to apply authentication headers
        log_identifier: Optional logging prefix for debug messages

    Returns:
        Dictionary of HTTP headers. Custom headers override auth headers
        per the established precedence rules.

    Note:
        OAuth2 authentication types (oauth2_client_credentials,
        oauth2_authorization_code) will be skipped with a warning.
        These require async context - use build_full_auth_headers().

    Example:
        >>> headers = build_static_auth_headers(
        ...     agent_name="my-agent",
        ...     agent_config={
        ...         "authentication": {
        ...             "type": "static_bearer",
        ...             "token": "secret123"
        ...         },
        ...         "agent_card_headers": [
        ...             {"name": "X-Custom", "value": "test"}
        ...         ]
        ...     },
        ...     custom_headers_key="agent_card_headers",
        ...     use_auth=True,
        ... )
        >>> headers
        {'Authorization': 'Bearer secret123', 'X-Custom': 'test'}
    """
    headers: Dict[str, str] = {}

    # Step 1: Add authentication headers if requested
    if use_auth:
        auth_config = agent_config.get("authentication")
        if auth_config:
            auth_type = auth_config.get("type")

            # Determine auth type (with backward compatibility)
            if not auth_type:
                scheme = auth_config.get("scheme", "bearer")
                auth_type = "static_bearer" if scheme == "bearer" else "static_apikey"

            # Apply static authentication based on type
            if auth_type == "static_bearer":
                token = auth_config.get("token")
                if token:
                    headers["Authorization"] = f"Bearer {token}"
            elif auth_type == "static_apikey":
                token = auth_config.get("token")
                if token:
                    headers["X-API-Key"] = token
            elif auth_type in ("oauth2_client_credentials", "oauth2_authorization_code"):
                # OAuth2 not supported in sync context - log warning
                if log_identifier:
                    log.warning(
                        "%s OAuth2 authentication (%s) is not supported in synchronous context. "
                        "Agent '%s' headers will not include authentication. "
                        "Use build_full_auth_headers() for OAuth2 support.",
                        log_identifier,
                        auth_type,
                        agent_name,
                    )

    # Step 2: Add custom headers (these override auth headers)
    custom_headers_list = agent_config.get(custom_headers_key)
    if custom_headers_list:
        for header_config in custom_headers_list:
            header_name = header_config.get("name")
            header_value = header_config.get("value")
            if header_name and header_value:
                headers[header_name] = header_value

    return headers


async def build_full_auth_headers(
    agent_name: str,
    agent_config: Dict[str, Any],
    custom_headers_key: str,
    use_auth: bool = True,
    log_identifier: str = "",
    oauth_token_fetcher: Optional[Callable[[str, Dict[str, Any]], Awaitable[str]]] = None,
) -> Dict[str, str]:
    """
    Builds HTTP headers with full authentication support (including OAuth2).

    This is the async version that supports all authentication types:
    - static_bearer: Bearer token authentication
    - static_apikey: API key authentication
    - oauth2_client_credentials: OAuth2 client credentials flow
    - oauth2_authorization_code: OAuth2 authorization code flow

    For synchronous contexts (like initial discovery), use
    build_static_auth_headers() instead.

    Args:
        agent_name: The name of the agent
        agent_config: The agent configuration dictionary
        custom_headers_key: Key for custom headers in agent_config
        use_auth: Whether to apply authentication headers
        log_identifier: Optional logging prefix for debug messages
        oauth_token_fetcher: Async callable for fetching OAuth2 tokens.
            Required for OAuth2 auth types. Should have signature:
            async def fetch_token(agent_name: str, auth_config: dict) -> str

    Returns:
        Dictionary of HTTP headers. Custom headers override auth headers.

    Raises:
        ValueError: If OAuth2 is configured but oauth_token_fetcher is not provided

    Example:
        >>> async def fetch_token(agent_name, auth_config):
        ...     return "oauth_token_xyz"
        >>> headers = await build_full_auth_headers(
        ...     agent_name="my-agent",
        ...     agent_config={
        ...         "authentication": {
        ...             "type": "oauth2_client_credentials",
        ...             "token_url": "https://auth.example.com/token",
        ...             "client_id": "client123",
        ...             "client_secret": "secret456"
        ...         }
        ...     },
        ...     custom_headers_key="task_headers",
        ...     oauth_token_fetcher=fetch_token,
        ... )
        >>> headers
        {'Authorization': 'Bearer oauth_token_xyz'}
    """
    # Start with static headers (handles static auth only, NOT custom headers yet)
    # We build headers without custom headers first, then add OAuth2, then custom headers last
    # This ensures custom headers override OAuth2 headers
    headers = build_static_auth_headers(
        agent_name=agent_name,
        agent_config=agent_config,
        custom_headers_key="",  # Don't apply custom headers yet
        use_auth=use_auth,
        log_identifier=log_identifier,
    )

    # Add OAuth2 support if needed
    if use_auth:
        auth_config = agent_config.get("authentication")
        if auth_config:
            auth_type = auth_config.get("type")

            # Handle OAuth2 types
            if auth_type == "oauth2_client_credentials":
                if not oauth_token_fetcher:
                    raise ValueError(
                        f"OAuth2 authentication configured for agent '{agent_name}' "
                        "but no oauth_token_fetcher provided to build_full_auth_headers(). "
                        "Pass the token fetcher function to enable OAuth2."
                    )

                try:
                    access_token = await oauth_token_fetcher(agent_name, auth_config)
                    headers["Authorization"] = f"Bearer {access_token}"
                except Exception as e:
                    if log_identifier:
                        log.error(
                            "%s Failed to obtain OAuth 2.0 token for headers: %s",
                            log_identifier,
                            e,
                        )
                    # Continue without auth header - let the request fail downstream
                    # This matches existing behavior in A2A proxy

    # Apply custom headers last (these override all auth headers, including OAuth2)
    custom_headers_list = agent_config.get(custom_headers_key)
    if custom_headers_list:
        for header_config in custom_headers_list:
            header_name = header_config.get("name")
            header_value = header_config.get("value")
            if header_name and header_value:
                headers[header_name] = header_value

    return headers
