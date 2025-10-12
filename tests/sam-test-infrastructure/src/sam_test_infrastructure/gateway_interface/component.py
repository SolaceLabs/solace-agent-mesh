"""
GDK-based Test Gateway Component for integration testing.
Translates test inputs into A2A messages, sends them via the dev_mode broker,
and captures A2A responses from the agent under test.
"""

import logging
import asyncio
import base64
import threading
from collections import defaultdict
from typing import Any, Dict, List, Union, Optional, Tuple

from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from solace_agent_mesh.common.a2a.types import ContentPart
from solace_agent_mesh.common import a2a
from a2a.types import (
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    Task,
    JSONRPCError,
)

log = logging.getLogger(__name__)

info = {
    "class_name": "TestGatewayComponent",
    "description": "GDK-based Test Gateway for integration testing.",
    "config_parameters": [],
    "input_schema": {},
    "output_schema": {},
}


class TestGatewayComponent(BaseGatewayComponent):
    """
    A GDK-based Test Gateway Component.
    - Receives test inputs programmatically.
    - Translates inputs to A2A messages.
    - Publishes A2A tasks to the dev_mode broker.
    - Subscribes to A2A responses/updates from the agent via dev_mode broker.
    - Captures these A2A responses for test assertions.
    """

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.name = self.component_config.get("gateway_id", "TestGateway")

        self._captured_outputs: Dict[
            str,
            asyncio.Queue[
                Union[
                    TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError
                ]
            ],
        ] = defaultdict(asyncio.Queue)
        self.captured_cancel_calls: List[str] = []
        self.context_lock = threading.Lock()
        log.info("%s TestGatewayComponent initialized.", self.log_identifier)

    async def _extract_initial_claims(
        self, external_event_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts the primary identity claims from the test input data.
        """
        user_identity_str = external_event_data.get(
            "user_identity", "default_test_user@example.com"
        )
        log.debug(
            "%s Extracted initial claims for test user: %s",
            self.log_identifier,
            user_identity_str,
        )
        if not user_identity_str:
            return None
        return {"id": user_identity_str, "source": "test_gateway"}

    async def _translate_external_input(
        self, external_event: dict[str, Any]
    ) -> Tuple[str, List[ContentPart], dict[str, Any]]:
        """
        Translates a structured test input dictionary into A2A task components.
        The `external_event` is expected to have keys like:
        - 'target_agent_name': str
        - 'a2a_parts': List[Dict] (where each dict defines a ContentPart)
        - 'external_context_override': Optional[Dict] (to be merged into the returned context)
        - '_authenticated_user_identity': Dict (injected by the caller)
        """
        log_id = f"{self.log_identifier}[TranslateTestInput]"
        log.debug("%s Translating test input: %s", log_id, external_event)

        authenticated_user_identity = external_event.get("_authenticated_user_identity")
        if not authenticated_user_identity:
            raise ValueError(
                "Internal error: authenticated_user_identity not passed to _translate_external_input"
            )

        target_agent_name = external_event.get("target_agent_name")
        if not target_agent_name:
            raise ValueError("Test input must specify 'target_agent_name'.")

        a2a_parts_data = external_event.get(
            "a2a_parts", external_event.get("parts", [])
        )
        a2a_parts: List[ContentPart] = []
        for part_data in a2a_parts_data:
            part_type = part_data.get("type")
            if part_type == "text":
                a2a_parts.append(a2a.create_text_part(text=part_data.get("text", "")))
            elif part_type == "file":
                if "bytes_base64" in part_data and part_data["bytes_base64"]:
                    content_bytes = base64.b64decode(part_data["bytes_base64"])
                    a2a_parts.append(
                        a2a.create_file_part_from_bytes(
                            content_bytes=content_bytes,
                            name=part_data.get("name", None),
                            mime_type=part_data.get(
                                "mime_type", "application/octet-stream"
                            ),
                            metadata=part_data.get("metadata"),
                        )
                    )
                elif "uri" in part_data and part_data["uri"]:
                    a2a_parts.append(
                        a2a.create_file_part_from_uri(
                            uri=part_data["uri"],
                            name=part_data.get("name", "testfile.dat"),
                            mime_type=part_data.get(
                                "mime_type", "application/octet-stream"
                            ),
                            metadata=part_data.get("metadata"),
                        )
                    )
                else:
                    log.warning(
                        "%s FilePart in test input is missing 'bytes_base64' or 'uri'. Skipping. Data: %s",
                        log_id,
                        part_data,
                    )
            elif part_type == "data":
                a2a_parts.append(
                    a2a.create_data_part(
                        data=part_data.get("data", {}),
                        metadata=part_data.get("metadata"),
                    )
                )
            else:
                log.warning(
                    "%s Unsupported part type in test input: %s", log_id, part_type
                )

        if not a2a_parts:
            log.warning("%s No A2A parts translated from test input.", log_id)

        test_provided_external_context = external_event.get("external_context", {})

        user_id_str = authenticated_user_identity.get("id")
        if "a2a_session_id" in test_provided_external_context:
            session_id_for_task_context = test_provided_external_context[
                "a2a_session_id"
            ]
        else:
            session_id_for_task_context = f"setup_session_for_{user_id_str}"

        first_text_part_content = (
            a2a_parts_data[0].get("text", "")
            if a2a_parts_data and a2a_parts_data[0].get("type") == "text"
            else ""
        )

        constructed_external_context = {
            "test_input_event_id": external_event.get(
                "test_event_id", f"test-event-{asyncio.get_running_loop().time()}"
            ),
            "authenticated_user_identity": authenticated_user_identity,
            "app_name_for_artifacts": target_agent_name,
            "user_id_for_artifacts": user_id_str,
            "a2a_session_id": session_id_for_task_context,
            "original_stateful_prompt": first_text_part_content,
            **{
                k: v
                for k, v in test_provided_external_context.items()
                if k != "a2a_session_id"
            },
        }
        if "a2a_session_id" in test_provided_external_context:
            constructed_external_context["a2a_session_id"] = (
                test_provided_external_context["a2a_session_id"]
            )

        invoked_artifacts = external_event.get("invoked_with_artifacts")
        if invoked_artifacts:
            constructed_external_context["invoked_with_artifacts"] = invoked_artifacts

        log.debug(
            "%s Translation complete. Target: %s, Parts: %d, Context: %s",
            log_id,
            target_agent_name,
            len(a2a_parts),
            constructed_external_context,
        )
        return target_agent_name, a2a_parts, constructed_external_context

    async def _send_update_to_external(
        self,
        external_request_context: Dict[str, Any],
        event_data: Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent],
        is_final_chunk_of_update: bool,
    ):
        task_id = event_data.task_id
        log.debug(
            "%s Capturing A2A update for task %s: %s",
            self.log_identifier,
            task_id,
            type(event_data).__name__,
        )
        await self._captured_outputs[task_id].put(event_data)

    async def _send_final_response_to_external(
        self, external_request_context: Dict[str, Any], task_data: Task
    ):
        task_id = task_data.id
        log.debug(
            "%s Capturing A2A final response for task %s", self.log_identifier, task_id
        )
        await self._captured_outputs[task_id].put(task_data)

    async def _send_error_to_external(
        self, external_request_context: Dict[str, Any], error_data: JSONRPCError
    ):
        task_id = external_request_context.get("a2a_task_id_for_event")
        if not task_id and error_data.data and isinstance(error_data.data, dict):
            task_id = error_data.data.get("taskId")

        log.debug(
            "%s Capturing A2A error for task %s: %s",
            self.log_identifier,
            task_id or "UNKNOWN_TASK",
            error_data.message,
        )
        if task_id:
            await self._captured_outputs[task_id].put(error_data)
        else:
            await self._captured_outputs["__unassigned_errors__"].put(error_data)
            log.warning(
                "%s Captured error for UNKNOWN_TASK: %s",
                self.log_identifier,
                error_data.message,
            )

    def _start_listener(self) -> None:
        log.debug(
            "%s TestGatewayComponent: _start_listener called (no-op).",
            self.log_identifier,
        )
        pass

    def _stop_listener(self) -> None:
        log.debug(
            "%s TestGatewayComponent: _stop_listener called (no-op).",
            self.log_identifier,
        )
        pass

    async def send_test_input(self, test_input_data: dict[str, Any]) -> str:
        """
        Primary method for tests to send input to this Test Gateway.
        It authenticates, translates, and submits the A2A task.

        Args:
            test_input_data: A dictionary representing the test input. Expected keys:
                             'target_agent_name', 'user_identity', 'a2a_parts' (list of dicts),
                             'external_context_override' (optional dict).

        Returns:
            The task_id assigned to the submitted A2A task.
        """
        log.debug(
            "%s TestGatewayComponent: send_test_input called with: %s",
            self.log_identifier,
            test_input_data,
        )

        user_identity = await self.authenticate_and_enrich_user(test_input_data)
        if user_identity is None:
            raise PermissionError("Test user authentication failed.")

        # Pass the user_identity into the event data for translation
        test_input_data_for_translation = test_input_data.copy()
        test_input_data_for_translation["_authenticated_user_identity"] = user_identity

        target_agent_name, a2a_parts, external_request_context_for_storage = (
            await self._translate_external_input(test_input_data_for_translation)
        )

        task_id = await self.submit_a2a_task(
            target_agent_name=target_agent_name,
            a2a_parts=a2a_parts,
            external_request_context=external_request_context_for_storage,
            user_identity=user_identity,
            is_streaming=test_input_data.get("is_streaming", True),
        )
        log.info(
            "%s TestGatewayComponent: Submitted task %s for agent %s.",
            self.log_identifier,
            task_id,
            target_agent_name,
        )
        return task_id

    async def cancel_task(
        self, agent_name: str, task_id: str, user_identity: str = "test_user"
    ):
        """
        Constructs and sends a task cancellation request.
        """
        log.info(
            "%s TestGatewayComponent: Cancelling task %s for agent %s.",
            self.log_identifier,
            task_id,
            agent_name,
        )
        self.captured_cancel_calls.append(task_id)

        target_topic, payload, user_properties = self.core_a2a_service.cancel_task(
            agent_name=agent_name,
            task_id=task_id,
            client_id=self.gateway_id,
            user_id=user_identity,
        )

        self.publish_a2a_message(
            topic=target_topic, payload=payload, user_properties=user_properties
        )
        log.info(
            "%s TestGatewayComponent: Cancellation message for task %s sent.",
            self.log_identifier,
            task_id,
        )

    def clear_all_captured_cancel_calls(self) -> None:
        """Clears the list of captured cancellation calls."""
        self.captured_cancel_calls = []
        log.debug(
            "%s TestGatewayComponent: Cleared all captured cancel calls.",
            self.log_identifier,
        )

    def was_cancel_called_for_task(self, task_id: str) -> bool:
        """Checks if cancel_task was called for a specific task ID."""
        return task_id in self.captured_cancel_calls

    async def get_next_captured_output(
        self, task_id: str, timeout: float = 5.0
    ) -> Optional[
        Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError]
    ]:
        """
        Retrieves the next captured A2A output for a given task_id.
        """
        if task_id not in self._captured_outputs:
            try:
                await asyncio.wait_for(
                    self._wait_for_queue_creation(task_id), timeout=0.1
                )
            except asyncio.TimeoutError:
                log.debug(
                    "%s TestGatewayComponent: No output queue for task_id %s after initial wait.",
                    self.log_identifier,
                    task_id,
                )
                return None

        try:
            output = await asyncio.wait_for(
                self._captured_outputs[task_id].get(), timeout=timeout
            )
            self._captured_outputs[task_id].task_done()
            log.debug(
                "%s TestGatewayComponent: Dequeued output for task %s: %s",
                self.log_identifier,
                task_id,
                type(output).__name__,
            )
            return output
        except asyncio.TimeoutError:
            log.debug(
                "%s TestGatewayComponent: Timeout waiting for output for task_id %s.",
                self.log_identifier,
                task_id,
            )
            return None
        except KeyError:
            log.warning(
                "%s TestGatewayComponent: KeyError for task_id %s in get_next_captured_output.",
                self.log_identifier,
                task_id,
            )
            return None

    async def _wait_for_queue_creation(self, task_id: str):
        """Helper to wait briefly for an asyncio.Queue to appear for a task_id."""
        poll_interval = 0.01
        max_polls = 10
        for _ in range(max_polls):
            if task_id in self._captured_outputs:
                return
            await asyncio.sleep(poll_interval)

    async def get_all_captured_outputs(
        self, task_id: str, drain_timeout: float = 0.2
    ) -> list[
        Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError]
    ]:
        """
        Retrieves all currently captured A2A outputs for a given task_id and empties the queue.
        Waits for `drain_timeout` for any final messages after the queue initially appears empty.
        """
        outputs: list[
            Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError]
        ] = []
        queue = self._captured_outputs[task_id]

        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.001)
                outputs.append(item)
                queue.task_done()
            except asyncio.TimeoutError:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=drain_timeout)
                    outputs.append(item)
                    queue.task_done()
                except asyncio.TimeoutError:
                    log.debug(
                        "%s TestGatewayComponent: Drain timeout reached for task %s. Collected %d outputs.",
                        self.log_identifier,
                        task_id,
                        len(outputs),
                    )
                    break
            except Exception as e:
                log.error(
                    "%s TestGatewayComponent: Unexpected error draining queue for task %s: %s",
                    self.log_identifier,
                    task_id,
                    e,
                )
                break
        return outputs

    def clear_all_captured_cancel_calls(self) -> None:
        """Clears the list of captured cancellation calls."""
        self.captured_cancel_calls = []
        log.debug(
            "%s TestGatewayComponent: Cleared all captured cancel calls.",
            self.log_identifier,
        )

    def was_cancel_called_for_task(self, task_id: str) -> bool:
        """Checks if cancel_task was called for a specific task ID."""
        return task_id in self.captured_cancel_calls

    def clear_captured_outputs(self, task_id: Optional[str] = None) -> None:
        """
        Clears captured outputs. If task_id is provided, clears for that specific task.
        If task_id is None, clears all captured outputs for all tasks.
        """
        with self.context_lock:
            if task_id:
                if task_id in self._captured_outputs:
                    q = self._captured_outputs[task_id]
                    while not q.empty():
                        try:
                            q.get_nowait()
                            q.task_done()
                        except asyncio.QueueEmpty:
                            break
                    del self._captured_outputs[task_id]
                    log.debug(
                        "%s TestGatewayComponent: Cleared outputs for task_id %s.",
                        self.log_identifier,
                        task_id,
                    )
            else:
                for tid in list(self._captured_outputs.keys()):
                    q = self._captured_outputs[tid]
                    while not q.empty():
                        try:
                            q.get_nowait()
                            q.task_done()
                        except asyncio.QueueEmpty:
                            break
                self._captured_outputs.clear()
                self._captured_outputs = defaultdict(asyncio.Queue)
                log.debug(
                    "%s TestGatewayComponent: Cleared all captured outputs.",
                    self.log_identifier,
                )
