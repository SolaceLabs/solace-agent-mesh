"""Request DTOs for model configuration create and update operations."""

from typing import Optional, Dict, Any
from pydantic import Field

from solace_agent_mesh.services.platform.api.routers.dto.base import CamelCaseModel


class ModelConfigurationCreateRequest(CamelCaseModel):
    """Request model for creating a new model configuration."""

    alias: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Model alias (e.g., 'gpt-4', 'claude-3')",
    )
    provider: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Model provider (e.g., 'openai', 'anthropic')",
    )
    model_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full model name",
    )
    api_base: str = Field(
        ...,
        max_length=2048,
        description="API base URL",
    )
    auth_type: str = Field(
        default="none",
        max_length=50,
        description="Type of authentication (e.g., 'apikey', 'oauth2', 'none')",
    )
    auth_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Authentication configuration (secrets like api_key should be included)",
    )
    model_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Model-specific parameters",
    )
    description: Optional[str] = Field(
        None,
        description="Description of this model configuration",
    )


class ModelConfigurationUpdateRequest(CamelCaseModel):
    """Request model for updating an existing model configuration.

    All fields are optional. Only provided fields will be updated.
    To preserve existing secrets while updating other fields, omit auth_config.
    If auth_config is provided, it will be merged with existing secrets.
    """

    alias: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Model alias (not recommended to update as it's the unique key)",
    )
    provider: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Model provider",
    )
    model_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Full model name",
    )
    api_base: Optional[str] = Field(
        None,
        max_length=2048,
        description="API base URL (set to empty string to clear)",
    )
    auth_type: Optional[str] = Field(
        None,
        max_length=50,
        description="Type of authentication",
    )
    auth_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Authentication configuration (will be merged with existing config)",
    )
    model_params: Optional[Dict[str, Any]] = Field(
        None,
        description="Model-specific parameters",
    )
    description: Optional[str] = Field(
        None,
        description="Description of this model configuration",
    )
