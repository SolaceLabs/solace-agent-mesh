"""
Reusable service layer for core A2A interactions like task submission,
cancellation, and agent discovery processing.
"""

import logging
import uuid
from typing import Dict, Optional, Any, List, Tuple

from a2a.types import (
    Message as A2AMessage,
    AgentCard,
)
from ..common import a2a
from ..common.agent_registry import AgentRegistry

log = logging.getLogger(__name__)

class CoreA2AService:
    """
    Encapsulates core A2A protocol logic, decoupled from specific gateways
    and SAC messaging implementation.
    """

    def __init__(self, agent_registry: AgentRegistry, namespace: str):
        """
        Initializes the CoreA2AService.

        Args:
            agent_registry: An instance of the shared AgentRegistry.
            namespace: The namespace string.
        """
        if not isinstance(agent_registry, AgentRegistry):
            raise TypeError("agent_registry must be an instance of AgentRegistry")
        if not namespace or not isinstance(namespace, str):
            raise ValueError("namespace must be a non-empty string")

        self.agent_registry = agent_registry
        self.namespace = namespace
        self.log_identifier = "[CoreA2AService]"
        log.info("%s Initialized with namespace: %s", self.log_identifier, namespace)

    def submit_task(
        self,
        agent_name: str,
        a2a_message: A2AMessage,
        session_id: str,
        client_id: str,
        reply_to_topic: str,
        user_id: str = "default_user",
        a2a_user_config: Optional[Dict[str, Any]] = None,
        metadata_override: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict, Dict]:
        """
        Constructs the topic, payload, and user properties for a non-streaming
        A2A SendTaskRequest.

        Args:
            agent_name: The name of the target agent.
            a2a_message: The A2AMessage object containing parts.
            session_id: The A2A session ID.
            client_id: The identifier of the originating client/gateway.
            reply_to_topic: The Solace topic where the final response should be sent.
            user_id: An identifier for the user (optional).
            a2a_user_config: Optional dictionary containing user-specific configuration or attributes.
            metadata_override: Optional dictionary to merge into task metadata.

        Returns:
            A tuple containing (target_topic, payload_dict, user_properties_dict).

        Raises:
            ValueError: If required parameters are missing or invalid.
            Exception: For other construction errors.
        """
        task_id = f"task-{uuid.uuid4().hex}"
        log_prefix = f"{self.log_identifier}[Task:{task_id}] "
        log.info(
            "%sConstructing non-streaming task request for agent '%s'",
            log_prefix,
            agent_name,
        )

        if not all([agent_name, a2a_message, session_id, client_id, reply_to_topic]):
            raise ValueError("Missing required parameters for submit_task")

        try:
            if not a2a_message.contextId:
                a2a_message.contextId = session_id

            request = a2a.create_send_message_request(
                message=a2a_message,
                task_id=task_id,
                metadata=metadata_override,
            )
            payload = request.model_dump(by_alias=True, exclude_none=True)

            target_topic = a2a.get_agent_request_topic(self.namespace, agent_name)

            user_properties = {
                "replyTo": reply_to_topic,
                "clientId": client_id,
                "userId": user_id,
            }
            if a2a_user_config is not None:
                user_properties["a2aUserConfig"] = a2a_user_config
                log.debug(
                    "%sAdded 'a2aUserConfig' to user_properties: %s",
                    log_prefix,
                    a2a_user_config,
                )

            log.debug(
                "%sPrepared SendTaskRequest data for topic: %s (ReplyTo: %s)",
                log_prefix,
                target_topic,
                reply_to_topic,
            )
            return target_topic, payload, user_properties

        except Exception as e:
            log.exception("%sFailed to construct task request data: %s", log_prefix, e)
            raise

    def submit_streaming_task(
        self,
        agent_name: str,
        a2a_message: A2AMessage,
        session_id: str,
        client_id: str,
        reply_to_topic: str,
        status_to_topic: str,
        user_id: str = "default_user",
        a2a_user_config: Optional[Dict[str, Any]] = None,
        metadata_override: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict, Dict]:
        """
        Constructs the topic, payload, and user properties for a streaming
        A2A SendTaskStreamingRequest.

        Args:
            agent_name: The name of the target agent.
            a2a_message: The A2AMessage object containing parts.
            session_id: The A2A session ID.
            client_id: The identifier of the originating client/gateway.
            reply_to_topic: The Solace topic where the final response should be sent.
            status_to_topic: The Solace topic where status updates should be sent.
            user_id: An identifier for the user (optional).
            a2a_user_config: Optional dictionary containing user-specific configuration or attributes.
            metadata_override: Optional dictionary to merge into task metadata.

        Returns:
            A tuple containing (target_topic, payload_dict, user_properties_dict).

        Raises:
            ValueError: If required parameters are missing or invalid.
            Exception: For other construction errors.
        """
        task_id = f"task-{uuid.uuid4().hex}"
        log_prefix = f"{self.log_identifier}[Task:{task_id}] "
        log.info(
            "%sConstructing streaming task request for agent '%s'",
            log_prefix,
            agent_name,
        )

        if not all(
            [
                agent_name,
                a2a_message,
                session_id,
                client_id,
                reply_to_topic,
                status_to_topic,
            ]
        ):
            raise ValueError("Missing required parameters for submit_streaming_task")

        try:
            if not a2a_message.contextId:
                a2a_message.contextId = session_id

            request = a2a.create_send_streaming_message_request(
                message=a2a_message,
                task_id=task_id,
                metadata=metadata_override,
            )
            payload = request.model_dump(by_alias=True, exclude_none=True)

            target_topic = a2a.get_agent_request_topic(self.namespace, agent_name)

            user_properties = {
                "replyTo": reply_to_topic,
                "a2aStatusTopic": status_to_topic,
                "clientId": client_id,
                "userId": user_id,
            }
            if a2a_user_config is not None:
                user_properties["a2aUserConfig"] = a2a_user_config
                log.debug(
                    "%sAdded 'a2aUserConfig' to user_properties: %s",
                    log_prefix,
                    a2a_user_config,
                )

            log.debug(
                "%sPrepared SendTaskStreamingRequest data for topic: %s (ReplyTo: %s, StatusTo: %s)",
                log_prefix,
                target_topic,
                reply_to_topic,
                status_to_topic,
            )
            return target_topic, payload, user_properties

        except Exception as e:
            log.exception(
                "%sFailed to construct streaming task request data: %s", log_prefix, e
            )
            raise

    def cancel_task(
        self,
        agent_name: str,
        task_id: str,
        client_id: str,
        user_id: str = "default_user",
    ) -> Tuple[str, Dict, Dict]:
        """
        Constructs the topic, payload, and user properties for an A2A CancelTaskRequest.

        Args:
            agent_name: The name of the agent handling the task.
            task_id: The ID of the task to cancel.
            client_id: The identifier of the originating client/gateway.
            user_id: An identifier for the user (optional).

        Returns:
            A tuple containing (target_topic, payload_dict, user_properties_dict).

        Raises:
            ValueError: If required parameters are missing or invalid.
            Exception: For other construction errors.
        """
        log_prefix = f"{self.log_identifier}[Task:{task_id}] "
        log.info(
            "%sConstructing task cancellation request for agent '%s'",
            log_prefix,
            agent_name,
        )

        if not all([agent_name, task_id, client_id]):
            raise ValueError("Missing required parameters for cancel_task")

        try:
            request = a2a.create_cancel_task_request(task_id=task_id)
            payload = request.model_dump(by_alias=True, exclude_none=True)

            target_topic = a2a.get_agent_request_topic(self.namespace, agent_name)

            user_properties = {
                "clientId": client_id,
                "userId": user_id,
            }

            log.debug(
                "%sPrepared CancelTaskRequest data for topic: %s",
                log_prefix,
                target_topic,
            )
            return target_topic, payload, user_properties

        except Exception as e:
            log.exception(
                "%sFailed to construct task cancellation request data: %s",
                log_prefix,
                e,
            )
            raise

    def get_agent(self, agent_name: str) -> Optional[AgentCard]:
        """Retrieves a specific agent card by name from the registry."""
        log.debug("%sRetrieving agent: %s", self.log_identifier, agent_name)
        return self.agent_registry.get_agent(agent_name)

    def get_all_agents(self) -> List[AgentCard]:
        """Retrieves all currently discovered agent cards from the registry."""
        log.debug("%sRetrieving all agents", self.log_identifier)
        agent_names = self.agent_registry.get_agent_names()
        agents = [
            self.agent_registry.get_agent(name)
            for name in agent_names
            if self.agent_registry.get_agent(name)
        ]
        return agents

    def process_discovery_message(self, agent_card: AgentCard):
        """Processes an incoming agent card discovery message."""
        if not isinstance(agent_card, AgentCard):
            log.warning("%sReceived invalid agent card data type.", self.log_identifier)
            return

        is_new = self.agent_registry.add_or_update_agent(agent_card)
        if is_new:
            log.info(
                "%sAdded new agent via discovery: %s",
                self.log_identifier,
                agent_card.name,
            )
