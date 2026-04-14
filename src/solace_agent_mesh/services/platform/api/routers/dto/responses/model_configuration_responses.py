"""Response DTOs for model configurations.

These schemas define safe response models that exclude sensitive information
like API keys and OAuth client secrets. Credential filtering is handled by
ModelConfigService using redact_auth_config().
"""

from typing import Optional, Dict, Any
from pydantic import Field

from solace_agent_mesh.services.platform.api.routers.dto.base import CamelCaseModel


class ModelConfigurationResponse(CamelCaseModel):
    """Safe response model for model configuration without secrets."""

    id: str = Field(..., description="Unique identifier for the model configuration")
    alias: str = Field(..., description="Model alias (e.g., 'gpt-4', 'claude-3')")
    provider: Optional[str] = Field(
        None, description="Model provider (e.g., 'openai', 'anthropic', 'bedrock')"
    )
    model_name: Optional[str] = Field(None, description="Full model name")
    api_base: Optional[str] = Field(
        None, description="API base URL (if using custom endpoint)"
    )
    auth_type: str = Field(
        ..., description="Type of authentication configured (e.g., 'apikey', 'oauth2', 'none')"
    )
    auth_config: Dict[str, Any] = Field(
        default_factory=dict, description="Authentication configuration (secrets redacted)"
    )
    model_params: Dict[str, Any] = Field(
        default_factory=dict, description="Model-specific parameters"
    )
    description: Optional[str] = Field(
        None, description="Description of this model configuration"
    )
    created_by: str = Field(..., description="User who created this configuration")
    updated_by: str = Field(..., description="User who last updated this configuration")
    created_time: int = Field(..., description="Creation timestamp (epoch ms)")
    updated_time: int = Field(..., description="Last update timestamp (epoch ms)")

class ModelConfigStatusResponse(CamelCaseModel):
    """Response model for model configuration status check."""

    configured: bool = Field(
        ..., description="Whether default LLM models (general, planning) are properly configured"
    )

class ModelConfigurationTestResponse(CamelCaseModel):
    """Response model for model configuration test connection result."""

    success: bool = Field(
        ..., description="Whether the test connection was successful"
    )
    message: str = Field(
        ..., description="Test result message (error details if failed, response content if succeeded)"
    )


class SupportedParamsResponse(CamelCaseModel):
    """Response model for supported model parameters.

    Returns the list of parameter names (snake_case) that a model supports,
    based on litellm's internal registry.
    """

    supported_params: list[str] = Field(
        ..., description="List of supported parameter names (snake_case)"
    )


class ModelDependentResponse(CamelCaseModel):
    """Response model for an agent that depends on a model configuration."""

    id: str = Field(..., description="Unique identifier of the agent")
    name: str = Field(..., description="Name of the agent")
    type: str = Field(..., description="Type of the agent")
    deployment_status: str = Field(..., description="Current deployment status of the agent")
