"""Model configurations router.

Provides endpoints for retrieving model configurations.
All sensitive authentication information (API keys, OAuth secrets) is filtered
from responses to ensure data security through the ModelConfigService business
logic layer.

Feature flag: model_config_ui
  When disabled, all endpoints return 501 Not Implemented.
"""

import logging
from openfeature import api as openfeature_api
from fastapi import APIRouter, Depends, HTTPException, status

from solace_agent_mesh.services.platform.services import ModelConfigService
from solace_agent_mesh.services.platform.api.dependencies import get_model_config_service
from solace_agent_mesh.services.platform.api.routers.dto.responses import (
    ModelConfigurationResponse,
    ModelConfigurationListResponse,
)

log = logging.getLogger(__name__)

router = APIRouter()

_MODEL_CONFIG_UI_FLAG = "model_config_ui"


def _require_model_config_ui_enabled() -> bool:
    """Dependency that checks if model configuration UI feature is enabled.

    Returns:
        True if feature is enabled, False otherwise.

    Raises:
        HTTPException: 501 Not Implemented if feature is disabled.
    """
    is_enabled = openfeature_api.get_client().get_boolean_value(_MODEL_CONFIG_UI_FLAG, False)
    if not is_enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Model configuration feature is not enabled",
        )
    return is_enabled


@router.get(
    "/models",
    response_model=ModelConfigurationListResponse,
    summary="List all model configurations",
    description="Retrieve all model configurations. Sensitive authentication information (API keys, secrets) is excluded.",
)
async def list_models(
    _: None = Depends(_require_model_config_ui_enabled),
    service: ModelConfigService = Depends(get_model_config_service),
) -> ModelConfigurationListResponse:
    """
    Retrieve all model configurations.

    Sensitive information (API keys, OAuth client secrets) is excluded from the response.
    Only the authentication type (apikey, oauth2, or none) is returned.

    Returns:
        ModelConfigurationListResponse: List of model configurations with safe data
    """
    try:
        configurations = service.list_all()
        return ModelConfigurationListResponse(
            configurations=configurations,
            total=len(configurations),
        )
    except Exception as e:
        log.error(f"Failed to retrieve model configurations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve model configurations",
        )


@router.get(
    "/models/{alias}",
    response_model=ModelConfigurationResponse,
    summary="Get model configuration by alias",
    description="Retrieve a model configuration by alias (e.g., 'gpt-4', 'claude-3'). Sensitive authentication information is excluded.",
)
async def get_model(
    alias: str,
    _: None = Depends(_require_model_config_ui_enabled),
    service: ModelConfigService = Depends(get_model_config_service),
) -> ModelConfigurationResponse:
    """
    Retrieve a model configuration by alias.

    The alias lookup is case. Sensitive information (API keys, OAuth
    client secrets) is excluded from the response.

    Args:
        alias: The model alias to look up

    Returns:
        ModelConfigurationResponse: The model configuration with safe data

    Raises:
        HTTPException: 404 if configuration not found
    """
    try:
        config = service.get_by_alias(alias)

        if not config:
            log.debug(f"Model configuration not found with alias: {alias}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model configuration with alias '{alias}' not found",
            )

        return config
    except HTTPException:
        raise
    except Exception as e:
        log.error(
            f"Failed to retrieve model configuration by alias {alias}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve model configuration",
        )
