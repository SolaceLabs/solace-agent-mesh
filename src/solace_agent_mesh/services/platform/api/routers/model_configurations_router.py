"""Model configurations router.

Provides endpoints for retrieving model configurations.
All sensitive authentication information (API keys, OAuth secrets) is filtered
from responses to ensure data security through the ModelConfigService business
logic layer.

Feature flag: SAM_FEATURE_MODEL_CONFIG_UI
  Controlled by environment variable. When disabled, all endpoints return 501 Not Implemented.
"""

import logging
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session


from solace_agent_mesh.services.platform.services import ModelConfigService, ModelListService
from solace_agent_mesh.services.platform.api.dependencies import (
    get_model_config_service,
    get_model_list_service,
    get_platform_db,
)

from solace_agent_mesh.services.platform.api.routers.dto.responses import ModelConfigurationResponse
from solace_agent_mesh.services.platform.api.routers.dto.requests import (
    ModelConfigurationCreateRequest,
    ModelConfigurationUpdateRequest,
)
from solace_agent_mesh.shared.api.pagination import DataResponse
from solace_agent_mesh.shared.auth.dependencies import get_current_user
from solace_agent_mesh.shared.api.response_utils import create_data_response

log = logging.getLogger(__name__)


router = APIRouter()


def _require_model_config_ui_enabled() -> bool:
    """Dependency that checks if model configuration UI feature is enabled.

    Checks the SAM_FEATURE_MODEL_CONFIG_UI environment variable at request time.

    Returns:
        True if feature is enabled, False otherwise.

    Raises:
        HTTPException: 501 Not Implemented if feature is disabled.
    """
    is_enabled = os.environ.get("SAM_FEATURE_MODEL_CONFIG_UI", "false").lower() == "true"
    if not is_enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Model configuration feature is not enabled",
        )
    return True


@router.get(
    "/models",
    response_model=DataResponse[list[ModelConfigurationResponse]],
    summary="List all model configurations",
    description="Retrieve all model configurations. Sensitive authentication information (API keys, secrets) is excluded.",
)
async def list_models(
    _: None = Depends(_require_model_config_ui_enabled),
    db: Session = Depends(get_platform_db),
    service: ModelConfigService = Depends(get_model_config_service),
) -> DataResponse[list[ModelConfigurationResponse]]:
    """
    Retrieve all model configurations.

    Sensitive information (API keys, OAuth client secrets) is excluded from the response.
    Only the authentication type (apikey, oauth2, or none) is returned.

    Returns:
        DataResponse with list of model configurations with safe data
    """
    configurations = service.list_all(db)
    return create_data_response(configurations)

@router.get(
    "/models/{alias}",
    response_model=DataResponse[ModelConfigurationResponse],
    summary="Get model configuration by alias",
    description="Retrieve a model configuration by alias (e.g., 'gpt-4', 'claude-3'). Sensitive authentication information is excluded.",
)
async def get_model(
    alias: str,
    _: None = Depends(_require_model_config_ui_enabled),
    db: Session = Depends(get_platform_db),
    service: ModelConfigService = Depends(get_model_config_service),
) -> DataResponse[ModelConfigurationResponse]:
    """
    Retrieve a model configuration by alias.

    The alias lookup is case-sensitive. Sensitive information (API keys, OAuth
    client secrets) is excluded from the response.

    Args:
        alias: The model alias to look up

    Returns:
        DataResponse with model configuration data

    Raises:
        HTTPException: 404 if configuration not found
    """
    config = service.get_by_alias(db, alias)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model configuration with alias '{alias}' not found",
        )

    return create_data_response(config)


