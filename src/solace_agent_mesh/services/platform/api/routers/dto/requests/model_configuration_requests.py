"""Request DTOs for model configuration create and update operations."""

from typing import Optional, Dict, Any
from pydantic import Field

from solace_agent_mesh.services.platform.api.routers.dto.base import CamelCaseModel


class ModelConfigurationBaseRequest(CamelCaseModel):
    """Base request model with common model configuration fields.

    All fields are optional in the base class. Subclasses override to make
    specific fields required based on the operation (create vs update).
    """

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

class SupportedModelsRequest(CamelCaseModel):
    """Request model for querying supported models from a provider.
    Supports two modes:
    1. Editing mode: provide model_alias to use stored credentials
    2. Creating mode: provide auth_type and appropriate credentials
    """
    provider: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Provider ID (e.g., 'openai', 'anthropic', 'custom')",
    )
    model_alias: Optional[str] = Field(
        None,
        description="Model alias for editing mode (uses stored credentials from database)",
    )
    api_base: Optional[str] = Field(
        None,
        max_length=2048,
        description="API base URL for custom endpoints (required for custom provider in creating mode)",
    )
    auth_type: Optional[str] = Field(
        None,
        max_length=50,
        description="Authentication type ('apikey', 'oauth2', 'none', 'aws_iam', 'gcp_service_account')",
    )
    api_key: Optional[str] = Field(
        None,
        description="API key for apikey authentication",
    )
    client_id: Optional[str] = Field(
        None,
        description="OAuth2 client ID",
    )
    client_secret: Optional[str] = Field(
        None,
        description="OAuth2 client secret",
    )
    token_url: Optional[str] = Field(
        None,
        description="OAuth2 token URL",
    )
    aws_access_key_id: Optional[str] = Field(
        None,
        description="AWS Access Key ID for aws_iam authentication",
    )
    aws_secret_access_key: Optional[str] = Field(
        None,
        description="AWS Secret Access Key for aws_iam authentication",
    )
    aws_session_token: Optional[str] = Field(
        None,
        description="AWS Session Token for aws_iam authentication (optional, for temporary credentials)",
    )
    gcp_service_account_json: Optional[str] = Field(
        None,
        description="GCP Service Account JSON key for gcp_service_account authentication",
    )
    model_params: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Provider-specific parameters (e.g., awsRegionName, vertexProject, vertexLocation, apiVersion)",
    )
