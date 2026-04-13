"""Request DTOs for platform service."""

from .model_configuration_requests import (
    ModelConfigurationBaseRequest,
    ModelConfigurationCreateRequest,
    ModelConfigurationUpdateRequest,
    ProviderQueryBaseRequest,
    SupportedParamsRequest,
    ModelConfigurationTestRequest,
)

__all__ = [
    "ModelConfigurationBaseRequest",
    "ModelConfigurationCreateRequest",
    "ModelConfigurationUpdateRequest",
    "ProviderQueryBaseRequest",
    "SupportedParamsRequest",
    "ModelConfigurationTestRequest",
]
