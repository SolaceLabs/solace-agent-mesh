"""
Test isolation between WebUI REST endpoints and A2A streaming.

Ensures WebUI operations don't affect A2A SSE streaming and vice versa.
The gateway serves dual purposes and we need to validate one doesn't
negatively impact the other under load.

This module uses httpx with ASGI transport for truly async HTTP requests,
enabling genuine concurrent operations where multiple HTTP requests can be
in flight simultaneously without blocking the event loop.
"""

import pytest
import asyncio
import time
from typing import List, Any, Dict, Union

from a2a.types import Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, JSONRPCError

from tests.stress.conftest import StressTestConfig, AsyncHTTPAdapter
from tests.stress.metrics.collector import MetricsCollector
from tests.stress.metrics.reporter import MetricsReporter

pytestmark = [pytest.mark.stress, pytest.mark.asyncio, pytest.mark.isolation]


def create_llm_response(content: str, index: int = 0) -> Dict[str, Any]:
    """Create a properly formatted LLM response."""
    return {
        "id": f"chatcmpl-isolation-{index}",
        "object": "chat.completion",
        "model": "test-llm-model",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": content,
            },
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


async def collect_task_events(
    gateway_component,
    task_id: str,
    overall_timeout: float = 10.0,
    polling_interval: float = 0.1,
) -> List[Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError]]:
    """Collect all events for a task using integration test patterns."""
    start_time = time.monotonic()
    captured_events: List[
        Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Task, JSONRPCError]
    ] = []

    while time.monotonic() - start_time < overall_timeout:
        event = await gateway_component.get_next_captured_output(
            task_id, timeout=polling_interval
        )
        if event:
            captured_events.append(event)
            if isinstance(event, (Task, JSONRPCError)):
                return captured_events

    return captured_events


