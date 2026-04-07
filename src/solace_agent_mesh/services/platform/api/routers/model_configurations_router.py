"""Model configurations router.

Provides endpoints for retrieving model configurations.
All sensitive authentication information (API keys, OAuth secrets) is filtered
from responses to ensure data security through the ModelConfigService business
logic layer.
"""

import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from solace_agent_mesh.services.platform.services import ModelConfigService
from solace_agent_mesh.services.platform.api.dependencies import (
    get_model_config_service,
    get_model_dependents_handler,
    get_platform_db,
    get_component_instance,
    require_model_config_ui_enabled,
    ModelDependentsHandler,
)
from solace_agent_mesh.services.platform.api.routers.dto.responses import (
    ModelConfigurationResponse,
    ModelConfigurationTestResponse,
    ModelConfigStatusResponse,
    ModelDependentResponse,
)
from solace_agent_mesh.services.platform.api.routers.dto.requests import (
    ModelConfigurationBaseRequest,
    ModelConfigurationCreateRequest,
    ModelConfigurationUpdateRequest,
    ModelConfigurationTestRequest,
)
from solace_agent_mesh.agent.adk.models.dynamic_model_provider_topics import get_model_config_update_topic
from solace_agent_mesh.shared.api.pagination import DataResponse
from solace_agent_mesh.shared.auth.dependencies import get_current_user
from solace_agent_mesh.shared.api.response_utils import create_data_response
from solace_agent_mesh.shared.exceptions.exceptions import ValidationErrorBuilder



router = APIRouter()


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
    _: None = Depends(require_model_config_ui_enabled),
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
    "/models/status",
    response_model=DataResponse[ModelConfigStatusResponse],
    summary="Check model configuration status",
    description="Check if default LLM models (general, planning) are properly configured. Not gated by feature flag.",
)
async def get_models_status(
    db: Session = Depends(get_platform_db),
    service: ModelConfigService = Depends(get_model_config_service),
) -> DataResponse[ModelConfigStatusResponse]:
    """Check whether the required default model aliases are configured.

    Returns configured=true only when both 'general' and 'planning' aliases
    exist and have a non-empty model_name value.
    """
    configs = service.list_all(db)
    if not configs:
        return create_data_response(ModelConfigStatusResponse(configured=False))

    alias_map = {c.alias: c for c in configs}
    general = alias_map.get("general")
    planning = alias_map.get("planning")

    if not general or not planning:
        return create_data_response(ModelConfigStatusResponse(configured=False))

    configured = bool(
        general.model_name and general.model_name.strip()
        and planning.model_name and planning.model_name.strip()
    )
    return create_data_response(ModelConfigStatusResponse(configured=configured))

@router.get(
    "/models/{model_id}",
    response_model=DataResponse[ModelConfigurationResponse],
    summary="Get model configuration by ID",
    description="Retrieve a model configuration by ID (UUID). Sensitive authentication information is excluded.",
)
async def get_model(
    model_id: str,
    _: None = Depends(require_model_config_ui_enabled),
    db: Session = Depends(get_platform_db),
    service: ModelConfigService = Depends(get_model_config_service),
) -> DataResponse[ModelConfigurationResponse]:
    """
    Retrieve a model configuration by ID.

    Args:
        model_id: The model UUID to look up

    Returns:
        DataResponse with model configuration data

    Raises:
        HTTPException: 404 if configuration not found
    """
    config = service.get_by_id(db, model_id)
    return create_data_response(config)


