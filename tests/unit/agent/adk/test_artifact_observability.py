"""Tests for artifact service observability instrumentation.

Tests verify that metrics are correctly recorded with proper labels for all
artifact service operations through ScopedArtifactServiceWrapper, following
sam-developer testing philosophy:
- Test behavior, not implementation details
- Minimize mocking - only mock at true external boundaries (MetricRegistry)
- Let real code execute (wrapper, monitors, context managers)
- Verify observable outcomes (metrics recorded, labels correct)
"""

import pytest
from typing import List, Tuple, Dict, Optional
from unittest.mock import Mock, patch, AsyncMock

from google.adk.artifacts import InMemoryArtifactService
from google.genai import types as adk_types

from solace_agent_mesh.agent.adk.services import ScopedArtifactServiceWrapper


def find_metric(
    recorded_metrics: List[Tuple[float, Dict[str, str]]],
    **expected_labels: str,
) -> Optional[Tuple[float, Dict[str, str]]]:
    """Find first metric matching all expected labels."""
    for duration, labels in recorded_metrics:
        if all(labels.get(key) == value for key, value in expected_labels.items()):
            return duration, labels
    return None


def find_all_metrics(
    recorded_metrics: List[Tuple[float, Dict[str, str]]],
    **expected_labels: str,
) -> List[Tuple[float, Dict[str, str]]]:
    """Find all metrics matching expected labels."""
    matches = []
    for duration, labels in recorded_metrics:
        if all(labels.get(key) == value for key, value in expected_labels.items()):
            matches.append((duration, labels))
    return matches


@pytest.fixture
def mock_component():
    """Minimal component mock for ScopedArtifactServiceWrapper."""
    component = Mock()
    component.get_config = Mock(return_value="namespace")
    component.namespace = "test-namespace"
    return component


@pytest.fixture
def wrapper(mock_component):
    """ScopedArtifactServiceWrapper around InMemoryArtifactService."""
    service = InMemoryArtifactService()
    return ScopedArtifactServiceWrapper(
        wrapped_service=service,
        component=mock_component,
    )


@pytest.fixture
def metric_capture():
    """Set up metric capture via MetricRegistry mock. Returns recorded_metrics list."""
    recorded_metrics = []

    def capture_record(duration, labels):
        recorded_metrics.append((duration, labels))

    return recorded_metrics, capture_record


def _make_text_artifact(text: str = "test content") -> adk_types.Part:
    """Create a simple text Part for testing."""
    return adk_types.Part(text=text)


