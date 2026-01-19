"""
Pydantic configuration models for A2A proxy applications.
"""

from typing import List, Literal, Optional
from urllib.parse import urlparse

from pydantic import Field, model_validator

from ..base.config import BaseProxyAppConfig, ProxiedAgentConfig
from ....common.utils.pydantic_utils import SamConfigBase


class HttpHeaderConfig(SamConfigBase):
    """Configuration for a single HTTP header."""

    name: str = Field(
        ...,
        description="The HTTP header name (e.g., 'X-API-Key', 'Authorization').",
    )
    value: str = Field(
        ...,
        description="The HTTP header value.",
    )


class AuthenticationConfig(SamConfigBase):
    """Authentication configuration for downstream A2A agents."""

    type: Optional[
        Literal["static_bearer", "static_apikey", "oauth2_client_credentials", "oauth2_authorization_code"]
    ] = Field(
        default=None,
        description="Authentication type. If not specified, inferred from 'scheme' for backward compatibility.",
    )
    scheme: Optional[str] = Field(
        default=None,
        description="(Legacy) The authentication scheme (e.g., 'bearer', 'apikey'). Use 'type' field instead.",
    )
    token: Optional[str] = Field(
        default=None,
        description="The authentication token or API key (for static_bearer and static_apikey types).",
    )
    token_url: Optional[str] = Field(
        default=None,
        description="OAuth 2.0 token endpoint URL (required for oauth2_client_credentials type).",
    )
    client_id: Optional[str] = Field(
        default=None,
        description="OAuth 2.0 client identifier (required for oauth2_client_credentials and oauth2_authorization_code types).",
    )
    client_secret: Optional[str] = Field(
        default=None,
        description="OAuth 2.0 client secret (required for oauth2_client_credentials type, optional for oauth2_authorization_code).",
    )
    scope: Optional[str] = Field(
        default=None,
        description="OAuth 2.0 scope as a space-separated string (optional for oauth2_client_credentials type).",
    )
    token_cache_duration_seconds: int = Field(
        default=3300,
        gt=0,
        description="How long to cache OAuth 2.0 tokens before refresh, in seconds (default: 3300 = 55 minutes).",
    )

    # NEW fields for oauth2_authorization_code
    authorization_url: Optional[str] = Field(
        default=None,
        description="OAuth 2.0 authorization endpoint URL (for oauth2_authorization_code type). Can override agent card URL.",
    )
    redirect_uri: Optional[str] = Field(
        default=None,
        description="OAuth 2.0 redirect URI (required for oauth2_authorization_code type).",
    )
    scopes: Optional[List[str]] = Field(
        default=None,
        description="OAuth 2.0 scopes as a list of strings (optional for oauth2_authorization_code type).",
    )

    @model_validator(mode="after")
    def validate_auth_config(self) -> "AuthenticationConfig":
        """Validates authentication configuration based on type."""
        # Determine effective auth type (with backward compatibility)
        auth_type = self.type
        if not auth_type and self.scheme:
            # Legacy config: infer type from scheme
            if self.scheme == "bearer":
                auth_type = "static_bearer"
            elif self.scheme == "apikey":
                auth_type = "static_apikey"
            else:
                raise ValueError(
                    f"Unknown legacy authentication scheme '{self.scheme}'. "
                    f"Supported schemes: 'bearer', 'apikey'."
                )

        if not auth_type:
            # No authentication configured
            return self

        # Validate based on auth type
        if auth_type in ["static_bearer", "static_apikey"]:
            if not self.token:
                raise ValueError(
                    f"Authentication type '{auth_type}' requires 'token' field."
                )

        elif auth_type == "oauth2_client_credentials":
            # Validate token_url
            if not self.token_url:
                raise ValueError(
                    "OAuth 2.0 client credentials flow requires 'token_url'."
                )

            # Validate token_url is HTTPS
            try:
                parsed_url = urlparse(self.token_url)
                if parsed_url.scheme != "https":
                    raise ValueError(
                        f"OAuth 2.0 'token_url' must use HTTPS for security. "
                        f"Got scheme: '{parsed_url.scheme}'"
                    )
            except Exception as e:
                raise ValueError(f"Failed to parse 'token_url': {e}")

            # Validate client_id
            if not self.client_id:
                raise ValueError(
                    "OAuth 2.0 client credentials flow requires 'client_id'."
                )

            # Validate client_secret
            if not self.client_secret:
                raise ValueError(
                    "OAuth 2.0 client credentials flow requires 'client_secret'."
                )

        elif auth_type == "oauth2_authorization_code":
            # Validate client_id
            if not self.client_id:
                raise ValueError(
                    "OAuth 2.0 authorization code flow requires 'client_id'."
                )

            # Validate redirect_uri
            if not self.redirect_uri:
                raise ValueError(
                    "OAuth 2.0 authorization code flow requires 'redirect_uri'."
                )

            # Optional: Validate authorization_url if provided (can also come from agent card)
            if self.authorization_url:
                try:
                    parsed_url = urlparse(self.authorization_url)
                    if parsed_url.scheme not in ["https", "http"]:
                        raise ValueError(
                            f"OAuth 2.0 'authorization_url' must use HTTP(S). "
                            f"Got scheme: '{parsed_url.scheme}'"
                        )
                except Exception as e:
                    raise ValueError(f"Failed to parse 'authorization_url': {e}")

        else:
            raise ValueError(
                f"Unsupported authentication type '{auth_type}'. "
                f"Supported types: static_bearer, static_apikey, oauth2_client_credentials, oauth2_authorization_code."
            )

        return self


class A2AProxiedAgentConfig(ProxiedAgentConfig):
    """Configuration for an A2A-over-HTTPS proxied agent."""

    url: str = Field(
        ...,
        description="The base URL of the downstream A2A agent's HTTP endpoint.",
    )
    authentication: Optional[AuthenticationConfig] = Field(
        default=None,
        description="Authentication details for the downstream agent.",
    )
    use_auth_for_agent_card: bool = Field(
        default=False,
        description="If true, applies the configured authentication to agent card fetching. "
        "If false, agent card requests are made without authentication.",
    )
    use_agent_card_url: bool = Field(
        default=True,
        description="If true, uses the URL from the agent card for task invocations. "
        "If false, uses the configured URL directly for task invocations. "
        "Note: The configured URL is always used to fetch the agent card itself.",
    )
    agent_card_headers: Optional[List[HttpHeaderConfig]] = Field(
        default=None,
        description="Custom HTTP headers to include when fetching the agent card. "
        "These headers are added alongside authentication headers.",
    )
    task_headers: Optional[List[HttpHeaderConfig]] = Field(
        default=None,
        description="Custom HTTP headers to include when invoking A2A tasks. "
        "These headers are added alongside authentication headers. Note: The A2A SDK's "
        "AuthInterceptor applies authentication headers after these are set, so custom "
        "headers cannot override authentication. For custom auth, omit the 'authentication' "
        "config and use task_headers to set auth headers directly.",
    )
    ssl_verify: bool = Field(
        default=True,
        description="SSL certificate verification. Set to False to disable "
        "verification for self-signed certificates.",
    )


class A2AProxyAppConfig(BaseProxyAppConfig):
    """Complete configuration for an A2A proxy application."""

    proxied_agents: List[A2AProxiedAgentConfig] = Field(
        ...,
        min_length=1,
        description="A list of downstream A2A agents to be proxied.",
    )
