"""
Unit tests for DataRetentionService.

Tests configuration validation, cleanup logic, and error handling
for the automatic data retention service that removes old tasks and feedback.
"""

from unittest.mock import Mock, patch

from solace_agent_mesh.gateway.http_sse.services.data_retention_service import (
    DataRetentionService,
)


class TestConfigurationValidation:
    """Tests for configuration validation."""

    def test_minimum_task_retention_days_enforced(self, caplog):
        """Test that task_retention_days below minimum is corrected to minimum."""
        # Arrange
        config = {
            "task_retention_days": 0,  # Below minimum of 1
            "enabled": True,
        }

        # Act
        with caplog.at_level("WARNING"):
            service = DataRetentionService(session_factory=None, config=config)

        # Assert
        assert (
            service.config["task_retention_days"]
            == DataRetentionService.MIN_RETENTION_DAYS
        )
        assert "task_retention_days" in caplog.text
        assert "below minimum" in caplog.text.lower()

    def test_minimum_feedback_retention_days_enforced(self, caplog):
        """Test that feedback_retention_days below minimum is corrected to minimum."""
        # Arrange
        config = {
            "feedback_retention_days": 0,  # Below minimum of 1
            "enabled": True,
        }

        # Act
        with caplog.at_level("WARNING"):
            service = DataRetentionService(session_factory=None, config=config)

        # Assert
        assert (
            service.config["feedback_retention_days"]
            == DataRetentionService.MIN_RETENTION_DAYS
        )
        assert "feedback_retention_days" in caplog.text
        assert "below minimum" in caplog.text.lower()

    def test_minimum_cleanup_interval_enforced(self, caplog):
        """Test that cleanup_interval_hours below minimum is corrected to minimum."""
        # Arrange
        config = {
            "cleanup_interval_hours": 0,  # Below minimum of 1
            "enabled": True,
        }

        # Act
        with caplog.at_level("WARNING"):
            service = DataRetentionService(session_factory=None, config=config)

        # Assert
        assert (
            service.config["cleanup_interval_hours"]
            == DataRetentionService.MIN_CLEANUP_INTERVAL_HOURS
        )
        assert "cleanup_interval_hours" in caplog.text
        assert "below minimum" in caplog.text.lower()

    def test_batch_size_minimum_enforced(self, caplog):
        """Test that batch_size below minimum is corrected to minimum."""
        # Arrange
        config = {
            "batch_size": 0,  # Below minimum of 1
            "enabled": True,
        }

        # Act
        with caplog.at_level("WARNING"):
            service = DataRetentionService(session_factory=None, config=config)

        # Assert
        assert service.config["batch_size"] == DataRetentionService.MIN_BATCH_SIZE
        assert "batch_size" in caplog.text
        assert "below minimum" in caplog.text.lower()

    def test_batch_size_maximum_enforced(self, caplog):
        """Test that batch_size above maximum is corrected to maximum."""
        # Arrange
        config = {
            "batch_size": 20000,  # Above maximum of 10000
            "enabled": True,
        }

        # Act
        with caplog.at_level("WARNING"):
            service = DataRetentionService(session_factory=None, config=config)

        # Assert
        assert service.config["batch_size"] == DataRetentionService.MAX_BATCH_SIZE
        assert "batch_size" in caplog.text
        assert "exceeds maximum" in caplog.text.lower()

    def test_valid_configuration_accepted(self, caplog):
        """Test that valid configuration values are accepted without warnings."""
        # Arrange
        config = {
            "enabled": True,
            "task_retention_days": 90,
            "feedback_retention_days": 60,
            "cleanup_interval_hours": 24,
            "batch_size": 1000,
        }

        # Act
        with caplog.at_level("WARNING"):
            service = DataRetentionService(session_factory=None, config=config)

        # Assert - all values should remain unchanged
        assert service.config["task_retention_days"] == 90
        assert service.config["feedback_retention_days"] == 60
        assert service.config["cleanup_interval_hours"] == 24
        assert service.config["batch_size"] == 1000

        # No warnings should be logged
        assert len(caplog.records) == 0


