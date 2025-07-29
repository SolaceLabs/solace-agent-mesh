import asyncio
from collections import defaultdict
from typing import Any, Dict, Union, Optional, List
from solace_ai_connector.common.message import Message as SolaceMessage

from sam_event_mesh_gateway.component import EventMeshGatewayComponent
from src.solace_agent_mesh.common.a2a_protocol import _topic_matches_subscription
from src.solace_agent_mesh.common.types import (
    Task,
    JSONRPCError,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
)
from solace_ai_connector.common.log import log
from src.solace_agent_mesh.gateway.base.component import BaseGatewayComponent

info = {
    "class_name": "TestEventMeshGatewayComponent",
    "description": "Test component for the Event Mesh Gateway.",
}


class TestEventMeshGatewayComponent(EventMeshGatewayComponent):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        # We are overriding the init completely because the original one has a lot of setup
        # for the data plane client that we don't need for testing.
        self._captured_outputs: Dict[str, asyncio.Queue[Union[Task, JSONRPCError]]] = (
            defaultdict(asyncio.Queue)
        )
        self._captured_artifacts: Dict[str, List[Any]] = defaultdict(list)
        self.is_test_mode = True
        self.last_submitted_task_id: Optional[str] = None
        self.event_handlers_config: List[Dict[str, Any]] = self.get_config(
            "event_handlers"
        )
        self.event_handler_map: Dict[str, Dict[str, Any]] = {
            handler_conf.get("name"): handler_conf
            for handler_conf in self.event_handlers_config
        }

    async def submit_a2a_task(self, *args, **kwargs):
        task_id = await super().submit_a2a_task(*args, **kwargs)
        self.last_submitted_task_id = task_id
        return task_id

    async def _send_final_response_to_external(
        self, external_request_context: Dict[str, Any], task_data: Task
    ):
        task_id = task_data.id
        log.debug(
            "%s Capturing A2A final response for task %s", self.log_identifier, task_id
        )
        await self._captured_outputs[task_id].put(task_data)

    async def authenticate_and_enrich_user(
        self, external_event_data: Any
    ) -> Optional[Dict[str, Any]]:
        return {"id": "test-user@example.com", "name": "Test User"}

    async def _send_error_to_external(
        self, external_request_context: Dict[str, Any], error_data: JSONRPCError
    ):
        task_id = external_request_context.get("a2a_task_id_for_event")
        log.info(f"Capturing error for task {task_id}: {error_data.message}")
        if task_id:
            log.debug(
                "%s Capturing A2A error for task %s: %s",
                self.log_identifier,
                task_id,
                error_data.message,
            )
            await self._captured_outputs[task_id].put(error_data)
        else:
            await self._captured_outputs["__unassigned_errors__"].put(error_data)
            log.warning(
                "%s Captured error for UNKNOWN_TASK: %s",
                self.log_identifier,
                error_data.message,
            )

    async def _initialize_and_subscribe_data_plane(self):
        if hasattr(self, "is_test_mode") and self.is_test_mode:
            log.info(
                "%s Skipping data plane initialization in test mode.",
                self.log_identifier,
            )
            return
        await super()._initialize_and_subscribe_data_plane()

    async def _stop_data_plane_client(self):
        if hasattr(self, "is_test_mode") and self.is_test_mode:
            log.info(
                "%s Skipping data plane client stop in test mode.", self.log_identifier
            )
            return
        await super()._stop_data_plane_client()

    def _start_listener(self) -> None:
        if hasattr(self, "is_test_mode") and self.is_test_mode:
            log.info("%s Skipping listener start in test mode.", self.log_identifier)
            return
        super()._start_listener()

    def _stop_listener(self) -> None:
        if hasattr(self, "is_test_mode") and self.is_test_mode:
            log.info("%s Skipping listener stop in test mode.", self.log_identifier)
            return
        super()._stop_listener()

    async def send_test_input(
        self, topic: str, payload: Any, user_properties: Optional[Dict] = None
    ) -> str:
        log.debug(
            "%s TestEventMeshGatewayComponent: send_test_input called with topic: %s",
            self.log_identifier,
            topic,
        )

        solace_msg = SolaceMessage(
            topic=topic, payload=payload, user_properties=user_properties or {}
        )
        await self._handle_incoming_solace_message(solace_msg)
        return self.last_submitted_task_id

    async def get_next_captured_output(
        self, task_id: str, timeout: float = 5.0
    ) -> Optional[Union[Task, JSONRPCError]]:
        try:
            output = await asyncio.wait_for(
                self._captured_outputs[task_id].get(), timeout=timeout
            )
            self._captured_outputs[task_id].task_done()
            return output
        except asyncio.TimeoutError:
            return None

    def clear_captured_outputs(self, task_id: Optional[str] = None):
        if task_id:
            if task_id in self._captured_outputs:
                del self._captured_outputs[task_id]
        else:
            self._captured_outputs.clear()

    def cleanup(self):
        """
        Custom cleanup for the test component to ensure base class resources are released.
        """
        log.info(
            "%s Running custom cleanup for TestEventMeshGatewayComponent...",
            self.log_identifier,
        )
        super().cleanup()
        log.info(
            "%s Custom cleanup for TestEventMeshGatewayComponent finished.",
            self.log_identifier,
        )
