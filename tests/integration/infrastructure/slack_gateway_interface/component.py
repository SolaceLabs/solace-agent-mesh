import asyncio
from collections import defaultdict
from typing import Any, Dict, List, Union, Optional, Tuple

from sam_slack.component import SlackGatewayComponent
from src.solace_agent_mesh.common.types import (
    Task,
    JSONRPCError,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    Part as A2APart,
)
from solace_ai_connector.common.log import log

info = {
    "class_name": "TestSlackGatewayComponent",
    "description": "Test component for the Slack Gateway.",
}


class TestSlackGatewayComponent(SlackGatewayComponent):
    def __init__(self, **kwargs: Any):
        # Mock slack dependencies before calling super().__init__
        self.slack_app = None
        self.slack_handler = None

        super().__init__(**kwargs)
        self._captured_outputs: Dict[
            str,
            asyncio.Queue[
                Union[
                    Task, JSONRPCError, TaskStatusUpdateEvent, TaskArtifactUpdateEvent
                ]
            ],
        ] = defaultdict(asyncio.Queue)
        self._captured_artifacts: Dict[str, List[Any]] = defaultdict(list)

    def _start_listener(self) -> None:
        log.debug(
            "%s TestSlackGatewayComponent: _start_listener called (no-op).",
            self.log_identifier,
        )
        pass

    def _stop_listener(self) -> None:
        log.debug(
            "%s TestSlackGatewayComponent: _stop_listener called (no-op).",
            self.log_identifier,
        )
        pass

    async def _send_update_to_external(
        self,
        external_request_context: Dict[str, Any],
        event_data: Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent],
        is_final_chunk_of_update: bool,
    ):
        task_id = event_data.id
        log.debug(
            "%s Capturing A2A update for task %s: %s",
            self.log_identifier,
            task_id,
            type(event_data).__name__,
        )
        if isinstance(event_data, TaskArtifactUpdateEvent):
            self._captured_artifacts[task_id].append(event_data.artifact)
        await self._captured_outputs[task_id].put(event_data)

    async def _send_final_response_to_external(
        self, external_request_context: Dict[str, Any], task_data: Task
    ):
        task_id = task_data.id
        # Forcefully inject any captured artifacts into the final task object
        # This simulates the aggregation that the real gateway component does.
        if self._captured_artifacts[task_id]:
            task_data.artifacts = self._captured_artifacts[task_id]

        log.debug(
            "%s Capturing A2A final response for task %s", self.log_identifier, task_id
        )
        await self._captured_outputs[task_id].put(task_data)

    async def _send_error_to_external(
        self, external_request_context: Dict[str, Any], error_data: JSONRPCError
    ):
        task_id = external_request_context.get("a2a_task_id_for_event")
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

    async def authenticate_and_enrich_user(
        self, external_event_data: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Mocks the authentication and returns a hardcoded user identity.
        """
        return {"id": "test-user@example.com", "name": "Test User"}

    async def send_test_input(self, test_input_data: Dict[str, Any]) -> str:
        """
        Simulates an incoming Slack event to the gateway.
        """
        log.debug(
            "%s TestSlackGatewayComponent: send_test_input called with: %s",
            self.log_identifier,
            test_input_data,
        )

        user_identity = await self.authenticate_and_enrich_user(test_input_data)
        if user_identity is None:
            raise PermissionError("Test user authentication failed.")

        target_agent_name, a2a_parts, external_request_context_for_storage = (
            await self._translate_external_input(test_input_data, user_identity)
        )

        task_id = await self.submit_a2a_task(
            target_agent_name=target_agent_name,
            a2a_parts=a2a_parts,
            external_request_context=external_request_context_for_storage,
            user_identity=user_identity,
            is_streaming=test_input_data.get("is_streaming", True),
        )
        log.info(
            "%s TestSlackGatewayComponent: Submitted task %s for agent %s.",
            self.log_identifier,
            task_id,
            target_agent_name,
        )
        return task_id

    async def get_next_captured_output(
        self, task_id: str, timeout: float = 5.0
    ) -> Optional[
        Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError]
    ]:
        """
        Retrieves the next captured A2A output for a given task_id.
        """
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
            if task_id in self._captured_artifacts:
                del self._captured_artifacts[task_id]
        else:
            self._captured_outputs.clear()
            self._captured_artifacts.clear()

    async def _translate_external_input(
        self, external_event: Any, authenticated_user_identity: Dict[str, Any]
    ) -> Tuple[str, List[A2APart], Dict[str, Any]]:
        """
        A simplified version of the real method that doesn't make external calls.
        """
        target_agent_name = external_event.get("target_agent_name")
        if not target_agent_name:
            raise ValueError("Test input must specify 'target_agent_name'.")

        a2a_parts = external_event.get("a2a_parts", [])

        external_request_context = {
            "slack_channel_id": external_event.get("channel"),
            "slack_thread_ts": external_event.get("ts"),
            "a2a_session_id": external_event.get("channel"),
            "user_id_for_a2a": authenticated_user_identity.get("id"),
            "target_agent_name": target_agent_name,
        }
        return target_agent_name, a2a_parts, external_request_context
