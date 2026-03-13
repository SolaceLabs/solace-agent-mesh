"""Shared utilities for redacting secret fields from values."""

from typing import Any, Optional


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
}


def redact_auth_config(auth_config: Optional[dict]) -> Optional[dict]:
    """
    Remove secret fields from an authentication configuration.

    Removes sensitive fields (client_secret, token, api_key, password) based
    on auth type. This follows the connector pattern of omitting secrets
    rather than replacing with sentinel values.

    Args:
        auth_config: Authentication configuration dictionary with 'type' field

    Returns:
        Copy of auth_config with secret fields removed, or None if input is None
    """
    if auth_config is None:
        return None

    auth_type = auth_config.get("type", "").lower()
    secret_fields = AUTH_SECRET_FIELDS.get(auth_type, set())

    return redact_fields_by_name(auth_config, secret_fields)


def get_hidden_field_names(field_schema: dict[str, Any]) -> set[str]:
    """
    Extract field names that should be hidden from a schema.

    Args:
        field_schema: Dictionary mapping field names to schema objects.
                     Each schema object must have a 'hidden' attribute (bool).

    Returns:
        Set of field names where hidden=True
    """
    hidden_fields = set()
    for field_name, schema in field_schema.items():
        if getattr(schema, 'hidden', False):
            hidden_fields.add(field_name)
    return hidden_fields


def redact_hidden_fields(values: dict, field_schema: dict[str, Any]) -> dict:
    """
    Remove hidden fields from a values dictionary based on schema.

    Args:
        values: Dictionary of field values to redact
        field_schema: Dictionary mapping field names to schema objects.
                     Each schema object must have a 'hidden' attribute (bool).

    Returns:
        Copy of values with hidden fields removed
    """
    if not isinstance(values, dict):
        return values

    hidden_fields = get_hidden_field_names(field_schema)

    result = values.copy()
    for field_name in hidden_fields:
        result.pop(field_name, None)

    return result


class SecretRedactor:
    """
    Unified utility for redacting secret fields based on schema definitions.

    A field is considered secret if it has hidden=True in the schema.
    This class works with both connector and gateway schemas.

    Usage:
        # For connectors
        connector = registry.get_connector(type, subtype)
        schema = connector.get_schema().field_schema
        redacted = SecretRedactor.redact(values, schema)

        # For gateways
        gateway_type = registry.get_gateway_type(type)
        schema = gateway_type.get_field_schema()
        redacted = SecretRedactor.redact(values, schema)
    """

    @staticmethod
    def get_hidden_fields(field_schema: dict[str, Any] | None) -> set[str]:
        """
        Extract field names that should be hidden from a schema.

        Args:
            field_schema: Dictionary mapping field names to schema objects,
                         or None if schema not found.

        Returns:
            Set of field names where hidden=True, empty set if schema is None
        """
        if not field_schema:
            return set()
        return get_hidden_field_names(field_schema)

    @staticmethod
    def redact(values: dict, field_schema: dict[str, Any] | None) -> dict:
        """
        Redact secret fields from values based on schema definition.

        Args:
            values: Dictionary of field values to redact
            field_schema: Dictionary mapping field names to schema objects,
                         or None if schema not found.

        Returns:
            Copy of values with hidden fields removed.
            Returns original values unchanged if schema is None.
        """
        if not field_schema:
            return values
        return redact_hidden_fields(values, field_schema)
