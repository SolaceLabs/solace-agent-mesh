import asyncio
import threading
from typing import Any, Dict, List, Optional

import uvicorn
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard
from fastapi import FastAPI, Request
from solace_ai_connector.common.log import log
from tests.integration.test_support.a2a_agent.executor import (
    DeclarativeAgentExecutor,
)


class TestA2AAgentServer:
    """
    Manages a runnable, in-process A2A agent for integration testing.

    This server uses a DeclarativeAgentExecutor to respond to requests based on
    directives provided in the test case, allowing for predictable and
    controllable behavior of a downstream A2A agent.
    """

    def __init__(self, host: str, port: int, agent_card: AgentCard):
        # 2.2.2: __init__ accepts host, port, and AgentCard
        self.host = host
        self.port = port
        self.agent_card = agent_card

        # 2.2.3: Initialize instance variables
        self._uvicorn_server: Optional[uvicorn.Server] = None
        self._server_thread: Optional[threading.Thread] = None
        self.captured_requests: List[Dict[str, Any]] = []
        self._stateful_responses_cache: Dict[str, List[Any]] = {}
        self._stateful_cache_lock = threading.Lock()

        # 2.3: A2A Application Setup
        # 2.3.1: Instantiate DeclarativeAgentExecutor
        executor = DeclarativeAgentExecutor(self)

        # 2.3.2: Instantiate InMemoryTaskStore
        task_store = InMemoryTaskStore()

        # 2.3.3: Instantiate DefaultRequestHandler
        handler = DefaultRequestHandler(agent_executor=executor, task_store=task_store)

        # 2.3.4: Instantiate A2AFastAPIApplication
        a2a_app_builder = A2AFastAPIApplication(
            agent_card=self.agent_card, http_handler=handler
        )

        # 2.3.5: Build the FastAPI app
        self.app: FastAPI = a2a_app_builder.build(rpc_url="/a2a")

        # 2.3.6: Add request capture middleware
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
