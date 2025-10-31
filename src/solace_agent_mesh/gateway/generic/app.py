"""
Custom Solace AI Connector App class for the Generic Gateway.
This app dynamically loads a specified gateway adapter.
"""

import logging
from typing import Any, Dict, List, Type

from ..base.app import BaseGatewayApp
from ..base.component import BaseGatewayComponent

log = logging.getLogger(__name__)

info = {
    "class_name": "GenericGatewayApp",
    "description": "A generic gateway app that hosts a gateway adapter plugin.",
}


class GenericGatewayApp(BaseGatewayApp):
    """
    Custom App class for the Generic Gateway.
    - Extends BaseGatewayApp for common gateway functionalities.
    - Dynamically loads a gateway adapter specified in configuration.
    """

    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = [
        {
            "name": "gateway_adapter",
            "required": True,
            "type": "string",
            "description": "The Python module path to the GatewayAdapter implementation class (e.g., 'my_gateway.adapter.MyAdapter').",
        },
        {
            "name": "adapter_config",
            "required": False,
            "type": "object",
            "default": {},
            "description": "A dictionary of configuration settings specific to the gateway adapter.",
        },
    ]

    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the specific gateway component class for this app.
        """
        # This component will be created in the next step.
        from .component import GenericGatewayComponent

        return GenericGatewayComponent
