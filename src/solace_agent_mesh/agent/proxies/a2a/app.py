"""
Concrete App class for the A2A-over-HTTPS proxy.
"""

from __future__ import annotations

from typing import Any, Dict, Type

from pydantic import ValidationError
from solace_ai_connector.common.log import log

from ..base.app import BaseProxyApp
from ..base.component import BaseProxyComponent
from .component import A2AProxyComponent
from .config import A2AProxyAppConfig

info = {
    "class_name": "A2AProxyApp",
}


class A2AProxyApp(BaseProxyApp):
    """
    Concrete App class for the A2A-over-HTTPS proxy.

    Extends the BaseProxyApp to add specific configuration validation for
    A2A agents (e.g., URL, authentication).
    """

    # Keep app_schema for documentation purposes, but it's now redundant
    # The Pydantic models handle all validation
    app_schema = {}

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        app_info["class_name"] = "A2AProxyApp"
        
        # Validate A2A-specific configuration before calling super().__init__
        app_config_dict = app_info.get("app_config", {})
        try:
            # Validate with A2A-specific config model
            app_config = A2AProxyAppConfig.model_validate_and_clean(app_config_dict)
            # Overwrite the raw dict with the validated object
            app_info["app_config"] = app_config
            log.debug("A2A proxy configuration validated successfully.")
        except ValidationError as e:
            message = A2AProxyAppConfig.format_validation_error_message(e, app_info['name'])
            log.error("Invalid A2A Proxy configuration:\n%s", message)
            raise
        
        super().__init__(app_info, **kwargs)

    def _get_component_class(self) -> Type[BaseProxyComponent]:
        """
        Returns the concrete A2AProxyComponent class.
        """
        return A2AProxyComponent
