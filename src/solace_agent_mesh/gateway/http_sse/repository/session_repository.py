"""
Session repository implementation using SQLAlchemy.
"""

from sqlalchemy.orm import Session as DBSession

from ..shared.base_repository import PaginatedRepository
from ..shared.pagination import PaginationParams
from ..shared.types import PaginationInfo, SessionId, UserId
from .entities import Session
from .interfaces import ISessionRepository
from .models import (
    SessionModel,
    CreateSessionModel,
    UpdateSessionModel,
)


class SessionRepository(PaginatedRepository[SessionModel, Session], ISessionRepository):
    """SQLAlchemy implementation of session repository using BaseRepository."""

    def __init__(self, db: DBSession):
        super().__init__(SessionModel, Session)
        self.db = db

    @property
    def entity_name(self) -> str:
        """Return the entity name for error messages."""
        return "session"

    def find_by_user(
        self, user_id: UserId, pagination: PaginationParams | None = None
    ) -> list[Session]:
        """Find all sessions for a specific user."""
        query = self.db.query(SessionModel).filter(SessionModel.user_id == user_id)
        query = query.order_by(SessionModel.updated_time.desc())

        if pagination:
            offset = (pagination.page_number - 1) * pagination.page_size
            query = query.offset(offset).limit(pagination.page_size)

        models = query.all()
        return [Session.model_validate(model) for model in models]

    def count_by_user(self, user_id: UserId) -> int:
        """Count total sessions for a specific user."""
        return self.db.query(SessionModel).filter(SessionModel.user_id == user_id).count()

    def find_user_session(
        self, session_id: SessionId, user_id: UserId
    ) -> Session | None:
        """Find a specific session belonging to a user."""
        model = (
            self.db.query(SessionModel)
            .filter(
                SessionModel.id == session_id,
                SessionModel.user_id == user_id,
            )
            .first()
        )
        return Session.model_validate(model) if model else None

    def save(self, session: Session) -> Session:
        """Save or update a session."""
        existing_model = self.db.query(SessionModel).filter(SessionModel.id == session.id).first()

        if existing_model:
            update_model = UpdateSessionModel(
                name=session.name,
                agent_id=session.agent_id,
                updated_time=session.updated_time,
            )
            return self.update(self.db, session.id, update_model.model_dump(exclude_none=True))
        else:
            create_model = CreateSessionModel(
                id=session.id,
                name=session.name,
                user_id=session.user_id,
                agent_id=session.agent_id,
                created_time=session.created_time,
                updated_time=session.updated_time,
            )
            return self.create(self.db, create_model.model_dump())

    def delete(self, session_id: SessionId, user_id: UserId) -> bool:
        """Delete a session belonging to a user."""
        # Check if session belongs to user first
        session_model = self.db.query(SessionModel).filter(
            SessionModel.id == session_id,
            SessionModel.user_id == user_id,
        ).first()

        if not session_model:
            return False

        # Use BaseRepository delete method
        super().delete(self.db, session_id)
        return True
