"""
Resolver for per-request model override aliases.

Resolves model config aliases (strings) to raw LiteLLM config dicts by
sending bootstrap requests to the platform service via the broker. Reuses
the same bootstrap protocol as DynamicModelProvider — zero platform changes.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.message import Message as SolaceMessage

from .models.dynamic_model_provider_topics import (
    get_bootstrap_request_topic,
    get_bootstrap_response_topic,
)

if TYPE_CHECKING:
    from solace_agent_mesh.common.sac.sam_component_base import SamComponentBase

log = logging.getLogger(__name__)

_RESOLVE_TIMEOUT_SECONDS = 10.0

_receiver_info = {
    "class_name": "ModelOverrideResolverReceiver",
    "description": (
        "Receives bootstrap responses for per-request model override alias resolution."
    ),
    "config_parameters": [
        {
            "name": "resolver_ref",
            "required": True,
            "type": "object",
            "description": "Reference to the ModelOverrideResolver instance.",
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "payload": {"type": "any"},
            "topic": {"type": "string"},
            "user_properties": {"type": "object"},
        },
        "required": ["payload", "topic"],
    },
    "output_schema": None,
}


class ModelOverrideResolverReceiver(ComponentBase):
    """SAC component that receives bootstrap responses and completes pending Futures."""

    info = _receiver_info

    def __init__(self, **kwargs: Any):
        super().__init__(_receiver_info, **kwargs)
        self.resolver: ModelOverrideResolver = self.get_config("resolver_ref")

    def invoke(self, message: SolaceMessage, data: Dict[str, Any]) -> None:
        try:
            topic = data.get("topic", "")
            payload = data.get("payload", {})

            # Extract alias from topic: ...configuration/model/response/{model_id}/{component_id}
            parts = topic.split("/")
            alias = parts[-2] if len(parts) >= 2 else None

            model_config = payload.get("model_config")

            log.info(
                "[ModelOverrideResolver] Received response for alias=%s, config_found=%s",
                alias,
                model_config is not None,
            )

            if alias:
                self.resolver.complete_pending(alias, model_config)

            message.call_acknowledgements()
        except Exception as e:
            log.exception("[ModelOverrideResolver] Error processing response: %s", e)
            if message:
                message.call_negative_acknowledgements()
            raise
        return None


class ModelOverrideResolver:
    """Resolves model config aliases to raw LiteLLM config dicts via the platform service."""

    def __init__(self, component: "SamComponentBase"):
        self._component = component
        self._pending: Dict[str, asyncio.Future] = {}
        self._internal_app = None
        self._setup_complete = False

    async def setup(self) -> None:
        """Create the internal SAC flow for receiving bootstrap responses."""
        try:
            self._create_listener_flow()
            self._setup_complete = True
            log.info(
                "%s ModelOverrideResolver setup complete",
                self._component.log_identifier,
            )
        except Exception as e:
            log.warning(
                "%s ModelOverrideResolver setup failed: %s",
                self._component.log_identifier,
                e,
            )

    async def resolve(self, alias: str, timeout: float = _RESOLVE_TIMEOUT_SECONDS) -> Optional[Dict[str, Any]]:
        """Resolve a model config alias to a raw LiteLLM config dict.

        Returns the config dict, or None if resolution fails or times out.
        """
        if not self._setup_complete:
            log.warning(
                "%s ModelOverrideResolver not ready, cannot resolve alias '%s'",
                self._component.log_identifier,
                alias,
            )
            return None

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[alias] = future

        component_id = self._component.get_component_id()
        resolver_id = f"override_resolver_{component_id}"
        response_topic = get_bootstrap_response_topic(
            self._component.namespace, alias, resolver_id
        )

        self._component.publish_a2a_message(
            payload={
                "model_id": alias,
                "reply_to": response_topic,
                "component_id": resolver_id,
                "component_type": "override_resolver",
            },
            topic=get_bootstrap_request_topic(self._component.namespace, alias),
        )

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            log.warning(
                "%s Model override alias resolution timed out for '%s' after %.1fs",
                self._component.log_identifier,
                alias,
                timeout,
            )
            return None
        finally:
            self._pending.pop(alias, None)

    def complete_pending(self, alias: str, model_config: Optional[Dict[str, Any]]) -> None:
        """Called by the receiver when a bootstrap response arrives."""
        future = self._pending.get(alias)
        if future and not future.done():
            future.set_result(model_config)

    def _create_listener_flow(self) -> None:
        """Create internal SAC flow subscribing to bootstrap response topics."""
        log_prefix = "[ModelOverrideResolver]"

        main_app = self._component.get_app()
        if not main_app or not main_app.connector:
            raise RuntimeError(f"{log_prefix} Main app or connector not available")

        main_broker_config = main_app.app_info.get("broker", {})
        if not main_broker_config:
            raise ValueError(f"{log_prefix} Broker configuration not found")

        component_id = self._component.get_component_id()
        resolver_id = f"override_resolver_{component_id}"

        # Wildcard subscription: any model_id, scoped to this resolver's component_id
        response_topic_wildcard = get_bootstrap_response_topic(
            self._component.namespace, "*", resolver_id
        )

        broker_input_cfg = {
            "component_module": "broker_input",
            "component_name": f"{component_id}_override_resolver_broker_input",
            "broker_queue_name": f"{self._component.namespace}q/override_resolver/{component_id}",
            "create_queue_on_start": True,
            "component_config": {
                **main_broker_config,
                "broker_subscriptions": [
                    {"topic": response_topic_wildcard},
                ],
            },
        }

        receiver_cfg = {
            "component_class": ModelOverrideResolverReceiver,
            "component_name": f"{component_id}_override_resolver_receiver",
            "component_config": {
                "resolver_ref": self,
            },
        }

        flow_config = {
            "name": f"{component_id}_override_resolver_flow",
            "components": [broker_input_cfg, receiver_cfg],
        }

        self._internal_app = main_app.connector.create_internal_app(
            app_name=f"{component_id}_override_resolver_app",
            flows=[flow_config],
        )

        if not self._internal_app or not self._internal_app.flows:
            self._internal_app = None
            raise RuntimeError(f"{log_prefix} Failed to create internal app/flow")

        self._internal_app.run()
        log.info("%s Internal listener flow started", log_prefix)

    def cleanup(self) -> None:
        """Stop the internal flow and cancel pending futures."""
        for alias, future in self._pending.items():
            if not future.done():
                future.cancel()
        self._pending.clear()

        if self._internal_app:
            try:
                self._internal_app.cleanup()
            except Exception as e:
                log.error("[ModelOverrideResolver] Error during cleanup: %s", e)
        self._internal_app = None
        self._setup_complete = False
