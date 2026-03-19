"""
Dynamic Model Provider for enterprise model configuration.
"""

from typing import Any, Dict, Union
import asyncio
from solace_ai_connector.components.component_base import ComponentBase as SamComponentBase
from solace_agent_mesh.agent.adk.models.lite_llm import LiteLlm
from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.message import Message as SolaceMessage
import logging

from .dynamic_model_provider_topics import (
    get_bootstrap_request_topic,
    get_bootstrap_response_topic,
    get_model_config_update_topic,
)

log = logging.getLogger(__name__)


# SAC Component Info for ModelConfigReceiverComponent
_receiver_info = {
    "class_name": "ModelConfigReceiverComponent",
    "description": (
        "Receives model configuration messages from a BrokerInput and applies them to the "
        "DynamicModelProvider's LiteLlm instance."
    ),
    "config_parameters": [
        {
            "name": "model_provider_ref",
            "required": True,
            "type": "object",
            "description": "A direct reference to the DynamicModelProvider instance.",
        }
    ],
    "input_schema": {
        "type": "object",
        "description": "Output from a BrokerInput component.",
        "properties": {
            "payload": {"type": "any", "description": "The message payload."},
            "topic": {"type": "string", "description": "The message topic."},
            "user_properties": {
                "type": "object",
                "description": "User properties of the message.",
            },
        },
        "required": ["payload", "topic"],
    },
    "output_schema": None,
}


class ModelConfigReceiverComponent(ComponentBase):
    """
    A SAC component that receives model configuration messages and updates
    the DynamicModelProvider accordingly.
    """
    info = _receiver_info

    def __init__(self, **kwargs: Any):
        super().__init__(_receiver_info, **kwargs)
        self.model_provider = self.get_config("model_provider_ref")
        if not isinstance(self.model_provider, DynamicModelProvider):
            log.error(
                "%s Configuration 'model_provider_ref' is not a valid DynamicModelProvider instance. Type: %s",
                self.log_identifier,
                type(self.model_provider),
            )
            raise ValueError(
                f"{self.log_identifier} 'model_provider_ref' must be a DynamicModelProvider instance."
            )
        log.info("%s ModelConfigReceiverComponent initialized.", self.log_identifier)

    def invoke(self, message: SolaceMessage, data: Dict[str, Any]) -> None:
        """
        Processes the incoming model configuration message.

        Args:
            message: The SolaceMessage object from BrokerInput.
            data: The data extracted by BrokerInput (payload, topic, user_properties).
        """
        log_id_prefix = f"{self.log_identifier}[Invoke]"
        try:
            topic = data.get("topic", "")
            payload = data.get("payload", {})

            log.info(
                "%s Received model config message on topic: %s",
                log_id_prefix,
                topic,
            )

            # Check if model_config exists in payload
            model_config = payload.get("model_config")

            if model_config:
                log.info(
                    "%s Model config found, updating LiteLlm: %s",
                    log_id_prefix,
                    model_config.get('model', 'N/A'),
                )
                self.model_provider._initialized = True
                self.model_provider.update_litellm_model(model_config)
            else:
                log.info(
                    "%s No model config or empty config, removing LiteLlm model",
                    log_id_prefix,
                )
                self.model_provider.remove_litellm_model()

            message.call_acknowledgements()
            log.debug("%s Message acknowledged to BrokerInput.", log_id_prefix)

        except Exception as e:
            log.exception(
                "%s Error in ModelConfigReceiverComponent invoke: %s",
                log_id_prefix,
                e,
            )
            if message:
                message.call_negative_acknowledgements()
            raise
        return None


