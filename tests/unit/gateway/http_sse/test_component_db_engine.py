"""Tests for WebUIBackendComponent.get_db_engine() method."""

from unittest.mock import MagicMock, patch


class TestWebUIBackendComponentGetDbEngine:
    """Tests for get_db_engine method."""

    @patch("solace_agent_mesh.gateway.http_sse.component.BaseGatewayComponent.__init__")
    def test_get_db_engine_returns_engine_when_session_local_exists(self, mock_init):
        """When SessionLocal is initialized, get_db_engine returns the bound engine."""
        mock_init.return_value = None

        from solace_agent_mesh.gateway.http_sse import dependencies
        from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent

        # Create component without calling __init__
        component = object.__new__(WebUIBackendComponent)

        # Mock the SessionLocal with a bound engine
        mock_engine = MagicMock()
        original_session_local = dependencies.SessionLocal
        dependencies.SessionLocal = MagicMock()
        dependencies.SessionLocal.kw = {"bind": mock_engine}

        try:
            result = component.get_db_engine()
            assert result is mock_engine
        finally:
            dependencies.SessionLocal = original_session_local

    @patch("solace_agent_mesh.gateway.http_sse.component.BaseGatewayComponent.__init__")
    def test_get_db_engine_returns_none_when_session_local_is_none(self, mock_init):
        """When SessionLocal is None, get_db_engine returns None."""
        mock_init.return_value = None

        from solace_agent_mesh.gateway.http_sse import dependencies
        from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent

        component = object.__new__(WebUIBackendComponent)

        original_session_local = dependencies.SessionLocal
        dependencies.SessionLocal = None

        try:
            result = component.get_db_engine()
            assert result is None
        finally:
            dependencies.SessionLocal = original_session_local
