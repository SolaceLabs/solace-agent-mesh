"""Unit tests for DataRetentionService artifact cleanup (Approach B)."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from solace_agent_mesh.gateway.http_sse.services.data_retention_service import DataRetentionService


class TestDataRetentionServiceArtifactCleanup:
    @pytest.fixture
    def base_config(self):
        return {
            "enabled": True,
            "cleanup_tasks": False,
            "cleanup_feedback": False,
            "cleanup_sse_events": False,
            "task_retention_days": 90,
            "feedback_retention_days": 90,
            "sse_event_retention_days": 30,
            "conversion_cache_retention_hours": 24,
            "cleanup_interval_hours": 24,
            "batch_size": 1000,
        }

    def test_artifact_cleanup_disabled_when_retention_days_is_none(self, base_config):
        config = dict(base_config)
        config["artifact_retention_days"] = None

        service = DataRetentionService(session_factory=Mock(), config=config, artifact_service=AsyncMock())

        with patch.object(service, "_cleanup_expired_session_artifacts", new_callable=AsyncMock) as cleanup_mock:
            service.cleanup_old_data()
            cleanup_mock.assert_not_called()

    def test_artifact_cleanup_skipped_when_retention_days_is_zero(self, base_config):
        config = dict(base_config)
        config["artifact_retention_days"] = 0

        service = DataRetentionService(session_factory=Mock(), config=config, artifact_service=AsyncMock())

        assert service.config["artifact_retention_days"] is None

    @pytest.mark.asyncio
    async def test_artifact_cleanup_queries_expired_sessions_with_cutoff_timestamp(self, base_config):
        config = dict(base_config)
        config["artifact_retention_days"] = 10

        mock_db = Mock()
        session_factory = Mock(return_value=mock_db)
        service = DataRetentionService(session_factory=session_factory, config=config, artifact_service=AsyncMock())

        with patch("solace_agent_mesh.gateway.http_sse.services.data_retention_service.now_epoch_ms", return_value=1_000_000):
            with patch("solace_agent_mesh.gateway.http_sse.services.data_retention_service.SessionRepository") as repo_cls:
                repo = Mock()
                repo.find_sessions_older_than.return_value = []
                repo_cls.return_value = repo

                await service._cleanup_expired_session_artifacts(10)

                expected_cutoff = 1_000_000 - (10 * 24 * 60 * 60 * 1000)
                repo.find_sessions_older_than.assert_called_once_with(mock_db, expected_cutoff)

    @pytest.mark.asyncio
    async def test_artifact_cleanup_calls_delete_for_each_expired_session(self, base_config):
        config = dict(base_config)
        config["artifact_retention_days"] = 7

        session_factory = Mock(return_value=Mock())
        artifact_service = AsyncMock()
        artifact_service.delete_session_artifacts = AsyncMock(side_effect=[2, 3])
        service = DataRetentionService(session_factory=session_factory, config=config, artifact_service=artifact_service)

        old_sessions = [
            Mock(id="s1", user_id="u1"),
            Mock(id="s2", user_id="u2"),
        ]

        with patch("solace_agent_mesh.gateway.http_sse.services.data_retention_service.SessionRepository") as repo_cls:
            repo = Mock()
            repo.find_sessions_older_than.return_value = old_sessions
            repo_cls.return_value = repo

            deleted_total = await service._cleanup_expired_session_artifacts(7)

        assert deleted_total == 5
        assert artifact_service.delete_session_artifacts.await_count == 2

    @pytest.mark.asyncio
    async def test_artifact_cleanup_handles_exceptions_per_session(self, base_config):
        config = dict(base_config)
        config["artifact_retention_days"] = 7

        session_factory = Mock(return_value=Mock())
        artifact_service = AsyncMock()
        artifact_service.delete_session_artifacts = AsyncMock(side_effect=[Exception("boom"), 4])
        service = DataRetentionService(session_factory=session_factory, config=config, artifact_service=artifact_service)

        old_sessions = [
            Mock(id="s1", user_id="u1"),
            Mock(id="s2", user_id="u2"),
        ]

        with patch("solace_agent_mesh.gateway.http_sse.services.data_retention_service.SessionRepository") as repo_cls:
            repo = Mock()
            repo.find_sessions_older_than.return_value = old_sessions
            repo_cls.return_value = repo

            deleted_total = await service._cleanup_expired_session_artifacts(7)

        assert deleted_total == 4

    @pytest.mark.asyncio
    async def test_artifact_cleanup_not_called_when_artifact_service_unavailable(self, base_config):
        config = dict(base_config)
        config["artifact_retention_days"] = 7

        service = DataRetentionService(session_factory=Mock(return_value=Mock()), config=config, artifact_service=None)

        deleted_total = await service._cleanup_expired_session_artifacts(7)

        assert deleted_total == 0

    @pytest.mark.asyncio
    async def test_artifact_cleanup_not_called_when_session_factory_unavailable(self, base_config):
        config = dict(base_config)
        config["artifact_retention_days"] = 7

        service = DataRetentionService(session_factory=None, config=config, artifact_service=AsyncMock())

        deleted_total = await service._cleanup_expired_session_artifacts(7)

        assert deleted_total == 0

    def test_artifact_retention_days_validation_minimum_enforced(self, base_config):
        config = dict(base_config)
        config["artifact_retention_days"] = -1

        service = DataRetentionService(session_factory=Mock(), config=config, artifact_service=AsyncMock())

        assert service.config["artifact_retention_days"] == 1

    @pytest.mark.asyncio
    async def test_artifact_cleanup_returns_total_count_of_deleted_artifacts(self, base_config):
        config = dict(base_config)
        config["artifact_retention_days"] = 7

        session_factory = Mock(return_value=Mock())
        artifact_service = AsyncMock()
        artifact_service.delete_session_artifacts = AsyncMock(side_effect=[1, 2, 3])
        service = DataRetentionService(session_factory=session_factory, config=config, artifact_service=artifact_service)

        old_sessions = [
            Mock(id="s1", user_id="u1"),
            Mock(id="s2", user_id="u1"),
            Mock(id="s3", user_id="u2"),
        ]

        with patch("solace_agent_mesh.gateway.http_sse.services.data_retention_service.SessionRepository") as repo_cls:
            repo = Mock()
            repo.find_sessions_older_than.return_value = old_sessions
            repo_cls.return_value = repo

            deleted_total = await service._cleanup_expired_session_artifacts(7)

        assert deleted_total == 6
