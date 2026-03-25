"""Request DTOs for platform service."""

from .model_configuration_requests import (
    ModelConfigurationCreateRequest,
    ModelConfigurationUpdateRequest,
    SupportedModelsRequest,
    ModelConfigurationTestRequest,
)

__all__ = [
    "ModelConfigurationCreateRequest",
    "ModelConfigurationUpdateRequest",
    "SupportedModelsRequest",
    "ModelConfigurationTestRequest",
]