class TestWebUIAndA2AIsolation:
    """
    Test that WebUI endpoints don't affect A2A streaming and vice versa.

    Key endpoints:
    - WebUI: /api/v1/sessions, /api/v1/config, /api/v1/agent-cards
    - A2A: task submission -> SSE event streaming
    """

    async def test_webui_load_doesnt_affect_a2a_streaming(
        self,
        test_gateway_app_instance,
        test_llm_server,
        async_stress_http_client: AsyncHTTPAdapter,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
        metrics_reporter: MetricsReporter,
    ):
        """
        Heavy WebUI REST load shouldn't delay A2A event delivery.

        Scenario:
        1. Start A2A task that produces streaming events
        2. Simultaneously hammer WebUI endpoints (sessions, config, agent-cards)
        3. Verify A2A event latency remains within bounds

        Uses truly async HTTP client for genuine concurrent operations.
        """
        await metrics_collector.start()

        # Prime LLM for A2A task with proper format
        test_llm_server.prime_responses([
            create_llm_response("A2A response under WebUI load", 0)
        ])

        # Start A2A streaming task
        a2a_start_time = time.monotonic()
        input_data = {
            "target_agent_name": "TestAgent",
            "user_identity": "isolation-test-user",
            "a2a_parts": [{"type": "text", "text": "Test message during WebUI load"}],
        }
        task_id = await test_gateway_app_instance.send_test_input(input_data)
        await metrics_collector.record_latency(
            "a2a_submit", (time.monotonic() - a2a_start_time) * 1000
        )

        # Concurrent tasks: WebUI hammering and A2A event collection
        webui_duration = 5.0  # seconds
        webui_request_interval = 0.05  # 20 req/sec per endpoint

        async def hammer_webui_endpoints(http_client: AsyncHTTPAdapter):
            """Generate continuous WebUI REST requests - truly async."""
            end_time = asyncio.get_event_loop().time() + webui_duration
            request_count = 0

            while asyncio.get_event_loop().time() < end_time:
                # Mix of WebUI endpoints - these are truly async now!
                try:
                    await http_client.get_config()
                    request_count += 1
                except Exception as e:
                    await metrics_collector.record_error("webui_config", e)

                try:
                    await http_client.get_agent_cards()
                    request_count += 1
                except Exception as e:
                    await metrics_collector.record_error("webui_agent_cards", e)

                try:
                    await http_client.get_sessions()
                    request_count += 1
                except Exception as e:
                    await metrics_collector.record_error("webui_sessions", e)

                await asyncio.sleep(webui_request_interval)

            return request_count

        async def collect_a2a_events():
            """Collect A2A events and measure latency."""
            event_start = time.monotonic()
            first_event_time = None
            events = []

            # Collect events individually to track timing
            while time.monotonic() - event_start < 15.0:
                event = await test_gateway_app_instance.get_next_captured_output(
                    task_id, timeout=0.1
                )
                if event:
                    event_time = time.monotonic()
                    if first_event_time is None:
                        first_event_time = event_time
                        # Time to first event is the key isolation metric
                        first_event_latency = (first_event_time - event_start) * 1000
                        await metrics_collector.record_latency(
                            "a2a_first_event_latency", first_event_latency
                        )

                    events.append(event)
                    await metrics_collector.increment_counter("a2a_events_received")

                    if isinstance(event, (Task, JSONRPCError)):
                        break

            # Record total time to completion (single value)
            total_time = (time.monotonic() - event_start) * 1000
            await metrics_collector.record_latency("a2a_total_completion_time", total_time)

            return events, [total_time]

        # Run both concurrently using async HTTP client
        async with async_stress_http_client as http_client:
            webui_task = asyncio.create_task(hammer_webui_endpoints(http_client))
            a2a_task = asyncio.create_task(collect_a2a_events())

            webui_count, (a2a_events, a2a_times) = await asyncio.gather(
                webui_task, a2a_task
            )

        await metrics_collector.stop()

        # Validate
        await metrics_collector.set_gauge("webui_requests_during_a2a", webui_count)
        await metrics_collector.set_gauge("a2a_events_during_webui", len(a2a_events))

        # A2A should complete successfully
        assert len(a2a_events) > 0, "No A2A events received"

        # Check A2A latency metrics
        summary = metrics_collector.get_summary()

        # Primary check: time to first event (best measure of isolation)
        # With truly async HTTP, we expect much tighter latencies
        if "a2a_first_event_latency" in summary["operations"]:
            first_event_p99 = summary["operations"]["a2a_first_event_latency"]["percentiles"]["p99"]
            # With async HTTP, first event should arrive within 2 seconds
            max_first_event = 2000.0
            assert first_event_p99 < max_first_event, (
                f"A2A first event latency {first_event_p99:.1f}ms exceeds {max_first_event}ms under WebUI load"
            )

        # Secondary check: total completion time
        if "a2a_total_completion_time" in summary["operations"]:
            total_p99 = summary["operations"]["a2a_total_completion_time"]["percentiles"]["p99"]
            # With async HTTP, total completion should be within 5 seconds
            max_total = 5000.0
            assert total_p99 < max_total, (
                f"A2A total completion time {total_p99:.1f}ms exceeds {max_total}ms under WebUI load"
            )

        # WebUI should also have reasonable latency
        webui_ops = ["config_fetch", "agent_cards_fetch", "sessions_list"]
        for op in webui_ops:
            if op in summary["operations"]:
                error_rate = summary["operations"][op]["error_rate_percent"]
                assert error_rate < 5.0, f"WebUI {op} error rate {error_rate:.1f}% too high"

    async def test_a2a_streaming_doesnt_affect_webui_response_time(
        self,
        test_gateway_app_instance,
        test_llm_server,
        async_stress_http_client: AsyncHTTPAdapter,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
    ):
        """
        Heavy A2A streaming load shouldn't delay WebUI REST responses.

        Scenario:
        1. Generate heavy A2A streaming load (multiple concurrent tasks)
        2. Simultaneously make WebUI REST requests
        3. Verify WebUI response times remain within bounds

        Uses truly async HTTP client for genuine concurrent operations.
        """
        await metrics_collector.start()

        a2a_task_count = 5
        test_duration = 5.0

        # Prime LLM for multiple A2A tasks with proper format
        responses = [
            create_llm_response(f"A2A load {i}", i)
            for i in range(a2a_task_count)
        ]
        test_llm_server.prime_responses(responses)

        # Start multiple A2A tasks
        async def run_a2a_task(idx: int):
            """Run a single A2A task."""
            input_data = {
                "target_agent_name": "TestAgent",
                "user_identity": f"a2a-load-user-{idx}",
                "a2a_parts": [{"type": "text", "text": f"A2A load message {idx}"}],
            }

            task_id = await test_gateway_app_instance.send_test_input(input_data)
            await metrics_collector.increment_counter("a2a_tasks_started")

            # Collect events using proven pattern
            events = await collect_task_events(
                test_gateway_app_instance,
                task_id,
                overall_timeout=15.0,
                polling_interval=0.1,
            )

            for event in events:
                await metrics_collector.increment_counter("a2a_load_events")
                if isinstance(event, (Task, JSONRPCError)):
                    await metrics_collector.increment_counter("a2a_tasks_completed")

        async def measure_webui_during_load(http_client: AsyncHTTPAdapter):
            """Measure WebUI response times during A2A load - truly async."""
            end_time = asyncio.get_event_loop().time() + test_duration
            request_count = 0

            while asyncio.get_event_loop().time() < end_time:
                # Make WebUI requests - truly async, doesn't block A2A processing
                await http_client.get_config()
                await http_client.get_agent_cards()
                request_count += 1
                await asyncio.sleep(0.1)

            return request_count

        # Use async HTTP client for WebUI requests
        async with async_stress_http_client as http_client:
            # Start A2A load
            a2a_tasks = [
                asyncio.create_task(run_a2a_task(i))
                for i in range(a2a_task_count)
            ]

            # Measure WebUI while A2A is running
            webui_task = asyncio.create_task(measure_webui_during_load(http_client))

            # Wait for both
            webui_count = await webui_task
            await asyncio.gather(*a2a_tasks, return_exceptions=True)

        await metrics_collector.stop()

        # Validate WebUI performance under A2A load
        summary = metrics_collector.get_summary()

        webui_ops = ["config_fetch", "agent_cards_fetch"]
        for op in webui_ops:
            if op in summary["operations"]:
                p99 = summary["operations"][op]["percentiles"]["p99"]
                # WebUI should stay fast even under A2A load
                # With async HTTP, we can use tighter thresholds
                assert p99 < 500, (  # 500ms max with async
                    f"WebUI {op} p99 {p99:.1f}ms too slow under A2A load"
                )
                error_rate = summary["operations"][op]["error_rate_percent"]
                assert error_rate < 1.0, f"WebUI {op} error rate {error_rate:.1f}% too high"

    async def test_mixed_workload_stability(
        self,
        test_gateway_app_instance,
        test_llm_server,
        async_stress_http_client: AsyncHTTPAdapter,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
        metrics_reporter: MetricsReporter,
    ):
        """
        Test stability under sustained mixed workload.

        Scenario:
        1. Run continuous mixed workload of WebUI and A2A operations
        2. Monitor for errors, latency spikes, or resource issues
        3. Validate system remains stable throughout

        Uses truly async HTTP client for genuine concurrent operations.
        """
        await metrics_collector.start()

        test_duration = min(stress_config.test_duration_seconds, 30.0)
        a2a_interval = 1.0  # New A2A task every second
        webui_interval = 0.1  # WebUI request every 100ms

        # Prime many LLM responses with proper format
        response_count = int(test_duration / a2a_interval) + 10
        responses = [
            create_llm_response(f"Mixed {i}", i)
            for i in range(response_count)
        ]
        test_llm_server.prime_responses(responses)

        running = True
        a2a_idx = 0

        async def a2a_generator():
            """Generate A2A tasks at regular intervals."""
            nonlocal a2a_idx
            end_time = asyncio.get_event_loop().time() + test_duration

            while asyncio.get_event_loop().time() < end_time and running:
                input_data = {
                    "target_agent_name": "TestAgent",
                    "user_identity": f"mixed-user-{a2a_idx}",
                    "a2a_parts": [{"type": "text", "text": f"Mixed workload {a2a_idx}"}],
                }

                try:
                    task_id = await test_gateway_app_instance.send_test_input(input_data)
                    await metrics_collector.increment_counter("mixed_a2a_submitted")

                    # Fire and forget event collection
                    asyncio.create_task(self._collect_task_events(
                        test_gateway_app_instance, task_id, metrics_collector
                    ))

                except Exception as e:
                    await metrics_collector.record_error("mixed_a2a_submit", e)

                a2a_idx += 1
                await asyncio.sleep(a2a_interval)

        async def webui_generator(http_client: AsyncHTTPAdapter):
            """Generate WebUI requests at regular intervals - truly async."""
            end_time = asyncio.get_event_loop().time() + test_duration

            while asyncio.get_event_loop().time() < end_time and running:
                try:
                    await http_client.get_config()
                except Exception as e:
                    await metrics_collector.record_error("mixed_webui", e)

                await asyncio.sleep(webui_interval)

        # Use async HTTP client for genuine concurrency
        async with async_stress_http_client as http_client:
            # Run both generators - truly concurrent now
            a2a_task = asyncio.create_task(a2a_generator())
            webui_task = asyncio.create_task(webui_generator(http_client))

            await asyncio.gather(a2a_task, webui_task)

        # Give time for in-flight A2A tasks to complete
        await asyncio.sleep(2.0)

        await metrics_collector.stop()

        # Validate
        summary = metrics_collector.get_summary()

        # Check overall error rate
        total_ops = sum(
            summary["operations"][op]["percentiles"]["count"]
            for op in summary["operations"]
        )
        if total_ops > 0:
            overall_error_rate = (summary["total_errors"] / total_ops) * 100
            assert overall_error_rate < 5.0, (
                f"Overall error rate {overall_error_rate:.1f}% too high"
            )

    async def _collect_task_events(
        self,
        gateway,
        task_id: str,
        metrics: MetricsCollector,
    ):
        """Helper to collect events for a task."""
        try:
            events = await collect_task_events(
                gateway,
                task_id,
                overall_timeout=10.0,
                polling_interval=0.1,
            )

            for event in events:
                await metrics.increment_counter("mixed_a2a_events")
                if isinstance(event, (Task, JSONRPCError)):
                    await metrics.increment_counter("mixed_a2a_completed")
        except Exception:
            pass  # Ignore collection errors in fire-and-forget
