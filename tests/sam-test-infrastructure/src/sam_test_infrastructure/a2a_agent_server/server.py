import asyncio
import threading
from typing import Any, Dict, List, Optional

import uvicorn
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard
from fastapi import FastAPI, Request
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
                    log.info(
                        "[TestA2AAgentServer] Event loop in server thread closed."
                    )

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

    def clear_stateful_cache(self):
        """Clears the stateful response cache."""
        with self._stateful_cache_lock:
            self._stateful_responses_cache.clear()