class TestArtifactOperationMetrics:
    """Test that each artifact operation records metrics with correct labels."""

    @pytest.mark.asyncio
    async def test_save_artifact_records_metric(self, wrapper, metric_capture):
        """save_artifact should record metric with operation.name=save."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            result = await wrapper.save_artifact(
                app_name="test-app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=_make_text_artifact(),
            )

            assert isinstance(result, int)

            metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{"component.name": "artifact_service", "operation.name": "save"},
            )
            assert metric is not None, (
                f"Expected artifact save metric not found in {recorded_metrics}"
            )
            duration, labels = metric
            assert labels["error.type"] == "none"
            assert duration >= 0

    @pytest.mark.asyncio
    async def test_load_artifact_records_metric(self, wrapper, metric_capture):
        """load_artifact should record metric with operation.name=load."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            # Save first so we have something to load
            await wrapper.save_artifact(
                app_name="test-app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=_make_text_artifact(),
            )

            recorded_metrics.clear()

            result = await wrapper.load_artifact(
                app_name="test-app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
            )

            metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{"component.name": "artifact_service", "operation.name": "load"},
            )
            assert metric is not None, (
                f"Expected artifact load metric not found in {recorded_metrics}"
            )
            _, labels = metric
            assert labels["error.type"] == "none"

    @pytest.mark.asyncio
    async def test_delete_artifact_records_metric(self, wrapper, metric_capture):
        """delete_artifact should record metric with operation.name=delete."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            # Save first so we have something to delete
            await wrapper.save_artifact(
                app_name="test-app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=_make_text_artifact(),
            )

            recorded_metrics.clear()

            await wrapper.delete_artifact(
                app_name="test-app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
            )

            metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{"component.name": "artifact_service", "operation.name": "delete"},
            )
            assert metric is not None, (
                f"Expected artifact delete metric not found in {recorded_metrics}"
            )
            _, labels = metric
            assert labels["error.type"] == "none"

    @pytest.mark.asyncio
    async def test_list_artifact_keys_records_metric(self, wrapper, metric_capture):
        """list_artifact_keys should record metric with operation.name=list_keys."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            result = await wrapper.list_artifact_keys(
                app_name="test-app",
                user_id="user1",
                session_id="session1",
            )

            assert isinstance(result, list)

            metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{
                    "component.name": "artifact_service",
                    "operation.name": "list_keys",
                },
            )
            assert metric is not None, (
                f"Expected artifact list_keys metric not found in {recorded_metrics}"
            )
            _, labels = metric
            assert labels["error.type"] == "none"

    @pytest.mark.asyncio
    async def test_list_versions_records_metric(self, wrapper, metric_capture):
        """list_versions should record metric with operation.name=list_versions."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            # Save an artifact so list_versions has something to return
            await wrapper.save_artifact(
                app_name="test-app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=_make_text_artifact(),
            )

            recorded_metrics.clear()

            result = await wrapper.list_versions(
                app_name="test-app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
            )

            assert isinstance(result, list)

            metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{
                    "component.name": "artifact_service",
                    "operation.name": "list_versions",
                },
            )
            assert metric is not None, (
                f"Expected artifact list_versions metric not found in {recorded_metrics}"
            )
            _, labels = metric
            assert labels["error.type"] == "none"

    @pytest.mark.asyncio
    async def test_list_artifact_versions_records_metric(
        self, wrapper, metric_capture
    ):
        """list_artifact_versions should record metric with operation.name=list_artifact_versions."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            result = await wrapper.list_artifact_versions(
                app_name="test-app",
                user_id="user1",
                filename="test.txt",
                session_id="session1",
            )

            assert isinstance(result, list)

            metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{
                    "component.name": "artifact_service",
                    "operation.name": "list_artifact_versions",
                },
            )
            assert metric is not None, (
                f"Expected artifact list_artifact_versions metric not found in {recorded_metrics}"
            )
            _, labels = metric
            assert labels["error.type"] == "none"

    @pytest.mark.asyncio
    async def test_get_artifact_version_records_metric(self, wrapper, metric_capture):
        """get_artifact_version should record metric with operation.name=get_version."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            result = await wrapper.get_artifact_version(
                app_name="test-app",
                user_id="user1",
                filename="test.txt",
                session_id="session1",
            )

            metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{
                    "component.name": "artifact_service",
                    "operation.name": "get_version",
                },
            )
            assert metric is not None, (
                f"Expected artifact get_version metric not found in {recorded_metrics}"
            )
            _, labels = metric
            assert labels["error.type"] == "none"


class TestArtifactErrorMetrics:
    """Test that errors during artifact operations are captured in metrics."""

    @pytest.mark.asyncio
    async def test_backend_error_records_error_type(self, mock_component, metric_capture):
        """Backend exception should record error.type and propagate the exception."""
        recorded_metrics, capture_record = metric_capture

        # Use a mock backend that raises on save
        mock_service = AsyncMock()
        mock_service.save_artifact = AsyncMock(side_effect=OSError("disk full"))

        wrapper = ScopedArtifactServiceWrapper(
            wrapped_service=mock_service,
            component=mock_component,
        )

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            with pytest.raises(OSError, match="disk full"):
                await wrapper.save_artifact(
                    app_name="test-app",
                    user_id="user1",
                    session_id="session1",
                    filename="test.txt",
                    artifact=_make_text_artifact(),
                )

            metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{"component.name": "artifact_service", "operation.name": "save"},
            )
            assert metric is not None, (
                f"Expected artifact save metric not found in {recorded_metrics}"
            )
            _, labels = metric
            assert labels["error.type"] != "none"

    @pytest.mark.asyncio
    async def test_load_error_records_error_type(self, mock_component, metric_capture):
        """Backend error on load should record error.type and propagate."""
        recorded_metrics, capture_record = metric_capture

        mock_service = AsyncMock()
        mock_service.load_artifact = AsyncMock(
            side_effect=ValueError("invalid filename")
        )

        wrapper = ScopedArtifactServiceWrapper(
            wrapped_service=mock_service,
            component=mock_component,
        )

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            with pytest.raises(ValueError, match="invalid filename"):
                await wrapper.load_artifact(
                    app_name="test-app",
                    user_id="user1",
                    session_id="session1",
                    filename="bad.txt",
                )

            metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{"component.name": "artifact_service", "operation.name": "load"},
            )
            assert metric is not None
            _, labels = metric
            assert labels["error.type"] == "validation_error"

    @pytest.mark.asyncio
    async def test_timeout_error_records_timeout_type(
        self, mock_component, metric_capture
    ):
        """TimeoutError should be categorized as 'timeout' in error.type."""
        recorded_metrics, capture_record = metric_capture

        mock_service = AsyncMock()
        mock_service.delete_artifact = AsyncMock(
            side_effect=TimeoutError("connection timed out")
        )

        wrapper = ScopedArtifactServiceWrapper(
            wrapped_service=mock_service,
            component=mock_component,
        )

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            with pytest.raises(TimeoutError):
                await wrapper.delete_artifact(
                    app_name="test-app",
                    user_id="user1",
                    session_id="session1",
                    filename="test.txt",
                )

            metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{"component.name": "artifact_service", "operation.name": "delete"},
            )
            assert metric is not None
            _, labels = metric
            assert labels["error.type"] == "timeout"


class TestArtifactScopingWithMonitoring:
    """Test that scoping still works correctly with monitoring instrumentation."""

    @pytest.mark.asyncio
    async def test_namespace_scoping_preserved(self, metric_capture):
        """Monitoring should not interfere with namespace scoping."""
        recorded_metrics, capture_record = metric_capture

        mock_service = AsyncMock()
        mock_service.list_artifact_keys = AsyncMock(return_value=[])

        component = Mock()
        component.get_config = Mock(return_value="namespace")
        component.namespace = "my-namespace"

        wrapper = ScopedArtifactServiceWrapper(
            wrapped_service=mock_service,
            component=component,
        )

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            await wrapper.list_artifact_keys(
                app_name="original-app",
                user_id="user1",
                session_id="session1",
            )

            # Verify the wrapped service was called with the scoped app_name
            mock_service.list_artifact_keys.assert_called_once_with(
                app_name="my-namespace",
                user_id="user1",
                session_id="session1",
            )

            # Verify metric was still recorded
            metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{
                    "component.name": "artifact_service",
                    "operation.name": "list_keys",
                },
            )
            assert metric is not None

    @pytest.mark.asyncio
    async def test_app_scoping_preserved(self, metric_capture):
        """Monitoring should not interfere with app-level scoping."""
        recorded_metrics, capture_record = metric_capture

        mock_service = AsyncMock()
        mock_service.save_artifact = AsyncMock(return_value=1)

        component = Mock()
        component.get_config = Mock(return_value="app")
        component.namespace = "my-namespace"

        wrapper = ScopedArtifactServiceWrapper(
            wrapped_service=mock_service,
            component=component,
        )

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            await wrapper.save_artifact(
                app_name="my-agent",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=_make_text_artifact(),
            )

            # With app scope, the original app_name should be passed through
            mock_service.save_artifact.assert_called_once_with(
                app_name="my-agent",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=_make_text_artifact(),
            )

    @pytest.mark.asyncio
    async def test_multiple_operations_record_separate_metrics(
        self, wrapper, metric_capture
    ):
        """Sequential artifact operations should each record their own metric."""
        recorded_metrics, capture_record = metric_capture

        with patch(
            "solace_ai_connector.common.observability.api.MetricRegistry"
        ) as mock_registry:
            mock_recorder = Mock()
            mock_recorder.record = Mock(side_effect=capture_record)
            mock_registry_instance = Mock()
            mock_registry_instance.get_recorder = Mock(return_value=mock_recorder)
            mock_registry.get_instance = Mock(return_value=mock_registry_instance)

            # Perform multiple different operations
            await wrapper.save_artifact(
                app_name="test-app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=_make_text_artifact(),
            )
            await wrapper.load_artifact(
                app_name="test-app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
            )
            await wrapper.list_artifact_keys(
                app_name="test-app",
                user_id="user1",
                session_id="session1",
            )

            # Find metrics for each operation type
            save_metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{"operation.name": "save"},
            )
            load_metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{"operation.name": "load"},
            )
            list_metric = find_metric(
                recorded_metrics,
                type="artifact",
                **{"operation.name": "list_keys"},
            )

            assert save_metric is not None, "Missing save metric"
            assert load_metric is not None, "Missing load metric"
            assert list_metric is not None, "Missing list_keys metric"
