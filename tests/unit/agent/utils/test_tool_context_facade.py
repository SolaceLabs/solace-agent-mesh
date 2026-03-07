"""
Unit tests for the ToolContextFacade class.

Tests cover context access, artifact operations, and status update methods.
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch


class TestToolContextFacadeStatusUpdates:
    """Tests for the status update methods in ToolContextFacade."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a mock ToolContext with all necessary attributes."""
        ctx = Mock()
        ctx.state = {"a2a_context": {"logical_task_id": "task-123", "contextId": "ctx-456"}}

        # Mock the invocation context chain
        mock_host_component = Mock()
        mock_host_component.publish_data_signal_from_thread = Mock(return_value=True)

        mock_agent = Mock()
        mock_agent.host_component = mock_host_component

        mock_inv_context = Mock()
        mock_inv_context.agent = mock_agent
        mock_inv_context.artifact_service = None
        mock_inv_context.app_name = "TestApp"
        mock_inv_context.user_id = "test-user"

        ctx._invocation_context = mock_inv_context

        return ctx

    @pytest.fixture
    def mock_tool_context_no_a2a(self):
        """Create a mock ToolContext without a2a_context (simulating test environment)."""
        ctx = Mock()
        ctx.state = {}  # No a2a_context

        mock_host_component = Mock()
        mock_host_component.publish_data_signal_from_thread = Mock(return_value=True)

        mock_agent = Mock()
        mock_agent.host_component = mock_host_component

        mock_inv_context = Mock()
        mock_inv_context.agent = mock_agent

        ctx._invocation_context = mock_inv_context

        return ctx

    @pytest.fixture
    def mock_tool_context_no_host(self):
        """Create a mock ToolContext without host_component."""
        ctx = Mock()
        ctx.state = {"a2a_context": {"logical_task_id": "task-123"}}

        mock_agent = Mock()
        mock_agent.host_component = None  # No host component

        mock_inv_context = Mock()
        mock_inv_context.agent = mock_agent

        ctx._invocation_context = mock_inv_context

        return ctx

    @pytest.fixture
    def mock_tool_context_minimal(self):
        """Create a minimal mock ToolContext (simulating unit test environment)."""
        ctx = Mock()
        ctx.state = {}
        ctx._invocation_context = None  # No invocation context at all

        return ctx

    def test_send_status_success(self, mock_tool_context):
        """Test successful status update sending."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        facade = ToolContextFacade(mock_tool_context)

        result = facade.send_status("Processing data...")

        assert result is True

        # Verify the host component method was called
        host = mock_tool_context._invocation_context.agent.host_component
        host.publish_data_signal_from_thread.assert_called_once()

        # Verify the call arguments
        call_args = host.publish_data_signal_from_thread.call_args
        assert call_args.kwargs["a2a_context"] == {"logical_task_id": "task-123", "contextId": "ctx-456"}

        # Verify signal data is AgentProgressUpdateData
        signal_data = call_args.kwargs["signal_data"]
        assert signal_data.status_text == "Processing data..."
        assert signal_data.type == "agent_progress_update"

    def test_send_status_no_a2a_context(self, mock_tool_context_no_a2a):
        """Test send_status returns False when a2a_context is missing."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        facade = ToolContextFacade(mock_tool_context_no_a2a)

        result = facade.send_status("Processing...")

        assert result is False

        # Verify publish was NOT called
        host = mock_tool_context_no_a2a._invocation_context.agent.host_component
        host.publish_data_signal_from_thread.assert_not_called()

    def test_send_status_no_host_component(self, mock_tool_context_no_host):
        """Test send_status returns False when host_component is missing."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        facade = ToolContextFacade(mock_tool_context_no_host)

        result = facade.send_status("Processing...")

        assert result is False

    def test_send_status_minimal_context(self, mock_tool_context_minimal):
        """Test send_status returns False gracefully with minimal context."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        facade = ToolContextFacade(mock_tool_context_minimal)

        result = facade.send_status("Processing...")

        assert result is False

    def test_send_signal_success(self, mock_tool_context):
        """Test successful custom signal sending."""
        from solace_agent_mesh.agent.utils import ToolContextFacade
        from solace_agent_mesh.common.data_parts import AgentProgressUpdateData

        facade = ToolContextFacade(mock_tool_context)

        signal = AgentProgressUpdateData(status_text="Custom signal")
        result = facade.send_signal(signal)

        assert result is True

        # Verify the call
        host = mock_tool_context._invocation_context.agent.host_component
        host.publish_data_signal_from_thread.assert_called_once()

        call_args = host.publish_data_signal_from_thread.call_args
        assert call_args.kwargs["signal_data"] == signal
        assert call_args.kwargs["skip_buffer_flush"] is False

    def test_send_signal_with_skip_buffer_flush(self, mock_tool_context):
        """Test send_signal with skip_buffer_flush=True."""
        from solace_agent_mesh.agent.utils import ToolContextFacade
        from solace_agent_mesh.common.data_parts import AgentProgressUpdateData

        facade = ToolContextFacade(mock_tool_context)

        signal = AgentProgressUpdateData(status_text="Test")
        result = facade.send_signal(signal, skip_buffer_flush=True)

        assert result is True

        host = mock_tool_context._invocation_context.agent.host_component
        call_args = host.publish_data_signal_from_thread.call_args
        assert call_args.kwargs["skip_buffer_flush"] is True

    def test_send_signal_no_context(self, mock_tool_context_minimal):
        """Test send_signal returns False gracefully without context."""
        from solace_agent_mesh.agent.utils import ToolContextFacade
        from solace_agent_mesh.common.data_parts import AgentProgressUpdateData

        facade = ToolContextFacade(mock_tool_context_minimal)

        signal = AgentProgressUpdateData(status_text="Test")
        result = facade.send_signal(signal)

        assert result is False

    def test_a2a_context_property(self, mock_tool_context):
        """Test the a2a_context property returns expected value."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        facade = ToolContextFacade(mock_tool_context)

        a2a_ctx = facade.a2a_context

        assert a2a_ctx == {"logical_task_id": "task-123", "contextId": "ctx-456"}

    def test_a2a_context_property_missing(self, mock_tool_context_minimal):
        """Test the a2a_context property returns None when missing."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        facade = ToolContextFacade(mock_tool_context_minimal)

        a2a_ctx = facade.a2a_context

        assert a2a_ctx is None

    def test_host_component_caching(self, mock_tool_context):
        """Test that host_component is cached after first access."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        facade = ToolContextFacade(mock_tool_context)

        # First call
        facade.send_status("First")

        # Second call
        facade.send_status("Second")

        # The host component should be cached, so _ensure_host_component
        # should not traverse the object chain again
        assert facade._host_component_resolved is True
        assert facade._host_component is not None

    def test_multiple_status_updates(self, mock_tool_context):
        """Test sending multiple status updates in sequence."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        facade = ToolContextFacade(mock_tool_context)

        messages = ["Starting...", "Step 1...", "Step 2...", "Done!"]

        for msg in messages:
            result = facade.send_status(msg)
            assert result is True

        host = mock_tool_context._invocation_context.agent.host_component
        assert host.publish_data_signal_from_thread.call_count == 4

    def test_send_deep_research_progress_signal(self, mock_tool_context):
        """Test sending a DeepResearchProgressData signal."""
        from solace_agent_mesh.agent.utils import ToolContextFacade
        from solace_agent_mesh.common.data_parts import DeepResearchProgressData

        facade = ToolContextFacade(mock_tool_context)

        signal = DeepResearchProgressData(
            phase="searching",
            status_text="Searching for sources...",
            progress_percentage=25,
            current_iteration=1,
            total_iterations=3,
            sources_found=5,
            elapsed_seconds=10,
        )

        result = facade.send_signal(signal)

        assert result is True

        host = mock_tool_context._invocation_context.agent.host_component
        call_args = host.publish_data_signal_from_thread.call_args
        sent_signal = call_args.kwargs["signal_data"]

        assert sent_signal.phase == "searching"
        assert sent_signal.progress_percentage == 25
        assert sent_signal.sources_found == 5


