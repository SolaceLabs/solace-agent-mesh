from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
Base = declarative_base()

class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    user_id = Column(String, nullable=True)  # None for global projects
    description = Column(String, nullable=True)
    system_prompt = Column(Text, nullable=True)
    is_global = Column(Boolean, default=False)
    template_id = Column(String, ForeignKey("projects.id"), nullable=True)  # Links to original template
    created_by_user_id = Column(String, nullable=False)  # Who created this project
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    sessions = relationship(
        "SessionModel", back_populates="project", cascade="all, delete-orphan"
    )

class SessionModel(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    user_id = Column(String, nullable=False)  # Simple string field, no foreign key
    agent_id = Column(String, nullable=True)
    project_id = Column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    project = relationship("Project", back_populates="sessions")
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
    sender_type = Column(String(50))  # 'user' or 'llm'
    sender_name = Column(String(255))
    session = relationship("SessionModel", back_populates="messages")
