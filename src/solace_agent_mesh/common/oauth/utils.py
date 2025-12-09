"""Utility functions for OAuth 2.0 operations."""

import time
from urllib.parse import urlparse


def validate_https_url(url: str) -> None:
    """Validate that a URL uses HTTPS scheme.

    OAuth 2.0 requires HTTPS for security when transmitting credentials.

    Args:
        url: The URL to validate

    Raises:
        ValueError: If the URL does not use HTTPS scheme
    """
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https":
        raise ValueError(
            f"OAuth 2.0 URLs must use HTTPS for security. "
            f"Got scheme: {parsed_url.scheme}"
        )


def calculate_expires_at(expires_in: int) -> float:
    """Calculate expiration timestamp from expires_in seconds.

    Args:
        expires_in: Number of seconds until token expires

    Returns:
        Unix timestamp (float) when the token will expire
    """
    return time.time() + expires_in


def is_token_expired(expires_at: float, buffer_seconds: int = 0) -> bool:
    """Check if a token is expired or will expire within buffer time.

    Args:
        expires_at: Unix timestamp when token expires
        buffer_seconds: Optional buffer to consider token expired early
                       (useful for proactive refresh)

    Returns:
        True if token is expired or within buffer time of expiring
    """
    current_time = time.time()
    return current_time >= (expires_at - buffer_seconds)