class TestToolContextFacadeContextAccess:
    """Tests for context property access in ToolContextFacade."""

    @pytest.fixture
    def mock_tool_context_full(self):
        """Create a fully populated mock ToolContext."""
        ctx = Mock()
        ctx.state = {"a2a_context": {"logical_task_id": "task-123"}, "custom_key": "custom_value"}

        mock_inv_context = Mock()
        mock_inv_context.artifact_service = Mock()
        mock_inv_context.app_name = "TestApp"
        mock_inv_context.user_id = "user-123"

        # Mock for get_original_session_id
        mock_inv_context.session = Mock()
        mock_inv_context.session.id = "session-456"

        ctx._invocation_context = mock_inv_context

        return ctx

    def test_session_id_property(self, mock_tool_context_full):
        """Test session_id property extraction."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        with patch('solace_agent_mesh.agent.utils.tool_context_facade.get_original_session_id', return_value="session-456"):
            facade = ToolContextFacade(mock_tool_context_full)

            session_id = facade.session_id

            assert session_id == "session-456"

    def test_user_id_property(self, mock_tool_context_full):
        """Test user_id property extraction."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        with patch('solace_agent_mesh.agent.utils.tool_context_facade.get_original_session_id', return_value="session-456"):
            facade = ToolContextFacade(mock_tool_context_full)

            user_id = facade.user_id

            assert user_id == "user-123"

    def test_app_name_property(self, mock_tool_context_full):
        """Test app_name property extraction."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        with patch('solace_agent_mesh.agent.utils.tool_context_facade.get_original_session_id', return_value="session-456"):
            facade = ToolContextFacade(mock_tool_context_full)

            app_name = facade.app_name

            assert app_name == "TestApp"

    def test_state_property(self, mock_tool_context_full):
        """Test state property access."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        facade = ToolContextFacade(mock_tool_context_full)

        state = facade.state

        assert state["custom_key"] == "custom_value"

    def test_raw_tool_context_property(self, mock_tool_context_full):
        """Test raw_tool_context property returns the original context."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        facade = ToolContextFacade(mock_tool_context_full)

        raw_ctx = facade.raw_tool_context

        assert raw_ctx is mock_tool_context_full

    def test_get_config(self, mock_tool_context_full):
        """Test get_config method."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        tool_config = {"api_key": "secret", "timeout": 30}
        facade = ToolContextFacade(mock_tool_context_full, tool_config=tool_config)

        assert facade.get_config("api_key") == "secret"
        assert facade.get_config("timeout") == 30
        assert facade.get_config("missing") is None
        assert facade.get_config("missing", "default") == "default"


