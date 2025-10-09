"""
User-related response DTOs.
"""

from pydantic import BaseModel


class UpdateDefaultCredentialsResponse(BaseModel):
    """Response DTO for updating default user credentials."""

    success: bool
    message: str
    credentials: dict[str, str]
