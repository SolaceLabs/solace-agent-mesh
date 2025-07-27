"""
Abstract base class for proxy apps.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Type

from solace_ai_connector.common.log import log
from solace_ai_connector.flow.app import App

from ....common.a2a_protocol import get_agent_request_topic
from .component import BaseProxyComponent


info = {
    "class_name": "BaseProxyApp",
    "description": "Abstract base class for proxy apps. Handles common configuration and subscription generation.",
}


class BaseProxyApp(App, ABC):
    """
    Abstract base class for proxy apps.

    Handles common configuration schema, generates Solace topic subscriptions for all
    proxied agents, and programmatically defines the single proxy component instance.
    """

    app_schema = {
        "config_parameters": [
            {
                "name": "namespace",
                "required": True,
                "type": "string",
                "description": "Absolute topic prefix for A2A communication (e.g., 'myorg/dev').",
            },
            {
                "name": "proxied_agents",
                "required": True,
                "type": "list",
                "description": "A list of downstream agents to be proxied.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "required": True,
                            "description": "The name the agent will have on the Solace mesh.",
                        }
                    },
                },
            },
            {
                "name": "artifact_service",
                "required": False,
                "type": "object",
                "default": {"type": "memory"},
                "description": "Configuration for the shared Artifact Service.",
            },
            {
                "name": "discovery_interval_seconds",
                "required": False,
                "type": "integer",
                "default": 60,
                "description": "Interval (seconds) to re-fetch agent cards. <= 0 disables periodic discovery.",
            },
        ]
    }

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        log.debug("Initializing BaseProxyApp...")

        app_config = app_info.get("app_config", {})
        namespace = app_config.get("namespace")
        proxied_agents = app_config.get("proxied_agents", [])

        if not namespace or not isinstance(namespace, str):
            raise ValueError("Config Error: 'namespace' is required and must be a string.")
        if not proxied_agents or not isinstance(proxied_agents, list):
            raise ValueError(
                "Config Error: 'proxied_agents' is required and must be a non-empty list."
            )

        # Generate subscriptions for each proxied agent
        required_topics = [
            get_agent_request_topic(namespace, agent["name"])
            for agent in proxied_agents
            if "name" in agent
        ]
        generated_subs = [{"topic": topic} for topic in required_topics]
        log.info(
            "Automatically generated subscriptions for proxy: %s",
            generated_subs,
        )

        # Programmatically define the component
        component_class = self._get_component_class()
        component_definition = {
            "name": f"{app_info.get('name', 'proxy')}_component",
            "component_class": component_class,
            "component_config": {},  # Component will get config from app_config
            "subscriptions": generated_subs,
        }
        app_info["components"] = [component_definition]
        log.debug("Replaced 'components' in app_info with programmatic definition.")

        # Ensure broker is configured for input/output
        broker_config = app_info.setdefault("broker", {})
        broker_config["input_enabled"] = True
        broker_config["output_enabled"] = True
        log.debug("Injected broker.input_enabled=True and broker.output_enabled=True")

        # Generate a unique queue name
        app_name = app_info.get("name", "proxy-app")
        generated_queue_name = f"{namespace.strip('/')}/q/proxy/{app_name}"
        broker_config["queue_name"] = generated_queue_name
        log.debug("Injected generated broker.queue_name: %s", generated_queue_name)

        broker_config["temporary_queue"] = True
        log.debug("Set broker_config.temporary_queue = True")

        super().__init__(app_info, **kwargs)
        log.debug("BaseProxyApp initialization complete.")

    @abstractmethod
    def _get_component_class(self) -> Type[BaseProxyComponent]:
        """
        Abstract method to be implemented by concrete proxy apps.
        Must return the specific proxy component class to be instantiated.
        """
        raise NotImplementedError