class TestToolContextFacadeInit:
    """Tests for ToolContextFacade initialization."""

    def test_init_with_tool_config(self):
        """Test initialization with tool configuration."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        mock_ctx = Mock()
        mock_ctx.state = {}
        mock_ctx._invocation_context = None

        tool_config = {"key": "value"}
        facade = ToolContextFacade(mock_ctx, tool_config=tool_config)

        assert facade._tool_config == tool_config
        assert facade.get_config("key") == "value"

    def test_init_without_tool_config(self):
        """Test initialization without tool configuration."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        mock_ctx = Mock()
        mock_ctx.state = {}
        mock_ctx._invocation_context = None

        facade = ToolContextFacade(mock_ctx)

        assert facade._tool_config == {}
        assert facade.get_config("any_key") is None

    def test_init_caches_are_empty(self):
        """Test that caches are empty on initialization."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        mock_ctx = Mock()
        mock_ctx.state = {}
        mock_ctx._invocation_context = None

        facade = ToolContextFacade(mock_ctx)

        assert facade._session_id is None
        assert facade._user_id is None
        assert facade._app_name is None
        assert facade._artifact_service is None
        assert facade._host_component is None
        assert facade._host_component_resolved is False


class TestToolContextFacadeRepr:
    """Tests for ToolContextFacade string representation."""

    def test_repr(self):
        """Test __repr__ method."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        mock_ctx = Mock()
        mock_ctx.state = {}

        mock_inv_context = Mock()
        mock_inv_context.artifact_service = None
        mock_inv_context.app_name = "MyApp"
        mock_inv_context.user_id = "user1"

        mock_ctx._invocation_context = mock_inv_context

        with patch('solace_agent_mesh.agent.utils.tool_context_facade.get_original_session_id', return_value="sess1"):
            facade = ToolContextFacade(mock_ctx)

            repr_str = repr(facade)

            assert "MyApp" in repr_str
            assert "user1" in repr_str
            assert "sess1" in repr_str


class TestToolContextFacadeErrorHandling:
    """Tests for error handling in ToolContextFacade."""

    def test_context_extraction_failure(self):
        """Test graceful handling when context extraction fails."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        mock_ctx = Mock()
        mock_ctx.state = {}
        # Simulate AttributeError when accessing _invocation_context
        mock_ctx._invocation_context = Mock()
        mock_ctx._invocation_context.artifact_service = Mock(side_effect=AttributeError("No artifact_service"))

        facade = ToolContextFacade(mock_ctx)

        # Should not raise, should return empty string
        # The _ensure_context will catch AttributeError
        with patch.object(mock_ctx, '_invocation_context', None):
            facade._session_id = None  # Reset cache
            # This should handle the error gracefully
            assert facade.session_id == ""

    def test_host_component_extraction_failure(self):
        """Test graceful handling when host_component extraction fails."""
        from solace_agent_mesh.agent.utils import ToolContextFacade

        mock_ctx = Mock()
        mock_ctx.state = {"a2a_context": {"logical_task_id": "task-123"}}

        # Make accessing _invocation_context raise an exception
        type(mock_ctx)._invocation_context = property(lambda self: (_ for _ in ()).throw(Exception("Access denied")))

        facade = ToolContextFacade(mock_ctx)

        # Should return False, not raise
        result = facade.send_status("Test")

        assert result is False
        assert facade._host_component_resolved is True
        assert facade._host_component is None