@router.post(
    "/models",
    response_model=DataResponse[ModelConfigurationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a model configuration",
    description="Create a new model configuration. The alias must be unique (case-sensitive).",
)
async def create_model(
    request: ModelConfigurationCreateRequest,
    _: None = Depends(_require_model_config_ui_enabled),
    db: Session = Depends(get_platform_db),
    user: dict = Depends(get_current_user),
    service: ModelConfigService = Depends(get_model_config_service),
) -> DataResponse[ModelConfigurationResponse]:
    """
    Create a new model configuration.

    Args:
        request: Model configuration details
        user: Authenticated user (from OAuth middleware)

    Returns:
        DataResponse with the created model configuration

    Raises:
        HTTPException: 400 if alias is invalid, 409 if alias already exists, 500 on server error
    """
    try:
        created_by = user.get("id", "unknown")
        config = service.create(db, request, created_by=created_by)
        return create_data_response(config)
    except ValueError as e:
        log.warning(f"Invalid model creation request: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except Exception as e:
        log.error(f"Failed to create model configuration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create model configuration",
        )

@router.put(
    "/models/{alias}",
    response_model=DataResponse[ModelConfigurationResponse],
    summary="Update a model configuration",
    description="Update an existing model configuration by alias. Only provided fields are updated.",
)
async def update_model(
    alias: str,
    request: ModelConfigurationUpdateRequest,
    _: None = Depends(_require_model_config_ui_enabled),
    db: Session = Depends(get_platform_db),
    user: dict = Depends(get_current_user),
    service: ModelConfigService = Depends(get_model_config_service),
) -> DataResponse[ModelConfigurationResponse]:
    """
    Update an existing model configuration.

    Args:
        alias: The model alias to update
        request: Fields to update (only non-None fields are modified)
        user: Authenticated user (from OAuth middleware)

    Returns:
        DataResponse with the updated model configuration

    Raises:
        HTTPException: 404 if not found, 409 if new alias conflicts, 500 on server error
    """
    try:
        updated_by = user.get("id", "unknown")
        config = service.update(db, alias, request, updated_by=updated_by)

        if not config:
            log.debug(f"Model configuration not found with alias: {alias}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model configuration with alias '{alias}' not found",
            )

        return create_data_response(config)
    except ValueError as e:
        log.warning(f"Invalid model update request: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to update model configuration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update model configuration",
        )


@router.delete(
    "/models/{alias}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a model configuration",
    description="Delete a model configuration by alias. This action cannot be undone.",
)
async def delete_model(
    alias: str,
    _: None = Depends(_require_model_config_ui_enabled),
    db: Session = Depends(get_platform_db),
    user: dict = Depends(get_current_user),
    service: ModelConfigService = Depends(get_model_config_service),
) -> None:
    """
    Delete a model configuration.

    Args:
        alias: The model alias to delete
        user: Authenticated user (from OAuth middleware)

    Raises:
        HTTPException: 404 if not found, 500 on server error
    """
    try:
        deleted = service.delete(db, alias)

        if not deleted:
            log.debug(f"Model configuration not found with alias: {alias}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model configuration with alias '{alias}' not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to delete model configuration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete model configuration",
        )

@router.get(
    "/supported-models/{provider}",
    response_model=DataResponse[list[dict]],
    summary="List supported models for a provider",
    description="Retrieve supported models for a specific provider. For openai_compatible, optionally pass model_alias to use stored credentials.",
)
async def list_supported_models_by_provider(
    provider: str,
    model_alias: Optional[str] = None,
    _: None = Depends(_require_model_config_ui_enabled),
    db: Session = Depends(get_platform_db),
    service: ModelListService = Depends(get_model_list_service),
    config_service: ModelConfigService = Depends(get_model_config_service),
) -> DataResponse[list[dict]]:
    """
    Retrieve supported models for a specific provider.

    For standard providers, uses LiteLLM to fetch available models.
    For openai_compatible providers with model_alias, acts as a proxy:
      - Looks up the model config by alias
      - Uses stored API base and credentials to fetch models from that endpoint
      - Returns models securely without exposing credentials

    Args:
        provider: The provider ID (e.g., 'openai', 'anthropic', 'openai_compatible')
        model_alias: Optional. For openai_compatible, the model alias to look up for stored credentials

    Returns:
        DataResponse with list of supported models for the provider
    """
    try:
        # For openai_compatible with model_alias, use stored credentials
        if provider == "openai_compatible" and model_alias:
            # Use raw unredacted config for backend proxy calls
            raw_config = config_service.get_raw_config_by_alias(db, model_alias)
            if not raw_config:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Model configuration with alias '{model_alias}' not found",
                )

            # Use the service to fetch models from the configured endpoint
            models = service.get_models_by_provider_with_config(
                provider=provider,
                api_base=raw_config.api_base,
                auth_type=raw_config.model_auth_type,
                auth_config=raw_config.model_auth_config,
            )
            return DataResponse.create(models)

        # Standard LiteLLM provider
        models = service.get_models_by_provider(provider)
        return DataResponse.create(models)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to retrieve supported models for provider {provider}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve supported models for provider {provider}",
        )
