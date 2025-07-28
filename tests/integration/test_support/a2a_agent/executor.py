import base64
import json
import re
from typing import TYPE_CHECKING

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import Event, EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    Message,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)
from solace_ai_connector.common.log import log

if TYPE_CHECKING:
    from tests.integration.infrastructure.a2a_agent_server.server import (
        TestA2AAgentServer,
    )


class DeclarativeAgentExecutor(AgentExecutor):
    """
    An agent executor that plays back a declarative sequence of A2A events.

    Its behavior is controlled by directives embedded in the user's message:
    - `[test_case_id=...]`: A unique ID for the test.
    - `[responses_json=...]`: A base64-encoded JSON array of response sequences.
    """

    def __init__(self, server: "TestA2AAgentServer"):
        self.server = server
        self.log_identifier = f"[DeclarativeAgentExecutor:{self.server.agent_card.name}]"

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        """
        Parses directives from the request, retrieves the scripted response for the
        current turn, and enqueues the corresponding A2A events.
        """
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        user_input = context.get_user_input()

        # 1.3.3: Parse directives
        case_id_match = re.search(r"\[test_case_id=([\w.-]+)\]", user_input)
        responses_match = re.search(r"\[responses_json=([\w=+/]+)\]", user_input)

        if not case_id_match or not responses_match:
            log.error(
                "%s Directives [test_case_id=...] and/or [responses_json=...] not found in request.",
                self.log_identifier,
            )
            await updater.failed(
                message=updater.new_agent_message(
                    [
                        {
                            "kind": "text",
                            "text": "DeclarativeAgentExecutor requires [test_case_id] and [responses_json] directives.",
                        }
                    ]
                )
            )
            return

        test_case_id = case_id_match.group(1)
        log.info("%s Executing for test case ID: %s", self.log_identifier, test_case_id)

        # 1.3.5: Turn 0 Logic - Cache responses if not already cached
        with self.server._stateful_cache_lock:
            if test_case_id not in self.server._stateful_responses_cache:
                log.info(
                    "%s Caching new response sequence for test case: %s",
                    self.log_identifier,
                    test_case_id,
                )
                b64_str = responses_match.group(1)
                try:
                    json_str = base64.b64decode(b64_str).decode("utf-8")
                    self.server._stateful_responses_cache[test_case_id] = json.loads(
                        json_str
                    )
                except (
                    base64.binascii.Error,
                    json.JSONDecodeError,
                    UnicodeDecodeError,
                ) as e:
                    log.exception(
                        "%s Failed to decode/parse [responses_json] for test case %s: %s",
                        self.log_identifier,
                        test_case_id,
                        e,
                    )
                    await updater.failed(
                        message=updater.new_agent_message(
                            [
                                {
                                    "kind": "text",
                                    "text": f"Invalid [responses_json] directive: {e}",
                                }
                            ]
                        )
                    )
                    return

        # 1.3.6: Turn-Based Playback
        # The first message creates a task with one user message in history.
        turn_index = (
            len([m for m in context.current_task.history if m.role == "user"]) - 1
        )
        log.info("%s Determined turn index: %d", self.log_identifier, turn_index)

        with self.server._stateful_cache_lock:
            response_sequence = self.server._stateful_responses_cache.get(
                test_case_id, []
            )

        if turn_index >= len(response_sequence):
            log.error(
                "%s Ran out of responses for test case %s. Requested turn %d, but only %d turns are defined.",
                self.log_identifier,
                test_case_id,
                turn_index,
                len(response_sequence),
            )
            await updater.failed(
                message=updater.new_agent_message(
                    [
                        {
                            "kind": "text",
                            "text": f"Test case {test_case_id} ran out of responses for turn {turn_index}.",
                        }
                    ]
                )
            )
            return

        events_for_this_turn = response_sequence[turn_index]
        log.info(
            "%s Found %d events to play back for turn %d.",
            self.log_identifier,
            len(events_for_this_turn),
            turn_index,
        )

        # 1.3.7: Event Processing
        for event_dict in events_for_this_turn:
            # For Task objects, the ID is 'id', not 'task_id'
            if event_dict.get("kind") == "task":
                event_dict["id"] = context.task_id
            else:
                event_dict["task_id"] = context.task_id

            event_dict["context_id"] = context.context_id

            event_kind = event_dict.get("kind")
            event_to_enqueue: Event = None
            try:
                if event_kind == "task":
                    event_to_enqueue = Task.model_validate(event_dict)
                elif event_kind == "status-update":
                    event_to_enqueue = TaskStatusUpdateEvent.model_validate(event_dict)
                elif event_kind == "artifact-update":
                    event_to_enqueue = TaskArtifactUpdateEvent.model_validate(
                        event_dict
                    )
                elif event_kind == "message":
                    event_to_enqueue = Message.model_validate(event_dict)
                else:
                    raise ValueError(
                        f"Unknown event kind '{event_kind}' in responses_json"
                    )

                await updater.event_queue.enqueue_event(event_to_enqueue)
                log.debug("%s Enqueued event of kind: %s", self.log_identifier, event_kind)

            except Exception as e:
                log.exception(
                    "%s Failed to process or enqueue event for test case %s: %s\nEvent data: %s",
                    self.log_identifier,
                    test_case_id,
                    e,
                    event_dict,
                )
                await updater.failed(
                    message=updater.new_agent_message(
                        [{"kind": "text", "text": f"Failed to process event: {e}"}]
                    )
                )
                return

        # 1.3.8: Finalization
        await updater.event_queue.close()
        log.info(
            "%s Finished playback for turn %d and closed queue.",
            self.log_identifier,
            turn_index,
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        """Handles a cancellation request for the test agent."""
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()
