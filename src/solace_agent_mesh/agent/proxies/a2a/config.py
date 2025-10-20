"""
Pydantic configuration models for A2A proxy applications.
"""

from typing import List, Literal, Optional
from urllib.parse import urlparse

from pydantic import Field, model_validator

from ..base.config import BaseProxyAppConfig, ProxiedAgentConfig
from ....common.utils.pydantic_utils import SamConfigBase


class AuthenticationConfig(SamConfigBase):
    """Authentication configuration for downstream A2A agents."""

    type: Optional[
        Literal["static_bearer", "static_apikey", "oauth2_client_credentials"]
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
        description="OAuth 2.0 client identifier (required for oauth2_client_credentials type).",
    )
    client_secret: Optional[str] = Field(
        default=None,
        description="OAuth 2.0 client secret (required for oauth2_client_credentials type).",
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

        else:
            raise ValueError(
                f"Unsupported authentication type '{auth_type}'. "
                f"Supported types: static_bearer, static_apikey, oauth2_client_credentials."
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


class A2AProxyAppConfig(BaseProxyAppConfig):
    """Complete configuration for an A2A proxy application."""

    proxied_agents: List[A2AProxiedAgentConfig] = Field(
        ...,
        min_length=1,
        description="A list of downstream A2A agents to be proxied.",
    )
