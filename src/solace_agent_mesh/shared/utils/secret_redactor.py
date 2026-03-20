"""Shared utilities for redacting secret fields from values."""

from typing import Optional


def redact_fields_by_name(values: dict, field_names: set[str]) -> dict:
    """
    Remove specified fields from a dictionary.

    This is a simple utility for removing known secret fields without
    requiring a schema definition. Useful for auth configs where secret
    field names are known by auth type.

    Args:
        values: Dictionary of values to redact
        field_names: Set of field names to remove

    Returns:
        Copy of values with specified fields removed
    """
    if not isinstance(values, dict):
        return values

    result = values.copy()
    for field_name in field_names:
        result.pop(field_name, None)

    return result


# Auth config secret field names by type
AUTH_SECRET_FIELDS = {
    "oauth2": {"client_secret"},
    "bearer": {"token"},
    "apikey": {"api_key"},
    "basic": {"password"},
    "aws_iam": {"aws_secret_access_key", "aws_session_token"},
    "gcp_service_account": {"service_account_json"},
}


def redact_auth_config(auth_config: Optional[dict]) -> Optional[dict]:
    """
    Remove secret fields and type metadata from an authentication configuration.

    Removes sensitive fields (client_secret, token, api_key, password) based
    on auth type, and the 'type' field itself. This follows the connector
    pattern of omitting secrets rather than replacing with sentinel values.

    Args:
        auth_config: Authentication configuration dictionary with 'type' field

    Returns:
        Copy of auth_config with secret fields and 'type' field removed,
        or None if input is None
    """
    if auth_config is None:
        return None

    auth_type = auth_config.get("type", "").lower()
    secret_fields = AUTH_SECRET_FIELDS.get(auth_type, set())
    # Also remove 'type' field
    secret_fields = secret_fields | {"type"}

    return redact_fields_by_name(auth_config, secret_fields)
