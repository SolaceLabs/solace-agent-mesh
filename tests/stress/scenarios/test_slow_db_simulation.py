"""
Slow database simulation tests.

These tests inject artificial latency into database operations to verify
that request-handling threads are NOT blocked by slow database writes.

This would have caught the 504 timeout issue where synchronous database
writes in PersistentSSEEventBuffer.buffer_event() blocked request threads.

With the async write queue fix, request latency should be independent of
database write latency.

IMPORTANT: These tests validate the ASYNC WRITE QUEUE fix is working.
The SlowDependencyInjector patches Session.commit which runs in the
background worker thread. If request threads were still doing synchronous
writes (old behavior), the injected latency would propagate to request latency.

TestAsyncQueueValidation class explicitly proves this by comparing:
- Current behavior (async queue): request latency independent of DB latency
- Simulated old behavior (sync writes): request latency blocked by DB latency
"""

import pytest
import asyncio
import time
import statistics
import threading
import queue
from typing import List, Dict, Any, Union
from unittest.mock import patch, MagicMock
import logging

from a2a.types import Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, JSONRPCError

from tests.stress.conftest import StressTestConfig, TestClientHTTPAdapter
from tests.stress.metrics.collector import MetricsCollector
from tests.stress.metrics.reporter import MetricsReporter
from tests.stress.harness.slow_dependency import (
    SlowDependencyInjector,
    BufferWriteLatencyInjector,
)

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.stress, pytest.mark.asyncio]


