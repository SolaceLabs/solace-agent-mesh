"""Unit tests for SessionService artifact cleanup (Approach A)."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from solace_agent_mesh.gateway.http_sse.services.session_service import SessionService


class TestSessionServiceArtifactCleanup:
    """Test artifact cleanup in delete_session_with_notifications."""

    def setup_method(self):
        self.mock_component = Mock()
        self.service = SessionService(component=self.mock_component)
        self.mock_db = Mock()
        self.session_id = "session-123"
        self.user_id = "user-456"

    @pytest.mark.asyncio
    async def test_delete_session_calls_artifact_service_with_correct_params(self):
        mock_session = Mock()
        mock_session.id = self.session_id
        mock_session.user_id = self.user_id
        mock_session.agent_id = None
        mock_session.can_be_deleted_by_user.return_value = True

        mock_artifact_service = AsyncMock()
        mock_artifact_service.delete_session_artifacts = AsyncMock(return_value=5)
        self.mock_component.get_shared_artifact_service.return_value = mock_artifact_service

        mock_repository = Mock()
        mock_repository.delete.return_value = True
        mock_repository.find_user_session.return_value = mock_session

        with patch.object(self.service, "_get_repositories", return_value=mock_repository):
            result = await self.service.delete_session_with_notifications(
                self.mock_db, self.session_id, self.user_id
            )

        assert result is True
        mock_artifact_service.delete_session_artifacts.assert_called_once_with(
            user_id=self.user_id,
            session_id=self.session_id,
        )

    @pytest.mark.asyncio
    async def test_delete_session_continues_if_artifact_service_raises_exception(self):
        mock_session = Mock()
        mock_session.id = self.session_id
        mock_session.user_id = self.user_id
        mock_session.agent_id = None
        mock_session.can_be_deleted_by_user.return_value = True

        mock_artifact_service = AsyncMock()
        mock_artifact_service.delete_session_artifacts = AsyncMock(side_effect=Exception("Storage error"))
        self.mock_component.get_shared_artifact_service.return_value = mock_artifact_service

        mock_repository = Mock()
        mock_repository.delete.return_value = True
        mock_repository.find_user_session.return_value = mock_session

        with patch.object(self.service, "_get_repositories", return_value=mock_repository):
            result = await self.service.delete_session_with_notifications(
                self.mock_db, self.session_id, self.user_id
            )

        assert result is True
        mock_repository.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_session_without_artifact_service_configured(self, caplog):
        mock_session = Mock()
        mock_session.id = self.session_id
        mock_session.user_id = self.user_id
        mock_session.agent_id = None
        mock_session.can_be_deleted_by_user.return_value = True

        self.mock_component.get_shared_artifact_service.return_value = None

        mock_repository = Mock()
        mock_repository.delete.return_value = True
        mock_repository.find_user_session.return_value = mock_session

        with patch.object(self.service, "_get_repositories", return_value=mock_repository):
            with caplog.at_level("DEBUG"):
                result = await self.service.delete_session_with_notifications(
                    self.mock_db, self.session_id, self.user_id
                )

        assert result is True
        assert "Artifact service not configured" in caplog.text

    @pytest.mark.asyncio
    async def test_delete_session_logs_artifact_deletion_success(self, caplog):
        mock_session = Mock()
        mock_session.id = self.session_id
        mock_session.user_id = self.user_id
        mock_session.agent_id = None
        mock_session.can_be_deleted_by_user.return_value = True

        mock_artifact_service = AsyncMock()
        mock_artifact_service.delete_session_artifacts = AsyncMock(return_value=10)
        self.mock_component.get_shared_artifact_service.return_value = mock_artifact_service

        mock_repository = Mock()
        mock_repository.delete.return_value = True
        mock_repository.find_user_session.return_value = mock_session

        with patch.object(self.service, "_get_repositories", return_value=mock_repository):
            with caplog.at_level("INFO"):
                result = await self.service.delete_session_with_notifications(
                    self.mock_db, self.session_id, self.user_id
                )

        assert result is True
        assert "Deleted 10 artifacts" in caplog.text

    @pytest.mark.asyncio
    async def test_delete_session_preserves_user_artifacts(self):
        mock_session = Mock()
        mock_session.id = self.session_id
        mock_session.user_id = self.user_id
        mock_session.agent_id = None
        mock_session.can_be_deleted_by_user.return_value = True

        mock_artifact_service = AsyncMock()
        mock_artifact_service.delete_session_artifacts = AsyncMock(return_value=5)
        self.mock_component.get_shared_artifact_service.return_value = mock_artifact_service

        mock_repository = Mock()
        mock_repository.delete.return_value = True
        mock_repository.find_user_session.return_value = mock_session

        with patch.object(self.service, "_get_repositories", return_value=mock_repository):
            result = await self.service.delete_session_with_notifications(
                self.mock_db, self.session_id, self.user_id
            )

        assert result is True
        call_kwargs = mock_artifact_service.delete_session_artifacts.call_args[1]
        assert call_kwargs["session_id"] == self.session_id
