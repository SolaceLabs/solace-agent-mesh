"""
Service for managing automatic cleanup of old data based on retention policies.
"""

import logging
import time
from typing import Any, Callable, Dict

from sqlalchemy.orm import Session as DBSession

from ..repository.feedback_repository import FeedbackRepository
from ..repository.task_repository import TaskRepository
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms

log = logging.getLogger(__name__)

class DataRetentionService:
    """
    Service for automatically cleaning up old tasks, task events, and feedback
    based on configurable retention policies.
    """

    # Validation constants
    MIN_RETENTION_DAYS = 1
    MIN_CLEANUP_INTERVAL_HOURS = 1
    MIN_BATCH_SIZE = 1
    MAX_BATCH_SIZE = 10000

    def __init__(
        self, session_factory: Callable[[], DBSession] | None, config: Dict[str, Any]
    ):
        """
        Initialize the DataRetentionService.

        Args:
            session_factory: Factory function to create database sessions
            config: Configuration dictionary with retention settings
        """
        self.session_factory = session_factory
        self.config = config
        self.log_identifier = "[DataRetentionService]"

        # Validate and store configuration
        self._validate_config()

        log.info(
            "%s Initialized with task_retention=%d days, feedback_retention=%d days, "
            "cleanup_interval=%d hours, batch_size=%d",
            self.log_identifier,
            self.config.get("task_retention_days"),
            self.config.get("feedback_retention_days"),
            self.config.get("cleanup_interval_hours"),
            self.config.get("batch_size"),
        )

    def _validate_config(self) -> None:
        """
        Validates configuration values and applies safe defaults if needed.
        Logs warnings for invalid values.
        """
        # Validate task retention days
        task_retention = self.config.get("task_retention_days", 90)
        if task_retention < self.MIN_RETENTION_DAYS:
            log.warning(
                "%s task_retention_days (%d) is below minimum (%d days). Using minimum.",
                self.log_identifier,
                task_retention,
                self.MIN_RETENTION_DAYS,
            )
            self.config["task_retention_days"] = self.MIN_RETENTION_DAYS
        else:
            self.config["task_retention_days"] = task_retention

        # Validate feedback retention days
        feedback_retention = self.config.get("feedback_retention_days", 90)
        if feedback_retention < self.MIN_RETENTION_DAYS:
            log.warning(
                "%s feedback_retention_days (%d) is below minimum (%d days). Using minimum.",
                self.log_identifier,
                feedback_retention,
                self.MIN_RETENTION_DAYS,
            )
            self.config["feedback_retention_days"] = self.MIN_RETENTION_DAYS
        else:
            self.config["feedback_retention_days"] = feedback_retention

        # Validate cleanup interval
        cleanup_interval = self.config.get("cleanup_interval_hours", 24)
        if cleanup_interval < self.MIN_CLEANUP_INTERVAL_HOURS:
            log.warning(
                "%s cleanup_interval_hours (%d) is below minimum (%d hours). Using minimum.",
                self.log_identifier,
                cleanup_interval,
                self.MIN_CLEANUP_INTERVAL_HOURS,
            )
            self.config["cleanup_interval_hours"] = self.MIN_CLEANUP_INTERVAL_HOURS
        else:
            self.config["cleanup_interval_hours"] = cleanup_interval

        # Validate batch size
        batch_size = self.config.get("batch_size", 1000)
        if batch_size < self.MIN_BATCH_SIZE:
            log.warning(
                "%s batch_size (%d) is below minimum (%d). Using minimum.",
                self.log_identifier,
                batch_size,
                self.MIN_BATCH_SIZE,
            )
            self.config["batch_size"] = self.MIN_BATCH_SIZE
        elif batch_size > self.MAX_BATCH_SIZE:
            log.warning(
                "%s batch_size (%d) exceeds maximum (%d). Using maximum.",
                self.log_identifier,
                batch_size,
                self.MAX_BATCH_SIZE,
            )
            self.config["batch_size"] = self.MAX_BATCH_SIZE
        else:
            self.config["batch_size"] = batch_size

    def cleanup_old_data(self) -> None:
        """
        Main orchestration method for cleaning up old data.
        Calls cleanup methods for tasks and feedback.
        """
        if not self.config.get("enabled", True):
            log.warning(
                "%s Data retention cleanup is disabled via configuration.",
                self.log_identifier,
            )
            return

        if not self.session_factory:
            log.warning(
                "%s No database session factory available. Skipping cleanup.",
                self.log_identifier,
            )
            return

        log.info("%s Starting data retention cleanup...", self.log_identifier)
        start_time = time.time()

        try:
            # Cleanup old tasks
            task_retention_days = self.config.get("task_retention_days")
            tasks_deleted = self._cleanup_old_tasks(task_retention_days)

            # Cleanup old feedback
            feedback_retention_days = self.config.get("feedback_retention_days")
            feedback_deleted = self._cleanup_old_feedback(feedback_retention_days)

            elapsed_time = time.time() - start_time
            log.info(
                "%s Cleanup completed. Tasks deleted: %d, Feedback deleted: %d, Time taken: %.2f seconds",
                self.log_identifier,
                tasks_deleted,
                feedback_deleted,
                elapsed_time,
            )

        except Exception as e:
            log.error(
                "%s Error during data retention cleanup: %s",
                self.log_identifier,
                e,
                exc_info=True,
            )

    def _cleanup_old_tasks(self, retention_days: int) -> int:
        """
        Deletes tasks (and their events via cascade) older than the retention period.

        Args:
            retention_days: Number of days to retain tasks

        Returns:
            Total number of tasks deleted
        """
        log.info(
            "%s Cleaning up tasks older than %d days...",
            self.log_identifier,
            retention_days,
        )

        # Calculate cutoff time in milliseconds
        cutoff_time_ms = now_epoch_ms() - (retention_days * 24 * 60 * 60 * 1000)
        batch_size = self.config.get("batch_size")

        db = self.session_factory()
        try:
            repo = TaskRepository()
            total_deleted = repo.delete_tasks_older_than(db, cutoff_time_ms, batch_size)

            if total_deleted == 0:
                log.info(
                    "%s No tasks found older than %d days.",
                    self.log_identifier,
                    retention_days,
                )
            else:
                log.info(
                    "%s Deleted %d tasks older than %d days.",
                    self.log_identifier,
                    total_deleted,
                    retention_days,
                )

            return total_deleted

        except Exception as e:
            log.error(
                "%s Error cleaning up old tasks: %s",
                self.log_identifier,
                e,
                exc_info=True,
            )
            db.rollback()
            return 0
        finally:
            db.close()

    def _cleanup_old_feedback(self, retention_days: int) -> int:
        """
        Deletes feedback records older than the retention period.

        Args:
            retention_days: Number of days to retain feedback

        Returns:
            Total number of feedback records deleted
        """
        log.info(
            "%s Cleaning up feedback older than %d days...",
            self.log_identifier,
            retention_days,
        )

        # Calculate cutoff time in milliseconds
        cutoff_time_ms = now_epoch_ms() - (retention_days * 24 * 60 * 60 * 1000)
        batch_size = self.config.get("batch_size")

        db = self.session_factory()
        try:
            repo = FeedbackRepository()
            total_deleted = repo.delete_feedback_older_than(db, cutoff_time_ms, batch_size)

            if total_deleted == 0:
                log.info(
                    "%s No feedback found older than %d days.",
                    self.log_identifier,
                    retention_days,
                )
            else:
                log.info(
                    "%s Deleted %d feedback records older than %d days.",
                    self.log_identifier,
                    total_deleted,
                    retention_days,
                )

            return total_deleted

        except Exception as e:
            log.error(
                "%s Error cleaning up old feedback: %s",
                self.log_identifier,
                e,
                exc_info=True,
            )
            db.rollback()
            return 0
        finally:
            db.close()
