"""Model configurations router.

Provides endpoints for retrieving model configurations.
All sensitive authentication information (API keys, OAuth secrets) is filtered
from responses to ensure data security through the ModelConfigService business
logic layer.
"""

import os
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from openfeature import api as openfeature_api

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
    SupportedModelsRequest,
    ModelConfigurationTestRequest,
)
from solace_agent_mesh.agent.adk.models.dynamic_model_provider_topics import get_model_config_update_topic
from solace_agent_mesh.shared.api.pagination import DataResponse
from solace_agent_mesh.shared.auth.dependencies import get_current_user
from solace_agent_mesh.shared.api.response_utils import create_data_response
from solace_agent_mesh.shared.exceptions.exceptions import ValidationErrorBuilder


router = APIRouter()


def _require_model_config_ui_enabled() -> bool:
    """Dependency that checks if model configuration UI feature is enabled.

    Checks the model_config_ui environment variable at request time.

    Returns:
        True if feature is enabled, False otherwise.

    Raises:
        HTTPException: 501 Not Implemented if feature is disabled.
    """
    is_enabled = openfeature_api.get_client().get_boolean_value("model_config_ui", False)
    if not is_enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Model configuration feature is not enabled",
        )
    return True


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
    """
    Fetch supported models from a provider.

    Two modes of operation:
    - **Editing mode**: Provide model_alias to use stored credentials from database
    - **Creating mode**: Provide auth_type and appropriate credentials to query provider

    Auth validation and config building is delegated to ModelListService.
    """
    # Mode 1: Editing - use stored credentials from database
    if request.model_alias:
        models = config_service.get_models_from_provider_by_alias(db, request.model_alias, service)
        return DataResponse.create(models)

    # Mode 2: Creating - use credentials from request
    # Validate that either model_alias or auth_type is provided
    if not request.auth_type:
        raise ValidationErrorBuilder(
            message="Either model_alias (for editing) or auth_type with credentials (for creating) is required"
        ).entity_type("SupportedModelsRequest").entity_identifier(request.provider).build()

    # Delegate auth validation and config building to service
    models = service.get_models_with_new_credentials(
        provider=request.provider,
        api_base=request.api_base,
        auth_type=request.auth_type,
        api_key=request.api_key,
        client_id=request.client_id,
        client_secret=request.client_secret,
        token_url=request.token_url,
        aws_access_key_id=request.aws_access_key_id,
        aws_secret_access_key=request.aws_secret_access_key,
        aws_session_token=request.aws_session_token,
        gcp_service_account_json=request.gcp_service_account_json,
        model_params=request.model_params,
    )

    return DataResponse.create(models)  

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
