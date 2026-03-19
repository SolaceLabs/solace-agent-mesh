"""Model configurations router.

Provides endpoints for retrieving model configurations.
All sensitive authentication information (API keys, OAuth secrets) is filtered
from responses to ensure data security through the ModelConfigService business
logic layer.

Feature flag: SAM_FEATURE_MODEL_CONFIG_UI
  Controlled by environment variable. When disabled, all endpoints return 501 Not Implemented.
"""

import os
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session

from solace_agent_mesh.services.platform.services import ModelConfigService
from solace_agent_mesh.services.platform.api.dependencies import (
    get_model_config_service,
    get_platform_db,
    get_component_instance,
)
from solace_agent_mesh.services.platform.api.routers.dto.responses import ModelConfigurationResponse
from solace_agent_mesh.agent.adk.models.dynamic_model_provider_topics import get_model_config_update_topic
from solace_agent_mesh.shared.api.pagination import DataResponse
from solace_agent_mesh.shared.api.response_utils import create_data_response

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

def _emit_model_config_update(component, model_id: str, alias: str, model_config: dict | None):
    """Emit model config update events on both ID and alias topics.

    Publishes to get_model_config_update_topic twice: once with the model's database ID
    and once with the model's alias. This ensures agents subscribing by either
    identifier receive the update.

    Args:
        component: PlatformServiceComponent instance for publishing.
        model_id: The model's database UUID.
        alias: The model's alias string.
        model_config: The full LiteLlm config dict, or None to unconfigure.
    """
    payload = {"model_config": model_config}

    # Emit by ID
    topic_by_id = get_model_config_update_topic(component.namespace, model_id)
    component.publish_a2a_message(payload=payload, topic=topic_by_id)

    # Emit by alias
    topic_by_alias = get_model_config_update_topic(component.namespace, alias)
    component.publish_a2a_message(payload=payload, topic=topic_by_alias)

@router.post(
    "/models",
    summary="Create model configuration (placeholder)",
    description="Placeholder for creating a model configuration. Emits A2A update events.",
)
async def create_model(
    body: dict = Body(...),
    _: None = Depends(_require_model_config_ui_enabled),
     db: Session = Depends(get_platform_db),
    service: ModelConfigService = Depends(get_model_config_service),
    component=Depends(get_component_instance),
):
    # TODO: Implement actual creation logic (persist to DB, generate ID, etc.)
    model_config = body.get("model_config")
    model_id = body.get("id", "")
    alias = body.get("alias", "")

    if model_config and model_id and alias:
        _emit_model_config_update(component, model_id, alias, model_config)

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.put(
    "/models/{alias}",
    summary="Update model configuration (placeholder)",
    description="Placeholder for updating a model configuration. Emits A2A update events.",
)
async def update_model(
    alias: str,
    body: dict = Body(...),
    _: None = Depends(_require_model_config_ui_enabled),
    service: ModelConfigService = Depends(get_model_config_service),
    db: Session = Depends(get_platform_db),
    component=Depends(get_component_instance),
):
    # TODO: Implement actual update logic (persist changes to DB, etc.)
    model_config = body.get("model_config")
    model_id = body.get("id", "")

    if model_config and model_id:
        _emit_model_config_update(component, model_id, alias, model_config)

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )