"""
Shared authentication dependencies for both gateways and services.

Provides FastAPI dependencies for:
- User authentication (get_current_user)
- Authorization/scope validation (ValidatedUserConfig)
- Config resolution (get_config_resolver, get_user_config)

These work with any component that implements the required interface:
- get_config_resolver() -> ConfigResolver
- get_namespace() -> str
"""

import logging
from typing import Any, Protocol

from fastapi import Depends, HTTPException, Request, status
from solace_agent_mesh.common.middleware.config_resolver import ConfigResolver

log = logging.getLogger(__name__)


class ComponentWithAuth(Protocol):
    """
    Protocol for components that support authentication and authorization.

    Both WebUIBackendComponent (gateway) and PlatformServiceComponent (service)
    implement this interface.
    """
    def get_config_resolver(self) -> ConfigResolver: ...
    def get_namespace(self) -> str: ...


def get_current_user(request: Request) -> dict:
    """
    Extract authenticated user from request state.

    The user is set by OAuth middleware during request processing.
    Works with both gateway and service contexts.

    Args:
        request: FastAPI Request object

    Returns:
        Dictionary containing user information (id, email, name, authenticated, etc.)

    Raises:
        HTTPException: 401 if user is not authenticated
    """
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return request.state.user


def _get_component_from_context() -> ComponentWithAuth:
    """
    Get component instance from either gateway or service context.

    Tries platform service first, then falls back to http_sse gateway.

    Returns:
        Component instance implementing ComponentWithAuth protocol

    Raises:
        HTTPException: 503 if no component is available
    """
    try:
        from solace_agent_mesh.services.platform.api.dependencies import platform_component_instance
        if platform_component_instance is not None:
            return platform_component_instance
    except ImportError:
        pass

    try:
        from solace_agent_mesh.gateway.http_sse.dependencies import sac_component_instance
        if sac_component_instance is not None:
            return sac_component_instance
    except ImportError:
        pass

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Component not initialized"
    )


def get_config_resolver() -> ConfigResolver:
    """
    Get ConfigResolver from current component context.

    Works with both gateway and service components.

    Returns:
        ConfigResolver instance for authorization checks
    """
    component = _get_component_from_context()
    return component.get_config_resolver()


async def get_user_config(
    request: Request,
    user: dict = Depends(get_current_user),
    config_resolver: ConfigResolver = Depends(get_config_resolver),
) -> dict[str, Any]:
    """
    Get user configuration including profile and permissions.

    Works with both gateway and service components.

    Args:
        request: FastAPI Request object
        user: Authenticated user (from get_current_user dependency)
        config_resolver: ConfigResolver (from get_config_resolver dependency)

    Returns:
        Dictionary containing user configuration and permissions
    """
    component = _get_component_from_context()
    user_id = user.get("id")

    log.debug(f"get_user_config called for user_id: {user_id}")

    namespace = component.get_namespace()

    app_config = {}
    if hasattr(component, "component_config"):
        app_config = getattr(component, "component_config", {}).get("app_config", {})

    gateway_context = {}
    if hasattr(component, "gateway_id"):
        gateway_context = {
            "gateway_id": component.gateway_id,
            "gateway_app_config": app_config,
            "request": request,
        }

    return await config_resolver.resolve_user_config(
        user_id, gateway_context, app_config
    )


class ValidatedUserConfig:
    """
    FastAPI dependency for scope-based authorization.

    Validates that the current user has required scopes before allowing access.
    Works with both gateways (http_sse) and services (platform).

    Args:
        required_scopes: List of scope strings required for authorization

    Raises:
        HTTPException: 403 if user lacks required scopes

    Example:
        @router.post("/agents")
        async def create_agent(
            user_config: dict = Depends(ValidatedUserConfig(["sam:agents:create"])),
        ):
            # Only users with sam:agents:create scope can access
            ...
    """

    def __init__(self, required_scopes: list[str]):
        self.required_scopes = required_scopes

    async def __call__(
        self,
        request: Request,
        config_resolver: ConfigResolver = Depends(get_config_resolver),
        user_config: dict[str, Any] = Depends(get_user_config),
    ) -> dict[str, Any]:
        user_id = user_config.get("user_profile", {}).get("id")

        log.debug(
            f"ValidatedUserConfig called for user_id: {user_id} with required scopes: {self.required_scopes}"
        )

        if not config_resolver.is_feature_enabled(
            user_config,
            {"tool_metadata": {"required_scopes": self.required_scopes}},
            {},
        ):
            log.warning(
                f"Authorization denied for user '{user_id}'. Required scopes: {self.required_scopes}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not authorized. Required scopes: {self.required_scopes}",
            )

        return user_config


__all__ = [
    "get_current_user",
    "get_config_resolver",
    "get_user_config",
    "ValidatedUserConfig",
    "ComponentWithAuth",
]
