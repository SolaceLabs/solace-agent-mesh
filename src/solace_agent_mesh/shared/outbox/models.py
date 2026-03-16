from pydantic import BaseModel
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from sqlalchemy import BigInteger, Column, Index, Integer, String, Text

from ..database import Base, OptimizedUUID, generate_uuidv7


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"

    id = Column(OptimizedUUID, primary_key=True, default=generate_uuidv7)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(36), nullable=False)
    event_type = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    payload = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    next_retry_at = Column(BigInteger, nullable=False, default=0)
    created_time = Column(BigInteger, nullable=False, default=now_epoch_ms)
    updated_time = Column(BigInteger, nullable=False, default=now_epoch_ms, onupdate=now_epoch_ms)

    __table_args__ = (
        Index("ix_outbox_status_retry", "status", "next_retry_at"),
        Index("ix_outbox_entity", "entity_type", "entity_id", "event_type", "status"),
        Index("ix_outbox_created_time", "created_time"),
        Index("ix_outbox_updated_time", "updated_time"),
    )


class CreateOutboxEventModel(BaseModel):
    entity_type: str
    entity_id: str
    event_type: str
    payload: str | None = None
    status: str = "pending"
    next_retry_at: int = 0


class UpdateOutboxEventModel(BaseModel):
    status: str | None = None
    error_message: str | None = None
    retry_count: int | None = None
    next_retry_at: int | None = None
