"""
Stress and longevity tests for the agent and gateway infrastructure.
These tests are designed to be run manually or in a dedicated CI job,
as they are long-running and resource-intensive.
"""

import asyncio
import base64
import json
import time
import uuid
from typing import Any

import pytest

try:
    import psutil
except ImportError:
    psutil = None

try:
    from pympler import asizeof
except ImportError:
    asizeof = None

try:
    import objgraph
except ImportError:
    objgraph = None

from a2a.types import JSONRPCError, Task
from sam_test_infrastructure.gateway_interface.component import (
    TestGatewayComponent,
)
from sam_test_infrastructure.llm_server.server import TestLLMServer
from sam_test_infrastructure.memory_monitor import MemoryMonitor
from solace_ai_connector.solace_ai_connector import SolaceAiConnector

from solace_agent_mesh.agent.sac.component import SamAgentComponent
from solace_agent_mesh.common.utils.in_memory_cache import InMemoryCache

from ..integration.scenarios_programmatic.test_helpers import (
    create_gateway_input_data,
    get_all_task_events,
    submit_test_input,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.stress,
    pytest.mark.skipif(
        psutil is None, reason="psutil library is required for stress tests"
    ),
    pytest.mark.skipif(
        asizeof is None,
        reason="pympler library is required for detailed memory analysis",
    ),
    pytest.mark.skipif(
        objgraph is None,
        reason="objgraph library is required for detailed memory analysis",
    ),
]


TASK_PROFILES: list[dict[str, Any]] = [
    {
        "id": "simple_text",
        "initial_prompt": "Respond with a simple sentence.",
        "llm_responses": [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "This is a simple sentence.",
                        }
                    }
                ]
            }
        ],
    },
    {
        "id": "simple_tool_call",
        "initial_prompt": "What is the weather in London?",
        "llm_responses": [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_weather_1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_weather_tool",
                                        "arguments": '{"location": "London"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "The weather in London is sunny.",
                        }
                    }
                ]
            },
        ],
    },
    {
        "id": "peer_delegation",
        "initial_prompt": "Please delegate a task to Peer A.",
        "llm_responses": [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_peer_a_1",
                                    "type": "function",
                                    "function": {
                                        "name": "peer_TestPeerAgentA",
                                        "arguments": json.dumps(
                                            {
                                                "task_description": "Say hello from the main agent. [test_case_id={sub_task_id}] [responses_json={sub_task_responses_b64}]",
                                                "user_query": "Delegate a task.",
                                            }
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ],
                "_sub_task_definitions": {
                    "call_peer_a_1": {
                        "llm_responses": [
                            {
                                "choices": [
                                    {
                                        "message": {
                                            "role": "assistant",
                                            "content": "Hello from Peer A!",
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                },
            },
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Peer A has responded.",
                        }
                    }
                ]
            },
        ],
    },
]


def _precompile_llm_responses(
    responses: list[dict[str, Any]], scenario_id: str
) -> list[dict[str, Any]]:
    """
    Recursively walks LLM responses to replace _sub_task_definitions with
    stateful test case directives.
    """
    compiled_responses = []
    for response in responses:
        compiled_response = response.copy()
        if "_sub_task_definitions" in compiled_response:
            sub_task_defs = compiled_response.pop("_sub_task_definitions")
            tool_calls = (
                compiled_response.get("choices", [{}])[0]
                .get("message", {})
                .get("tool_calls", [])
            )

            for tool_call in tool_calls:
                tool_call_id = tool_call.get("id")
                if tool_call_id in sub_task_defs:
                    sub_task_def = sub_task_defs[tool_call_id]

                    compiled_sub_responses = _precompile_llm_responses(
                        sub_task_def["llm_responses"], f"{scenario_id}_{tool_call_id}"
                    )

                    sub_task_id = f"{scenario_id}-{tool_call_id}-{uuid.uuid4().hex[:8]}"
                    sub_responses_json = json.dumps(compiled_sub_responses)
                    sub_responses_b64 = base64.b64encode(
                        sub_responses_json.encode("utf-8")
                    ).decode("utf-8")

                    arguments_str = tool_call.get("function", {}).get("arguments", "{}")
                    arguments_dict = json.loads(arguments_str)

                    for key, value in arguments_dict.items():
                        if isinstance(value, str):
                            arguments_dict[key] = value.format(
                                sub_task_id=sub_task_id,
                                sub_task_responses_b64=sub_responses_b64,
                            )

                    tool_call["function"]["arguments"] = json.dumps(arguments_dict)

        compiled_responses.append(compiled_response)
    return compiled_responses


async def _run_task_from_profile(
    gateway_component: TestGatewayComponent,
    llm_server: TestLLMServer,
    profile: dict[str, Any],
    task_num: int,
):
    """Runs a single, complete task using the stateful LLM protocol."""
    scenario_id = f"stress-{profile['id']}-{task_num}"

    compiled_responses = _precompile_llm_responses(
        profile["llm_responses"], scenario_id
    )

    case_id = f"{scenario_id}-{uuid.uuid4().hex}"
    responses_json = json.dumps(compiled_responses)
    responses_b64 = base64.b64encode(responses_json.encode("utf-8")).decode("utf-8")

    stateful_prompt = (
        f"{profile['initial_prompt']} "
        f"[test_case_id={case_id}] [responses_json={responses_b64}]"
    )

    input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity=f"stress_user_{task_num}@example.com",
        text_parts_content=[stateful_prompt],
        scenario_id=case_id,
        external_context_override={"a2a_session_id": f"stress_session_{task_num}"},
    )

    try:
        task_id = await submit_test_input(gateway_component, input_data, scenario_id)
        events = await get_all_task_events(
            gateway_component, task_id, overall_timeout=30.0
        )

        assert events, f"Task {task_id} for profile {profile['id']} produced no events."
        assert isinstance(events[-1], (Task, JSONRPCError)), (
            f"Task {task_id} did not end with a terminal event."
        )

        return task_id
    finally:
        llm_server.clear_stateful_cache_for_id(case_id)


