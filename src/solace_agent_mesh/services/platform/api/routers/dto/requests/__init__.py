"""Request DTOs for platform service."""

from .model_configuration_requests import (
    ModelConfigurationCreateRequest,
    ModelConfigurationUpdateRequest,
    ModelConfigurationTestRequest,
)

__all__ = [
    "ModelConfigurationCreateRequest",
    "ModelConfigurationUpdateRequest",
    "ModelConfigurationTestRequest",
]
