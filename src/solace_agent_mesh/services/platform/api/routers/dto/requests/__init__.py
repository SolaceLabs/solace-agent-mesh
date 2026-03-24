"""Request DTOs for platform service."""

from .model_configuration_requests import (
    ModelConfigurationCreateRequest,
    ModelConfigurationUpdateRequest,
    SupportedModelsRequest,
)

__all__ = [
    "ModelConfigurationCreateRequest",
    "ModelConfigurationUpdateRequest",
    "SupportedModelsRequest",
]
