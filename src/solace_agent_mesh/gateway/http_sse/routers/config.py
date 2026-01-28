"""
API Router for providing frontend configuration.
"""
from __future__ import annotations

import logging
from typing import Dict, Any
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status

from ..routers.dto.requests.project_requests import CreateProjectRequest
from ....gateway.http_sse.dependencies import get_sac_component, get_api_config

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent

log = logging.getLogger(__name__)

router = APIRouter()


# Default max upload size (50MB) - matches gateway_max_upload_size_bytes default
DEFAULT_MAX_UPLOAD_SIZE_BYTES = 52428800
# Default max ZIP upload size (100MB) - for project import ZIP files
DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES = 104857600


def _get_validation_limits(component: "WebUIBackendComponent" = None) -> Dict[str, Any]:
    """
    Extract validation limits from Pydantic models to expose to frontend.
    This ensures frontend and backend validation limits stay in sync.
    """
    # Extract limits from CreateProjectRequest model
    create_fields = CreateProjectRequest.model_fields
    
    # Get max upload size from component config, with fallback to default
    max_upload_size_bytes = (
        component.get_config("gateway_max_upload_size_bytes", DEFAULT_MAX_UPLOAD_SIZE_BYTES)
        if component else DEFAULT_MAX_UPLOAD_SIZE_BYTES
    )
    
    # Get max ZIP upload size from component config, with fallback to default (100MB)
    max_zip_upload_size_bytes = (
        component.get_config("gateway_max_zip_upload_size_bytes", DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES)
        if component else DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES
    )
    
    return {
        "projectNameMax": create_fields["name"].metadata[1].max_length if create_fields["name"].metadata else 255,
        "projectDescriptionMax": create_fields["description"].metadata[0].max_length if create_fields["description"].metadata else 1000,
        "projectInstructionsMax": create_fields["system_prompt"].metadata[0].max_length if create_fields["system_prompt"].metadata else 4000,
        "maxUploadSizeBytes": max_upload_size_bytes,
        "maxZipUploadSizeBytes": max_zip_upload_size_bytes,
    }


def _get_background_tasks_config(
    component: "WebUIBackendComponent",
    log_prefix: str
) -> Dict[str, Any]:
    """
    Extracts background tasks configuration for the frontend.
    
    Returns:
        Dict with background tasks non-boolean settings:
        - default_timeout_ms: Default timeout for background tasks
        
    Note: The 'enabled' flag is now in frontend_feature_enablement.background_tasks
    """
    background_config = component.get_config("background_tasks", {})
    default_timeout_ms = background_config.get("default_timeout_ms", 3600000)  # 1 hour default
    
    return {
        "default_timeout_ms": default_timeout_ms,
    }


def _determine_background_tasks_enabled(
    component: "WebUIBackendComponent",
    log_prefix: str
) -> bool:
    """
    Determines if background tasks feature should be enabled.
    
    Returns:
        bool: True if background tasks should be enabled
    """
    feature_flags = component.get_config("frontend_feature_enablement", {})
    enabled = feature_flags.get("background_tasks", False)
    
    if enabled:
        log.debug("%s Background tasks enabled globally for all agents", log_prefix)
    else:
        log.debug("%s Background tasks disabled", log_prefix)
    
    return enabled


def _determine_auto_title_generation_enabled(
    component: "WebUIBackendComponent",
    api_config: Dict[str, Any],
    log_prefix: str
) -> bool:
    """
    Determines if automatic title generation feature should be enabled.
    
    Logic:
    1. Check if persistence is enabled (required for title generation)
    2. Check explicit auto_title_generation config (must be explicitly enabled)
    3. Check frontend_feature_enablement.auto_title_generation override
    
    Returns:
        bool: True if auto title generation should be enabled
    """
    # Auto title generation requires persistence
    persistence_enabled = api_config.get("persistence_enabled", False)
    if not persistence_enabled:
        log.debug("%s Auto title generation disabled: persistence is not enabled", log_prefix)
        return False
    
    # Check explicit auto_title_generation config - disabled by default
    auto_title_config = component.get_config("auto_title_generation", {})
    explicitly_enabled = False
    if isinstance(auto_title_config, dict):
        explicitly_enabled = auto_title_config.get("enabled", False)
    
    # Check frontend_feature_enablement override
    feature_flags = component.get_config("frontend_feature_enablement", {})
    if "auto_title_generation" in feature_flags:
        explicitly_enabled = feature_flags.get("auto_title_generation", False)
    
    if not explicitly_enabled:
        log.debug("%s Auto title generation disabled: not explicitly enabled in config", log_prefix)
        return False
    
    log.debug("%s Auto title generation enabled: explicitly enabled in config", log_prefix)
    return True


