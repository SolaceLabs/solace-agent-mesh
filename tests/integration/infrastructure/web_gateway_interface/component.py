import asyncio
import threading
from collections import defaultdict
from typing import Any, Dict, List, Union, Optional, Tuple

import uvicorn
import threading
from src.solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from src.solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent
from src.solace_agent_mesh.common.types import (
    Task,
    JSONRPCError,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    Part as A2APart,
)
from solace_ai_connector.common.log import log

info = {
    "class_name": "TestWebGatewayComponent",
    "description": "Test component for the Web Gateway.",
}


class TestWebGatewayComponent(WebUIBackendComponent):
    def __init__(self, **kwargs: Any):
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
        # Mock out the visualization processor task as it's not needed for these tests
        self._visualization_processor_task = None

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
        return {"id": "test-user@example.com", "name": "Test User"}

    async def send_test_input(self, test_input_data: Dict[str, Any]) -> str:
        log.debug(
            "%s TestWebGatewayComponent: send_test_input called with: %s",
            self.log_identifier,
            test_input_data,
        )

        user_identity = await self.authenticate_and_enrich_user(test_input_data)
        if user_identity is None:
            raise PermissionError("Test user authentication failed.")

        target_agent_name, a2a_parts, external_request_context_for_storage = (
            await self._translate_test_input(test_input_data)
        )

        task_id = await self.submit_a2a_task(
            target_agent_name=target_agent_name,
            a2a_parts=a2a_parts,
            external_request_context=external_request_context_for_storage,
            user_identity=user_identity,
            is_streaming=test_input_data.get("is_streaming", True),
        )
        log.info(
            "%s TestWebGatewayComponent: Submitted task %s for agent %s.",
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

    async def _translate_test_input(
        self, external_event: Dict[str, Any]
    ) -> tuple[str, list[dict], dict[str, Any]]:
        target_agent_name = external_event.get("target_agent_name")
        if not target_agent_name:
            raise ValueError("Test input must specify 'target_agent_name'.")

        a2a_parts = external_event.get("a2a_parts", [])

        constructed_external_context = {
            "test_input_event_id": external_event.get(
                "test_event_id", f"test-event-{asyncio.get_running_loop().time()}"
            ),
            "app_name_for_artifacts": target_agent_name,
            "user_id_for_artifacts": "test-user@example.com",
            "a2a_session_id": f"test-session-{asyncio.get_running_loop().time()}",
        }

        if (
            "external_context_override" in external_event
            and "a2a_session_id" in external_event["external_context_override"]
        ):
            constructed_external_context["a2a_session_id"] = external_event[
                "external_context_override"
            ]["a2a_session_id"]

        return target_agent_name, a2a_parts, constructed_external_context

    async def _translate_external_input(
        self, external_event: Any, authenticated_user_identity: Dict[str, Any]
    ) -> Tuple[str, List[A2APart], Dict[str, Any]]:
        return None, [], {}

    def _start_fastapi_server(self):
        """
        Starts the Uvicorn server in a separate thread, but WITHOUT the visualization
        components that are not needed for tests and cause cleanup issues.
        This method overrides the one in WebUIBackendComponent.
        """
        log.info(
            "%s [_start_listener] Attempting to start TEST FastAPI/Uvicorn server...",
            self.log_identifier,
        )
        if self.fastapi_thread and self.fastapi_thread.is_alive():
            log.warning(
                "%s FastAPI server thread already started.", self.log_identifier
            )
            return

        try:
            from src.solace_agent_mesh.gateway.http_sse.main import (
                app as fastapi_app_instance,
                setup_dependencies,
            )

            self.fastapi_app = fastapi_app_instance
            setup_dependencies(self)

            config = uvicorn.Config(
                app=self.fastapi_app,
                host=self.fastapi_host,
                port=self.fastapi_port,
                log_level="info",
                lifespan="on",
            )
            self.uvicorn_server = uvicorn.Server(config)

            @self.fastapi_app.on_event("startup")
            async def capture_event_loop():
                log.info(
                    "%s [_start_listener] TEST FastAPI startup event triggered.",
                    self.log_identifier,
                )
                try:
                    self.fastapi_event_loop = asyncio.get_running_loop()
                    log.info(
                        "%s [_start_listener] Captured FastAPI event loop for test server: %s",
                        self.log_identifier,
                        self.fastapi_event_loop,
                    )
                    # NOTE: The visualization flow setup is INTENTIONALLY OMITTED for tests.
                except Exception as startup_err:
                    log.exception(
                        "%s [_start_listener] Error during TEST FastAPI startup event: %s",
                        self.log_identifier,
                        startup_err,
                    )
                    self.stop_signal.set()

            self.fastapi_thread = threading.Thread(
                target=self.uvicorn_server.run, daemon=True, name="FastAPI_Thread"
            )
            self.fastapi_thread.start()
            log.info(
                "%s [_start_listener] TEST FastAPI/Uvicorn server starting in background thread on http://%s:%d",
                self.log_identifier,
                self.fastapi_host,
                self.fastapi_port,
            )
        except Exception as e:
            log.exception(
                "%s [_start_listener] Failed to start TEST FastAPI/Uvicorn server: %s",
                self.log_identifier,
                e,
            )
            self.stop_signal.set()
            raise

    def _stop_listener(self) -> None:
        """
        GDK Hook Override: Shuts down the Uvicorn server and joins its thread.
        This is overridden for tests to ensure a graceful shutdown.
        """
        log.info(
            "%s TestWebGatewayComponent._stop_listener called. Shutting down Uvicorn server.",
            self.log_identifier,
        )
        if (
            self.uvicorn_server
            and self.fastapi_event_loop
            and self.fastapi_event_loop.is_running()
        ):
            log.info(
                "%s Shutting down Uvicorn server gracefully...", self.log_identifier
            )
            future = asyncio.run_coroutine_threadsafe(
                self.uvicorn_server.shutdown(), self.fastapi_event_loop
            )
            try:
                future.result(timeout=10)
                log.info("%s Uvicorn server shutdown complete.", self.log_identifier)
            except Exception as e:
                log.warning(
                    "%s Error during Uvicorn server graceful shutdown: %s. Forcing exit.",
                    self.log_identifier,
                    e,
                )
                self.uvicorn_server.should_exit = True
        elif self.uvicorn_server:
            self.uvicorn_server.should_exit = True
            log.info(
                "%s Signaled Uvicorn server to exit (event loop not available).",
                self.log_identifier,
            )

        if self.fastapi_thread and self.fastapi_thread.is_alive():
            log.info(
                "%s Waiting for FastAPI server thread to exit...", self.log_identifier
            )
            self.fastapi_thread.join(timeout=10)
            if self.fastapi_thread.is_alive():
                log.warning(
                    "%s FastAPI server thread did not exit gracefully.",
                    self.log_identifier,
                )

    def cleanup(self):
        """
        Custom cleanup for the test component. This method provides a safe shutdown
        sequence, bypassing the problematic cleanup logic in the parent class.
        """
        log.info(
            "%s Running custom cleanup for TestWebGatewayComponent...",
            self.log_identifier,
        )

        # Log all running threads for diagnostics
        log.info("--- Active Threads Before Cleanup ---")
        for thread in threading.enumerate():
            log.info(f"Thread: {thread.name} (Daemon: {thread.daemon})")
        log.info("------------------------------------")

        # 1. Stop the FastAPI server using our overridden, graceful _stop_listener.
        self._stop_listener()

        # 2. Call the grandparent's cleanup to release base resources,
        #    bypassing the broken WebUIBackendComponent.cleanup() entirely.
        log.info(
            "%s Calling BaseGatewayComponent.cleanup() directly...", self.log_identifier
        )
        BaseGatewayComponent.cleanup(self)

        log.info(
            "%s Custom cleanup for TestWebGatewayComponent finished.",
            self.log_identifier,
        )
