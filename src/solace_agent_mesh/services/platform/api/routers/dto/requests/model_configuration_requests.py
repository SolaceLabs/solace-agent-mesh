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
    api_base: Optional[str] = Field(
        None,
        max_length=2048,
        description="API base URL (auto-filled for known providers if not provided)",
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


class ModelConfigurationTestRequest(CamelCaseModel):
    """Request model for testing a model configuration connection.

    Supports two scenarios:
    1. New configurations: Provide provider, model_name, and auth credentials (no alias)
    2. Existing model test: Provide alias to load all config from database
       - If alias is provided, provider/model_name are optional (loaded from database)
       - Can override provider/model_name with new values to test compatibility
       - Credentials loaded from database if not provided in authConfig

    When alias is provided:
    - Stored credentials are used as fallback for any missing/empty auth_config fields
    - Stored provider/model_name used if not provided in request
    - Can override provider/model_name to test if credentials work with new configuration
    """

    alias: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Optional: Model alias to load configuration from database",
    )
    provider: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Model provider (e.g., 'openai', 'anthropic'). Required if no alias provided.",
    )
    model_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Full model name (litellm model string). Required if no alias provided.",
    )
    api_base: Optional[str] = Field(
        None,
        max_length=2048,
        description="API base URL (auto-filled for known providers if not provided)",
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
        description="Model-specific parameters to test validation",
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
