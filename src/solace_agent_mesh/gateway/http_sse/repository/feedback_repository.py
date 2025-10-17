"""
Feedback repository implementation using SQLAlchemy.
"""

from sqlalchemy.orm import Session as DBSession

from .entities import Feedback
from .interfaces import IFeedbackRepository
from .models import FeedbackModel


class FeedbackRepository(IFeedbackRepository):
    """SQLAlchemy implementation of feedback repository."""

    def save(self, session: DBSession, feedback: Feedback) -> Feedback:
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
        session.add(model)
        session.flush()
        session.refresh(model)
        return self._model_to_entity(model)

    def delete_feedback_older_than(self, session: DBSession, cutoff_time_ms: int, batch_size: int) -> int:
        """
        Delete feedback records older than the cutoff time.
        Uses batch deletion to avoid long-running transactions.

        Args:
            cutoff_time_ms: Epoch milliseconds - feedback with created_time before this will be deleted
            batch_size: Number of feedback records to delete per batch

        Returns:
            Total number of feedback records deleted
        """
        total_deleted = 0

        while True:
            # Find a batch of feedback IDs to delete
            feedback_ids_to_delete = (
                session.query(FeedbackModel.id)
                .filter(FeedbackModel.created_time < cutoff_time_ms)
                .limit(batch_size)
                .all()
            )

            if not feedback_ids_to_delete:
                break

            # Extract IDs from the result tuples
            ids = [feedback_id[0] for feedback_id in feedback_ids_to_delete]

            # Delete this batch
            deleted_count = (
                session.query(FeedbackModel)
                .filter(FeedbackModel.id.in_(ids))
                .delete(synchronize_session=False)
            )

            session.commit()
            total_deleted += deleted_count

            # If we deleted fewer than batch_size, we're done
            if deleted_count < batch_size:
                break

        return total_deleted

    def _model_to_entity(self, model: FeedbackModel) -> Feedback:
        """Convert SQLAlchemy model to domain entity."""
        return Feedback.model_validate(model)
