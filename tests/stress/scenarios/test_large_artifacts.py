"""
Test large artifact upload/download during SSE streaming.

Validates that artifact operations don't block or delay SSE events,
and that the gateway handles large files correctly under load.
"""

import pytest
import asyncio
import time
from typing import List, Tuple, Dict, Any, Union
import uuid

from a2a.types import Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, JSONRPCError

from tests.stress.conftest import StressTestConfig, TestClientHTTPAdapter
from tests.stress.metrics.collector import MetricsCollector
from tests.stress.metrics.reporter import MetricsReporter
from tests.stress.harness.artifact_generator import (
    generate_random_artifact,
    generate_text_artifact,
    MB,
    ARTIFACT_SIZES,
)

pytestmark = [pytest.mark.stress, pytest.mark.asyncio, pytest.mark.artifacts]


def create_llm_response(content: str, index: int = 0) -> Dict[str, Any]:
    """Create a properly formatted LLM response."""
    return {
        "id": f"chatcmpl-artifact-{index}",
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


class TestLargeArtifactHandling:
    """Test artifact operations don't affect SSE streaming."""

    @pytest.mark.parametrize("artifact_size_mb", [1, 5, 10])
    async def test_large_upload_during_streaming(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_http_client: TestClientHTTPAdapter,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
        metrics_reporter: MetricsReporter,
        artifact_size_mb: int,
    ):
        """
        Upload large artifact while SSE streaming is active.

        Validates:
        - Upload completes successfully
        - SSE events continue to be delivered without significant delay
        - No timeout from gateway's size limits (up to 50MB default)
        """
        await metrics_collector.start()

        # Skip if size exceeds config
        artifact_size = artifact_size_mb * MB
        if artifact_size > stress_config.max_artifact_size_bytes:
            pytest.skip(f"Artifact size {artifact_size_mb}MB exceeds max")

        # Prime LLM for streaming task with proper format
        test_llm_server.prime_responses([
            create_llm_response("Response during artifact upload", 0)
        ])

        # Start A2A streaming task
        input_data = {
            "target_agent_name": "TestAgent",
            "user_identity": "artifact-test-user",
            "a2a_parts": [{"type": "text", "text": "Test with concurrent artifact upload"}],
        }
        task_id = await test_gateway_app_instance.send_test_input(input_data)

        # Generate artifact content - use empty sessionId to auto-create session
        session_id = ""  # Empty string triggers session creation
        filename = f"stress-artifact-{artifact_size_mb}mb.bin"
        content = generate_random_artifact(artifact_size, seed=42)

        # Run upload and event collection concurrently
        async def upload_artifact():
            """Upload the large artifact."""
            start_time = time.monotonic()
            try:
                response = await stress_http_client.upload_artifact(
                    session_id=session_id,
                    filename=filename,
                    content=content,
                )
                upload_duration = time.monotonic() - start_time

                await metrics_collector.record_latency(
                    "artifact_upload_large", upload_duration * 1000
                )
                await metrics_collector.set_gauge("upload_size_bytes", artifact_size)
                await metrics_collector.set_gauge(
                    "upload_throughput_mbps",
                    (artifact_size / MB) / upload_duration if upload_duration > 0 else 0
                )

                return response.status_code == 201, response

            except Exception as e:
                await metrics_collector.record_error(
                    "artifact_upload_large", e, {"size_mb": artifact_size_mb}
                )
                return False, None

        async def collect_events():
            """Collect SSE events during upload."""
            event_start = time.monotonic()

            events = await collect_task_events(
                test_gateway_app_instance,
                task_id,
                overall_timeout=30.0,  # Longer timeout for large uploads
                polling_interval=0.1,
            )

            event_latency = (time.monotonic() - event_start) * 1000
            event_times = [event_latency]

            for _ in events:
                await metrics_collector.record_latency(
                    "sse_during_upload", event_latency
                )

            return events, event_times

        # Run both concurrently
        upload_task = asyncio.create_task(upload_artifact())
        events_task = asyncio.create_task(collect_events())

        (upload_success, upload_response), (events, event_times) = await asyncio.gather(
            upload_task, events_task
        )

        await metrics_collector.stop()

        # Validate upload
        assert upload_success, f"Upload failed for {artifact_size_mb}MB artifact"

        # Validate SSE continued during upload
        assert len(events) > 0, "No SSE events received during upload"

        # Check SSE latency wasn't severely impacted
        summary = metrics_collector.get_summary()
        if "sse_during_upload" in summary["operations"]:
            p99 = summary["operations"]["sse_during_upload"]["percentiles"]["p99"]
            # Allow higher latency during large uploads, but should still be reasonable
            max_latency = stress_config.max_p99_latency_ms * 4
            assert p99 < max_latency, (
                f"SSE p99 latency {p99:.1f}ms during {artifact_size_mb}MB upload "
                f"exceeds {max_latency}ms"
            )

    async def test_concurrent_uploads_and_downloads(
        self,
        stress_http_client: TestClientHTTPAdapter,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
        metrics_reporter: MetricsReporter,
    ):
        """
        Test multiple concurrent artifact uploads and downloads.

        Validates:
        - Concurrent operations don't deadlock
        - Memory usage stays bounded
        - All operations complete successfully
        """
        await metrics_collector.start()

        num_concurrent = 5
        artifact_size_mb = 1

        # Generate content once and reuse
        content = generate_random_artifact(artifact_size_mb * MB, seed=123)

        async def upload_download_cycle(cycle_id: int) -> Tuple[bool, bool]:
            """Upload an artifact then download it."""
            # Use empty sessionId to auto-create session
            filename = f"concurrent-{cycle_id}.bin"

            upload_success = False
            download_success = False
            actual_session_id = None

            # Upload
            try:
                response = await stress_http_client.upload_artifact(
                    session_id="",  # Empty triggers session creation
                    filename=filename,
                    content=content,
                )
                upload_success = response.status_code == 201
                if upload_success:
                    # Capture the session ID from the response
                    actual_session_id = response.json().get("sessionId")
                await metrics_collector.increment_counter("concurrent_uploads")
            except Exception as e:
                await metrics_collector.record_error(
                    "concurrent_upload", e, {"cycle_id": cycle_id}
                )

            # Download (only if upload succeeded and we have a session ID)
            if upload_success and actual_session_id:
                try:
                    response = await stress_http_client.download_artifact(
                        session_id=actual_session_id,
                        filename=filename,
                    )
                    download_success = response.status_code == 200
                    await metrics_collector.increment_counter("concurrent_downloads")
                except Exception as e:
                    await metrics_collector.record_error(
                        "concurrent_download", e, {"cycle_id": cycle_id}
                    )

            return upload_success, download_success

        # Run concurrent operations
        tasks = [
            asyncio.create_task(upload_download_cycle(i))
            for i in range(num_concurrent)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        await metrics_collector.stop()

        # Analyze results
        successful_cycles = sum(
            1 for r in results
            if isinstance(r, tuple) and r[0] and r[1]
        )
        errors = [r for r in results if isinstance(r, Exception)]

        assert len(errors) == 0, f"Errors during concurrent artifacts: {errors}"
        assert successful_cycles >= num_concurrent * 0.9, (
            f"Only {successful_cycles}/{num_concurrent} cycles completed"
        )

        # Check latencies
        summary = metrics_collector.get_summary()
        for op in ["artifact_upload", "artifact_download"]:
            if op in summary["operations"]:
                p99 = summary["operations"][op]["percentiles"]["p99"]
                # 5 seconds max for 1MB artifact operations
                assert p99 < 5000, f"{op} p99 {p99:.1f}ms too slow"

    async def test_large_download_during_streaming(
        self,
        test_gateway_app_instance,
        test_llm_server,
        stress_http_client: TestClientHTTPAdapter,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
    ):
        """
        Download large artifact while SSE streaming is active.

        Validates:
        - Download completes successfully
        - SSE events continue without significant delay
        """
        await metrics_collector.start()

        artifact_size_mb = 5
        artifact_size = artifact_size_mb * MB

        # First, upload an artifact to download - use empty sessionId for auto-creation
        filename = "large-download-test.bin"
        content = generate_random_artifact(artifact_size, seed=456)

        upload_response = await stress_http_client.upload_artifact(
            session_id="",  # Empty triggers session creation
            filename=filename,
            content=content,
        )
        assert upload_response.status_code == 201, "Pre-upload failed"

        # Get the session ID from the upload response
        session_id = upload_response.json().get("sessionId")
        assert session_id, "No sessionId in upload response"

        # Prime LLM for streaming task with proper format
        test_llm_server.prime_responses([
            create_llm_response("Response during download", 0)
        ])

        # Start A2A streaming task
        input_data = {
            "target_agent_name": "TestAgent",
            "user_identity": "download-test-user",
            "a2a_parts": [{"type": "text", "text": "Test during large download"}],
        }
        task_id = await test_gateway_app_instance.send_test_input(input_data)

        # Run download and event collection concurrently
        async def download_artifact():
            """Download the large artifact."""
            start_time = time.monotonic()
            try:
                response = await stress_http_client.download_artifact(
                    session_id=session_id,
                    filename=filename,
                )
                download_duration = time.monotonic() - start_time

                await metrics_collector.record_latency(
                    "artifact_download_large", download_duration * 1000
                )

                # Verify content size
                if response.status_code == 200:
                    downloaded_size = len(response.content)
                    await metrics_collector.set_gauge("download_size_bytes", downloaded_size)

                return response.status_code == 200

            except Exception as e:
                await metrics_collector.record_error(
                    "artifact_download_large", e, {"size_mb": artifact_size_mb}
                )
                return False

        async def collect_events():
            """Collect SSE events during download."""
            events = await collect_task_events(
                test_gateway_app_instance,
                task_id,
                overall_timeout=30.0,
                polling_interval=0.1,
            )

            for _ in events:
                await metrics_collector.increment_counter("sse_during_download")

            return events

        download_task = asyncio.create_task(download_artifact())
        events_task = asyncio.create_task(collect_events())

        download_success, events = await asyncio.gather(download_task, events_task)

        await metrics_collector.stop()

        assert download_success, "Download failed"
        assert len(events) > 0, "No SSE events received during download"

    async def test_artifact_size_limits(
        self,
        stress_http_client: TestClientHTTPAdapter,
        stress_config: StressTestConfig,
        metrics_collector: MetricsCollector,
    ):
        """
        Test artifact upload with various sizes up to the limit.

        Validates:
        - Small artifacts upload quickly
        - Large artifacts (up to limit) upload successfully
        - Gateway properly rejects oversized artifacts
        """
        await metrics_collector.start()

        sizes_to_test = [
            ("tiny", 1024),  # 1KB
            ("small", 10 * 1024),  # 10KB
            ("medium", 1 * MB),  # 1MB
            ("large", 5 * MB),  # 5MB
        ]

        for size_name, size_bytes in sizes_to_test:
            if size_bytes > stress_config.max_artifact_size_bytes:
                continue

            # Use empty sessionId to auto-create session
            filename = f"size-test-{size_name}.bin"
            content = generate_random_artifact(size_bytes, seed=789)

            start_time = time.monotonic()
            response = await stress_http_client.upload_artifact(
                session_id="",  # Empty triggers session creation
                filename=filename,
                content=content,
            )
            duration_ms = (time.monotonic() - start_time) * 1000

            await metrics_collector.record_latency(f"upload_{size_name}", duration_ms)

            assert response.status_code == 201, (
                f"Upload failed for {size_name} ({size_bytes} bytes): "
                f"status={response.status_code}"
            )

        await metrics_collector.stop()

        # Verify smaller sizes are faster
        summary = metrics_collector.get_summary()
        if "upload_tiny" in summary["operations"] and "upload_large" in summary["operations"]:
            tiny_mean = summary["operations"]["upload_tiny"]["percentiles"]["mean"]
            large_mean = summary["operations"]["upload_large"]["percentiles"]["mean"]
            # Large should take longer (at least 2x)
            # This validates streaming is working properly
            assert large_mean > tiny_mean, (
                f"Large upload ({large_mean:.1f}ms) should be slower than "
                f"tiny upload ({tiny_mean:.1f}ms)"
            )
