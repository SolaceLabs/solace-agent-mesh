"""
Authentication and authorization dependencies.

Provides FastAPI dependencies for:
- User authentication (extracting current user from request)
- Authorization (scope-based validation)
- User configuration resolution

Works with both gateways and services.
"""

from .dependencies import (
    get_current_user,
    get_config_resolver,
    get_user_config,
    ValidatedUserConfig,
    ComponentWithAuth,
)

__all__ = [
    "get_current_user",
    "get_config_resolver",
    "get_user_config",
    "ValidatedUserConfig",
    "ComponentWithAuth",
]