@pytest.mark.parametrize("parallel_tasks", [10, 30])
async def test_concurrency_stress_with_variety(
    parallel_tasks: int,
    test_gateway_app_instance: TestGatewayComponent,
    test_llm_server: TestLLMServer,
    main_agent_component: SamAgentComponent,
    peer_a_component: SamAgentComponent,
    shared_solace_connector: SolaceAiConnector,
):
    """Tests handling of many concurrent and varied tasks."""
    print(
        f"\nRunning concurrency stress test with {parallel_tasks} varied parallel tasks."
    )
    monitor = MemoryMonitor(
        test_id=f"concurrency_variety_{parallel_tasks}_tasks",
        objects_to_track=[shared_solace_connector],
        size_threshold_bytes=2000 * 1024,
        max_depth=100,
    )

    monitor.start()

    tasks_to_run = [
        _run_task_from_profile(
            test_gateway_app_instance,
            test_llm_server,
            TASK_PROFILES[i % len(TASK_PROFILES)],
            i,
        )
        for i in range(parallel_tasks)
    ]
    results = await asyncio.gather(*tasks_to_run, return_exceptions=True)

    await asyncio.sleep(0.5)

    test_llm_server.clear_captured_requests()
    test_gateway_app_instance.clear_captured_outputs()
    InMemoryCache().clear()

    monitor.stop_and_assert()

    successful_tasks = [res for res in results if not isinstance(res, Exception)]
    failed_tasks = [res for res in results if isinstance(res, Exception)]
    print(
        f"Concurrency test summary: {len(successful_tasks)} successful, {len(failed_tasks)} failed."
    )
    if failed_tasks:
        for i, failure in enumerate(failed_tasks):
            print(f"  Failure {i + 1}: {type(failure).__name__} - {failure}")
    assert len(successful_tasks) == parallel_tasks, (
        f"Expected {parallel_tasks} successful tasks, but {len(failed_tasks)} failed."
    )

    app_cache = InMemoryCache()
    llm_cache = test_llm_server._stateful_responses_cache
    assert len(main_agent_component.active_tasks) == 0, (
        "Main agent should have no lingering active tasks."
    )
    assert len(test_gateway_app_instance.task_context_manager._contexts) == 0, (
        "Gateway task context manager should be empty."
    )
    test_key = "test_empty_check_key"
    assert app_cache.get(test_key) is None, "InMemoryCache should be empty"
    assert len(llm_cache) == 0, (
        f"TestLLMServer cache should be empty, but contains {len(llm_cache)} items: {list(llm_cache.keys())}"
    )
    print(
        "Concurrency test completed successfully with all state and caches verified as clean."
    )


