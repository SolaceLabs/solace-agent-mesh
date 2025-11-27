"""
Version-related response DTOs.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductInfo(BaseModel):
    """Information about a single installed product."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Product identifier")
    name: str = Field(..., description="Human-readable product name")
    description: str = Field(..., description="Product description")
    version: str = Field(..., description="Product version")
    dependencies: Optional[dict[str, str]] = Field(
        default=None, description="Optional map of dependency names to versions"
    )


class VersionResponse(BaseModel):
    """Response containing version information for all installed products."""

    model_config = ConfigDict(populate_by_name=True)

    products: list[ProductInfo] = Field(
        ..., description="List of installed product information"
    )
