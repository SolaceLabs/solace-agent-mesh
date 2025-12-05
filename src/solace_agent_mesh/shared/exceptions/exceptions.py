"""
Generic web exceptions for HTTP/REST APIs.

This module provides a comprehensive set of generic exception classes
that can be used by any web application for consistent error handling.
"""

from typing import Any, Dict, List, Optional
from enum import Enum


class EntityOperation(Enum):
    """Operations that can be performed on entities."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    READ = "read"


class WebUIBackendException(Exception):
    """Base exception for all web UI backend errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(WebUIBackendException):
    """
    Exception for validation errors with field-level details.

    This exception supports both simple validation messages and detailed
    field-level validation errors with user-friendly message formatting.
    """

    def __init__(
        self,
        message: str,
        validation_details: Optional[Dict[str, List[str]]] = None,
        entity_type: Optional[str] = None,
        entity_identifier: Optional[str] = None
    ):
        self.validation_details = validation_details or {}
        self.entity_type = entity_type
        self.entity_identifier = entity_identifier
        super().__init__(message)

    def get_user_friendly_message(self, operation: EntityOperation) -> str:
        """Generate a user-friendly error message based on context."""
        if not self.entity_identifier or not self.entity_type:
            return self.message

        if self.validation_details:
            field = next(iter(self.validation_details.keys()))
            error_msg = self.validation_details[field][0]
            return f"Unable to {operation.value} {self.entity_type} {self.entity_identifier} because of a problem with the {field}: {error_msg.lower()}"

        if self.message:
            return f"Unable to {operation.value} {self.entity_type} {self.entity_identifier}: {self.message.lower()}"

        return self.message

    @classmethod
    def builder(cls):
        """Create a ValidationErrorBuilder for fluent error construction."""
        return ValidationErrorBuilder()


class ValidationErrorBuilder:
    """Builder for constructing ValidationError instances with fluent API."""

    def __init__(self):
        self._message = ""
        self._validation_details = {}
        self._entity_type = None
        self._entity_identifier = None

    def message(self, message: str):
        """Set the main error message."""
        self._message = message
        return self

    def formatted_message(self, pattern: str, *args):
        """Set a formatted error message."""
        self._message = pattern.format(*args)
        return self

    def validation_detail(self, field: str, errors: List[str]):
        """Add validation details for a specific field."""
        self._validation_details[field] = errors
        return self

    def formatted_validation_detail(self, field: str, pattern: str, *args):
        """Add a formatted validation detail for a field."""
        error_msg = pattern.format(*args)
        self._validation_details[field] = [error_msg]
        return self

    def entity_type(self, entity_type: str):
        """Set the entity type for context."""
        self._entity_type = entity_type
        return self

    def entity_identifier(self, identifier: str):
        """Set the entity identifier for context."""
        self._entity_identifier = identifier
        return self

    def build(self) -> ValidationError:
        """Build the ValidationError instance."""
        return ValidationError(
            self._message,
            self._validation_details,
            self._entity_type,
            self._entity_identifier
        )


class EntityNotFoundError(WebUIBackendException):
    """
    Generic exception for when an entity is not found.

    This replaces all specific "NotFound" exceptions with a single generic one.
    Format: "Could not find {entity_type} with id: {entity_id}"
    """

    def __init__(self, entity_type: str, entity_id: str):
        self.entity_type = entity_type
        self.entity_id = str(entity_id)
        message = f"Could not find {entity_type} with id: {self.entity_id}"
        details = {"entity_type": entity_type, "entity_id": self.entity_id}
        super().__init__(message, details)


class EntityAlreadyExistsError(WebUIBackendException):
    """Exception for when an entity already exists."""

    def __init__(self, entity_type: str, identifier: str, value: Any = None):
        self.entity_type = entity_type
        self.identifier = identifier
        self.value = str(value) if value is not None else None

        if value is not None:
            message = f"{entity_type} with {identifier} '{self.value}' already exists"
        else:
            message = f"{entity_type} already exists"

        details = {"entity_type": entity_type, "identifier": identifier}
        if self.value:
            details["value"] = self.value

        super().__init__(message, details)


class BusinessRuleViolationError(WebUIBackendException):
    """Exception for business rule violations."""

    def __init__(self, rule: str, message: str):
        self.rule = rule
        details = {"rule": rule}
        super().__init__(message, details)


class ConfigurationError(WebUIBackendException):
    """Exception for configuration-related errors."""

    def __init__(self, component: str, message: str):
        self.component = component
        details = {"component": component}
        super().__init__(message, details)


class DataIntegrityError(WebUIBackendException):
    """Exception for data integrity violations."""

    def __init__(self, constraint: str, message: str):
        self.constraint = constraint
        details = {"constraint": constraint}
        super().__init__(message, details)


class ExternalServiceError(WebUIBackendException):
    """Exception for external service communication errors."""

    def __init__(self, service: str, message: str, status_code: Optional[int] = None):
        self.service = service
        self.status_code = status_code
        details = {"service": service}
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, details)