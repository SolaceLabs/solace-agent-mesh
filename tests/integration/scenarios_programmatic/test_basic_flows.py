"""
Programmatic integration tests for basic agent flows.
"""

import pytest
from sam_test_infrastructure.llm_server.server import (
    TestLLMServer,
    ChatCompletionResponse,
    Message,
    Choice,
    ToolCall,
    ToolCallFunction,
    Usage,
)
from sam_test_infrastructure.gateway_interface.component import (
    TestGatewayComponent,
)
from sam_test_infrastructure.a2a_validator.validator import (
    A2AMessageValidator,
)
from solace_agent_mesh.agent.sac.app import SamAgentApp

from .test_helpers import (
    prime_llm_server,
    create_gateway_input_data,
    submit_test_input,
    get_all_task_events,
    extract_outputs_from_event_list,
    assert_llm_request_count,
    assert_final_response_text_contains,
)

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.default
]


async def test_programmatic_basic_text_response(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    a2a_message_validator: A2AMessageValidator,
):
    """
    Test a basic scenario where the agent receives a text query and responds with text.
    """
    scenario_id = "programmatic_basic_text_response_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    llm_response_data = {
        "id": "chatcmpl-prog-basictext",
        "object": "chat.completion",
        "model": "test-llm-model-prog",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Programmatically, 2+2 still equals 4.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11},
    }
    prime_llm_server(test_llm_server, [llm_response_data])

    target_agent = "TestAgent"
    user_identity = "programmatic_user@example.com"
    input_texts = ["Hello Agent, what is 2+2 programmatically?"]

    test_input_data = create_gateway_input_data(
        target_agent=target_agent,
        user_identity=user_identity,
        text_parts_content=input_texts,
        scenario_id=scenario_id,
    )
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )

    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=5.0
    )
    terminal_event, aggregated_stream_text, terminal_event_text = (
        extract_outputs_from_event_list(all_events, scenario_id)
    )
    content_to_verify = (
        aggregated_stream_text
        if aggregated_stream_text is not None
        else terminal_event_text
    )
    assert_final_response_text_contains(
        content_to_verify,
        "Programmatically, 2+2 still equals 4.",
        scenario_id,
        terminal_event,
    )

    assert_llm_request_count(test_llm_server, 1, scenario_id)

    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_programmatic_simple_tool_call(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    a2a_message_validator: A2AMessageValidator,
):
    """
    Test a scenario with a simple tool call.
    """
    scenario_id = "programmatic_simple_tool_call_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    llm_response_tool_request_dict = ChatCompletionResponse(
        id="chatcmpl-prog-toolreq",
        model="test-llm-model-tool-req",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id="call_prog_weather_456",
                            type="function",
                            function=ToolCallFunction(
                                name="get_weather_tool",
                                arguments='{"location": "Paris"}',
                            ),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=8, total_tokens=18),
    ).model_dump(exclude_none=True)

    llm_response_after_tool_dict = ChatCompletionResponse(
        id="chatcmpl-prog-toolresp",
        model="test-llm-model-tool-resp",
        choices=[
            Choice(
                message=Message(
                    role="assistant", content="The weather in Paris is lovely and 25°C."
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=40, completion_tokens=12, total_tokens=52),
    ).model_dump(exclude_none=True)

    prime_llm_server(
        test_llm_server, [llm_response_tool_request_dict, llm_response_after_tool_dict]
    )

    target_agent = "TestAgent"
    user_identity = "programmatic_user_tool@example.com"
    input_texts = ["What's the weather like in Paris?"]

    test_input_data = create_gateway_input_data(
        target_agent=target_agent,
        user_identity=user_identity,
        text_parts_content=input_texts,
        scenario_id=scenario_id,
    )
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )

    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=10.0
    )
    terminal_event, aggregated_stream_text, terminal_event_text = (
        extract_outputs_from_event_list(all_events, scenario_id)
    )
    content_to_verify = (
        aggregated_stream_text
        if aggregated_stream_text is not None
        else terminal_event_text
    )
    assert_final_response_text_contains(
        content_to_verify, "Paris is lovely and 25°C", scenario_id, terminal_event
    )

    assert_llm_request_count(test_llm_server, 2, scenario_id)

    print(f"Scenario {scenario_id}: Completed successfully.")
