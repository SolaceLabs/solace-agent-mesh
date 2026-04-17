"""Request DTOs for model configuration create and update operations."""

from typing import Optional, Dict, Any
from pydantic import Field

from solace_agent_mesh.services.platform.api.routers.dto.base import CamelCaseModel


class ModelConfigurationBaseRequest(CamelCaseModel):
    """Base request model with common model configuration fields.

    All fields are optional in the base class. Subclasses override to make
    specific fields required based on the operation (create vs update).
    """

    model_id: Optional[str] = Field(
        None,
        description="Model ID (UUID) — only used with validateOnly=true for stored credential fallback. Ignored by create/update.",
    )
    alias: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Model alias (e.g., 'gpt-4', 'claude-3')",
    )
    provider: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Model provider (e.g., 'openai', 'anthropic')",
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
        description="API base URL",
    )
    auth_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Authentication configuration",
    )
    model_params: Optional[Dict[str, Any]] = Field(
        None,
        description="Model-specific parameters",
    )
    max_input_tokens: Optional[int] = Field(
        None,
        ge=1,
        description="Context window size (max input tokens). Optional — used for the session context-usage indicator.",
    )
    description: Optional[str] = Field(
        None,
        description="Description of this model configuration",
    )


class ModelConfigurationCreateRequest(ModelConfigurationBaseRequest):
    """Request model for creating a new model configuration.

    Overrides base class to make required fields non-optional.
    """

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
    auth_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Authentication configuration. Must include 'type' field (e.g., 'apikey', 'oauth2', 'none').",
    )


class ModelConfigurationUpdateRequest(ModelConfigurationBaseRequest):
    """Request model for updating an existing model configuration.

    All fields are optional. Only provided fields will be updated.
    To preserve existing secrets while updating other fields, omit auth_config.
    If auth_config is provided, it will be merged with existing secrets.
    """

    pass

class ProviderQueryBaseRequest(CamelCaseModel):
    """Base request for endpoints that query a provider (supported-models, test-connection).

    Shared fields: model_id for stored-credential mode, plus api_base, auth_config,
    and model_params for request-provided credentials.
    """

    model_id: Optional[str] = Field(
        None,
        description="Model ID (UUID) to use stored credentials from database",
    )
    api_base: Optional[str] = Field(
        None,
        max_length=2048,
        description="API base URL",
    )
    auth_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Authentication configuration. Must include 'type' field (e.g., 'apikey', 'oauth2', 'none', 'aws_iam', 'gcp_service_account').",
    )
    model_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Model-specific parameters",
    )


class SupportedParamsRequest(CamelCaseModel):
    """Request model for querying supported parameters for a model.

    Provider is passed as a URL path parameter. This request only
    contains the model name in the body. No credentials needed — this
    is a local litellm registry lookup, not a provider API call.
    """

    model_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Model name (e.g., 'gpt-4o', 'claude-3-5-sonnet-20241022')",
    )


class ModelConfigurationTestRequest(ProviderQueryBaseRequest):
    """Request model for testing a model configuration connection.
    Supports two scenarios:
    1. New configurations: Provide provider, model_name, and auth credentials
    2. Existing model test: Provide model_id to load config from database
       - Provider/model_name are optional (loaded from database if not provided)
       - Stored credentials used as fallback for missing auth_config fields
    """

    provider: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Model provider (e.g., 'openai', 'anthropic'). Required if no model_id provided.",
    )
    model_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Full model name (litellm model string). Required if no model_id provided.",
    )
