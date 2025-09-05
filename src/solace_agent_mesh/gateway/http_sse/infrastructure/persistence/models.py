from sqlalchemy import Column, DateTime, ForeignKey, String, Text, JSON
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class SessionModel(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    user_id = Column(String, nullable=False)
    agent_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    messages = relationship(
        "MessageModel", back_populates="session", cascade="all, delete-orphan"
    )


class MessageModel(Base):
    __tablename__ = "chat_messages"
    id = Column(String, primary_key=True)
    session_id = Column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    sender_type = Column(String(50))
    sender_name = Column(String(255))
    session = relationship("SessionModel", back_populates="messages")


class AgentCardModel(Base):
    __tablename__ = "agent_cards"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    description = Column(Text, nullable=True)
    default_input_modes = Column(JSON, nullable=True)
    default_output_modes = Column(JSON, nullable=True)
    agent = relationship("AgentModel", back_populates="agent_card", uselist=False)


class AgentModel(Base):
    __tablename__ = "agents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name = Column(String, nullable=False)
    prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    agent_card_id = Column(UUID(as_uuid=True), ForeignKey("agent_cards.id"), nullable=False)
    agent_card = relationship("AgentCardModel", back_populates="agent")
