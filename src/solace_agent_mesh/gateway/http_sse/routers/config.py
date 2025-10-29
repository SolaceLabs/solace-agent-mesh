"""
API Router for providing frontend configuration.
"""

import logging
import os
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

        # Determine if prompt library should be enabled
        prompt_library_config = component.get_config("prompt_library", {})
        prompt_library_enabled = prompt_library_config.get("enabled", True)
        
        if prompt_library_enabled:
            # Check if SQL persistence is available (REQUIRED for prompts)
            session_config = component.get_config("session_service", {})
            session_type = session_config.get("type", "memory")
            
            if session_type != "sql":
                log.warning(
                    "%s Prompt library is configured but session_service type is '%s' (not 'sql'). "
                    "Disabling prompt library for frontend.",
                    log_prefix,
                    session_type
                )
                prompt_library_enabled = False
            else:
                feature_enablement["promptLibrary"] = True
                log.debug("%s promptLibrary feature flag is enabled.", log_prefix)
                
                # Check AI-assisted sub-feature (only if parent is enabled)
                ai_assisted_config = prompt_library_config.get("ai_assisted", {})
                ai_assisted_enabled = ai_assisted_config.get("enabled", True)
                
                if ai_assisted_enabled:
                    # Verify LLM is configured
                    llm_model = os.getenv("LLM_SERVICE_GENERAL_MODEL_NAME")
                    if llm_model:
                        feature_enablement["promptAIAssisted"] = True
                        log.debug("%s promptAIAssisted feature flag is enabled.", log_prefix)
                    else:
                        feature_enablement["promptAIAssisted"] = False
                        log.warning(
                            "%s AI-assisted prompts disabled: LLM_SERVICE_GENERAL_MODEL_NAME not configured",
                            log_prefix
                        )
                else:
                    feature_enablement["promptAIAssisted"] = False
                
                # Check version history sub-feature (only if parent is enabled)
                version_history_config = prompt_library_config.get("version_history", {})
                version_history_enabled = version_history_config.get("enabled", True)
                
                if version_history_enabled:
                    feature_enablement["promptVersionHistory"] = True
                    log.debug("%s promptVersionHistory feature flag is enabled.", log_prefix)
                else:
                    feature_enablement["promptVersionHistory"] = False
                
                # Future: prompt sharing (only if parent is enabled)
                sharing_config = prompt_library_config.get("sharing", {})
                sharing_enabled = sharing_config.get("enabled", False)
                
                if sharing_enabled:
                    feature_enablement["promptSharing"] = True
                    log.debug("%s promptSharing feature flag is enabled.", log_prefix)
                else:
                    feature_enablement["promptSharing"] = False
        else:
            # Explicitly set to false when disabled
            feature_enablement["promptLibrary"] = False
            feature_enablement["promptAIAssisted"] = False
            feature_enablement["promptVersionHistory"] = False
            feature_enablement["promptSharing"] = False
            log.info("%s Prompt library feature is explicitly disabled.", log_prefix)

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
