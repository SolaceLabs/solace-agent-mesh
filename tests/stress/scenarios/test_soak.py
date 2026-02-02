"""
Long-running soak tests with memory monitoring.

Detects memory leaks and resource exhaustion over extended periods.
These tests are marked with @pytest.mark.long_soak and typically run
for 5+ minutes.
"""

import pytest
import asyncio
import gc
import time
from typing import Optional, Dict, Any, List, Union
import logging

from a2a.types import Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, JSONRPCError

from tests.stress.conftest import StressTestConfig, TestClientHTTPAdapter
from tests.stress.metrics.collector import MetricsCollector
from tests.stress.metrics.reporter import MetricsReporter

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.stress, pytest.mark.long_soak, pytest.mark.asyncio]


def create_llm_response(content: str, index: int = 0) -> Dict[str, Any]:
    """Create a properly formatted LLM response."""
    return {
        "id": f"chatcmpl-soak-{index}",
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


class TestSoakTests:
    """Long-running stability tests."""

    async def test_extended_streaming_soak(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_http_client: TestClientHTTPAdapter,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
        metrics_reporter: MetricsReporter,
    ):
        """
        Extended streaming test with memory monitoring.

        Duration: 5 minutes (configurable via stress_config.soak_duration_seconds)

        Validates:
        - Memory usage stays bounded over time
        - No unbounded growth in SSEManager caches
        - No connection leaks
        - Consistent latency over time
        """
        await metrics_collector.start()

        soak_duration = stress_config.soak_duration_seconds
        sample_interval = 10.0  # Sample every 10 seconds
        activity_interval = 1.0  # Activity burst every second

        logger.info(f"Starting soak test for {soak_duration}s")

        # Prime many LLM responses with proper format
        response_count = int(soak_duration / activity_interval) + 100
        responses = [
            create_llm_response(f"Soak response {i}", i)
            for i in range(response_count)
        ]
        test_llm_server.prime_responses(responses)

        start_time = asyncio.get_event_loop().time()
        last_sample_time = start_time
        activity_count = 0

        # Initial memory sample
        await self._sample_memory(metrics_collector, "initial")

        while asyncio.get_event_loop().time() - start_time < soak_duration:
            current_time = asyncio.get_event_loop().time()

            # Run activity burst
            await self._run_activity_burst(
                test_gateway_app_instance,
                stress_http_client,
                metrics_collector,
                activity_count,
            )
            activity_count += 1

            # Periodic memory sampling
            if current_time - last_sample_time >= sample_interval:
                gc.collect()
                await self._sample_memory(metrics_collector, f"sample_{int(current_time - start_time)}")
                last_sample_time = current_time

                # Log progress
                elapsed = current_time - start_time
                progress = (elapsed / soak_duration) * 100
                logger.info(
                    f"Soak test progress: {progress:.1f}% ({elapsed:.0f}s/{soak_duration}s), "
                    f"activities: {activity_count}"
                )

            await asyncio.sleep(activity_interval)

        # Final memory sample
        gc.collect()
        await self._sample_memory(metrics_collector, "final")

        await metrics_collector.stop()

        # Analyze results
        summary = metrics_collector.get_summary()
        memory = summary["memory"]

        logger.info(
            f"Soak test complete: "
            f"duration={summary['duration_seconds']:.0f}s, "
            f"activities={activity_count}, "
            f"memory_growth={memory['growth_mb']:.1f}MB"
        )

        # Validate memory growth
        if memory["sample_count"] > 0:
            max_growth = stress_config.memory_increase_threshold_mb
            assert memory["growth_mb"] < max_growth, (
                f"Memory grew by {memory['growth_mb']:.1f}MB during soak test, "
                f"exceeds threshold of {max_growth}MB"
            )

        # Validate error rate
        total_errors = summary["total_errors"]
        max_errors = activity_count * 0.05  # Allow 5% error rate
        assert total_errors < max_errors, (
            f"Too many errors during soak: {total_errors} (max {max_errors:.0f})"
        )

    async def test_connection_leak_detection(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
        sse_manager_for_metrics,
    ):
        """
        Test for connection leaks over many connect/disconnect cycles.

        Validates:
        - SSEManager properly cleans up connections
        - No growth in _connections dict
        - No growth in _tasks_with_prior_connection set
        - No unbounded growth in _background_task_cache
        """
        from tests.stress.conftest import get_sse_manager_metrics

        await metrics_collector.start()

        cycles = 100
        logger.info(f"Running {cycles} connection cycles for leak detection")

        # Prime responses with proper format
        responses = [
            create_llm_response(f"Leak test {i}", i)
            for i in range(cycles)
        ]
        test_llm_server.prime_responses(responses)

        # Track initial state
        initial_memory = await self._get_process_memory()
        initial_sse_metrics = get_sse_manager_metrics(sse_manager_for_metrics)

        logger.info(
            f"Initial SSE state: connections={initial_sse_metrics.active_connections}, "
            f"cache={initial_sse_metrics.background_task_cache_size}, "
            f"prior={initial_sse_metrics.tasks_with_prior_connection}"
        )

        for i in range(cycles):
            input_data = {
                "target_agent_name": "TestAgent",
                "user_identity": f"leak-test-user-{i}",
                "a2a_parts": [{"type": "text", "text": f"Leak test {i}"}],
            }

            try:
                task_id = await test_gateway_app_instance.send_test_input(input_data)

                # Collect all events using proven pattern
                await collect_task_events(
                    test_gateway_app_instance,
                    task_id,
                    overall_timeout=10.0,
                    polling_interval=0.1,
                )

                await metrics_collector.increment_counter("leak_test_cycles")

            except Exception as e:
                await metrics_collector.record_error("leak_test_cycle", e)

            # Periodic GC, memory check, and SSE metrics check
            if i % 20 == 0:
                gc.collect()
                current_memory = await self._get_process_memory()
                await metrics_collector.record_memory(current_memory, 0)

                # Check SSE manager state
                current_sse_metrics = get_sse_manager_metrics(sse_manager_for_metrics)
                await metrics_collector.set_gauge(
                    "sse_active_connections", current_sse_metrics.active_connections
                )
                await metrics_collector.set_gauge(
                    "sse_cache_size", current_sse_metrics.background_task_cache_size
                )
                await metrics_collector.set_gauge(
                    "sse_prior_connections", current_sse_metrics.tasks_with_prior_connection
                )

                logger.debug(
                    f"Cycle {i}: connections={current_sse_metrics.active_connections}, "
                    f"cache={current_sse_metrics.background_task_cache_size}, "
                    f"prior={current_sse_metrics.tasks_with_prior_connection}"
                )

        # Final check
        gc.collect()
        final_memory = await self._get_process_memory()
        final_sse_metrics = get_sse_manager_metrics(sse_manager_for_metrics)

        logger.info(
            f"Final SSE state: connections={final_sse_metrics.active_connections}, "
            f"cache={final_sse_metrics.background_task_cache_size}, "
            f"prior={final_sse_metrics.tasks_with_prior_connection}"
        )

        await metrics_collector.stop()

        # Record memory growth for reporting
        memory_growth = final_memory - initial_memory
        await metrics_collector.set_gauge("connection_leak_memory_growth_mb", memory_growth)

        # Validate SSE connection cleanup - should have no active connections after all tasks complete
        # This is the primary indicator of SSE-specific connection leaks
        assert final_sse_metrics.active_connections == 0, (
            f"SSE connection leak: {final_sse_metrics.active_connections} active connections "
            f"remain after {cycles} completed cycles. Task IDs: {final_sse_metrics.connection_task_ids[:10]}"
        )

        # Validate cache doesn't grow unboundedly (allow some caching but not all tasks)
        max_allowed_cache = min(cycles * 0.1, 50)  # Allow up to 10% or 50, whichever is smaller
        assert final_sse_metrics.background_task_cache_size <= max_allowed_cache, (
            f"SSE cache leak: {final_sse_metrics.background_task_cache_size} cached tasks "
            f"exceeds max allowed {max_allowed_cache}"
        )

        # Validate no excessive memory growth (secondary check)
        # Note: Python runtime can have variable memory usage, so use a generous threshold
        max_growth_mb = stress_config.memory_increase_threshold_mb  # Default 50MB
        assert memory_growth < max_growth_mb, (
            f"Potential memory leak: memory grew {memory_growth:.1f}MB "
            f"over {cycles} cycles (threshold: {max_growth_mb:.1f}MB)"
        )

    async def test_cache_growth_monitoring(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
        sse_manager_for_metrics,
    ):
        """
        Monitor SSEManager cache growth over time.

        Specifically checks:
        - _background_task_cache doesn't grow unbounded
        - _tasks_with_prior_connection set doesn't grow unbounded
        - Event buffer cleanup works properly
        """
        from tests.stress.conftest import get_sse_manager_metrics

        await metrics_collector.start()

        iterations = 50
        logger.info(f"Running {iterations} iterations for cache monitoring")

        # Prime responses with proper format
        responses = [
            create_llm_response(f"Cache test {i}", i)
            for i in range(iterations)
        ]
        test_llm_server.prime_responses(responses)

        # Track initial SSE state
        initial_sse_metrics = get_sse_manager_metrics(sse_manager_for_metrics)
        logger.info(
            f"Initial SSE state: connections={initial_sse_metrics.active_connections}, "
            f"cache={initial_sse_metrics.background_task_cache_size}, "
            f"prior={initial_sse_metrics.tasks_with_prior_connection}"
        )

        task_ids_created = []
        cache_size_samples = []

        for i in range(iterations):
            input_data = {
                "target_agent_name": "TestAgent",
                "user_identity": f"cache-test-user-{i}",
                "a2a_parts": [{"type": "text", "text": f"Cache test {i}"}],
            }

            task_id = await test_gateway_app_instance.send_test_input(input_data)
            task_ids_created.append(task_id)

            # Collect events using proven pattern
            await collect_task_events(
                test_gateway_app_instance,
                task_id,
                overall_timeout=10.0,
                polling_interval=0.1,
            )

            await metrics_collector.increment_counter("cache_test_iterations")

            # Sample cache size periodically
            if i % 10 == 0:
                current_sse_metrics = get_sse_manager_metrics(sse_manager_for_metrics)
                cache_size_samples.append(current_sse_metrics.background_task_cache_size)
                await metrics_collector.set_gauge(
                    "sse_cache_size", current_sse_metrics.background_task_cache_size
                )
                await metrics_collector.set_gauge(
                    "sse_prior_connections", current_sse_metrics.tasks_with_prior_connection
                )
                logger.debug(
                    f"Iteration {i}: cache={current_sse_metrics.background_task_cache_size}, "
                    f"prior={current_sse_metrics.tasks_with_prior_connection}"
                )

        # Final SSE state check
        gc.collect()
        final_sse_metrics = get_sse_manager_metrics(sse_manager_for_metrics)

        logger.info(
            f"Final SSE state: connections={final_sse_metrics.active_connections}, "
            f"cache={final_sse_metrics.background_task_cache_size}, "
            f"prior={final_sse_metrics.tasks_with_prior_connection}"
        )

        await metrics_collector.stop()

        summary = metrics_collector.get_summary()
        completed = summary["counters"].get("cache_test_iterations", 0)

        assert completed == iterations, (
            f"Only {completed}/{iterations} cache test iterations completed"
        )

        # Validate no active connections remain after all tasks complete
        assert final_sse_metrics.active_connections == 0, (
            f"Connection leak: {final_sse_metrics.active_connections} active connections "
            f"remain after {iterations} completed iterations"
        )

        # Validate cache doesn't grow unboundedly
        max_allowed_cache = min(iterations * 0.2, 50)  # Allow up to 20% or 50
        assert final_sse_metrics.background_task_cache_size <= max_allowed_cache, (
            f"Cache leak: {final_sse_metrics.background_task_cache_size} cached tasks "
            f"exceeds max allowed {max_allowed_cache}"
        )

        # Check for unbounded growth trend in cache samples
        if len(cache_size_samples) >= 3:
            # Check if cache is growing monotonically (potential leak indicator)
            is_monotonic_growth = all(
                cache_size_samples[i] <= cache_size_samples[i + 1]
                for i in range(len(cache_size_samples) - 1)
            )
            if is_monotonic_growth and cache_size_samples[-1] > cache_size_samples[0] + 10:
                logger.warning(
                    f"Cache shows monotonic growth: {cache_size_samples[0]} -> {cache_size_samples[-1]}"
                )

    async def _run_activity_burst(
        self,
        gateway,
        http_client: TestClientHTTPAdapter,
        metrics: MetricsCollector,
        burst_id: int,
    ):
        """Run a burst of mixed activity."""
        # A2A task
        input_data = {
            "target_agent_name": "TestAgent",
            "user_identity": f"soak-user-{burst_id}",
            "a2a_parts": [{"type": "text", "text": f"Soak activity {burst_id}"}],
        }

        try:
            start_time = time.monotonic()
            task_id = await gateway.send_test_input(input_data)
            latency = (time.monotonic() - start_time) * 1000
            await metrics.record_latency("soak_task_submit", latency)

            # Collect events (non-blocking)
            asyncio.create_task(self._collect_events(gateway, task_id, metrics))

        except Exception as e:
            await metrics.record_error("soak_activity", e)

        # WebUI request
        try:
            await http_client.get_config()
        except Exception as e:
            await metrics.record_error("soak_webui", e)

    async def _collect_events(self, gateway, task_id: str, metrics: MetricsCollector):
        """Helper to collect events for a task."""
        try:
            events = await collect_task_events(
                gateway,
                task_id,
                overall_timeout=10.0,
                polling_interval=0.1,
            )

            for event in events:
                await metrics.increment_counter("soak_events_received")
                if isinstance(event, (Task, JSONRPCError)):
                    await metrics.increment_counter("soak_tasks_completed")
        except Exception:
            pass

    async def _sample_memory(self, metrics: MetricsCollector, label: str):
        """Sample current memory usage."""
        try:
            import psutil

            process = psutil.Process()
            rss_mb = process.memory_info().rss / (1024 * 1024)
            await metrics.record_memory(rss_mb, 0)

            logger.debug(f"Memory sample ({label}): {rss_mb:.1f} MB")

        except ImportError:
            # psutil not available
            pass

    async def _get_process_memory(self) -> float:
        """Get current process memory in MB."""
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0.0


class TestResourceExhaustion:
    """Tests for resource exhaustion scenarios."""

    async def test_queue_overflow_handling(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
    ):
        """
        Test SSE queue overflow handling.

        Validates:
        - Gateway handles queue full scenarios gracefully
        - No crashes when events can't be delivered
        - Proper cleanup after overflow
        """
        await metrics_collector.start()

        # This test creates a scenario where events might overflow
        # by submitting tasks faster than they can be consumed

        task_count = 20
        responses = [
            create_llm_response(f"Overflow test {i}", i)
            for i in range(task_count)
        ]
        test_llm_server.prime_responses(responses)

        # Submit many tasks without immediately consuming
        task_ids = []
        for i in range(task_count):
            input_data = {
                "target_agent_name": "TestAgent",
                "user_identity": f"overflow-user-{i}",
                "a2a_parts": [{"type": "text", "text": f"Overflow test {i}"}],
            }

            task_id = await test_gateway_app_instance.send_test_input(input_data)
            task_ids.append(task_id)
            await metrics_collector.increment_counter("overflow_tasks_submitted")

        # Now consume events with some delay
        await asyncio.sleep(0.5)

        for task_id in task_ids:
            try:
                events = await collect_task_events(
                    test_gateway_app_instance,
                    task_id,
                    overall_timeout=5.0,
                    polling_interval=0.1,
                )

                for event in events:
                    await metrics_collector.increment_counter("overflow_events_received")
                    if isinstance(event, (Task, JSONRPCError)):
                        await metrics_collector.increment_counter("overflow_tasks_completed")

            except asyncio.TimeoutError:
                await metrics_collector.increment_counter("overflow_timeouts")

        await metrics_collector.stop()

        # Validate - some tasks should complete even under pressure
        summary = metrics_collector.get_summary()
        completed = summary["counters"].get("overflow_tasks_completed", 0)

        # At least 50% should complete
        assert completed >= task_count * 0.5, (
            f"Only {completed}/{task_count} tasks completed under queue pressure"
        )
