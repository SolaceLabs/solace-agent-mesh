"""Model configurations router.

Provides endpoints for retrieving model configurations.
All sensitive authentication information (API keys, OAuth secrets) is filtered
from responses to ensure data security through the ModelConfigService business
logic layer.

Feature flag: SAM_FEATURE_MODEL_CONFIG_UI
  Controlled by environment variable. When disabled, all endpoints return 501 Not Implemented.
"""

import asyncio
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
    get_component_instance,
)

from solace_agent_mesh.services.platform.api.routers.dto.responses import (
    ModelConfigurationResponse,
    ModelConfigurationTestResponse,
)
from solace_agent_mesh.services.platform.api.routers.dto.requests import (
    ModelConfigurationCreateRequest,
    ModelConfigurationUpdateRequest,
    ModelConfigurationTestRequest,
    SupportedModelsRequest
)
from solace_agent_mesh.agent.adk.models.dynamic_model_provider_topics import get_model_config_update_topic
from solace_agent_mesh.shared.api.pagination import DataResponse
from solace_agent_mesh.shared.auth.dependencies import get_current_user
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

@router.post(
    "/models/test",
    response_model=DataResponse[ModelConfigurationTestResponse],
    summary="Test a model configuration",
    description="Test connectivity by making a minimal LLM call. Supports both new configurations (all config in body) and existing models (provide alias to use stored credentials as fallback).",
)
async def test_model_connection(
    request: ModelConfigurationTestRequest,
    _: None = Depends(_require_model_config_ui_enabled),
    db: Session = Depends(get_platform_db),
    service: ModelConfigService = Depends(get_model_config_service),
) -> DataResponse[ModelConfigurationTestResponse]:
    """
    Test a model configuration connection.

    Makes a minimal LLM call with the provided configuration to verify connectivity
    and validate credentials. Supports two scenarios:

    1. New model: Provide all configuration details
    2. Editing existing model: Provide alias to use stored credentials as fallback

    When testing an existing model by alias, any empty auth_config fields will use
    the stored values. This allows testing a new provider/model with existing credentials.

    Args:
        request: Test request with model configuration details
        _: Feature flag dependency
        db: Database session
        service: Model configuration service

    Returns:
        DataResponse with success status and message
    """
    success, message = await asyncio.to_thread(service.test_connection, db, request)
    response = ModelConfigurationTestResponse(success=success, message=message)
    return create_data_response(response)

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
    component=Depends(get_component_instance),
) -> DataResponse[ModelConfigurationResponse]:
    created_by = user.get("id", "unknown")
    config = service.create(db, request, created_by=created_by)
    raw_config = service.get_by_alias(db, config.alias, raw=True)
    _emit_model_config_update(component, config.id, config.alias, raw_config)
    return create_data_response(config)

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
    component=Depends(get_component_instance),
) -> DataResponse[ModelConfigurationResponse]:
    updated_by = user.get("id", "unknown")
    config = service.update(db, alias, request, updated_by=updated_by)
    raw_config = service.get_by_alias(db, config.alias, raw=True)
    _emit_model_config_update(component, config.id, config.alias, raw_config)
    return create_data_response(config)


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
    component=Depends(get_component_instance),
) -> None:
    config = service.get_by_alias(db, alias)
    service.delete(db, alias)
    _emit_model_config_update(component, config.id, alias, None)


@router.post(
    "/supported-models",
    response_model=DataResponse[list[dict]],
    summary="List supported models for a provider",
    description="Retrieve supported models by querying the provider API directly. Use model_alias for editing (stored credentials) or provide credentials for creating new models.",
)
async def list_supported_models_by_provider(
    request: SupportedModelsRequest,
    _: None = Depends(_require_model_config_ui_enabled),
    db: Session = Depends(get_platform_db),
    service: ModelListService = Depends(get_model_list_service),
    config_service: ModelConfigService = Depends(get_model_config_service),
) -> DataResponse[list[dict]]:
    provider = request.provider
    model_alias = request.model_alias

    # Mode 1: Editing - use stored credentials from database
    if model_alias:
        raw_config = config_service.get_raw_config_by_alias(db, model_alias)
        if not raw_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model configuration with alias '{model_alias}' not found",
            )

        models = service.get_models_by_provider_with_config(
            provider=raw_config.provider,
            api_base=raw_config.api_base,
            auth_type=raw_config.model_auth_type,
            auth_config=raw_config.model_auth_config,
            model_params=raw_config.model_params or {},
        )
        return DataResponse.create(models)

    # Mode 2: Creating - use credentials from request
    if not request.auth_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either model_alias (for editing) or auth_type with credentials (for creating) is required",
        )

    # Validate and build auth_config based on auth_type
    auth_config = {}

    if request.auth_type == "apikey":
        if not request.api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="api_key is required for apikey authentication",
            )
        auth_config["api_key"] = request.api_key

    elif request.auth_type == "oauth2":
        if not (request.client_id and request.client_secret and request.token_url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="client_id, client_secret, and token_url are required for oauth2 authentication",
            )
        auth_config["client_id"] = request.client_id
        auth_config["client_secret"] = request.client_secret
        auth_config["token_url"] = request.token_url

    elif request.auth_type == "aws_iam":
        if not (request.aws_access_key_id and request.aws_secret_access_key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="aws_access_key_id and aws_secret_access_key are required for aws_iam authentication",
            )
        auth_config["aws_access_key_id"] = request.aws_access_key_id
        auth_config["aws_secret_access_key"] = request.aws_secret_access_key
        if request.aws_session_token:
            auth_config["aws_session_token"] = request.aws_session_token

    elif request.auth_type == "gcp_service_account":
        if not request.gcp_service_account_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="gcp_service_account_json is required for gcp_service_account authentication",
            )
        auth_config["service_account_json"] = request.gcp_service_account_json

    elif request.auth_type == "none":
        pass  # No credentials needed
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported auth_type: {request.auth_type}",
        )

    # Query provider with provided credentials
    models = service.get_models_by_provider_with_config(
        provider=provider,
        api_base=request.api_base,
        auth_type=request.auth_type,
        auth_config=auth_config,
        model_params=request.model_params or {},
    )

    return DataResponse.create(models)
