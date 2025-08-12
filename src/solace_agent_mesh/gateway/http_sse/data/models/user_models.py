"""
User domain models moved from the original models.py file.
"""

from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base_models import Base


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    info = Column(Text)  # Storing user info as a JSON string
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "info": self.info,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }