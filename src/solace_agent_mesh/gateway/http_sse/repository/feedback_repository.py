"""
Feedback repository implementation using SQLAlchemy.
"""

from sqlalchemy.orm import Session as DBSession

from .entities import Feedback
from .interfaces import IFeedbackRepository
from .models import FeedbackModel


class FeedbackRepository(IFeedbackRepository):
    """SQLAlchemy implementation of feedback repository."""

    def __init__(self, db: DBSession):
        self.db = db

    def save(self, feedback: Feedback) -> Feedback:
        """Save feedback."""
        model = FeedbackModel(
            id=feedback.id,
            session_id=feedback.session_id,
            task_id=feedback.task_id,
            user_id=feedback.user_id,
            rating=feedback.rating,
            comment=feedback.comment,
            created_time=feedback.created_time,
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def _model_to_entity(self, model: FeedbackModel) -> Feedback:
        """Convert SQLAlchemy model to domain entity."""
        return Feedback.model_validate(model)
