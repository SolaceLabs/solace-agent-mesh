"""
Custom Solace AI Connector App class for the GDK-based Test Gateway.
Defines configuration schema (if any specific needed) and programmatically
creates the TestGatewayComponent.
"""

from typing import Any, Dict, List, Type

from pydantic import ValidationError
from solace_ai_connector.common.log import log

from solace_agent_mesh.gateway.base.app import BaseGatewayApp, BaseGatewayAppConfig
from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

from .component import TestGatewayComponent

info = {
    "class_name": "TestGatewayApp",
    "description": "App class for the GDK-based Test Gateway used in integration testing.",
}


class TestGatewayAppConfig(BaseGatewayAppConfig):
    """Pydantic model for the Test Gateway application configuration."""

    pass


class TestGatewayApp(BaseGatewayApp):
    """
    Custom App class for the GDK-based Test Gateway.
    - Extends BaseGatewayApp for common gateway functionalities.
    - Specifies TestGatewayComponent as its operational component.
    """

    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = []

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        """
        Initializes the TestGatewayApp.
        Most setup is handled by BaseGatewayApp.
        """
        log.debug(
            "%s Initializing TestGatewayApp...",
            app_info.get("name", "TestGatewayApp"),
        )

        app_config_dict = app_info.get("app_config", {})
        try:
            # Validate the raw dict, cleaning None values to allow defaults to apply
            app_config = TestGatewayAppConfig.model_validate_and_clean(
                app_config_dict
            )
            app_info["app_config"] = app_config
        except ValidationError as e:
            log.error("Test Gateway configuration validation failed:\n%s", e)
            raise ValueError(f"Invalid Test Gateway configuration: {e}") from e

        app_info.setdefault("broker", {})
        app_info["broker"]["dev_mode"] = True

        super().__init__(app_info=app_info, **kwargs)
        log.debug("%s TestGatewayApp initialization complete.", self.name)

    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the specific gateway component class for this app.
        """
        return TestGatewayComponent
