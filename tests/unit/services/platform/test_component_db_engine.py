"""Tests for PlatformServiceComponent.get_db_engine() method."""

from unittest.mock import MagicMock, patch


class TestPlatformServiceComponentGetDbEngine:
    """Tests for get_db_engine method."""

    @patch("solace_agent_mesh.services.platform.component.SamComponentBase.__init__")
    def test_get_db_engine_returns_engine_when_session_local_exists(self, mock_init):
        """When PlatformSessionLocal is initialized, get_db_engine returns the bound engine."""
        mock_init.return_value = None

        from solace_agent_mesh.services.platform.api import dependencies
        from solace_agent_mesh.services.platform.component import (
            PlatformServiceComponent,
        )

        component = object.__new__(PlatformServiceComponent)

        mock_engine = MagicMock()
        original_session_local = dependencies.PlatformSessionLocal
        dependencies.PlatformSessionLocal = MagicMock()
        dependencies.PlatformSessionLocal.kw = {"bind": mock_engine}

        try:
            result = component.get_db_engine()
            assert result is mock_engine
        finally:
            dependencies.PlatformSessionLocal = original_session_local

    @patch("solace_agent_mesh.services.platform.component.SamComponentBase.__init__")
    def test_get_db_engine_returns_none_when_session_local_is_none(self, mock_init):
        """When PlatformSessionLocal is None, get_db_engine returns None."""
        mock_init.return_value = None

        from solace_agent_mesh.services.platform.api import dependencies
        from solace_agent_mesh.services.platform.component import (
            PlatformServiceComponent,
        )

        component = object.__new__(PlatformServiceComponent)

        original_session_local = dependencies.PlatformSessionLocal
        dependencies.PlatformSessionLocal = None

        try:
            result = component.get_db_engine()
            assert result is None
        finally:
            dependencies.PlatformSessionLocal = original_session_local
