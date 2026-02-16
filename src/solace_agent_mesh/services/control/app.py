"""
Control Service App class for Solace Agent Mesh.
Defines configuration schema and creates the ControlServiceComponent.
"""

import logging
from typing import Any, Dict, List

from ...common.app_base import SamAppBase
from .component import ControlServiceComponent
from ...common.a2a import get_control_subscription_topic

log = logging.getLogger(__name__)

info = {
    "class_name": "ControlServiceApp",
    "description": "Control plane service for dynamic app management",
}


class ControlServiceApp(SamAppBase):
    """
    Control Service App.

    Provides a RESTful API over the Solace broker for managing apps at runtime:
    list, create, stop, start, update, and remove apps without restarting.
    """

    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = [
        {
            "name": "namespace",
            "required": True,
            "type": "string",
            "description": "Namespace for service configuration.",
        },
        {
            "name": "authorization",
            "required": False,
            "type": "object",
            "default": {"type": "none"},
            "description": "Authorization configuration. 'type' can be 'none' (allow all) or 'deny_all'.",
        },
        {
            "name": "max_message_size_bytes",
            "required": False,
            "type": "integer",
            "default": 10000000,
            "description": "Maximum message size in bytes for control messages (default: 10MB).",
        },
        {
            "name": "trust_manager",
            "required": False,
            "type": "object",
            "default": None,
            "description": "Trust Manager configuration (enterprise feature).",
        },
    ]

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        """
        Initialize the ControlServiceApp.
        Programmatically creates the component and configures broker before calling parent App.__init__().
        """
        log.debug(
            "%s Initializing ControlServiceApp...",
            app_info.get("name", "ControlServiceApp"),
        )

        modified_app_info = app_info.copy()
        app_config = modified_app_info.get("app_config", {})

        # Get namespace from config
        namespace = app_config.get("namespace", "")
        if not namespace:
            raise ValueError("Namespace is required in app_config for ControlServiceApp")

        # Subscribe to all control topics: {namespace}/sam/v1/control/>
        subscriptions = [
            {"topic": get_control_subscription_topic(namespace)},
        ]

        # Add trust card subscription if trust manager is enabled (enterprise feature)
        trust_config = app_config.get("trust_manager")
        if trust_config and trust_config.get("enabled", False):
            from ...common.a2a.protocol import get_trust_card_subscription_topic

            trust_card_topic = get_trust_card_subscription_topic(namespace)
            subscriptions.append({"topic": trust_card_topic})
            log.info(
                "Trust Manager enabled for Control Service, added trust card subscription: %s",
                trust_card_topic,
            )

        # Create component definition
        component_definition = {
            "name": f"{app_info.get('name', 'control_service')}_component",
            "component_class": ControlServiceComponent,
            "component_config": {"app_config": app_config},
            "subscriptions": subscriptions,
        }

        modified_app_info["components"] = [component_definition]

        # Configure broker connection
        broker_config = modified_app_info.setdefault("broker", {})
        broker_config["input_enabled"] = True
        broker_config["output_enabled"] = True

        log.info(
            "Configured broker for Control Service with namespace: %s",
            namespace,
        )

        super().__init__(modified_app_info, **kwargs)
        log.debug("%s ControlServiceApp initialization complete.", self.name)

    def get_component(self):
        """
        Retrieve the running ControlServiceComponent instance from the app's flow.

        Returns:
            ControlServiceComponent instance if found, None otherwise.
        """
        if self.flows and self.flows[0].component_groups:
            for group in self.flows[0].component_groups:
                for component_wrapper in group:
                    component = (
                        component_wrapper.component
                        if hasattr(component_wrapper, "component")
                        else component_wrapper
                    )
                    if isinstance(component, ControlServiceComponent):
                        return component
        return None
