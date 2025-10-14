"""
Service layer for handling A2A task submissions and cancellations.
Uses CoreA2AService for logic and a provided function for publishing.
"""

import logging
import threading
from typing import Callable, Dict, Optional

from ....common import a2a
from ....gateway.http_sse.sse_manager import SSEManager
from ....core_a2a.service import CoreA2AService

log = logging.getLogger(__name__)

PublishFunc = Callable[[str, Dict, Optional[Dict]], None]


class TaskService:
    """
    Handles the logic for submitting and cancelling tasks to A2A agents.
    Delegates A2A message construction to CoreA2AService and publishing
    to an injected function.
    """

    def __init__(
        self,
        core_a2a_service: CoreA2AService,
        publish_func: PublishFunc,
        namespace: str,
        gateway_id: str,
        sse_manager: SSEManager,
        task_context_map: Dict[str, Dict],
        task_context_lock: threading.Lock,
        app_name: str,
    ):
        """
        Initializes the TaskService.

        Args:
            core_a2a_service: An instance of the CoreA2AService.
            publish_func: A callable function (provided by WebUIBackendComponent)
                          to publish messages to the A2A messaging layer.
                          Expected signature: publish_func(topic: str, payload: Dict, user_properties: Optional[Dict])
            namespace: The namespace string.
            gateway_id: The unique ID of this gateway instance.
            sse_manager: An instance of the SSEManager.
            task_context_map: Shared dictionary to store task context.
            task_context_lock: Lock for accessing the task context map.
            app_name: The name of the SAC application (used for artifact context).
        """
        if not isinstance(core_a2a_service, CoreA2AService):
            raise TypeError("core_a2a_service must be an instance of CoreA2AService")
        if not callable(publish_func):
            raise TypeError("publish_func must be a callable function")
        if not isinstance(sse_manager, SSEManager):
            raise TypeError("sse_manager must be an instance of SSEManager")

        self.core_a2a_service = core_a2a_service
        self._publish_func = publish_func
        self._namespace = namespace
        self._gateway_id = gateway_id
        self._sse_manager = sse_manager
        self._task_context_map = task_context_map
        self._task_context_lock = task_context_lock
        self._app_name = app_name
        log.info(
            "[TaskService] Initialized with Gateway ID: %s, App Name: %s",
            self._gateway_id,
            self._app_name,
        )

    async def cancel_task(
        self,
        agent_name: str,
        task_id: str,
        client_id: str,
        user_id: str = "web_user",
    ):
        """
        Constructs and publishes an A2A CancelTaskRequest using CoreA2AService.

        Args:
            agent_name: The name of the agent that owns the task.
            task_id: The ID of the task to cancel.
            client_id: The ID of the client requesting cancellation (frontend).
            user_id: An identifier for the user (optional).

        Raises:
            Exception: If constructing or publishing the message fails.
        """
        log_prefix = "[TaskService][Task:%s] " % task_id
        log.info(
            "%sRequesting cancellation for task owned by agent '%s'",
            log_prefix,
            agent_name,
        )

        try:
            target_topic, payload, user_properties = self.core_a2a_service.cancel_task(
                agent_name=agent_name,
                task_id=task_id,
                client_id=client_id,
                user_id=user_id,
            )

            log.debug(
                "%sPublishing CancelTaskRequest to topic: %s", log_prefix, target_topic
            )
            self._publish_func(
                topic=target_topic, payload=payload, user_properties=user_properties
            )
            log.info("%sSuccessfully published task cancellation request.", log_prefix)

        except Exception as e:
            log.exception("%sFailed to publish cancellation request: %s", log_prefix, e)
            raise a2a.create_internal_error(
                message="Failed to publish cancellation request: %s" % e
            ) from e