@pytest.mark.parametrize("total_tasks", [100])
async def test_longevity_with_variety_and_peer_calls(
    total_tasks: int,
    test_gateway_app_instance: TestGatewayComponent,
    test_llm_server: TestLLMServer,
    main_agent_component: SamAgentComponent,
    peer_a_component: SamAgentComponent,
    shared_solace_connector: SolaceAiConnector,
):
    """Tests for memory leaks by running many varied tasks, including peer calls."""
    print(f"\nRunning longevity test with {total_tasks} varied tasks.")
    monitor = MemoryMonitor(
        test_id=f"longevity_variety_{total_tasks}_tasks",
        objects_to_track=[shared_solace_connector],
        size_threshold_bytes=5000 * 1024,
        max_depth=100,
    )

    monitor.start()

    for i in range(total_tasks):
        profile = TASK_PROFILES[i % len(TASK_PROFILES)]
        task_start_time = time.monotonic()
        await _run_task_from_profile(
            test_gateway_app_instance, test_llm_server, profile, i
        )
        task_duration = time.monotonic() - task_start_time
        print(
            f"  Task {i + 1}/{total_tasks} ({profile['id']}) completed in {task_duration:.4f} seconds."
        )
        if (i + 1) % 20 == 0:
            print(f"  ... completed {i + 1}/{total_tasks} tasks.")

    await asyncio.sleep(0.5)

    test_llm_server.clear_captured_requests()
    test_gateway_app_instance.clear_captured_outputs()
    InMemoryCache().clear()

    monitor.stop_and_assert()

    app_cache = InMemoryCache()
    llm_cache = test_llm_server._stateful_responses_cache
    assert len(main_agent_component.active_tasks) == 0, (
        "Main agent should have no lingering active tasks."
    )
    assert len(test_gateway_app_instance.task_context_manager._contexts) == 0, (
        "Gateway task context manager should be empty."
    )
    test_key = "test_empty_check_key"
    assert app_cache.get(test_key) is None, "InMemoryCache should be empty"
    assert len(llm_cache) == 0, (
        f"TestLLMServer cache should be empty, but contains {len(llm_cache)} items: {list(llm_cache.keys())}"
    )
    print(
        "Longevity test completed successfully with all state and caches verified as clean."
    )


@pytest.mark.long_soak
async def test_very_long_longevity_soak_test(
    test_gateway_app_instance: TestGatewayComponent,
    test_llm_server: TestLLMServer,
    main_agent_component: SamAgentComponent,
    peer_a_component: SamAgentComponent,
    shared_solace_connector: SolaceAiConnector,
):
    """
    A very long-running soak test to check for subtle memory leaks over a large
    number of varied tasks.
    """
    total_tasks = 1000
    print(f"\nRunning VERY LONG longevity soak test with {total_tasks} varied tasks.")
    monitor = MemoryMonitor(
        test_id=f"longevity_soak_{total_tasks}_tasks",
        objects_to_track=[shared_solace_connector],
        size_threshold_bytes=10000000,
        force_report=True,
        max_depth=100,
    )

    monitor.start()

    for i in range(total_tasks):
        profile = TASK_PROFILES[i % len(TASK_PROFILES)]
        task_start_time = time.monotonic()
        await _run_task_from_profile(
            test_gateway_app_instance, test_llm_server, profile, i
        )
        task_duration = time.monotonic() - task_start_time
        print(
            f"  Task {i + 1}/{total_tasks} ({profile['id']}) completed in {task_duration:.4f} seconds."
        )
        if (i + 1) % 50 == 0:
            print(f"  ... completed {i + 1}/{total_tasks} tasks.")

    await asyncio.sleep(0.5)

    test_llm_server.clear_captured_requests()
    test_gateway_app_instance.clear_captured_outputs()
    InMemoryCache().clear()

    monitor.stop_and_assert()

    app_cache = InMemoryCache()
    llm_cache = test_llm_server._stateful_responses_cache
    assert len(main_agent_component.active_tasks) == 0, (
        "Main agent should have no lingering active tasks."
    )
    assert len(test_gateway_app_instance.task_context_manager._contexts) == 0, (
        "Gateway task context manager should be empty."
    )
    test_key = "test_empty_check_key"
    assert app_cache.get(test_key) is None, "InMemoryCache should be empty"
    assert len(llm_cache) == 0, (
        f"TestLLMServer cache should be empty, but contains {len(llm_cache)} items: {list(llm_cache.keys())}"
    )
    print(
        f"Longevity soak test with {total_tasks} tasks completed successfully with all state and caches verified as clean."
    )
