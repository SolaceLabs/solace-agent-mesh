"""
Unit tests for DataRetentionService.

Tests configuration validation, cleanup logic, and error handling
for the automatic data retention service that removes old tasks and feedback.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta, timezone

from solace_agent_mesh.gateway.http_sse.services.data_retention_service import (
    DataRetentionService,
)
from solace_agent_mesh.gateway.http_sse.repository.task_repository import (
    TaskRepository,
)
from solace_agent_mesh.gateway.http_sse.repository.feedback_repository import (
    FeedbackRepository,
)
from solace_agent_mesh.gateway.http_sse.repository.models import (
    TaskModel,
    TaskEventModel,
    FeedbackModel,
)
from solace_agent_mesh.gateway.http_sse.shared import now_epoch_ms
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine


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
        assert service.config["task_retention_days"] == DataRetentionService.MIN_RETENTION_DAYS
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
        assert service.config["feedback_retention_days"] == DataRetentionService.MIN_RETENTION_DAYS
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
        assert service.config["cleanup_interval_hours"] == DataRetentionService.MIN_CLEANUP_INTERVAL_HOURS
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
