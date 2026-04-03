"""
Unit tests for _determine_scheduler_enabled in config.py router.
"""
import pytest
from unittest.mock import MagicMock

from solace_agent_mesh.gateway.http_sse.routers.config import (
    _determine_scheduler_enabled,
)


class TestDetermineSchedulerEnabled:
    """Tests for _determine_scheduler_enabled function."""

    def test_disabled_when_session_type_is_not_sql(self):
        """Scheduler requires SQL persistence; memory session type should return False."""
        mock_component = MagicMock()
        mock_component.get_config.side_effect = lambda k, d=None: (
            {"type": "memory"} if k == "session_service" else d
        )

        result = _determine_scheduler_enabled(mock_component, {}, "[TEST]")

        assert result is False

    def test_disabled_when_no_scheduler_config(self):
        """Missing scheduler_service config section should return False."""
        mock_component = MagicMock()
        mock_component.get_config.side_effect = lambda k, d=None: (
            {"type": "sql"} if k == "session_service"
            else "not-a-dict" if k == "scheduler_service"
            else d
        )

        result = _determine_scheduler_enabled(mock_component, {}, "[TEST]")

        assert result is False

    def test_disabled_when_scheduler_enabled_is_false(self):
        """Scheduler config present but enabled=false should return False."""
        mock_component = MagicMock()
        mock_component.get_config.side_effect = lambda k, d=None: (
            {"type": "sql"} if k == "session_service"
            else {"enabled": False} if k == "scheduler_service"
            else d
        )

        result = _determine_scheduler_enabled(mock_component, {}, "[TEST]")

        assert result is False

    def test_enabled_when_sql_and_scheduler_enabled(self):
        """SQL session type + scheduler_service.enabled=true should return True."""
        mock_component = MagicMock()
        mock_component.get_config.side_effect = lambda k, d=None: (
            {"type": "sql"} if k == "session_service"
            else {"enabled": True} if k == "scheduler_service"
            else d
        )

        result = _determine_scheduler_enabled(mock_component, {}, "[TEST]")

        assert result is True
