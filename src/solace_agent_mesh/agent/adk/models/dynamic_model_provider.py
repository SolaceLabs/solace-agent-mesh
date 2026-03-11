"""
Dynamic Model Provider for enterprise model configuration.
"""

from typing import Any, Dict, Union
from solace_agent_mesh.common.sac.sam_component_base import SamComponentBase
from solace_agent_mesh.agent.adk.models.lite_llm import LiteLlm
import logging

log = logging.getLogger(__name__)

BOOTSTRAP_REQUEST_TOPIC = "{namespace}/agents/{id}/bootstrap"
MODEL_CONFIG_UPDATE_TOPIC = "{namespace}/agents/{id}/configuration"

class DynamicModelProvider:

    def __init__(self, component: SamComponentBase, litellm_instance: LiteLlm):
        self._component = component
        self._litellm_instance = litellm_instance

        # Initial model configuration
        self.request_model_config()

    def update_litellm_model(self, model_config: Union[str, Dict[str, Any]]) -> None:
        """
        Update the LiteLlm instance with the new model configuration.

        Args:
            model_config: The new model configuration (model name or config dict).
        """
        log.info(f"Updating LiteLlm instance with new model config: {model_config}")
        self._litellm_instance.configure_model(model_config)

    def remove_litellm_model(self) -> None:
        """
        Remove the model configuration from the LiteLlm instance.
        """
        log.info("Removing model configuration from LiteLlm instance.")
        self._litellm_instance.unconfigure_model()

    def get_bootstrap_request_topic(self) -> str:
        """
        Get the A2A topic to publish model configuration requests to.

        Returns:
            The topic string to publish model config requests to.
        """

        return BOOTSTRAP_REQUEST_TOPIC.format(
            namespace=self._component.namespace,
            id=self._component.get_component_id(),
        )
    
    def get_model_config_update_topic(self) -> str:
        """
        Get the A2A topic to listen for model configuration updates on.

        Returns:
            The topic string to listen for model config updates on.
        """
        return MODEL_CONFIG_UPDATE_TOPIC.format(
            namespace=self._component.namespace,
            id=self._component.get_component_id(),
        )   

    async def request_model_config(self) -> Union[str, Dict[str, Any]]:
        """
        Request model configuration for the component.
        """
        component_id = self._component.get_component_id()
        log.info("Requesting model configuration for LiteLlm instance for component %s", component_id)
        topic = self.get_bootstrap_request_topic()
        payload = {
            "component_id": component_id,
            "reply_to": self.get_model_config_update_topic()
        }
        self._component.publish_a2a_message(
            payload=payload,
            topic=topic
        )
        log.debug("Published model config request to topic %s with payload: %s", topic, payload)

    async def listen_for_model_config_change(self) -> None:
        """
        Listen for changes in the model configuration.
        """
        # Future: listen for model config change events and update litellm_instance
        raise NotImplementedError(
            "Enterprise DynamicModelProvider event-based listening not yet implemented."
        )
    
    def cleanup(self) -> None:
        """
        Cleanup resources when the provider is no longer needed.
        """
        # Future: cleanup event listeners, etc.
        pass


async def start_model_listener(litellm_instance: LiteLlm, component: SamComponentBase):
    """
    Start a model configuration listener for the given LiteLlm instance.

    Currently a placeholder. Future: subscribes to A2A topic for model config
    events and calls litellm_instance.configure_model(config) when received.

    Args:
        litellm_instance: The LiteLlm instance to configure when model arrives.
        component: The SamAgentComponent for context (namespace, agent_name, etc.)
    """
    # Future: start A2A event listener for model config events
    # When config arrives: litellm_instance.configure_model(config)
    # When config removed: litellm_instance.unconfigure_model()
    model_config_provider = DynamicModelProvider(component, litellm_instance)
    await model_config_provider.listen_for_model_config_change()
