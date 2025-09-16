"""
Custom Solace AI Connector App class for the Web UI Backend.
Defines configuration schema and programmatically creates the WebUIBackendComponent.
"""

from typing import Any, Dict, List, Optional
import os
from alembic import command
from alembic.config import Config
from pydantic import Field, ValidationError
from solace_ai_connector.common.log import log

from ...gateway.http_sse.component import WebUIBackendComponent

from ...gateway.base.app import BaseGatewayApp, BaseGatewayAppConfig
from ...gateway.base.component import BaseGatewayComponent


info = {
    "class_name": "WebUIBackendApp",
    "description": "Custom App class for the A2A Web UI Backend with automatic subscription generation.",
}


class WebUIBackendAppConfig(BaseGatewayAppConfig):
    """Pydantic model for the Web UI Backend application configuration."""

    session_secret_key: str = Field(
        ..., description="Secret key for signing web user sessions."
    )
    fastapi_host: str = Field(
        default="127.0.0.1", description="Host address for the embedded FastAPI server."
    )
    fastapi_port: int = Field(
        default=8000, description="Port for the embedded FastAPI server."
    )
    fastapi_https_port: int = Field(
        default=8443, description="Port for the embedded FastAPI server when SSL is enabled."
    )
    cors_allowed_origins: List[str] = Field(
        default=["*"], description="List of allowed origins for CORS requests."
    )
    sse_max_queue_size: int = Field(
        default=200,
        description="Maximum size of the SSE connection queues. Adjust based on expected load.",
    )
    sse_buffer_max_age_seconds: int = Field(
        default=600,  # 10 minutes
        description="Maximum age in seconds for a pending event buffer before it is cleaned up.",
    )
    sse_buffer_cleanup_interval_seconds: int = Field(
        default=300,  # 5 minutes
        description="How often to run the cleanup task for stale pending event buffers.",
    )
    resolve_artifact_uris_in_gateway: bool = Field(
        default=True,
        description="If true, the gateway will resolve artifact:// URIs found in A2A messages and embed the content as bytes before sending to the UI. If false, URIs are passed through.",
    )
    system_purpose: str = Field(
        default="",
        description="Detailed description of the system's overall purpose, to be optionally used by agents.",
    )
    response_format: str = Field(
        default="",
        description="General guidelines on how agent responses should be structured, to be optionally used by agents.",
    )
    frontend_welcome_message: str = Field(
        default="Hi! How can I help?",
        description="Initial welcome message displayed in the chat.",
    )
    frontend_bot_name: str = Field(
        default="A2A Agent", description="Name displayed for the bot/agent in the UI."
    )
    frontend_collect_feedback: bool = Field(
        default=False, description="Enable/disable the feedback buttons in the UI."
    )
    frontend_auth_login_url: str = Field(
        default="", description="URL for the external login page (if auth is enabled)."
    )
    frontend_use_authorization: bool = Field(
        default=False, description="Tell frontend whether backend expects authorization."
    )
    frontend_redirect_url: str = Field(
        default="", description="Redirect URL for OAuth flows (if auth is enabled)."
    )
    external_auth_callback_uri: str = Field(
        default="", description="Redirect URI for the OIDC application."
    )
    external_auth_service_url: str = Field(
        default="http://localhost:8080",
        description="External authorization service URL for login initiation.",
    )
    external_auth_provider: str = Field(
        default="", description="The external authentication provider."
    )
    ssl_keyfile: str = Field(
        default="", description="The file path to the SSL private key."
    )
    ssl_certfile: str = Field(
        default="", description="The file path to the SSL certificate."
    )
    ssl_keyfile_password: str = Field(
        default="", description="The passphrase for the SSL private key."
    )


class WebUIBackendApp(BaseGatewayApp):
    """
    Custom App class for the A2A Web UI Backend.
    - Extends BaseGatewayApp for common gateway functionalities.
    - Defines WebUI-specific configuration parameters.
    """

    # This is now a placeholder. Validation is handled by the Pydantic model.
    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = []

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        """
        Initializes the WebUIBackendApp.
        Most setup is handled by BaseGatewayApp.
        """
        log.debug(
            "%s Initializing WebUIBackendApp...",
            app_info.get("name", "WebUIBackendApp"),
        )

        app_config_dict = app_info.get("app_config", {})
        try:
            # Validate the raw dict, cleaning None values to allow defaults to apply
            app_config = WebUIBackendAppConfig.model_validate_and_clean(
                app_config_dict
            )
            app_info["app_config"] = app_config
        except ValidationError as e:
            log.error("Web UI Gateway configuration validation failed:\n%s", e)
            raise ValueError(f"Invalid Web UI Gateway configuration: {e}") from e

        super().__init__(app_info, **kwargs)

        try:
            
            alembic_ini_path = os.path.join(os.path.dirname(__file__), "alembic.ini")
            if os.path.exists(alembic_ini_path):
                log.debug("Loading Alembic configuration from alembic.ini.")
                alembic_cfg = Config(alembic_ini_path)
            else:
                log.warning(
                    "alembic.ini not found. Falling back to programmatic configuration."
                )
                alembic_cfg = Config()
                alembic_cfg.set_main_option(
                    "script_location",
                    os.path.join(os.path.dirname(__file__), "alembic"),
                )
            
            session_service_config = self.get_config("session_service", {})
            db_url = session_service_config.get("database_url")
            if db_url:
                alembic_cfg.set_main_option("sqlalchemy.url", db_url)
                command.upgrade(alembic_cfg, "head")
            else:
                log.warning("Database URL not configured. Skipping migrations.")
        except Exception as e:
            log.warning(f"Alembic migration failed: {e}")

        log.debug("%s WebUIBackendApp initialization complete.", self.name)

    def _get_gateway_component_class(self) -> type[BaseGatewayComponent]:
        return WebUIBackendComponent
