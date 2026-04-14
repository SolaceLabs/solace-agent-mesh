"""Comprehensive tests for agent and tool execution observability instrumentation.

Tests verify that metrics are correctly recorded with proper labels for both
agent and tool execution paths, following sam-developer testing philosophy:
- Test behavior, not implementation details
- Minimize mocking - only mock at true external boundaries (MetricRegistry)
- Let real code execute (tool wrappers, monitors, context managers)
- Verify observable outcomes (metrics recorded, labels correct, timing accurate)
"""

import asyncio
import pytest
from typing import List, Tuple, Dict, Optional
from unittest.mock import Mock, patch, AsyncMock
from solace_agent_mesh.agent.adk.tool_wrapper import ADKToolWrapper


def find_metric(
    recorded_metrics: List[Tuple[float, Dict[str, str]]],
    **expected_labels: str
) -> Optional[Tuple[float, Dict[str, str]]]:
    """
    Find first metric matching all expected labels.

    Args:
        recorded_metrics: List of (duration, labels) tuples
        **expected_labels: Label key-value pairs to match

    Returns:
        Matching (duration, labels) tuple or None if not found
    """
    for duration, labels in recorded_metrics:
        if all(labels.get(key) == value for key, value in expected_labels.items()):
            return duration, labels
    return None


def find_all_metrics(
    recorded_metrics: List[Tuple[float, Dict[str, str]]],
    **expected_labels: str
) -> List[Tuple[float, Dict[str, str]]]:
    """
    Find all metrics matching expected labels.

    Args:
        recorded_metrics: List of (duration, labels) tuples
        **expected_labels: Label key-value pairs to match

    Returns:
        List of matching (duration, labels) tuples
    """
    matches = []
    for duration, labels in recorded_metrics:
        if all(labels.get(key) == value for key, value in expected_labels.items()):
            matches.append((duration, labels))
    return matches


