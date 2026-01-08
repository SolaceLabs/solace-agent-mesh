"""
Standardized error response DTOs for HTTP APIs.

This module provides consistent error response formats that can be used
across any web application for uniform error handling.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class EventErrorDTO(BaseModel):
    """
    Simplified and standardized error response format.

    This provides consistent error responses across all endpoints with:
    - message: Human-readable error description
    - validationDetails: Field-level validation errors (optional)

    Examples:
        404 Not Found:
        {
            "message": "Could not find User with id: 123",
            "validationDetails": null
        }

        422 Validation Error:
        {
            "message": "Invalid input data",
            "validationDetails": {
                "email": ["Invalid email format"],
                "name": ["Name is required"]
            }
        }
    """
    message: str = Field(..., description="Human-readable error message")
    validationDetails: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Field-level validation errors"
    )

    @classmethod
    def create(
        cls,
        message: str,
        validation_details: Optional[Dict[str, List[str]]] = None
    ) -> "EventErrorDTO":
        """
        Create a new EventErrorDTO.

        Args:
            message: Human-readable error message
            validation_details: Optional field-level validation errors

        Returns:
            EventErrorDTO instance
        """
        return cls(
            message=message,
            validationDetails=validation_details
        )

    @classmethod
    def not_found(cls, entity_type: str, entity_id: str) -> "EventErrorDTO":
        """
        Create a 404 Not Found error with standardized message format.

        Args:
            entity_type: The type of entity (e.g., "User", "Product", "Order")
            entity_id: The ID that was not found

        Returns:
            EventErrorDTO with 404 message format

        Example:
            EventErrorDTO.not_found("User", "123")
            # Returns: {"message": "Could not find User with id: 123", "validationDetails": null}
        """
        message = f"Could not find {entity_type} with id: {entity_id}"
        return cls.create(message=message)

    @classmethod
    def validation_error(
        cls,
        message: str,
        validation_details: Dict[str, List[str]]
    ) -> "EventErrorDTO":
        """
        Create a validation error with field-level details.

        Args:
            message: Main validation error message
            validation_details: Dict mapping field names to error lists

        Returns:
            EventErrorDTO with validation details

        Example:
            EventErrorDTO.validation_error(
                "Invalid user data",
                {"email": ["Invalid format"], "age": ["Must be positive"]}
            )
        """
        return cls.create(
            message=message,
            validation_details=validation_details
        )