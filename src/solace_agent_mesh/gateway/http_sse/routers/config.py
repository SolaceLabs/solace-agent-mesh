"""
API Router for providing frontend configuration.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from solace_ai_connector.common.log import log

from ....gateway.http_sse.dependencies import get_sac_component, get_api_config
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gateway.http_sse.component import WebUIBackendComponent

router = APIRouter()


@router.get("/config", response_model=Dict[str, Any])
async def get_app_config(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    api_config: Dict[str, Any] = Depends(get_api_config),
):
    """
    Provides configuration settings needed by the frontend application.
    """
    log_prefix = "[GET /api/v1/config] "
    log.info("%sRequest received.", log_prefix)
    try:
        config_data = {
            "frontend_server_url": "",
            "frontend_auth_login_url": component.get_config(
                "frontend_auth_login_url", ""
            ),
            "frontend_use_authorization": component.get_config(
                "frontend_use_authorization", False
            ),
            "frontend_welcome_message": component.get_config(
                "frontend_welcome_message", ""
            ),
            "frontend_redirect_url": component.get_config("frontend_redirect_url", ""),
            "frontend_collect_feedback": component.get_config(
                "frontend_collect_feedback", False
            ),
            "frontend_bot_name": component.get_config("frontend_bot_name", "A2A Agent"),
            "frontend_feature_enablement": component.get_config("frontend_feature_enablement", {}),
            "persistence_enabled": api_config.get("persistence_enabled", False),
        }
        log.info("%sReturning frontend configuration.", log_prefix)
        return config_data
    except Exception as e:
        log.exception(
            "%sError retrieving configuration for frontend: %s", log_prefix, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving configuration.",
        )