class TestToolExecutionInstrumentation:
    """Test that tool execution records metrics with correct labels."""

    @pytest.mark.asyncio
    async def test_async_tool_success_records_metric(self):
        """Async tool success should record metric with type=tool, error.type=none."""
        # Create real async tool function
        async def sample_tool(input_text: str, tool_context=None):
            await asyncio.sleep(0.005)  # Simulate work
            return {"result": f"processed {input_text}"}

        # Create real ADKToolWrapper (not mocked)
        wrapper = ADKToolWrapper(
            original_func=sample_tool,
            tool_config={},
            tool_name="web_search",
            origin="test"
        )

        # Minimal tool context mock (unavoidable external dependency)
        mock_tool_context = Mock()
        mock_tool_context.session = Mock()
        mock_tool_context.state = {}

        recorded_metrics = []

        def capture_record(duration, labels):
            """Capture metrics as they're recorded."""
            recorded_metrics.append((duration, labels))

        # Mock only at the MetricRegistry boundary
        with patch('solace_ai_connector.common.observability.api.MetricRegistry') as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)

            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            # Execute real tool code
            result = await wrapper(input_text="test", tool_context=mock_tool_context)

            # Verify tool actually executed correctly
            assert result == {"result": "processed test"}

            # Find the metric we care about (may have other metrics from system)
            metric = find_metric(
                recorded_metrics,
                type="tool",
                **{"component.name": "web_search"}
            )
            assert metric is not None, f"Expected web_search tool metric not found in {recorded_metrics}"
            duration, labels = metric

            # Verify labels are correct
            assert labels["type"] == "tool"
            assert labels["component.name"] == "web_search"
            assert labels["operation.name"] == "execute"
            assert labels["error.type"] == "none"

            # Verify duration was measured and is reasonable (>= sleep time)
            assert duration >= 0.005, f"Expected duration >= 0.005s, got {duration}s"

    @pytest.mark.asyncio
    async def test_sync_tool_records_metric_with_correct_timing(self):
        """Sync tool should record metrics with accurate timing when wrapped for async execution."""
        import time

        # Create real sync tool function
        def sync_tool(input_text: str, tool_context=None):
            time.sleep(0.005)
            return {"result": f"sync {input_text}"}

        wrapper = ADKToolWrapper(
            original_func=sync_tool,
            tool_config={},
            tool_name="sync_processor",
            origin="test"
        )

        mock_tool_context = Mock()
        mock_tool_context.session = Mock()
        mock_tool_context.state = {}

        recorded_metrics = []

        def capture_record(duration, labels):
            recorded_metrics.append((duration, labels))

        with patch('solace_ai_connector.common.observability.api.MetricRegistry') as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)

            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            # Execute sync tool via wrapper
            result = await wrapper(input_text="test", tool_context=mock_tool_context)

            # Verify tool executed correctly
            assert result == {"result": "sync test"}

            # Find the metric we care about
            metric = find_metric(
                recorded_metrics,
                type="tool",
                **{"component.name": "sync_processor"}
            )
            assert metric is not None, f"Expected sync_processor tool metric not found in {recorded_metrics}"
            duration, labels = metric

            assert labels["type"] == "tool"
            assert labels["component.name"] == "sync_processor"
            assert labels["error.type"] == "none"
            assert duration >= 0.005, f"Expected duration >= 0.005s, got {duration}s"

    @pytest.mark.asyncio
    async def test_tool_error_records_metric_with_error_type(self):
        """Tool raising exception should record metric with categorized error.type."""
        # Create tool that raises exception
        async def failing_tool(input_text: str, tool_context=None):
            await asyncio.sleep(0.002)
            raise ValueError("Invalid input parameter")

        wrapper = ADKToolWrapper(
            original_func=failing_tool,
            tool_config={},
            tool_name="query_data",
            origin="test"
        )

        mock_tool_context = Mock()
        mock_tool_context.session = Mock()
        mock_tool_context.state = {}

        recorded_metrics = []

        def capture_record(duration, labels):
            recorded_metrics.append((duration, labels))

        with patch('solace_ai_connector.common.observability.api.MetricRegistry') as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)

            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            # Execute tool - wrapper catches exception and returns error dict
            result = await wrapper(input_text="bad", tool_context=mock_tool_context)

            # Verify tool returned error result (not raised)
            assert result["status"] == "error"
            assert "query_data" in result["message"]

            # Find the metric we care about
            metric = find_metric(
                recorded_metrics,
                type="tool",
                **{"component.name": "query_data"}
            )
            assert metric is not None, f"Expected query_data tool metric not found in {recorded_metrics}"
            duration, labels = metric

            assert labels["type"] == "tool"
            assert labels["component.name"] == "query_data"
            assert labels["operation.name"] == "execute"
            assert labels["error.type"] == "validation_error"  # ValueError categorized as validation_error

            # Duration should still be measured even on error
            assert duration >= 0.002, f"Expected duration >= 0.002s, got {duration}s"

    @pytest.mark.asyncio
    async def test_timeout_error_categorized_correctly(self):
        """TimeoutError should be categorized as 'timeout' in error.type."""
        async def timeout_tool(input_text: str, tool_context=None):
            raise TimeoutError("Operation timed out")

        wrapper = ADKToolWrapper(
            original_func=timeout_tool,
            tool_config={},
            tool_name="slow_tool",
            origin="test"
        )

        mock_tool_context = Mock()
        mock_tool_context.session = Mock()
        mock_tool_context.state = {}

        recorded_metrics = []

        def capture_record(duration, labels):
            recorded_metrics.append((duration, labels))

        with patch('solace_ai_connector.common.observability.api.MetricRegistry') as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)

            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            # Execute tool
            result = await wrapper(input_text="test", tool_context=mock_tool_context)

            # Verify error was caught
            assert result["status"] == "error"

            # Find the metric we care about
            metric = find_metric(
                recorded_metrics,
                type="tool",
                **{"component.name": "slow_tool"}
            )
            assert metric is not None, f"Expected slow_tool metric not found in {recorded_metrics}"
            _, labels = metric
            assert labels["error.type"] == "timeout"

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_record_separate_metrics(self):
        """Sequential tool calls should each record their own metric."""
        async def quick_tool(input_text: str, tool_context=None):
            await asyncio.sleep(0.001)
            return {"result": input_text}

        wrapper = ADKToolWrapper(
            original_func=quick_tool,
            tool_config={},
            tool_name="batch_processor",
            origin="test"
        )

        mock_tool_context = Mock()
        mock_tool_context.session = Mock()
        mock_tool_context.state = {}

        recorded_metrics = []

        def capture_record(duration, labels):
            recorded_metrics.append((duration, labels))

        with patch('solace_ai_connector.common.observability.api.MetricRegistry') as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)

            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            # Execute tool 3 times
            await wrapper(input_text="first", tool_context=mock_tool_context)
            await wrapper(input_text="second", tool_context=mock_tool_context)
            await wrapper(input_text="third", tool_context=mock_tool_context)

            # Find all metrics for batch_processor
            batch_metrics = find_all_metrics(
                recorded_metrics,
                type="tool",
                **{"component.name": "batch_processor"}
            )

            # Should have recorded at least 3 separate metrics for this tool
            assert len(batch_metrics) >= 3, (
                f"Expected at least 3 batch_processor metrics, found {len(batch_metrics)}"
            )

            # All batch_processor metrics should indicate successful execution
            for _, labels in batch_metrics:
                assert labels["component.name"] == "batch_processor"
                assert labels["error.type"] == "none"


