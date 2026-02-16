"""
SQLAlchemy ORM models for stateless agent checkpointing.

These tables live in the ADK session database and store task coordination
state when an agent is paused waiting for peer responses. This enables
any instance of the same agent to resume the task.
"""

from sqlalchemy import Column, String, Integer, Float, Text, Index, ForeignKey
from sqlalchemy.orm import declarative_base

CheckpointBase = declarative_base()


class AgentPausedTask(CheckpointBase):
    """Checkpointed task state for paused agents waiting on peer responses."""

    __tablename__ = "agent_paused_tasks"

    logical_task_id = Column(String, primary_key=True)
    agent_name = Column(String, nullable=False, index=True)
    a2a_context = Column(Text, nullable=False)  # JSON
    effective_session_id = Column(String, nullable=True)
    user_id = Column(String, nullable=True)
    current_invocation_id = Column(String, nullable=True)
    produced_artifacts = Column(Text, nullable=True)  # JSON
    artifact_signals_to_return = Column(Text, nullable=True)  # JSON
    response_buffer = Column(Text, nullable=True)
    flags = Column(Text, nullable=True)  # JSON
    security_context = Column(Text, nullable=True)  # JSON
    token_usage = Column(Text, nullable=True)  # JSON
    checkpointed_at = Column(Float, nullable=False)


class AgentPeerSubTask(CheckpointBase):
    """Pending peer agent calls with timeout deadlines."""

    __tablename__ = "agent_peer_sub_tasks"

    sub_task_id = Column(String, primary_key=True)
    logical_task_id = Column(
        String,
        ForeignKey("agent_paused_tasks.logical_task_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invocation_id = Column(String, nullable=False, index=True)
    correlation_data = Column(Text, nullable=False)  # JSON
    timeout_deadline = Column(Float, nullable=True)
    created_at = Column(Float, nullable=False)

    __table_args__ = (
        Index("ix_agent_peer_sub_tasks_timeout", "timeout_deadline"),
    )


class AgentParallelInvocation(CheckpointBase):
    """Tracks completion of parallel peer calls within an invocation."""

    __tablename__ = "agent_parallel_invocations"

    logical_task_id = Column(
        String,
        ForeignKey("agent_paused_tasks.logical_task_id", ondelete="CASCADE"),
        primary_key=True,
    )
    invocation_id = Column(String, primary_key=True)
    total_expected = Column(Integer, nullable=False)
    completed_count = Column(Integer, nullable=False, default=0)
    results = Column(Text, nullable=False, default="[]")  # JSON array