class TestCleanupLogic:
    """Tests for cleanup logic and behavior."""

    def test_cleanup_skipped_when_disabled(self, caplog):
        """Test that cleanup_old_data returns early when service is disabled."""
        # Arrange
        config = {
            "enabled": False,
            "task_retention_days": 90,
            "feedback_retention_days": 90,
        }

        mock_session_factory = Mock()
        service = DataRetentionService(
            session_factory=mock_session_factory, config=config
        )

        # Act
        with caplog.at_level("WARNING"):
            service.cleanup_old_data()

        # Assert
        assert "disabled via configuration" in caplog.text.lower()
        # Session factory should never be called since cleanup is disabled
        mock_session_factory.assert_not_called()

    def test_cleanup_skipped_without_session_factory(self, caplog):
        """Test that cleanup_old_data returns early when session_factory is None."""
        # Arrange
        config = {
            "enabled": True,
            "task_retention_days": 90,
            "feedback_retention_days": 90,
        }

        service = DataRetentionService(session_factory=None, config=config)

        # Act
        with caplog.at_level("WARNING"):
            service.cleanup_old_data()

        # Assert
        assert "no database session factory" in caplog.text.lower()

    @patch(
        "solace_agent_mesh.gateway.http_sse.services.data_retention_service.now_epoch_ms"
    )
    def test_cutoff_time_calculation_for_tasks(self, mock_now):
        """Test that cutoff time is correctly calculated for task cleanup."""
        # Arrange
        # Set current time to a fixed point: 2025-03-01 00:00:00 UTC
        # This is 1709251200000 milliseconds since epoch
        fixed_now_ms = 1709251200000
        mock_now.return_value = fixed_now_ms

        config = {
            "enabled": True,
            "task_retention_days": 30,
            "batch_size": 100,
        }

        mock_session = Mock()
        mock_session_factory = Mock(return_value=mock_session)

        # Mock the repository to capture the cutoff time
        captured_cutoff = {}

        def mock_delete_tasks(*args, **kwargs):
            # Handle the call signature with db as first parameter
            if len(args) >= 3:
                _db, cutoff_time_ms, batch_size = args[0], args[1], args[2]
            else:
                cutoff_time_ms, batch_size = args[0], args[1]

            captured_cutoff["cutoff_time_ms"] = cutoff_time_ms
            captured_cutoff["batch_size"] = batch_size
            return 0  # No tasks deleted

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.data_retention_service.TaskRepository"
        ) as mock_task_repo_class:
            mock_repo = Mock()
            mock_repo.delete_tasks_older_than = Mock(side_effect=mock_delete_tasks)
            mock_task_repo_class.return_value = mock_repo

            service = DataRetentionService(
                session_factory=mock_session_factory, config=config
            )

            # Act
            service.cleanup_old_data()

        # Assert
        # Expected cutoff: now - 30 days = 1709251200000 - (30 * 24 * 60 * 60 * 1000)
        # = 1709251200000 - 2592000000 = 1706659200000
        expected_cutoff = fixed_now_ms - (30 * 24 * 60 * 60 * 1000)

        assert "cutoff_time_ms" in captured_cutoff
        assert captured_cutoff["cutoff_time_ms"] == expected_cutoff
        assert captured_cutoff["batch_size"] == 100

        # Verify the repository method was called
        mock_repo.delete_tasks_older_than.assert_called_once()

    @patch(
        "solace_agent_mesh.gateway.http_sse.services.data_retention_service.now_epoch_ms"
    )
    def test_cutoff_time_calculation_for_feedback(self, mock_now):
        """Test that cutoff time is correctly calculated for feedback cleanup."""
        # Arrange
        # Set current time to a fixed point: 2025-03-01 00:00:00 UTC
        fixed_now_ms = 1709251200000
        mock_now.return_value = fixed_now_ms

        config = {
            "enabled": True,
            "feedback_retention_days": 60,
            "batch_size": 100,
        }

        mock_session = Mock()
        mock_session_factory = Mock(return_value=mock_session)

        # Mock the repository to capture the cutoff time
        captured_cutoff = {}

        def mock_delete_feedback(*args, **kwargs):
            # Handle the call signature with db as first parameter
            if len(args) >= 3:
                _db, cutoff_time_ms, batch_size = args[0], args[1], args[2]
            else:
                cutoff_time_ms, batch_size = args[0], args[1]

            captured_cutoff["cutoff_time_ms"] = cutoff_time_ms
            captured_cutoff["batch_size"] = batch_size
            return 0  # No feedback deleted

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.data_retention_service.FeedbackRepository"
        ) as mock_feedback_repo_class:
            mock_repo = Mock()
            mock_repo.delete_feedback_older_than = Mock(
                side_effect=mock_delete_feedback
            )
            mock_feedback_repo_class.return_value = mock_repo

            service = DataRetentionService(
                session_factory=mock_session_factory, config=config
            )

            # Act
            service.cleanup_old_data()

        # Assert
        # Expected cutoff: now - 60 days = 1709251200000 - (60 * 24 * 60 * 60 * 1000)
        # = 1709251200000 - 5184000000 = 1704067200000
        expected_cutoff = fixed_now_ms - (60 * 24 * 60 * 60 * 1000)

        assert "cutoff_time_ms" in captured_cutoff
        assert captured_cutoff["cutoff_time_ms"] == expected_cutoff
        assert captured_cutoff["batch_size"] == 100

        # Verify the repository method was called
        mock_repo.delete_feedback_older_than.assert_called_once()