class TestAgentExecutionInstrumentation:
    """Test that agent execution records metrics with correct labels."""

    @pytest.mark.asyncio
    async def test_agent_success_records_metric_with_timing(self):
        """Successful agent execution should record metric with type=agent, error.type=none and accurate timing."""
        from solace_agent_mesh.agent.adk.runner import run_adk_async_task_thread_wrapper

        # Mock only essential external dependencies
        mock_component = Mock()
        mock_component.agent_name = "ResearchAgent"
        mock_component.log_identifier = "[ResearchAgent]"
        mock_component.auto_summarization_config = {"enabled": False}
        mock_component.active_tasks_lock = Mock()
        mock_component.active_tasks_lock.__enter__ = Mock()
        mock_component.active_tasks_lock.__exit__ = Mock()

        mock_task_context = Mock()
        mock_task_context.flush_streaming_buffer = Mock()
        mock_component.active_tasks = {"test-task": mock_task_context}

        mock_session = Mock()
        mock_session.user_id = "user123"
        mock_session.id = "session456"
        mock_session.events = []

        mock_content = Mock()
        mock_run_config = Mock()
        a2a_context = {"logical_task_id": "test-task"}

        recorded_metrics = []

        def capture_record(duration, labels):
            recorded_metrics.append((duration, labels))

        # Mock the actual agent execution logic
        async def mock_compaction_retry(*args, **kwargs):
            await asyncio.sleep(0.005)  # Simulate agent work
            return False, mock_session  # is_paused=False, session

        with patch('solace_ai_connector.common.observability.api.MetricRegistry') as mock_registry:
            with patch('solace_agent_mesh.agent.adk.runner._run_with_compaction_retry', side_effect=mock_compaction_retry):
                with patch('solace_agent_mesh.agent.adk.runner._send_deferred_compaction_notification', new_callable=AsyncMock):
                    mock_recorder = Mock()
                    mock_recorder.record = Mock(side_effect=capture_record)

                    mock_registry_instance = Mock()
                    mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
                    mock_registry.get_instance = Mock(return_value=mock_registry_instance)

                    # Execute agent runner (MonitorLatency runs real code)
                    await run_adk_async_task_thread_wrapper(
                        component=mock_component,
                        adk_session=mock_session,
                        adk_content=mock_content,
                        run_config=mock_run_config,
                        a2a_context=a2a_context,
                        append_context_event=False,
                        skip_finalization=True
                    )

                    # Find the metric we care about
                    metric = find_metric(
                        recorded_metrics,
                        type="agent",
                        **{"component.name": "ResearchAgent"}
                    )
                    assert metric is not None, f"Expected ResearchAgent metric not found in {recorded_metrics}"
                    duration, labels = metric

                    # Verify labels are correct
                    assert labels["type"] == "agent"
                    assert labels["component.name"] == "ResearchAgent"
                    assert labels["operation.name"] == "execute"
                    assert labels["error.type"] == "none"

                    # Verify duration was measured accurately
                    assert duration >= 0.005, f"Expected duration >= 0.005s, got {duration}s"

    @pytest.mark.asyncio
    async def test_agent_error_records_metric_with_error_type_and_timing(self):
        """Agent raising exception should record metric with error.type and measure timing despite error."""
        from solace_agent_mesh.agent.adk.runner import run_adk_async_task_thread_wrapper

        mock_component = Mock()
        mock_component.agent_name = "FailingAgent"
        mock_component.log_identifier = "[FailingAgent]"
        mock_component.auto_summarization_config = {"enabled": False}
        mock_component.active_tasks_lock = Mock()
        mock_component.active_tasks_lock.__enter__ = Mock()
        mock_component.active_tasks_lock.__exit__ = Mock()

        mock_task_context = Mock()
        mock_task_context.flush_streaming_buffer = Mock()
        mock_component.active_tasks = {"test-task": mock_task_context}

        mock_session = Mock()
        mock_session.events = []

        mock_content = Mock()
        mock_run_config = Mock()
        a2a_context = {"logical_task_id": "test-task"}

        recorded_metrics = []

        def capture_record(duration, labels):
            recorded_metrics.append((duration, labels))

        # Mock agent execution to raise exception
        async def mock_compaction_retry_error(*args, **kwargs):
            await asyncio.sleep(0.003)
            raise RuntimeError("Agent execution failed")

        with patch('solace_ai_connector.common.observability.api.MetricRegistry') as mock_registry:
            with patch('solace_agent_mesh.agent.adk.runner._run_with_compaction_retry', side_effect=mock_compaction_retry_error):
                mock_recorder = Mock()
                mock_recorder.record = Mock(side_effect=capture_record)

                mock_registry_instance = Mock()
                mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
                mock_registry.get_instance = Mock(return_value=mock_registry_instance)

                # Execute agent - exception is caught and handled
                await run_adk_async_task_thread_wrapper(
                    component=mock_component,
                    adk_session=mock_session,
                    adk_content=mock_content,
                    run_config=mock_run_config,
                    a2a_context=a2a_context,
                    append_context_event=False,
                    skip_finalization=True
                )

                # Find the metric we care about
                metric = find_metric(
                    recorded_metrics,
                    type="agent",
                    **{"component.name": "FailingAgent"}
                )
                assert metric is not None, f"Expected FailingAgent metric not found in {recorded_metrics}"
                duration, labels = metric

                # Verify error was captured
                assert labels["type"] == "agent"
                assert labels["component.name"] == "FailingAgent"
                assert labels["operation.name"] == "execute"
                assert labels["error.type"] == "RuntimeError"

                # Duration should still be measured even on error
                assert duration >= 0.003, f"Expected duration >= 0.003s, got {duration}s"