def _determine_mentions_enabled(
    component: "WebUIBackendComponent",
    log_prefix: str
) -> bool:
    """
    Determines if mentions (@user) feature should be enabled.
    
    Logic:
    1. Check if identity_service is configured (required for user search)
    2. Check explicit mentions.enabled config (must be explicitly enabled, defaults to False)
    3. Check frontend_feature_enablement.mentions override
    
    Returns:
        bool: True if mentions should be enabled
    """
    # Mentions require identity_service to be configured for user search
    if component.identity_service is None:
        log.debug("%s Mentions disabled: no identity_service configured", log_prefix)
        return False
    
    # Check explicit mentions config - disabled by default
    mentions_config = component.get_config("mentions", {})
    explicitly_enabled = False
    if isinstance(mentions_config, dict):
        explicitly_enabled = mentions_config.get("enabled", False)
    
    # Check frontend_feature_enablement override
    feature_flags = component.get_config("frontend_feature_enablement", {})
    if "mentions" in feature_flags:
        explicitly_enabled = feature_flags.get("mentions", False)
    
    if not explicitly_enabled:
        log.debug("%s Mentions disabled: not explicitly enabled in config", log_prefix)
        return False
    
    log.debug("%s Mentions enabled: identity_service configured and explicitly enabled", log_prefix)
    return True


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

        identity_service_config = component.get_config("identity_service", None)
        identity_service_type = identity_service_config.get("type") if identity_service_config else None

        # Manually check for the task_logging feature and add it
        task_logging_config = component.get_config("task_logging", {})
        if task_logging_config and task_logging_config.get("enabled", False):
            feature_enablement["taskLogging"] = True
            log.debug("%s taskLogging feature flag is enabled.", log_prefix)

        # Determine if prompt library should be enabled
        # Prompts require SQL session storage for persistence
        prompt_library_config = component.get_config("prompt_library", {})
        prompt_library_explicitly_enabled = prompt_library_config.get("enabled", True)
        
        if prompt_library_explicitly_enabled:
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
                prompt_library_enabled = True
                feature_enablement["promptLibrary"] = True
                log.debug("%s promptLibrary feature flag is enabled.", log_prefix)
                
                # Check AI-assisted sub-feature (only if parent is enabled)
                ai_assisted_config = prompt_library_config.get("ai_assisted", {})
                ai_assisted_enabled = ai_assisted_config.get("enabled", True)
                
                if ai_assisted_enabled:
                    # Verify LLM is configured through the model config
                    model_config = component.get_config("model", {})
                    
                    llm_model = None
                    if isinstance(model_config, dict):
                        llm_model = model_config.get("model")
                    
                    if llm_model:
                        feature_enablement["promptAIAssisted"] = True
                        log.debug("%s promptAIAssisted feature flag is enabled.", log_prefix)
                    else:
                        feature_enablement["promptAIAssisted"] = False
                        log.warning(
                            "%s AI-assisted prompts disabled: model not configured",
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
                
                # Check prompt sharing sub-feature (only if parent is enabled)
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
        
        # Determine if projects should be enabled
        # Projects require SQL session storage for persistence
        projects_enabled = _determine_projects_enabled(component, api_config, log_prefix)
        feature_enablement["projects"] = projects_enabled
        if projects_enabled:
            log.debug("%s Projects feature flag is enabled.", log_prefix)
        else:
            log.debug("%s Projects feature flag is disabled.", log_prefix)
        
        
        # Determine if background tasks should be enabled
        background_tasks_enabled = _determine_background_tasks_enabled(component, log_prefix)
        feature_enablement["background_tasks"] = background_tasks_enabled
        if background_tasks_enabled:
            log.debug("%s Background tasks feature flag is enabled.", log_prefix)
        else:
            log.debug("%s Background tasks feature flag is disabled.", log_prefix)

        # Determine if mentions (@user) should be enabled
        # Mentions require identity_service AND explicit enablement (defaults to False)
        mentions_enabled = _determine_mentions_enabled(component, log_prefix)
        feature_enablement["mentions"] = mentions_enabled
        
        # Determine if auto title generation should be enabled
        auto_title_generation_enabled = _determine_auto_title_generation_enabled(component, api_config, log_prefix)
        feature_enablement["auto_title_generation"] = auto_title_generation_enabled
        if auto_title_generation_enabled:
            log.debug("%s Auto title generation feature flag is enabled.", log_prefix)
        else:
            log.debug("%s Auto title generation feature flag is disabled.", log_prefix)
        
        # Check tool configuration status
        tool_config_status = {}
        
        # Check TTS configuration from component config (not environment variables)
        speech_config = component.get_config("speech", {})
        tts_config = speech_config.get("tts", {})
        
        # Check if speech/TTS section is defined in config
        # If not defined, disable TTS even if keys might be present elsewhere
        if not speech_config or not tts_config:
            log.debug("%s TTS disabled: speech.tts section not configured", log_prefix)
            tts_configured = False
            tts_provider = "gemini"  # Default fallback
        else:
            # Get provider from config (with fallback to default)
            preferred_provider = tts_config.get("provider", "gemini").lower()
            
            # Check which providers are configured
            gemini_config = tts_config.get("gemini", {})
            azure_config = tts_config.get("azure", {})
            polly_config = tts_config.get("polly", {})
            
            gemini_key = gemini_config.get("api_key")
            azure_speech_key = azure_config.get("api_key")
            azure_speech_region = azure_config.get("region")
            aws_access_key = polly_config.get("aws_access_key_id")
            aws_secret_key = polly_config.get("aws_secret_access_key")
            
            # Determine which providers are available
            gemini_available = bool(gemini_key)
            azure_available = bool(azure_speech_key and azure_speech_region)
            polly_available = bool(aws_access_key and aws_secret_key)
            tts_configured = gemini_available or azure_available or polly_available
            tool_config_status["text_to_speech"] = tts_configured
            
            # Determine TTS provider based on preference and availability
            if preferred_provider == "azure" and azure_available:
                tts_provider = "azure"
            elif preferred_provider == "gemini" and gemini_available:
                tts_provider = "gemini"
            elif preferred_provider == "polly" and polly_available:
                tts_provider = "polly"
            elif gemini_available:
                # Default to Gemini if available
                tts_provider = "gemini"
            elif azure_available:
                # Fall back to Azure if Gemini not available
                tts_provider = "azure"
            elif polly_available:
                # Fall back to Polly if others not available
                tts_provider = "polly"
            else:
                # No provider available, default to gemini (will use browser fallback)
                tts_provider = "gemini"
            
            if tts_configured:
                log.debug("%s TTS is configured (API keys present, provider: %s)", log_prefix, tts_provider)
                if preferred_provider and preferred_provider != tts_provider:
                    log.warning(
                        "%s TTS_PROVIDER set to '%s' but using '%s' (preferred provider not available)",
                        log_prefix, preferred_provider, tts_provider
                    )
            else:
                log.debug("%s TTS not configured (no API keys found)", log_prefix)
        
        # TTS settings - enable if API keys are present
        tts_settings = {
            "textToSpeech": tts_configured,
            "engineTTS": "external" if tts_configured else "browser",
            "ttsProvider": tts_provider,
        }

        platform_config = component.get_config("platform_service", {})
        platform_service_url = platform_config.get("url", "")

        config_data = {
            "frontend_server_url": component.frontend_server_url,
            "frontend_platform_server_url": platform_service_url,
            "frontend_auth_login_url": component.get_config(
                "frontend_auth_login_url", ""
            ),
            "frontend_use_authorization": component.get_config("frontend_use_authorization", False),
            "frontend_welcome_message": component.get_config(
                "frontend_welcome_message", ""
            ),
            "frontend_redirect_url": component.get_config("frontend_redirect_url", ""),
            "frontend_collect_feedback": feedback_enabled,
            "frontend_bot_name": component.get_config("frontend_bot_name", "A2A Agent"),
            "frontend_logo_url": component.get_config("frontend_logo_url", ""),
            "frontend_feature_enablement": feature_enablement,
            "persistence_enabled": api_config.get("persistence_enabled", False),
            "validation_limits": _get_validation_limits(component),
            "tool_config_status": tool_config_status,
            "tts_settings": tts_settings,
            "background_tasks_config": _get_background_tasks_config(component, log_prefix),
            "identity_service_type": identity_service_type
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