class DynamicModelProvider:

    def __init__(self, component: SamComponentBase, litellm_instance: LiteLlm, model_id: str):
        self._component = component
        self._litellm_instance = litellm_instance
        self._model_id = model_id

        # Internal SAC flow for subscribing to model config updates
        self._internal_app = None
        self._broker_input = None

        # Initial model configuration
        self._initialized = False
        asyncio.create_task(self.initialize())

    async def initialize(self):
        """
        Initialize the DynamicModelProvider by starting to listen for model config changes.
        """
        await self.listen_for_model_config_change()

        # Call request_model_config up to 3 times, once every 5 seconds, until initialized
        for i in range(3):
            await self.request_model_config()
            await asyncio.sleep(5)
            if self._initialized:
                break
        
        if not self._initialized:
            log.warning(
                "%s Model configuration not received after multiple attempts. LiteLlm instance may not be configured.",
                self._component.log_identifier,
            )

    def update_litellm_model(self, model_config: Union[str, Dict[str, Any]]) -> None:
        """
        Update the LiteLlm instance with the new model configuration.

        Args:
            model_config: The new model configuration (model name or config dict).
        """
        log.info("Updating LiteLlm instance with new model: %s", model_config.get('model', 'N/A') if isinstance(model_config, dict) else model_config)
        self._litellm_instance.configure_model(model_config)

    def remove_litellm_model(self) -> None:
        """
        Remove the model configuration from the LiteLlm instance.
        """
        log.info("Removing model configuration from LiteLlm instance.")
        self._litellm_instance.unconfigure_model()

    async def request_model_config(self) -> None:
        """
        Request model configuration for the component.
        """
        component_id = self._component.get_component_id()
        log.info("Requesting model configuration for LiteLlm instance for component %s", component_id)
        topic = get_bootstrap_request_topic(self._component.namespace, self._model_id)
        payload = {
            "component_id": component_id,
            "component_type": self._component._get_component_type(),
            "reply_to": get_bootstrap_response_topic(self._component.namespace, self._model_id, component_id),
            "model_id": self._model_id,
        }
        self._component.publish_a2a_message(
            payload=payload,
            topic=topic
        )
        log.debug("Published model config request to topic %s with payload: %s", topic, payload)

    def _ensure_config_listener_flow_is_running(self) -> None:
        """
        Ensures the internal SAC flow for model config updates is created and running.
        This method is designed to be called once during component startup.
        """
        log_id_prefix = f"[DynamicModelProvider][EnsureConfigFlow]"
        if self._internal_app is not None:
            log.debug("%s Config listener flow already running.", log_id_prefix)
            return

        log.info("%s Initializing internal model config listener flow...", log_id_prefix)
        try:
            main_app = self._component.get_app()
            if not main_app or not main_app.connector:
                log.error(
                    "%s Cannot get main app or connector instance. Config listener flow NOT started.",
                    log_id_prefix,
                )
                raise RuntimeError(
                    "Main app or connector not available for internal flow creation."
                )

            main_broker_config = main_app.app_info.get("broker", {})
            if not main_broker_config:
                log.error(
                    "%s Main app broker configuration not found. Config listener flow NOT started.",
                    log_id_prefix,
                )
                raise ValueError("Main app broker configuration is missing.")

            # Subscribe to the model config update topic
            config_update_topic = get_model_config_update_topic(self._component.namespace, self._model_id)
            config_bootstrap_topic = get_bootstrap_response_topic(self._component.namespace, self._model_id, self._component.get_component_id())
            component_id = self._component.get_component_id()

            broker_input_cfg = {
                "component_module": "broker_input",
                "component_name": f"{component_id}_model_config_broker_input",
                "broker_queue_name": f"{self._component.namespace}q/model_config/{component_id}",
                "create_queue_on_start": True,
                "component_config": {
                    **main_broker_config,
                    "broker_subscriptions": [
                        {"topic": config_update_topic},
                        {"topic": config_bootstrap_topic}
                        ],
                },
            }

            receiver_cfg = {
                "component_class": ModelConfigReceiverComponent,
                "component_name": f"{component_id}_model_config_receiver",
                "component_config": {
                    "model_provider_ref": self
                },
            }

            flow_config = {
                "name": f"{component_id}_model_config_flow",
                "components": [broker_input_cfg, receiver_cfg],
            }

            internal_app_broker_config = main_broker_config.copy()
            internal_app_broker_config["input_enabled"] = True
            internal_app_broker_config["output_enabled"] = False

            app_config_for_internal_flow = {
                "name": f"{component_id}_model_config_internal_app",
                "flows": [flow_config],
                "broker": internal_app_broker_config,
                "app_config": {},
            }

            self._internal_app = main_app.connector.create_internal_app(
                app_name=app_config_for_internal_flow["name"],
                flows=app_config_for_internal_flow["flows"],
            )

            if not self._internal_app or not self._internal_app.flows:
                log.error(
                    "%s Failed to create internal model config app/flow.",
                    log_id_prefix,
                )
                self._internal_app = None
                raise RuntimeError("Internal model config app/flow creation failed.")

            self._internal_app.run()
            log.info("%s Internal model config app started.", log_id_prefix)

            flow_instance = self._internal_app.flows[0]
            if flow_instance.component_groups and flow_instance.component_groups[0]:
                from solace_ai_connector.components.inputs_outputs.broker_input import BrokerInput
                self._broker_input = flow_instance.component_groups[0][0]
                if not isinstance(self._broker_input, BrokerInput):
                    log.error(
                        "%s First component in config flow is not BrokerInput. Type: %s",
                        log_id_prefix,
                        type(self._broker_input).__name__,
                    )
                    self._broker_input = None
                    raise RuntimeError(
                        "Config listener flow setup error: BrokerInput not found."
                    )
                log.debug(
                    "%s Obtained reference to internal BrokerInput component.",
                    log_id_prefix,
                )
            else:
                log.error(
                    "%s Could not get BrokerInput instance from internal flow.",
                    log_id_prefix,
                )
                raise RuntimeError(
                    "Config listener flow setup error: BrokerInput instance not accessible."
                )

        except Exception as e:
            log.exception(
                "%s Failed to ensure config listener flow is running: %s",
                log_id_prefix,
                e,
            )
            if self._internal_app:
                try:
                    self._internal_app.cleanup()
                except Exception as cleanup_err:
                    log.error(
                        "%s Error during cleanup after config flow init failure: %s",
                        log_id_prefix,
                        cleanup_err,
                    )
            self._internal_app = None
            self._broker_input = None
            raise

    async def listen_for_model_config_change(self) -> None:
        """
        Listen for changes in the model configuration.
        Sets up the internal SAC flow to subscribe to model config updates.
        """
        log.info("Setting up model configuration listener...")
        self._ensure_config_listener_flow_is_running()

    def cleanup(self) -> None:
        """
        Cleanup resources when the provider is no longer needed.
        """
        log.info("Cleaning up DynamicModelProvider...")
        if self._internal_app:
            log.info("Cleaning up internal model config app...")
            try:
                self._internal_app.cleanup()
            except Exception as e:
                log.error(
                    "Error cleaning up internal model config app: %s",
                    e,
                )
        self._internal_app = None
        self._broker_input = None


async def start_model_listener(litellm_instance: LiteLlm, component: SamComponentBase, model_provider_id: str):
    """
    Start a model configuration listener for the given LiteLlm instance.

    Subscribes to A2A topic for model config events and calls
    litellm_instance.configure_model(config) when received.

    Args:
        litellm_instance: The LiteLlm instance to configure when model arrives.
        component: The SamAgentComponent for context (namespace, agent_name, etc.)
        model_provider_id: The identifier for the model provider
    """
    log.info("Starting model '%s' listener for component %s", model_provider_id, component.get_component_id())
    model_config_provider = DynamicModelProvider(component, litellm_instance, model_provider_id)
    return model_config_provider
