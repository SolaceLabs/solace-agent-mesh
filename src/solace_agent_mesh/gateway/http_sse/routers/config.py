"""
API Router for providing frontend configuration.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from ....gateway.http_sse.dependencies import get_sac_component, get_api_config
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gateway.http_sse.component import WebUIBackendComponent

log = logging.getLogger(__name__)

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
        # Start with explicitly defined feature flags
        feature_enablement = component.get_config("frontend_feature_enablement", {})

        # Manually check for the task_logging feature and add it
        task_logging_config = component.get_config("task_logging", {})
        if task_logging_config and task_logging_config.get("enabled", False):
            feature_enablement["taskLogging"] = True
            log.debug("%s taskLogging feature flag is enabled.", log_prefix)

        # Determine if feedback should be enabled
        # Feedback requires SQL session storage for persistence
        feedback_enabled = component.get_config("frontend_collect_feedback", False)
        if feedback_enabled:
            session_config = component.get_config("session_service", {})
            session_type = session_config.get("type", "memory")
            if session_type != "sql":
                log.warning(
                    "%s Feedback is configured but session_service type is '%s' (not 'sql'). "
                    "Disabling feedback for frontend.",
                    log_prefix,
                    session_type
                )
                feedback_enabled = False

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
            "frontend_collect_feedback": feedback_enabled,
            "frontend_bot_name": component.get_config("frontend_bot_name", "A2A Agent"),
            "frontend_feature_enablement": feature_enablement,
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
