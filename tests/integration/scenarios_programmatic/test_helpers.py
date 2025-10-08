"""
Helper functions for programmatic integration tests to reduce boilerplate.
"""

import pytest
from typing import List, Dict, Any, Optional

from sam_test_infrastructure.llm_server.server import (
    TestLLMServer,
)
from sam_test_infrastructure.gateway_interface.component import (
    TestGatewayComponent,
)
from a2a.types import (
    TextPart,
    Task,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    JSONRPCError,
)
from a2a.utils.message import get_message_text
import time
import logging

logger = logging.getLogger(__name__)


def prime_llm_server(
    llm_server: TestLLMServer, responses: List[Dict[str, Any]]
) -> None:
    """
    Primes the TestLLMServer with a list of response dictionaries.
    Each dictionary in the list should conform to the structure expected by
    TestLLMServer.prime_responses (i.e., parsable into ChatCompletionResponse).
    """
    llm_server.prime_responses(responses)


def create_gateway_input_data(
    target_agent: str,
    user_identity: str,
    text_parts_content: List[str],
    scenario_id: str,
    external_context_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Constructs the input data dictionary for TestGatewayComponent.send_test_input.
    """
    a2a_parts_as_dicts: List[Dict[str, Any]] = []
    for text_content in text_parts_content:
        a2a_parts_as_dicts.append({"type": "text", "text": text_content})

    effective_external_context = external_context_override or {"test_case": scenario_id}

    input_data = {
        "target_agent_name": target_agent,
        "user_identity": user_identity,
        "a2a_parts": a2a_parts_as_dicts,
        "external_context_override": effective_external_context,
    }
    return input_data


async def submit_test_input(
    gateway_component: TestGatewayComponent,
    input_data: Dict[str, Any],
    scenario_id: str,
) -> str:
    """
    Submits the test input data to the gateway component and returns the task_id.
    Fails the test if task_id is not returned.
    """
    task_id = await gateway_component.send_test_input(input_data)
    assert (
        task_id
    ), f"Scenario {scenario_id}: Failed to submit task via TestGatewayComponent."
    return task_id


from typing import Union, Tuple


def extract_outputs_from_event_list(
    all_events: List[
        Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError]
    ],
    scenario_id: str,
) -> Tuple[Union[Task, JSONRPCError], Optional[str], Optional[str]]:
    """
    Processes a list of captured A2A events to extract terminal event, aggregated intermediate stream text,
    and text from the terminal event.
    Returns a tuple: (terminal_event_object, aggregated_intermediate_stream_text, text_from_terminal_event).
    - aggregated_intermediate_stream_text: Concatenation of text from non-final TaskStatusUpdateEvents.
    - text_from_terminal_event: Text extracted directly from the terminal Task or JSONRPCError.
    Assumes all_events contains a terminal event as ensured by get_all_task_events.
    """

    aggregated_intermediate_stream_text = ""
    text_from_terminal_event: Optional[str] = None
    terminal_event_obj: Optional[Union[Task, JSONRPCError]] = None

    for event in all_events:
        if isinstance(event, TaskStatusUpdateEvent):
            if not event.final and event.status and event.status.message:
                aggregated_intermediate_stream_text += get_message_text(
                    event.status.message, delimiter=""
                )
        elif isinstance(event, (Task, JSONRPCError)):
            terminal_event_obj = event

    if not terminal_event_obj:
        pytest.fail(
            f"Scenario {scenario_id}: Internal error - get_all_task_events did not provide a terminal event, but also did not fail the test."
        )

    if isinstance(terminal_event_obj, Task):
        if terminal_event_obj.status and terminal_event_obj.status.message:
            text_from_terminal_event = get_message_text(
                terminal_event_obj.status.message, delimiter=""
            )
        print(
            f"TestHelper: Scenario {scenario_id}: Extracted text from terminal Task object (length: {len(text_from_terminal_event) if text_from_terminal_event else 0})."
        )
    elif isinstance(terminal_event_obj, JSONRPCError):
        text_from_terminal_event = terminal_event_obj.message

    if not aggregated_intermediate_stream_text:
        aggregated_intermediate_stream_text = None
    else:
        pass

    return (
        terminal_event_obj,
        aggregated_intermediate_stream_text,
        text_from_terminal_event,
    )


async def get_all_task_events(
    gateway_component: TestGatewayComponent,
    task_id: str,
    overall_timeout: float = 10.0,
    polling_interval: float = 0.05,
) -> List[Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError]]:
    """
    Retrieves the complete, ordered list of A2A events for a specified task_id.
    Collects events until a terminal event (Task or JSONRPCError) is received
    or an overall_timeout is reached.
    Fails the test if no terminal event is received within the timeout.
    """
    start_time = time.monotonic()
    captured_events: List[
        Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError]
    ] = []
    scenario_id_for_log = f"get_all_task_events_for_{task_id}"

    while time.monotonic() - start_time < overall_timeout:
        event = await gateway_component.get_next_captured_output(
            task_id, timeout=polling_interval
        )
        if event:
            captured_events.append(event)
            print(
                f"TestHelper: Scenario {scenario_id_for_log}: Captured event {type(event).__name__} for task {task_id}."
            )
            if isinstance(event, (Task, JSONRPCError)):
                print(
                    f"TestHelper: Scenario {scenario_id_for_log}: Terminal event ({type(event).__name__}) received for task {task_id}."
                )
                return captured_events

    if not captured_events or not isinstance(captured_events[-1], (Task, JSONRPCError)):
        pytest.fail(
            f"Scenario {scenario_id_for_log}: Timeout ({overall_timeout}s). "
            f"No terminal event (Task or JSONRPCError) received for task {task_id}. "
            f"Captured {len(captured_events)} events: {[type(e).__name__ for e in captured_events]}"
        )
    return captured_events


def assert_llm_request_count(
    llm_server: TestLLMServer, expected_count: int, scenario_id: str
) -> None:
    """
    Asserts that the number of captured LLM requests matches the expected count.
    """
    captured_llm_requests = llm_server.get_captured_requests()
    assert (
        len(captured_llm_requests) == expected_count
    ), f"Scenario {scenario_id}: Mismatch in number of LLM calls. Expected {expected_count}, Got {len(captured_llm_requests)}."


def _extract_text_from_event(event: Any) -> Optional[str]:
    """Helper to extract primary text content from various event types."""
    text_content = None
    if isinstance(event, (Task, TaskStatusUpdateEvent)):
        if event.status and event.status.message:
            # get_message_text returns an empty string if no text parts are found.
            return get_message_text(event.status.message, delimiter="")
    elif isinstance(event, JSONRPCError):
        text_content = event.message
    return text_content


def find_first_event_of_type(
    events_list: List[Any], event_type_model: type, fail_if_not_found: bool = True
) -> Optional[Any]:
    """
    Finds the first event in the list that is an instance of event_type_model.
    Optionally fails the test if not found.
    """
    for event in events_list:
        if isinstance(event, event_type_model):
            return event
    if fail_if_not_found:
        pytest.fail(
            f"Expected to find an event of type {event_type_model.__name__} but none was found in the list of {len(events_list)} events."
        )
    return None


def assert_event_text_contains(
    event: Any,
    expected_substring: str,
    scenario_id: str,
    event_description: str = "Event",
) -> None:
    """
    Asserts that the textual content of a given event contains the expected substring.
    Fails the test if the event has no text or if the substring is not found.
    """
    text_content = _extract_text_from_event(event)
    if text_content is None:
        pytest.fail(
            f"Scenario {scenario_id}: {event_description} (type: {type(event).__name__}) had no extractable text content for assertion against '{expected_substring}'."
        )
    assert (
        expected_substring in text_content
    ), f"Scenario {scenario_id}: {event_description} text mismatch. Expected to contain '{expected_substring}', Got '{text_content}'"


def assert_final_response_text(
    all_events: List[
        Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError]
    ],
    expected_text: str,
    scenario_id: str,
) -> None:
    """
    Asserts that the final response text from a task matches the expected text exactly.
    It prioritizes the aggregated stream text if available, otherwise uses the
    text from the terminal event.
    """
    (
        terminal_event,
        stream_text,
        terminal_text,
    ) = extract_outputs_from_event_list(all_events, scenario_id)

    # Prioritize the full streamed text if it exists, otherwise use the terminal event's text.
    # This is because the terminal event might be truncated or just a summary.
    actual_text = stream_text if stream_text is not None else terminal_text

    if actual_text is None:
        pytest.fail(
            f"Scenario {scenario_id}: No text content found in the final response to assert."
        )

    assert actual_text == expected_text, (
        f"Scenario {scenario_id}: Final response text mismatch.\n"
        f"Expected: '{expected_text}'\n"
        f"Got     : '{actual_text}'"
    )


def assert_final_response_text_contains(
    verification_content: Optional[str],
    expected_substring: str,
    scenario_id: str,
    terminal_event: Union[Task, JSONRPCError],
) -> None:
    """
    Asserts that the provided verification_content (derived from prioritized event processing)
    contains the expected substring.
    If the terminal_event was an error and verification_content is its message, it will be checked.
    If verification_content is None, the assertion fails.
    """
    if verification_content is None:
        pytest.fail(
            f"Scenario {scenario_id}: No content available for verification. Terminal event was {type(terminal_event).__name__}."
        )

    if (
        isinstance(terminal_event, JSONRPCError)
        and verification_content == terminal_event.message
    ):
        assert (
            expected_substring in verification_content
        ), f"Scenario {scenario_id}: Unexpected error message. Expected to contain '{expected_substring}', Got '{verification_content}'."

        return

    assert (
        expected_substring in verification_content
    ), f"Scenario {scenario_id}: Unexpected text in verified content. Expected to contain '{expected_substring}', Got '{verification_content}'."
