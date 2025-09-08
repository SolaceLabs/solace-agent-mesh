from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import Task, TaskArtifactUpdateEvent, TaskState, TaskStatus, TaskStatusUpdateEvent
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
        the test server and enqueuing it. It ensures the task ID and context ID
        from the incoming request are preserved in the response.
        """
        log_id = f"[DeclarativeAgentExecutor:{context.task_id}]"
        if not self.server:
            log.error(f"{log_id} TestA2AAgentServer reference not set on executor.")
            await event_queue.close()
            return

        while response_data := self.server.get_next_primed_response():
            log.info(f"{log_id} Serving primed response from test server.")
            try:
                event_obj = None
                kind = response_data.get("kind")

                if kind == "task":
                    event_obj = Task.model_validate(response_data)
                elif kind == "status-update":
                    event_obj = TaskStatusUpdateEvent.model_validate(response_data)
                elif kind == "artifact-update":
                    event_obj = TaskArtifactUpdateEvent.model_validate(response_data)
                else:
                    raise ValueError(f"Unknown response kind in primed response: {kind}")

                # IMPORTANT: Overwrite the ID/ContextID from the YAML with the actual
                # ones from the request context to ensure proper correlation.
                if hasattr(event_obj, "id"):
                    event_obj.id = context.task_id
                if hasattr(event_obj, "task_id"):
                    event_obj.task_id = context.task_id
                if hasattr(event_obj, "context_id"):
                    event_obj.context_id = context.context_id

                await event_queue.enqueue_event(event_obj)

                # If the event is a final task, stop processing more responses for this request.
                if isinstance(event_obj, Task):
                    break
            except Exception as e:
                log.error(f"{log_id} Failed to validate or enqueue primed response: {e}")
                # Stop processing on error to avoid cascading failures
                break
        else:
            log.warning(f"{log_id} No more primed responses available to serve.")

        await event_queue.close()

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        """Handles a cancellation request by updating the task state."""
        log_id = f"[DeclarativeAgentExecutor:{context.task_id}]"
        log.info(f"{log_id} Received cancellation request.")
        if context.current_task:
            task = context.current_task
            task.status = TaskStatus(state=TaskState.canceled)
            await event_queue.enqueue_event(task)
        await event_queue.close()
