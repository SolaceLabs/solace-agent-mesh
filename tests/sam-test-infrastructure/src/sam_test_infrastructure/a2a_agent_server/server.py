import asyncio
import threading
import time
from typing import Any, Dict, List, Optional

import uvicorn
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse
from solace_ai_connector.common.log import log


class TestA2AAgentServer:
    """
    Manages a runnable, in-process A2A agent for integration testing.

    This server uses a DeclarativeAgentExecutor to respond to requests based on
    directives provided in the test case, allowing for predictable and
    controllable behavior of a downstream A2A agent.
    """

    def __init__(
        self, host: str, port: int, agent_card: AgentCard, agent_executor: AgentExecutor
    ):
        # 2.2.2: __init__ accepts host, port, and AgentCard
        self.host = host
        self.port = port
        self.agent_card = agent_card
        self.agent_executor = agent_executor

        # 2.2.3: Initialize instance variables
        self._uvicorn_server: Optional[uvicorn.Server] = None
        self._server_thread: Optional[threading.Thread] = None
        self.captured_requests: List[Dict[str, Any]] = []
        self._stateful_responses_cache: Dict[str, List[Any]] = {}
        self._stateful_cache_lock = threading.Lock()
        self._primed_responses: List[Dict[str, Any]] = []
        self._primed_responses_lock = threading.Lock()

        # Auth testing state
        self._auth_validation_enabled = False
        self._expected_auth_type: Optional[str] = None  # "bearer", "apikey", None
        self._expected_auth_value: Optional[str] = None
        self._auth_should_fail_once = False  # For testing retry logic
        self._auth_failure_count = 0
        self._captured_auth_headers: List[Dict[str, str]] = []

        # HTTP error simulation state
        self._http_error_config: Optional[Dict[str, Any]] = None

        # 2.3: A2A Application Setup
        # 2.3.2: Instantiate InMemoryTaskStore
        task_store = InMemoryTaskStore()

        # 2.3.3: Instantiate DefaultRequestHandler
        handler = DefaultRequestHandler(
            agent_executor=self.agent_executor, task_store=task_store
        )

        # 2.3.4: Instantiate A2AFastAPIApplication
        a2a_app_builder = A2AFastAPIApplication(
            agent_card=self.agent_card, http_handler=handler
        )

        # 2.3.5: Build the FastAPI app
        self.app: FastAPI = a2a_app_builder.build(rpc_url="/a2a")

        # 2.3.6: Update the agent card with the correct, full URL
        self.agent_card.url = f"{self.url}/a2a"

        # 2.3.7: Add request capture middleware
        @self.app.middleware("http")
        async def capture_request_middleware(request: Request, call_next):
            if request.url.path == "/a2a":
                try:
                    body = await request.json()
                    self.captured_requests.append(body)
                    log.debug(
                        "[TestA2AAgentServer] Captured request: %s",
                        body.get("method"),
                    )
                except Exception as e:
                    log.error(
                        "[TestA2AAgentServer] Failed to capture request body: %s", e
                    )
            response = await call_next(request)
            return response

        # 2.3.7b: Add HTTP error simulation middleware (runs before other middleware)
        @self.app.middleware("http")
        async def http_error_simulation_middleware(request: Request, call_next):
            # Only simulate errors for A2A endpoint
            if request.url.path == "/a2a" and self._http_error_config:
                config = self._http_error_config
                self._http_error_config = None  # One-time use
                log.info(
                    "[TestA2AAgentServer] Simulating HTTP error: status=%d",
                    config["status_code"],
                )
                return JSONResponse(
                    status_code=config["status_code"],
                    content=config.get(
                        "error_body", {"error": f"HTTP {config['status_code']}"}
                    ),
                )
            return await call_next(request)

        # 2.3.8: Add auth validation middleware
        @self.app.middleware("http")
        async def auth_validation_middleware(request: Request, call_next):
            # Skip validation for non-A2A endpoints
            if request.url.path != "/a2a":
                return await call_next(request)

            # Capture auth headers for test assertions
            auth_header = request.headers.get("Authorization", "")
            apikey_header = request.headers.get("X-API-Key", "")

            self._captured_auth_headers.append(
                {
                    "authorization": auth_header,
                    "x_api_key": apikey_header,
                    "path": request.url.path,
                    "timestamp": time.time(),
                }
            )

            # If auth validation is disabled, just pass through
            if not self._auth_validation_enabled:
                return await call_next(request)

            # Test retry logic: fail once, then succeed
            if self._auth_should_fail_once and self._auth_failure_count == 0:
                self._auth_failure_count += 1
                log.info(
                    "[TestA2AAgentServer] Simulating 401 for retry test (first attempt)"
                )
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "unauthorized",
                        "message": "Invalid or expired token",
                    },
                )

            # Validate bearer token
            if self._expected_auth_type == "bearer":
                if not auth_header.startswith("Bearer "):
                    log.warning(
                        "[TestA2AAgentServer] Missing or malformed Bearer token"
                    )
                    return JSONResponse(
                        status_code=401,
                        content={
                            "error": "unauthorized",
                            "message": "Bearer token required",
                        },
                    )

                token = auth_header.replace("Bearer ", "")
                if self._expected_auth_value and token != self._expected_auth_value:
                    log.warning(
                        "[TestA2AAgentServer] Invalid token. Expected '%s', got '%s'",
                        self._expected_auth_value,
                        token,
                    )
                    return JSONResponse(
                        status_code=401,
                        content={"error": "unauthorized", "message": "Invalid token"},
                    )

            # Validate API key
            elif self._expected_auth_type == "apikey":
                if not apikey_header:
                    log.warning("[TestA2AAgentServer] Missing API key")
                    return JSONResponse(
                        status_code=401,
                        content={
                            "error": "unauthorized",
                            "message": "API key required",
                        },
                    )

                if (
                    self._expected_auth_value
                    and apikey_header != self._expected_auth_value
                ):
                    log.warning("[TestA2AAgentServer] Invalid API key")
                    return JSONResponse(
                        status_code=401,
                        content={"error": "unauthorized", "message": "Invalid API key"},
                    )

            # Auth validation passed
            return await call_next(request)

    @property
    def url(self) -> str:
        """Returns the base URL of the running server."""
        return f"http://{self.host}:{self.port}"

    @property
    def started(self) -> bool:
        """Checks if the uvicorn server instance is started."""
        return self._uvicorn_server is not None and self._uvicorn_server.started

    def start(self):
        """Starts the FastAPI server in a separate thread."""
        if self._server_thread is not None and self._server_thread.is_alive():
            log.warning("[TestA2AAgentServer] Server is already running.")
            return

        self.clear_captured_requests()
        self.clear_stateful_cache()
        self.clear_primed_responses()

        config = uvicorn.Config(
            self.app, host=self.host, port=self.port, log_level="warning"
        )
        self._uvicorn_server = uvicorn.Server(config)

        async def async_serve_wrapper():
            try:
                if self._uvicorn_server:
                    await self._uvicorn_server.serve()
            except asyncio.CancelledError:
                log.info("[TestA2AAgentServer] Server.serve() task was cancelled.")
            except Exception as e:
                log.error(
                    f"[TestA2AAgentServer] Error during server.serve(): {e}",
                    exc_info=True,
                )

        def run_server_in_new_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(async_serve_wrapper())
            finally:
                try:
                    all_tasks = asyncio.all_tasks(loop)
                    if all_tasks:
                        for task in all_tasks:
                            task.cancel()
                        loop.run_until_complete(
                            asyncio.gather(*all_tasks, return_exceptions=True)
                        )
                    if hasattr(loop, "shutdown_asyncgens"):
                        loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception as e:
                    log.error(
                        f"[TestA2AAgentServer] Error during loop shutdown: {e}",
                        exc_info=True,
                    )
                finally:
                    loop.close()
                    log.info("[TestA2AAgentServer] Event loop in server thread closed.")

        self._server_thread = threading.Thread(
            target=run_server_in_new_loop, daemon=True
        )
        self._server_thread.start()
        log.info(f"[TestA2AAgentServer] Starting on http://{self.host}:{self.port}...")

    def stop(self):
        """Stops the FastAPI server."""
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True

        if self._server_thread and self._server_thread.is_alive():
            log.info("[TestA2AAgentServer] Stopping, joining thread...")
            self._server_thread.join(timeout=5.0)
            if self._server_thread.is_alive():
                log.warning("[TestA2AAgentServer] Server thread did not exit cleanly.")
        self._server_thread = None
        self._uvicorn_server = None
        self.clear_primed_responses()
        self.clear_auth_state()
        log.info("[TestA2AAgentServer] Stopped.")

    def clear_captured_requests(self):
        """Clears the list of captured requests."""
        self.captured_requests.clear()

    def prime_responses(self, responses: List[Dict[str, Any]]):
        """
        Primes the server with a sequence of responses to serve for subsequent requests.
        Each call to this method overwrites any previously primed responses.
        """
        with self._primed_responses_lock:
            self._primed_responses = list(responses)
            log.info(
                "[TestA2AAgentServer] Primed with %d responses.",
                len(self._primed_responses),
            )

    def get_next_primed_response(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves the next available primed response in a thread-safe manner.
        This is intended to be called by the agent executor.
        """
        with self._primed_responses_lock:
            if self._primed_responses:
                response = self._primed_responses.pop(0)
                log.debug(
                    "[TestA2AAgentServer] Consumed primed response. %d remaining.",
                    len(self._primed_responses),
                )
                return response
        return None

    def clear_primed_responses(self):
        """Clears the primed response queue."""
        with self._primed_responses_lock:
            self._primed_responses.clear()
            log.debug("[TestA2AAgentServer] Cleared primed responses.")

    def configure_auth_validation(
        self,
        enabled: bool = True,
        auth_type: Optional[str] = None,
        expected_value: Optional[str] = None,
        should_fail_once: bool = False,
    ):
        """
        Configures authentication validation for testing.

        Args:
            enabled: Whether to validate auth headers
            auth_type: "bearer" or "apikey"
            expected_value: The expected token/key value
            should_fail_once: If True, first request returns 401, subsequent succeed
        """
        self._auth_validation_enabled = enabled
        self._expected_auth_type = auth_type
        self._expected_auth_value = expected_value
        self._auth_should_fail_once = should_fail_once
        self._auth_failure_count = 0
        log.info(
            "[TestA2AAgentServer] Auth validation configured: "
            "enabled=%s, type=%s, fail_once=%s",
            enabled,
            auth_type,
            should_fail_once,
        )

    def get_captured_auth_headers(self) -> List[Dict[str, str]]:
        """Returns all captured authentication headers for test assertions."""
        return self._captured_auth_headers.copy()

    def clear_auth_state(self):
        """Clears all auth-related test state."""
        self._auth_validation_enabled = False
        self._expected_auth_type = None
        self._expected_auth_value = None
        self._auth_should_fail_once = False
        self._auth_failure_count = 0
        self._captured_auth_headers.clear()
        log.debug("[TestA2AAgentServer] Auth state cleared")

    def clear_stateful_cache(self):
        """Clears the stateful response cache."""
        with self._stateful_cache_lock:
            self._stateful_responses_cache.clear()

    def configure_http_error_response(
        self, status_code: int, error_body: Optional[Dict[str, Any]] = None
    ):
        """
        Configures the server to return an HTTP error for the next request.

        This is a one-time configuration - after returning the error once,
        the server returns to normal operation.

        Args:
            status_code: HTTP status code to return (e.g., 500, 503)
            error_body: Optional JSON body to return with the error
        """
        self._http_error_config = {
            "status_code": status_code,
            "error_body": error_body or {"error": f"HTTP {status_code}"},
        }
        log.info(
            "[TestA2AAgentServer] Configured to return HTTP %d on next request",
            status_code,
        )

    def clear_captured_auth_headers(self):
        """Clears the captured authentication headers list."""
        self._captured_auth_headers.clear()
        log.debug("[TestA2AAgentServer] Cleared captured auth headers.")

    def get_cancel_requests(self) -> List[Dict[str, Any]]:
        """Returns all captured cancel requests."""
        return [
            req for req in self.captured_requests if req.get("method") == "tasks/cancel"
        ]

    def was_cancel_requested_for_task(self, task_id: str) -> bool:
        """Checks if a cancel request was received for a specific task ID."""
        cancel_requests = self.get_cancel_requests()
        for req in cancel_requests:
            params = req.get("params", {})
            if params.get("id") == task_id:
                return True
        return False
