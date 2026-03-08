"""
Test concurrent SSE connections under load.

Stresses the SSEManager's single threading.Lock bottleneck and validates
that multiple concurrent connections can receive events without issues.
"""

import pytest
import asyncio
import time
from typing import List, Dict, Any, Union

from a2a.types import Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, JSONRPCError

from tests.stress.conftest import StressTestConfig, TestClientHTTPAdapter
from tests.stress.metrics.collector import MetricsCollector
from tests.stress.metrics.reporter import MetricsReporter

pytestmark = [pytest.mark.stress, pytest.mark.asyncio]


def create_llm_response(content: str, index: int = 0) -> Dict[str, Any]:
    """Create a properly formatted LLM response."""
    return {
        "id": f"chatcmpl-stress-{index}",
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
    """
    Collect all events for a task using integration test patterns.

    Polls for events until a terminal event (Task or JSONRPCError) is received
    or overall_timeout is reached.
    """
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


class TestConcurrentSSEConnections:
    """Test SSE manager under concurrent connection load."""

    @pytest.mark.parametrize("connection_count", [5, 10, 25])
    async def test_concurrent_sse_connections(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
        metrics_reporter: MetricsReporter,
        connection_count: int,
    ):
        """
        Test N concurrent SSE connections receiving events simultaneously.

        Validates:
        - All connections establish successfully
        - Events are delivered to all connections
        - No connection timeouts under load
        - Queue put() 0.1s timeout doesn't cause failures
        """
        await metrics_collector.start()

        # Prime LLM server with properly formatted responses for each connection
        responses = [
            create_llm_response(f"Response for connection {i}", i)
            for i in range(connection_count)
        ]
        test_llm_server.prime_responses(responses)

        # Create test inputs for each connection
        task_ids = []
        for i in range(connection_count):
            input_data = {
                "target_agent_name": "TestAgent",
                "user_identity": f"stress-user-{i}",
                "a2a_parts": [{"type": "text", "text": f"Stress test message {i}"}],
                "external_context_override": {"test_case": f"concurrent_sse_{i}"},
            }

            start_time = time.monotonic()
            task_id = await test_gateway_app_instance.send_test_input(input_data)
            submit_latency = (time.monotonic() - start_time) * 1000
            await metrics_collector.record_latency("task_submit", submit_latency)

            task_ids.append(task_id)
            await metrics_collector.increment_counter("tasks_submitted")

        # Collect responses concurrently using proven integration test pattern
        async def collect_events_with_metrics(task_id: str, idx: int) -> List[Any]:
            """Collect all events for a task with metrics."""
            start_time = time.monotonic()

            try:
                # Use short polling interval (10s overall timeout per task)
                events = await collect_task_events(
                    test_gateway_app_instance,
                    task_id,
                    overall_timeout=15.0,
                    polling_interval=0.1,
                )

                # Record metrics for events
                for event in events:
                    event_latency = (time.monotonic() - start_time) * 1000
                    await metrics_collector.record_latency("event_received", event_latency)
                    await metrics_collector.increment_counter("events_received")

                    if isinstance(event, (Task, JSONRPCError)):
                        await metrics_collector.increment_counter("terminal_events")

                return events

            except Exception as e:
                await metrics_collector.record_error(
                    "event_collection",
                    e,
                    {"task_id": task_id, "idx": idx},
                )
                return []

        # Run event collection concurrently
        tasks = [
            asyncio.create_task(collect_events_with_metrics(task_id, idx))
            for idx, task_id in enumerate(task_ids)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        await metrics_collector.stop()

        # Analyze results
        successful = sum(1 for r in results if isinstance(r, list) and len(r) > 0)
        errors = sum(1 for r in results if isinstance(r, Exception))

        await metrics_collector.set_gauge("successful_connections", successful)
        await metrics_collector.set_gauge("failed_connections", errors)

        # Validate
        success_rate = successful / connection_count * 100
        assert success_rate >= 95, f"Success rate {success_rate:.1f}% below 95%"

        summary = metrics_collector.get_summary()
        if "task_submit" in summary["operations"]:
            p99 = summary["operations"]["task_submit"]["percentiles"]["p99"]
            assert p99 < stress_config.max_p99_latency_ms, (
                f"Task submit p99 latency {p99:.1f}ms exceeds threshold "
                f"{stress_config.max_p99_latency_ms}ms"
            )

    async def test_sse_connection_churn(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
    ):
        """
        Test rapid connection/disconnection cycles.

        Validates:
        - SSEManager handles rapid churn without resource leaks
        - No deadlocks from lock contention
        """
        await metrics_collector.start()

        # Scale churn cycles based on config (e.g., smoke=6, small=15, medium=50)
        churn_cycles = stress_config.concurrent_sse_connections * 2

        # Prime enough responses with proper format
        responses = [
            create_llm_response(f"Churn {i}", i)
            for i in range(churn_cycles)
        ]
        test_llm_server.prime_responses(responses)

        async def connect_disconnect_cycle(cycle_id: int):
            """Connect, receive one event, disconnect."""
            start_time = time.monotonic()

            input_data = {
                "target_agent_name": "TestAgent",
                "user_identity": f"churn-user-{cycle_id}",
                "a2a_parts": [{"type": "text", "text": f"Churn message {cycle_id}"}],
            }

            try:
                task_id = await test_gateway_app_instance.send_test_input(input_data)
                connect_latency = (time.monotonic() - start_time) * 1000
                await metrics_collector.record_latency("churn_connect", connect_latency)

                # Get just one event then "disconnect" - use short polling interval
                events = await collect_task_events(
                    test_gateway_app_instance,
                    task_id,
                    overall_timeout=10.0,
                    polling_interval=0.1,
                )

                if events:
                    await metrics_collector.increment_counter("churn_events_received")

                await metrics_collector.increment_counter("churn_cycles_completed")

            except Exception as e:
                await metrics_collector.record_error(
                    "churn_cycle",
                    e,
                    {"cycle_id": cycle_id},
                )

        # Run churn cycles with some concurrency
        batch_size = stress_config.concurrent_sse_connections
        for batch_start in range(0, churn_cycles, batch_size):
            batch_end = min(batch_start + batch_size, churn_cycles)
            tasks = [
                asyncio.create_task(connect_disconnect_cycle(i))
                for i in range(batch_start, batch_end)
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(0.05)  # Brief pause between batches

        await metrics_collector.stop()

        # Validate
        summary = metrics_collector.get_summary()
        completed = summary["counters"].get("churn_cycles_completed", 0)
        total_errors = summary["total_errors"]

        assert completed >= churn_cycles * 0.9, (
            f"Only {completed}/{churn_cycles} cycles completed"
        )
        assert total_errors < churn_cycles * 0.1, (
            f"Too many errors: {total_errors}/{churn_cycles}"
        )

    async def test_concurrent_task_submission_burst(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
    ):
        """
        Test burst of concurrent task submissions.

        Validates:
        - Gateway handles burst of simultaneous task submissions
        - All tasks get unique task IDs
        - No race conditions in task creation
        """
        await metrics_collector.start()

        burst_size = stress_config.concurrent_sse_connections

        # Prime responses with proper format
        responses = [
            create_llm_response(f"Burst {i}", i)
            for i in range(burst_size)
        ]
        test_llm_server.prime_responses(responses)

        async def submit_task(idx: int) -> str:
            """Submit a single task and return task_id."""
            input_data = {
                "target_agent_name": "TestAgent",
                "user_identity": f"burst-user-{idx}",
                "a2a_parts": [{"type": "text", "text": f"Burst message {idx}"}],
            }

            start_time = time.monotonic()
            task_id = await test_gateway_app_instance.send_test_input(input_data)
            latency = (time.monotonic() - start_time) * 1000

            await metrics_collector.record_latency("burst_submit", latency)
            return task_id

        # Submit all tasks concurrently
        tasks = [asyncio.create_task(submit_task(i)) for i in range(burst_size)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        await metrics_collector.stop()

        # Analyze
        task_ids = [r for r in results if isinstance(r, str)]
        errors = [r for r in results if isinstance(r, Exception)]

        # Validate uniqueness
        unique_ids = set(task_ids)
        assert len(unique_ids) == len(task_ids), "Duplicate task IDs detected!"

        # Validate success rate
        success_rate = len(task_ids) / burst_size * 100
        assert success_rate >= 95, f"Success rate {success_rate:.1f}% below 95%"

        # Validate latency
        summary = metrics_collector.get_summary()
        if "burst_submit" in summary["operations"]:
            p99 = summary["operations"]["burst_submit"]["percentiles"]["p99"]
            # Allow higher latency for burst since it's concurrent
            assert p99 < stress_config.max_p99_latency_ms * 2, (
                f"Burst submit p99 {p99:.1f}ms too high"
            )