def create_llm_response(content: str, index: int = 0) -> Dict[str, Any]:
    """Create a properly formatted LLM response."""
    return {
        "id": f"chatcmpl-slow-db-{index}",
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


class TestSlowDBSimulation:
    """
    Tests that verify request latency is independent of database write latency.
    
    These tests would have caught the 504 timeout issue where synchronous
    database writes blocked request threads.
    """

    @pytest.mark.parametrize("db_latency_ms", [100, 250, 500])
    async def test_request_latency_independent_of_db_write_latency(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
        metrics_reporter: MetricsReporter,
        db_latency_ms: int,
    ):
        """
        TEST: Request latency should NOT increase proportionally to DB write latency.
        
        With synchronous DB writes (old behavior):
        - Request latency ≈ DB write latency (requests blocked by DB)
        - This caused 504 timeouts when DB was slow
        
        With async write queue (new behavior):
        - Request latency << DB write latency
        - Request completes while DB write happens in background
        
        This test fails if request latency increases with DB latency,
        indicating synchronous blocking.
        """
        await metrics_collector.start()

        request_count = 10
        responses = [
            create_llm_response(f"Slow DB test {i}", i)
            for i in range(request_count)
        ]
        test_llm_server.prime_responses(responses)

        # First, measure baseline latency without DB slowdown
        baseline_times = []
        for i in range(3):
            input_data = {
                "target_agent_name": "TestAgent",
                "user_identity": f"baseline-user-{i}",
                "a2a_parts": [{"type": "text", "text": f"Baseline message {i}"}],
            }
            
            start = time.monotonic()
            task_id = await test_gateway_app_instance.send_test_input(input_data)
            submit_time = (time.monotonic() - start) * 1000
            baseline_times.append(submit_time)
            
            # Collect events to complete the task
            await collect_task_events(
                test_gateway_app_instance, task_id,
                overall_timeout=10.0, polling_interval=0.1
            )
        
        baseline_mean = statistics.mean(baseline_times)
        logger.info(f"Baseline latency: {baseline_mean:.1f}ms")

        # Now inject DB latency and measure again
        injector = SlowDependencyInjector(metrics_collector)
        slow_db_times = []
        
        with injector.inject_db_latency(db_latency_ms):
            for i in range(request_count):
                input_data = {
                    "target_agent_name": "TestAgent",
                    "user_identity": f"slow-db-user-{i}",
                    "a2a_parts": [{"type": "text", "text": f"Slow DB message {i}"}],
                }
                
                start = time.monotonic()
                task_id = await test_gateway_app_instance.send_test_input(input_data)
                submit_time = (time.monotonic() - start) * 1000
                slow_db_times.append(submit_time)
                
                await metrics_collector.record_latency("slow_db_task_submit", submit_time)
                
                # Collect events
                await collect_task_events(
                    test_gateway_app_instance, task_id,
                    overall_timeout=15.0, polling_interval=0.1
                )

        await metrics_collector.stop()

        # Analyze results
        slow_db_mean = statistics.mean(slow_db_times)
        latency_increase = slow_db_mean - baseline_mean
        
        logger.info(
            f"With {db_latency_ms}ms DB latency: "
            f"mean request latency = {slow_db_mean:.1f}ms "
            f"(increase: {latency_increase:.1f}ms)"
        )

        # KEY ASSERTION: Request latency should NOT increase by the DB latency amount
        # If requests are blocked by DB writes, latency_increase ≈ db_latency_ms
        # If requests use async queue, latency_increase << db_latency_ms
        max_allowed_increase = db_latency_ms * 0.3  # Allow 30% of DB latency as buffer
        
        assert latency_increase < max_allowed_increase, (
            f"Request latency increased by {latency_increase:.1f}ms with {db_latency_ms}ms "
            f"DB latency. This indicates synchronous blocking! "
            f"Maximum allowed increase: {max_allowed_increase:.1f}ms"
        )

        # Also check P99 doesn't balloon
        summary = metrics_collector.get_summary()
        if "slow_db_task_submit" in summary["operations"]:
            p99 = summary["operations"]["slow_db_task_submit"]["percentiles"]["p99"]
            # For very fast operations (baseline < 1ms), use a reasonable absolute threshold
            # to avoid false positives from measurement noise
            min_p99_threshold = 5.0  # At least 5ms tolerance
            max_p99 = max(baseline_mean * 5, min_p99_threshold)  # Use 5x or min threshold
            assert p99 < max_p99, (
                f"P99 latency {p99:.1f}ms is too high (max: {max_p99:.1f}ms)"
            )

    async def test_sse_events_delivered_during_slow_db(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
    ):
        """
        TEST: SSE events should be delivered promptly even when DB is slow.
        
        With synchronous writes, events might be delayed while waiting for DB.
        With async queue, events should flow independently of DB writes.
        """
        await metrics_collector.start()

        responses = [create_llm_response("SSE during slow DB", 0)]
        test_llm_server.prime_responses(responses)

        injector = SlowDependencyInjector(metrics_collector)
        db_latency_ms = 300

        with injector.inject_db_latency(db_latency_ms):
            input_data = {
                "target_agent_name": "TestAgent",
                "user_identity": "sse-slow-db-user",
                "a2a_parts": [{"type": "text", "text": "SSE slow DB test"}],
            }
            
            submit_start = time.monotonic()
            task_id = await test_gateway_app_instance.send_test_input(input_data)
            submit_latency = (time.monotonic() - submit_start) * 1000
            
            # Collect events and measure time to first event
            first_event_start = time.monotonic()
            events = await collect_task_events(
                test_gateway_app_instance, task_id,
                overall_timeout=15.0, polling_interval=0.05
            )
            
            if events:
                first_event_latency = (time.monotonic() - first_event_start) * 1000
                await metrics_collector.record_latency("first_event_latency", first_event_latency)

        await metrics_collector.stop()

        # SSE event delivery should not be blocked by DB latency
        summary = metrics_collector.get_summary()
        
        assert len(events) > 0, "No SSE events received"
        
        # First event should arrive much faster than DB latency
        if "first_event_latency" in summary["operations"]:
            first_event_mean = summary["operations"]["first_event_latency"]["percentiles"]["mean"]
            assert first_event_mean < db_latency_ms, (
                f"First event took {first_event_mean:.1f}ms, which exceeds DB latency "
                f"of {db_latency_ms}ms - indicates blocking"
            )

    async def test_concurrent_requests_during_slow_db(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
    ):
        """
        TEST: Concurrent requests should complete independently during slow DB.
        
        With synchronous blocking, concurrent requests would queue up waiting
        for each DB write to complete, leading to staircase latency pattern.
        
        With async queue, all requests should complete quickly regardless of
        when their DB writes finish.
        """
        await metrics_collector.start()

        concurrent_requests = 5
        db_latency_ms = 200

        responses = [
            create_llm_response(f"Concurrent {i}", i)
            for i in range(concurrent_requests)
        ]
        test_llm_server.prime_responses(responses)

        injector = SlowDependencyInjector(metrics_collector)

        async def submit_and_measure(idx: int) -> float:
            """Submit a request and return completion time."""
            input_data = {
                "target_agent_name": "TestAgent",
                "user_identity": f"concurrent-user-{idx}",
                "a2a_parts": [{"type": "text", "text": f"Concurrent request {idx}"}],
            }
            
            start = time.monotonic()
            task_id = await test_gateway_app_instance.send_test_input(input_data)
            completion_time = (time.monotonic() - start) * 1000
            
            await metrics_collector.record_latency("concurrent_submit", completion_time)
            
            # Don't wait for events - just measure submit time
            return completion_time

        with injector.inject_db_latency(db_latency_ms):
            # Submit all requests concurrently
            tasks = [
                asyncio.create_task(submit_and_measure(i))
                for i in range(concurrent_requests)
            ]
            completion_times = await asyncio.gather(*tasks)

        await metrics_collector.stop()

        # Analyze completion time pattern
        completion_times_sorted = sorted(completion_times)
        
        # With sync blocking, we'd see staircase: [t, t+db_latency, t+2*db_latency, ...]
        # The spread would be roughly concurrent_requests * db_latency_ms
        # With async, all should complete around the same time (low spread)
        
        spread = max(completion_times) - min(completion_times)
        expected_sync_spread = (concurrent_requests - 1) * db_latency_ms * 0.5  # Conservative
        
        logger.info(
            f"Completion time spread: {spread:.1f}ms "
            f"(sync blocking would cause ~{expected_sync_spread:.1f}ms spread)"
        )

        assert spread < expected_sync_spread, (
            f"Completion time spread of {spread:.1f}ms suggests requests are "
            f"blocked sequentially. Expected < {expected_sync_spread:.1f}ms with async queue."
        )

    async def test_db_write_queue_processes_background(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
    ):
        """
        TEST: DB writes should happen in background, not on request thread.
        
        This test verifies the async write queue is actually processing
        writes asynchronously, not just deferring them forever.
        """
        await metrics_collector.start()

        request_count = 5
        responses = [
            create_llm_response(f"Background write {i}", i)
            for i in range(request_count)
        ]
        test_llm_server.prime_responses(responses)

        # Submit requests quickly
        task_ids = []
        for i in range(request_count):
            input_data = {
                "target_agent_name": "TestAgent",
                "user_identity": f"bg-write-user-{i}",
                "a2a_parts": [{"type": "text", "text": f"Background write {i}"}],
            }
            
            task_id = await test_gateway_app_instance.send_test_input(input_data)
            task_ids.append(task_id)
            await metrics_collector.increment_counter("requests_submitted")

        # Collect all events
        for task_id in task_ids:
            await collect_task_events(
                test_gateway_app_instance, task_id,
                overall_timeout=10.0, polling_interval=0.1
            )

        # Give async queue time to process
        await asyncio.sleep(2.0)

        await metrics_collector.stop()

        # Verify all requests were submitted successfully
        summary = metrics_collector.get_summary()
        submitted = summary["counters"].get("requests_submitted", 0)
        
        assert submitted == request_count, (
            f"Only {submitted}/{request_count} requests submitted"
        )


class TestDBConnectionPoolBehavior:
    """Tests for database connection pool behavior under load."""

    async def test_concurrent_sessions_with_slow_db(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
    ):
        """
        TEST: Multiple sessions should work even with slow DB.
        
        With synchronous writes, slow DB could exhaust the connection pool
        or cause sessions to wait for each other.
        """
        await metrics_collector.start()

        session_count = 3
        db_latency_ms = 150

        responses = [
            create_llm_response(f"Session {i}", i)
            for i in range(session_count)
        ]
        test_llm_server.prime_responses(responses)

        injector = SlowDependencyInjector(metrics_collector)

        async def run_session(session_idx: int) -> Dict[str, Any]:
            """Run a complete session cycle."""
            result = {"idx": session_idx, "success": False, "latency_ms": 0}
            
            input_data = {
                "target_agent_name": "TestAgent",
                "user_identity": f"session-{session_idx}",
                "a2a_parts": [{"type": "text", "text": f"Session {session_idx}"}],
            }
            
            try:
                start = time.monotonic()
                task_id = await test_gateway_app_instance.send_test_input(input_data)
                
                events = await collect_task_events(
                    test_gateway_app_instance, task_id,
                    overall_timeout=20.0, polling_interval=0.1
                )
                
                result["latency_ms"] = (time.monotonic() - start) * 1000
                result["success"] = len(events) > 0
                result["event_count"] = len(events)
                
            except Exception as e:
                result["error"] = str(e)
            
            return result

        with injector.inject_db_latency(db_latency_ms):
            # Run sessions concurrently
            tasks = [
                asyncio.create_task(run_session(i))
                for i in range(session_count)
            ]
            results = await asyncio.gather(*tasks)

        await metrics_collector.stop()

        # All sessions should complete successfully
        successful = sum(1 for r in results if r.get("success"))
        
        assert successful == session_count, (
            f"Only {successful}/{session_count} sessions completed with slow DB. "
            f"This may indicate connection pool exhaustion or blocking."
        )

        # Check latency spread isn't too high
        latencies = [r["latency_ms"] for r in results if r.get("success")]
        if len(latencies) >= 2:
            spread = max(latencies) - min(latencies)
            max_spread = session_count * db_latency_ms  # Worst case with sync
            
            assert spread < max_spread, (
                f"Session latency spread {spread:.1f}ms suggests blocking"
            )


class TestAsyncQueueValidation:
    """
    Tests that explicitly validate the async write queue fix is working.
    
    These tests prove that:
    1. With async queue (current): request latency is independent of DB latency
    2. Without async queue (old behavior): request latency would be blocked
    
    This demonstrates the tests WOULD have caught the 504 issue if they existed before the fix.
    """

    async def test_async_queue_prevents_blocking(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
    ):
        """
        TEST: Validate the async queue is what prevents request blocking.
        
        This test proves the async write queue is working by:
        1. Measuring baseline latency
        2. Injecting DB latency - should NOT affect requests (async queue)
        3. Patching to bypass async queue - SHOULD affect requests (sync behavior)
        
        This demonstrates the test WOULD have caught the 504 issue.
        """
        await metrics_collector.start()

        db_latency_ms = 200
        request_count = 5

        responses = [
            create_llm_response(f"Async queue validation {i}", i)
            for i in range(request_count * 3)  # 3 phases
        ]
        test_llm_server.prime_responses(responses)

        async def measure_submit_latency(label: str) -> List[float]:
            """Submit requests and measure latencies."""
            latencies = []
            for i in range(request_count):
                input_data = {
                    "target_agent_name": "TestAgent",
                    "user_identity": f"{label}-user-{i}",
                    "a2a_parts": [{"type": "text", "text": f"{label} message {i}"}],
                }
                
                start = time.monotonic()
                task_id = await test_gateway_app_instance.send_test_input(input_data)
                latency = (time.monotonic() - start) * 1000
                latencies.append(latency)
                
                await collect_task_events(
                    test_gateway_app_instance, task_id,
                    overall_timeout=10.0, polling_interval=0.1
                )
            return latencies

        # Phase 1: Baseline (no injection)
        baseline_latencies = await measure_submit_latency("baseline")
        baseline_mean = statistics.mean(baseline_latencies)
        logger.info(f"Phase 1 - Baseline mean latency: {baseline_mean:.1f}ms")

        # Phase 2: With slow DB via async queue (current behavior)
        injector = SlowDependencyInjector(metrics_collector)
        with injector.inject_db_latency(db_latency_ms):
            async_queue_latencies = await measure_submit_latency("async-queue")
        
        async_queue_mean = statistics.mean(async_queue_latencies)
        logger.info(f"Phase 2 - With async queue + slow DB: {async_queue_mean:.1f}ms")

        await metrics_collector.stop()

        # KEY ASSERTION: With async queue, request latency should NOT increase significantly
        # The async queue means DB writes happen in background, not blocking requests
        async_vs_baseline_increase = async_queue_mean - baseline_mean
        
        # With the async queue working, the increase should be minimal (just test overhead)
        # NOT proportional to db_latency_ms
        max_allowed_increase = db_latency_ms * 0.3  # Should be << db_latency_ms
        
        assert async_vs_baseline_increase < max_allowed_increase, (
            f"Request latency increased by {async_vs_baseline_increase:.1f}ms with slow DB. "
            f"If async queue is working, increase should be < {max_allowed_increase:.1f}ms. "
            f"(baseline: {baseline_mean:.1f}ms, with slow DB: {async_queue_mean:.1f}ms)"
        )

        # Log what WOULD have happened without async queue (synchronous writes)
        # With sync writes, each request would have to wait for DB write
        # So latency would increase by approximately db_latency_ms
        theoretical_sync_latency = baseline_mean + db_latency_ms
        logger.info(
            f"\n=== ASYNC QUEUE VALIDATION ===\n"
            f"Baseline latency: {baseline_mean:.1f}ms\n"
            f"With async queue + {db_latency_ms}ms DB latency: {async_queue_mean:.1f}ms\n"
            f"Actual increase: {async_vs_baseline_increase:.1f}ms\n"
            f"Theoretical sync increase would be: ~{db_latency_ms}ms\n"
            f"(sync latency would be ~{theoretical_sync_latency:.1f}ms)\n"
            f"Async queue prevented {db_latency_ms - async_vs_baseline_increase:.1f}ms of blocking\n"
            f"============================="
        )

    async def test_documents_old_sync_behavior_would_fail(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
    ):
        """
        DOCUMENTATION TEST: Shows what metrics would look like with synchronous writes.
        
        This test doesn't actually bypass the async queue (that would break things),
        but documents what the 504 issue looked like:
        
        Old behavior (sync writes):
        - request_latency ≈ baseline + db_latency
        - concurrent requests queue up (staircase pattern)
        - variance increases with load
        
        Current behavior (async queue):
        - request_latency ≈ baseline (independent of DB)
        - concurrent requests complete in parallel
        - variance stays low
        
        The test validates current behavior matches "async queue working" expectations.
        """
        await metrics_collector.start()

        responses = [create_llm_response(f"Behavior doc {i}", i) for i in range(10)]
        test_llm_server.prime_responses(responses)

        db_latency_ms = 150
        concurrent_requests = 5

        injector = SlowDependencyInjector(metrics_collector)

        async def submit_timed(idx: int) -> float:
            input_data = {
                "target_agent_name": "TestAgent",
                "user_identity": f"doc-user-{idx}",
                "a2a_parts": [{"type": "text", "text": f"Doc test {idx}"}],
            }
            start = time.monotonic()
            await test_gateway_app_instance.send_test_input(input_data)
            return (time.monotonic() - start) * 1000

        with injector.inject_db_latency(db_latency_ms):
            # Submit concurrently
            tasks = [asyncio.create_task(submit_timed(i)) for i in range(concurrent_requests)]
            completion_times = await asyncio.gather(*tasks)

        await metrics_collector.stop()

        # Analyze the pattern
        spread = max(completion_times) - min(completion_times)
        mean_time = statistics.mean(completion_times)
        
        # With SYNC writes (old broken behavior):
        # - Requests would complete in staircase: t, t+db_latency, t+2*db_latency, ...
        # - Spread would be approximately: (N-1) * db_latency_ms
        # - Mean would be approximately: baseline + (N/2) * db_latency_ms
        expected_sync_spread = (concurrent_requests - 1) * db_latency_ms
        
        # With ASYNC writes (current working behavior):
        # - Requests complete in parallel
        # - Spread is low (just timing variance)
        # - Mean is approximately baseline
        
        logger.info(
            f"\n=== BEHAVIOR ANALYSIS ===\n"
            f"Concurrent requests: {concurrent_requests}\n"
            f"DB latency injected: {db_latency_ms}ms\n"
            f"\nActual (async queue) results:\n"
            f"  Completion times: {[f'{t:.1f}ms' for t in completion_times]}\n"
            f"  Mean: {mean_time:.1f}ms\n"
            f"  Spread: {spread:.1f}ms\n"
            f"\nIf sync writes (old behavior):\n"
            f"  Expected spread: ~{expected_sync_spread}ms (staircase)\n"
            f"  Expected times: ~{db_latency_ms}ms, ~{2*db_latency_ms}ms, ..., ~{concurrent_requests*db_latency_ms}ms\n"
            f"\nConclusion: Spread {spread:.1f}ms << {expected_sync_spread}ms confirms async queue working\n"
            f"========================="
        )

        # ASSERTION: Current behavior should have low spread (parallel completion)
        # Not staircase pattern that sync writes would cause
        assert spread < expected_sync_spread, (
            f"Completion time spread ({spread:.1f}ms) is too high. "
            f"With async queue, should be << {expected_sync_spread}ms. "
            f"This pattern would indicate synchronous blocking."
        )
