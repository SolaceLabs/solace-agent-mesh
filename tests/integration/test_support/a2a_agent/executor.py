from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import TaskEvent
from a2a.server.events.event_queue import EventQueue
from a2a.types import Task, TaskState, TaskStatus
from solace_ai_connector.common.log import log

if TYPE_CHECKING:
    from sam_test_infrastructure.a2a_agent_server.server import TestA2AAgentServer


class DeclarativeAgentExecutor(AgentExecutor):
    """
    An AgentExecutor for testing that returns pre-configured, declarative
    responses provided by the TestA2AAgentServer.
    """

    def __init__(self):
        """Initializes the executor. The server must be set separately."""
        self.server: Optional[TestA2AAgentServer] = None

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        """
        Executes the agent logic by retrieving the next primed response from
        the test server and enqueuing it as a TaskEvent.
        """
        log_id = f"[DeclarativeAgentExecutor:{context.task_id}]"
        if not self.server:
            log.error(f"{log_id} TestA2AAgentServer reference not set on executor.")
            event_queue.finished()
            return

        response_data = self.server.get_next_primed_response()
        if response_data:
            log.info(f"{log_id} Serving primed response from test server.")
            try:
                # The primed response is a full Task object
                task_obj = Task.model_validate(response_data)
                event_queue.enqueue_event(TaskEvent(task=task_obj))
            except Exception as e:
                log.error(f"{log_id} Failed to validate or enqueue primed response: {e}")
        else:
            log.warning(f"{log_id} No primed response available to serve.")

        event_queue.finished()

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        """Handles a cancellation request by updating the task state."""
        log_id = f"[DeclarativeAgentExecutor:{context.task_id}]"
        log.info(f"{log_id} Received cancellation request.")
        if context.current_task:
            task = context.current_task
            task.status = TaskStatus(state=TaskState.canceled)
            event_queue.enqueue_event(TaskEvent(task=task))
        event_queue.finished()
