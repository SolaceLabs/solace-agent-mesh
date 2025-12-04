"""
Shared utility functions.

Contains generic utility functions used across the application.
"""

import uuid


def generate_uuid() -> str:
    """Generate a UUID string for database storage."""
    return str(uuid.uuid4())


def to_snake_case(name: str) -> str:
    """Convert a string to snake_case."""
    return name.replace(" ", "_").lower()


def to_pascal_case(name: str) -> str:
    """Convert a string to PascalCase."""
    return "".join(word.capitalize() for word in name.split())