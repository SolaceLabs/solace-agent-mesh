"""Providers router.

Provides endpoints for querying provider capabilities: listing available models
and fetching supported parameters. These are provider-level queries that do not
operate on stored model configurations.
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from solace_agent_mesh.services.platform.services import ModelConfigService, ModelListService
from solace_agent_mesh.services.platform.api.dependencies import (
    get_model_config_service,
    get_model_list_service,
    get_platform_db,
    require_model_config_ui_enabled,
)
from solace_agent_mesh.services.platform.api.routers.dto.requests import (
    ProviderQueryBaseRequest,
    SupportedParamsRequest,
)
from solace_agent_mesh.services.platform.api.routers.dto.responses import (
    SupportedParamsResponse,
)
from solace_agent_mesh.shared.api.pagination import DataResponse
from solace_agent_mesh.shared.api.response_utils import create_data_response
from solace_agent_mesh.shared.exceptions.exceptions import ValidationErrorBuilder

log = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/providers/{provider}/models",
    response_model=DataResponse[list[dict]],
    summary="List available models from a provider",
    description="Query a provider's API to list available models. Use model_id for editing (stored credentials) or provide credentials directly.",
)
async def list_provider_models(
    provider: str,
    request: ProviderQueryBaseRequest,
    _: None = Depends(require_model_config_ui_enabled),
    db: Session = Depends(get_platform_db),
    service: ModelListService = Depends(get_model_list_service),
    config_service: ModelConfigService = Depends(get_model_config_service),
) -> DataResponse[list[dict]]:
    """
    Fetch available models from a provider.

    Three modes of operation:
    - **Editing (no changes)**: Provide model_id only — uses stored credentials
    - **Editing (with changes)**: Provide model_id + auth_config — merges stored
      credentials with overrides (stored values fill in missing fields).
      If auth type changed, only overrides are used (no cross-provider merging).
    - **Creating**: Provide auth_config with credentials — queries provider directly
    """
    auth_config = dict(request.auth_config) if request.auth_config else {}

    # Editing mode: use stored credentials, optionally merged with overrides
    if request.model_id:
        models = config_service.get_models_from_provider_by_id(
            db,
            request.model_id,
            service,
            provider_override=provider,
            auth_config_overrides=auth_config if auth_config else None,
            api_base_override=request.api_base,
        )
        return create_data_response(models)

    # Creating mode: use credentials from request
    auth_type = auth_config.get("type")
    if not auth_type:
        raise ValidationErrorBuilder().message(
            "Either model_id (for editing) or auth_config with 'type' (for creating) is required"
        ).entity_type("ProviderQueryBaseRequest").entity_identifier(provider).build()

    models = service.get_models_with_new_credentials(
        provider=provider,
        api_base=request.api_base,
        auth_type=auth_type,
        auth_config=auth_config,
        model_params=request.model_params,
    )

    return create_data_response(models)


@router.post(
    "/providers/{provider}/params",
    response_model=DataResponse[SupportedParamsResponse],
    summary="Get supported parameters for a model",
    description="Returns the list of advanced parameters supported by a specific model, based on litellm's parameter registry. No credentials needed.",
)
async def get_supported_params(
    provider: str,
    request: SupportedParamsRequest,
    _: None = Depends(require_model_config_ui_enabled),
    service: ModelListService = Depends(get_model_list_service),
) -> DataResponse[SupportedParamsResponse]:
    """
    Get supported parameters for a model.

    Uses litellm's internal registry to determine which OpenAI-compatible
    parameters a model supports. This is a local lookup — no credentials
    or provider API calls needed.
    """
    params = service.get_supported_params(provider, request.model_name)
    response = SupportedParamsResponse(supported_params=params)
    return create_data_response(response)
