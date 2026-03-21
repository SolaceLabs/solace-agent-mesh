"""
SQLAlchemy model for per-user project pin preferences.

Each row represents a single user's decision to pin a specific project.
This replaces the global `is_pinned` column on the projects table so that
each user (owner or shared collaborator) can independently pin/unpin a project
without affecting anyone else's view.
"""

from sqlalchemy import Column, String, BigInteger, UniqueConstraint

from .base import Base


class ProjectUserPinModel(Base):
    """
    SQLAlchemy model for per-user project pin state.

    Columns:
        id         – surrogate primary key (UUID string)
        project_id – FK to projects.id (not enforced at DB level to avoid
                     cross-schema issues, but logically required)
        user_id    – the user who pinned the project (email / user identifier)
        pinned_at  – epoch milliseconds when the pin was created
    """

    __tablename__ = "project_user_pins"

    id = Column(String, primary_key=True)
    project_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    pinned_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_user_pin"),
    )
