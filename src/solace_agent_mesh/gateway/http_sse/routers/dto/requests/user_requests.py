"""
User-related request DTOs.
"""

from pydantic import BaseModel, Field


class UpdateDefaultCredentialsRequest(BaseModel):
    """Request DTO for updating default user credentials."""

    id: str = Field(
        ..., min_length=1, max_length=100, description="User ID for development mode"
    )
    name: str = Field(
        ..., min_length=1, max_length=255, description="Display name for the user"
    )
    email: str = Field(
        ...,
        pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        description="Email address for the user"
    )