@router.post(
    "/models",
    response_model=DataResponse,
    summary="Create a model configuration",
    description="Create a new model configuration. The alias must be unique (case-sensitive). "
    "Pass validateOnly=true to test connectivity without persisting.",
)
async def create_model(
    request: ModelConfigurationBaseRequest,
    response: Response,
    _: None = Depends(require_model_config_ui_enabled),
    validate_only: bool = Query(False, alias="validateOnly"),
    db: Session = Depends(get_platform_db),
    user: dict = Depends(get_current_user),
    service: ModelConfigService = Depends(get_model_config_service),
    component=Depends(get_component_instance),
) -> DataResponse:
    if validate_only:
        test_request = ModelConfigurationTestRequest(
            model_id=request.model_id,
            provider=request.provider,
            model_name=request.model_name,
            api_base=request.api_base,
            auth_config=request.auth_config or {},
            model_params=request.model_params or {},
        )
        try:
            success, message = await asyncio.to_thread(service.test_connection, db, test_request)
        except Exception as e:
            success = False
            message = f"Test connection failed. {e}"
        return create_data_response(ModelConfigurationTestResponse(success=success, message=message))

    try:
        create_request = ModelConfigurationCreateRequest.model_validate(request.model_dump(exclude_none=True))
    except PydanticValidationError as e:
        builder = ValidationErrorBuilder().message("Invalid model configuration request")
        for error in e.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            builder.validation_detail(field, [error["msg"]])
        raise builder.build()

    created_by = user.get("id", "unknown")
    config = service.create(db, create_request, created_by=created_by)
    raw_config = service.get_by_id(db, config.id, raw=True)
    _emit_model_config_update(component, config.id, config.alias, raw_config)
    response.status_code = status.HTTP_201_CREATED
    return create_data_response(config)

@router.patch(
    "/models/{model_id}",
    response_model=DataResponse[ModelConfigurationResponse],
    summary="Update a model configuration",
    description="Update an existing model configuration by ID. Only provided fields are updated.",
)
async def update_model(
    model_id: str,
    request: ModelConfigurationUpdateRequest,
    _: None = Depends(require_model_config_ui_enabled),
    db: Session = Depends(get_platform_db),
    user: dict = Depends(get_current_user),
    service: ModelConfigService = Depends(get_model_config_service),
    component=Depends(get_component_instance),
) -> DataResponse[ModelConfigurationResponse]:
    updated_by = user.get("id", "unknown")
    config = service.update(db, model_id, request, updated_by=updated_by)
    raw_config = service.get_by_id(db, config.id, raw=True)
    _emit_model_config_update(component, config.id, config.alias, raw_config)
    return create_data_response(config)


@router.get(
    "/models/{model_id}/dependents",
    response_model=DataResponse[list[ModelDependentResponse]],
    summary="Get agents that depend on a model",
    description="Return deployed agents whose model_provider references the given model by alias or ID. Requires enterprise package.",
)
async def get_model_dependents(
    model_id: str,
    _: None = Depends(require_model_config_ui_enabled),
    db: Session = Depends(get_platform_db),
    service: ModelConfigService = Depends(get_model_config_service),
) -> DataResponse[list[ModelDependentResponse]]:
    """Return agents that depend on the given model configuration.

    Attempts to import the enterprise ModelDependentsService. If the enterprise
    package is not installed, returns an empty list.
    """
    config = service.get_by_id(db, model_id)

    try:
        from solace_agent_mesh_enterprise.platform_service.services.model_dependents_service import (
            ModelDependentsService,
        )
        from solace_agent_mesh_enterprise.platform_service.repositories.agent_repository import (
            AgentRepository,
        )
        from solace_agent_mesh_enterprise.platform_service.repositories.deployment_repository import (
            DeploymentRepository,
        )

        dependents_service = ModelDependentsService(AgentRepository(), DeploymentRepository())
        dependents = dependents_service.get_dependents(db, config.alias, config.id)

        return create_data_response([
            ModelDependentResponse(
                id=str(agent.id),
                name=agent.name,
                type=agent.type,
                deployment_status=agent.deployment_status,
            )
            for agent in dependents
        ])
    except ImportError:
        return create_data_response([])


@router.delete(
    "/models/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a model configuration",
    description="Delete a model configuration by ID. Automatically undeploys any agents that depend on this model. This action cannot be undone.",
)
async def delete_model(
    model_id: str,
    _: None = Depends(require_model_config_ui_enabled),
    db: Session = Depends(get_platform_db),
    user: dict = Depends(get_current_user),
    service: ModelConfigService = Depends(get_model_config_service),
    component=Depends(get_component_instance),
    dependents_handler: ModelDependentsHandler = Depends(get_model_dependents_handler),
) -> None:
    config = service.get_by_id(db, model_id)
    await dependents_handler.undeploy_dependents(config.alias, config.id, component)
    service.delete(db, model_id)
    _emit_model_config_update(component, config.id, config.alias, None)


