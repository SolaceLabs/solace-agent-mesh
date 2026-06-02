"""Unit tests for SessionService.update_session_agent method."""

import pytest
from unittest.mock import Mock, patch
from solace_agent_mesh.gateway.http_sse.services.session_service import SessionService


class TestSessionServiceUpdateAgent:
    """Test the update_session_agent backfill method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_component = Mock()
        self.service = SessionService(component=self.mock_component)
        self.mock_db = Mock()
        self.session_id = "test-session-123"
        self.user_id = "user-123"
        self.agent_id = "TestAgent"

    def test_backfills_agent_and_delegates_to_repository(self):
        """Backfill delegates to the repo with the right args and returns True."""
        mock_repository = Mock()
        mock_repository.update_agent.return_value = True

        with patch.object(self.service, "_get_repositories", return_value=mock_repository):
            result = self.service.update_session_agent(
                db=self.mock_db,
                session_id=self.session_id,
                user_id=self.user_id,
                agent_id=self.agent_id,
            )

        mock_repository.update_agent.assert_called_once_with(
            self.mock_db, self.session_id, self.user_id, self.agent_id
        )
        assert result is True

    def test_returns_false_when_no_row_updated(self):
        """When the repo updates no row (missing or already had agent), returns False."""
        mock_repository = Mock()
        mock_repository.update_agent.return_value = False

        with patch.object(self.service, "_get_repositories", return_value=mock_repository):
            result = self.service.update_session_agent(
                db=self.mock_db,
                session_id=self.session_id,
                user_id=self.user_id,
                agent_id=self.agent_id,
            )

        assert result is False

    @pytest.mark.parametrize("invalid_session_id", [None, "", "   ", "null", "undefined"])
    def test_raises_on_invalid_session_id(self, invalid_session_id):
        """Invalid session IDs are rejected before touching the repository."""
        mock_repository = Mock()
        with patch.object(self.service, "_get_repositories", return_value=mock_repository):
            with pytest.raises(ValueError, match="Invalid session ID"):
                self.service.update_session_agent(
                    db=self.mock_db,
                    session_id=invalid_session_id,
                    user_id=self.user_id,
                    agent_id=self.agent_id,
                )
        mock_repository.update_agent.assert_not_called()

    @pytest.mark.parametrize("invalid_agent_id", [None, "", "   "])
    def test_raises_on_empty_agent_id(self, invalid_agent_id):
        """Empty agent IDs are rejected before touching the repository."""
        mock_repository = Mock()
        with patch.object(self.service, "_get_repositories", return_value=mock_repository):
            with pytest.raises(ValueError, match="Agent ID cannot be empty"):
                self.service.update_session_agent(
                    db=self.mock_db,
                    session_id=self.session_id,
                    user_id=self.user_id,
                    agent_id=invalid_agent_id,
                )
        mock_repository.update_agent.assert_not_called()
