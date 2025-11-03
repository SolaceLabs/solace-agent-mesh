"""
API Router for providing frontend configuration.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from ....gateway.http_sse.dependencies import get_sac_component, get_api_config
from ..routers.dto.requests.project_requests import CreateProjectRequest, UpdateProjectRequest
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gateway.http_sse.component import WebUIBackendComponent

log = logging.getLogger(__name__)

router = APIRouter()


def _get_validation_limits() -> Dict[str, Any]:
    """
    Extract validation limits from Pydantic models to expose to frontend.
    This ensures frontend and backend validation limits stay in sync.
    """
    # Extract limits from CreateProjectRequest model
    create_fields = CreateProjectRequest.model_fields
    
    return {
        "projectNameMax": create_fields["name"].metadata[1].max_length if create_fields["name"].metadata else 255,
        "projectDescriptionMax": create_fields["description"].metadata[0].max_length if create_fields["description"].metadata else 1000,
        "projectInstructionsMax": create_fields["system_prompt"].metadata[0].max_length if create_fields["system_prompt"].metadata else 4000,
    }


def _determine_projects_enabled(
    component: "WebUIBackendComponent",
    api_config: Dict[str, Any],
    log_prefix: str
) -> bool:
    """
    Determines if projects feature should be enabled.
    
    Logic:
    1. Check if persistence is enabled (required for projects)
    2. Check explicit projects.enabled config
    3. Check frontend_feature_enablement.projects override
    
    Returns:
        bool: True if projects should be enabled
    """
    # Projects require persistence
    persistence_enabled = api_config.get("persistence_enabled", False)
    if not persistence_enabled:
        log.debug("%s Projects disabled: persistence is not enabled", log_prefix)
        return False
    
    # Check explicit projects config
    projects_config = component.get_config("projects", {})
    if isinstance(projects_config, dict):
        projects_explicitly_enabled = projects_config.get("enabled", True)
        if not projects_explicitly_enabled:
            log.debug("%s Projects disabled: explicitly disabled in config", log_prefix)
            return False
    
    # Check frontend_feature_enablement override
    feature_flags = component.get_config("frontend_feature_enablement", {})
    if "projects" in feature_flags:
        projects_flag = feature_flags.get("projects", True)
        if not projects_flag:
            log.debug("%s Projects disabled: disabled in frontend_feature_enablement", log_prefix)
            return False
    
    # All checks passed
    log.debug("%s Projects enabled: persistence enabled and no explicit disable", log_prefix)
    return True


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
        
        # Determine if projects should be enabled
        # Projects require SQL session storage for persistence
        projects_enabled = _determine_projects_enabled(component, api_config, log_prefix)
        feature_enablement["projects"] = projects_enabled
        if projects_enabled:
            log.debug("%s Projects feature flag is enabled.", log_prefix)
        else:
            log.debug("%s Projects feature flag is disabled.", log_prefix)

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
            "validation_limits": _get_validation_limits(),
        }
        log.debug("%sReturning frontend configuration.", log_prefix)
        return config_data
    except Exception as e:
        log.exception(
            "%sError retrieving configuration for frontend: %s", log_prefix, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving configuration.",
        )
