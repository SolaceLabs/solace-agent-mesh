"""
Scheduled Task SQLAlchemy models.
"""

from enum import Enum
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from ...shared import now_epoch_ms
from .base import Base


class ScheduleType(str, Enum):
    """Enum for schedule types"""
    CRON = "cron"
    INTERVAL = "interval"
    ONE_TIME = "one_time"


class ExecutionStatus(str, Enum):
    """Enum for execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ScheduledTaskModel(Base):
    """SQLAlchemy model for scheduled task definitions."""

    __tablename__ = "scheduled_tasks"

    # Primary identification
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Ownership & Multi-tenancy
    namespace = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)  # NULL = namespace-level
    created_by = Column(String, nullable=False)

    # Scheduling Configuration
    schedule_type = Column(
        SQLEnum(ScheduleType), 
        nullable=False,
        index=True
    )
    schedule_expression = Column(String, nullable=False)
    timezone = Column(String, nullable=False, default="UTC")

    # Task Configuration
    target_agent_name = Column(String, nullable=False, index=True)
    task_message = Column(JSON, nullable=False)  # A2A Message parts
    task_metadata = Column(JSON, nullable=True)  # Additional A2A metadata

    # Execution Control
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    max_retries = Column(Integer, nullable=False, default=0)
    retry_delay_seconds = Column(Integer, nullable=False, default=60)
    timeout_seconds = Column(Integer, nullable=False, default=3600)

    # Notification Configuration
    notification_config = Column(JSON, nullable=True)

    # Timestamps (epoch milliseconds)
    created_at = Column(BigInteger, nullable=False, default=now_epoch_ms)
    updated_at = Column(
        BigInteger, 
        nullable=False, 
        default=now_epoch_ms, 
        onupdate=now_epoch_ms
    )
    next_run_at = Column(BigInteger, nullable=True, index=True)
    last_run_at = Column(BigInteger, nullable=True)

    # Soft delete
    deleted_at = Column(BigInteger, nullable=True)
    deleted_by = Column(String, nullable=True)

    # Relationships
    executions = relationship(
        "ScheduledTaskExecutionModel",
        back_populates="scheduled_task",
        cascade="all, delete-orphan",
        order_by="ScheduledTaskExecutionModel.scheduled_for.desc()"
    )


class ScheduledTaskExecutionModel(Base):
    """SQLAlchemy model for individual executions of scheduled tasks."""

    __tablename__ = "scheduled_task_executions"

    # Primary identification
    id = Column(String, primary_key=True)
    scheduled_task_id = Column(
        String, 
        ForeignKey("scheduled_tasks.id"), 
        nullable=False,
        index=True
    )

    # Execution Details
    status = Column(
        SQLEnum(ExecutionStatus), 
        nullable=False, 
        default=ExecutionStatus.PENDING,
        index=True
    )
    a2a_task_id = Column(String, nullable=True, index=True)

    # Timing (epoch milliseconds)
    scheduled_for = Column(BigInteger, nullable=False, index=True)
    started_at = Column(BigInteger, nullable=True)
    completed_at = Column(BigInteger, nullable=True)

    # Results
    result_summary = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)

    # Artifacts & Notifications
    artifacts = Column(JSON, nullable=True)  # List of artifact URIs
    notifications_sent = Column(JSON, nullable=True)  # Track notification delivery

    # Relationships
    scheduled_task = relationship(
        "ScheduledTaskModel", 
        back_populates="executions"
    )


class SchedulerLockModel(Base):
    """SQLAlchemy model for distributed scheduler leader election lock."""

    __tablename__ = "scheduler_locks"

    # Single row lock table
    id = Column(Integer, primary_key=True, default=1)
    
    # Leader information
    leader_id = Column(String, nullable=False)
    leader_namespace = Column(String, nullable=False)
    
    # Lock timing (epoch milliseconds)
    acquired_at = Column(BigInteger, nullable=False)
    expires_at = Column(BigInteger, nullable=False, index=True)
    heartbeat_at = Column(BigInteger, nullable=False)