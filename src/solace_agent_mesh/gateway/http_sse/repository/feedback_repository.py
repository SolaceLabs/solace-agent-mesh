"""
Feedback repository implementation using SQLAlchemy.
"""

from sqlalchemy.orm import Session as DBSession

from solace_agent_mesh.shared.api.pagination import PaginationParams
from solace_agent_mesh.shared.utils.types import UserId
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

    def search(
        self,
        session: DBSession,
        user_id: UserId,
        start_date: int | None = None,
        end_date: int | None = None,
        task_id: str | None = None,
        session_id: str | None = None,
        rating: str | None = None,
        pagination: PaginationParams | None = None,
    ) -> list[Feedback]:
        """
        Search feedback with flexible filtering.
        All filters are optional and can be combined.
        """
        query = session.query(FeedbackModel)

        # User filter (unless admin querying all users)
        if user_id != "*":
            query = query.filter(FeedbackModel.user_id == user_id)

        # Time-based filters
        if start_date:
            query = query.filter(FeedbackModel.created_time >= start_date)
        if end_date:
            query = query.filter(FeedbackModel.created_time <= end_date)

        # Resource-based filters
        if task_id:
            query = query.filter(FeedbackModel.task_id == task_id)
        if session_id:
            query = query.filter(FeedbackModel.session_id == session_id)
        if rating:
            query = query.filter(FeedbackModel.rating == rating)

        # Order by most recent first
        query = query.order_by(FeedbackModel.created_time.desc())

        # Apply pagination
        if pagination:
            query = query.offset(pagination.offset).limit(pagination.page_size)

        models = query.all()
        return [self._model_to_entity(model) for model in models]

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
