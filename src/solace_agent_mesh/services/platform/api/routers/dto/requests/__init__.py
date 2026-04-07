"""Request DTOs for platform service."""

from .model_configuration_requests import (
    ModelConfigurationBaseRequest,
    ModelConfigurationCreateRequest,
    ModelConfigurationUpdateRequest,
    SupportedModelsRequest,
    SupportedParamsRequest,
    ModelConfigurationTestRequest,
)

__all__ = [
    "ModelConfigurationBaseRequest",
    "ModelConfigurationCreateRequest",
    "ModelConfigurationUpdateRequest",
    "SupportedModelsRequest",
    "SupportedParamsRequest",
    "ModelConfigurationTestRequest",
]
