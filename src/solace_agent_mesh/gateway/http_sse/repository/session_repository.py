"""
Session repository implementation using SQLAlchemy.
"""

from sqlalchemy.orm import Session as DBSession

from ..shared.base_repository import PaginatedRepository
from ..shared.pagination import PaginationParams
from ..shared.types import SessionId, UserId
from .entities import Session
from .interfaces import ISessionRepository
from .models import CreateSessionModel, SessionModel, UpdateSessionModel


class SessionRepository(PaginatedRepository[SessionModel, Session], ISessionRepository):
    """SQLAlchemy implementation of session repository using BaseRepository."""

    def __init__(self):
        super().__init__(SessionModel, Session)

    @property
    def entity_name(self) -> str:
        """Return the entity name for error messages."""
        return "session"

    def find_by_user(
        self, session: DBSession, user_id: UserId, pagination: PaginationParams | None = None
    ) -> list[Session]:
        """Find all sessions for a specific user."""
        query = session.query(SessionModel).filter(SessionModel.user_id == user_id)
        query = query.order_by(SessionModel.updated_time.desc())

        if pagination:
            query = query.offset(pagination.offset).limit(pagination.page_size)

        models = query.all()
        return [Session.model_validate(model) for model in models]

    def count_by_user(self, session: DBSession, user_id: UserId) -> int:
        """Count total sessions for a specific user."""
        return (
            session.query(SessionModel).filter(SessionModel.user_id == user_id).count()
        )

    def find_user_session(
        self, session: DBSession, session_id: SessionId, user_id: UserId
    ) -> Session | None:
        """Find a specific session belonging to a user."""
        model = (
            session.query(SessionModel)
            .filter(
                SessionModel.id == session_id,
                SessionModel.user_id == user_id,
            )
            .first()
        )
        return Session.model_validate(model) if model else None

    def save(self, db_session: DBSession, session: Session) -> Session:
        """Save or update a session."""
        existing_model = (
            db_session.query(SessionModel).filter(SessionModel.id == session.id).first()
        )

        if existing_model:
            update_model = UpdateSessionModel(
                name=session.name,
                agent_id=session.agent_id,
                updated_time=session.updated_time,
            )
            return self.update(
                db_session, session.id, update_model.model_dump(exclude_none=True)
            )
        else:
            create_model = CreateSessionModel(
                id=session.id,
                name=session.name,
                user_id=session.user_id,
                agent_id=session.agent_id,
                created_time=session.created_time,
                updated_time=session.updated_time,
            )
            return self.create(db_session, create_model.model_dump())

    def delete(self, db_session: DBSession, session_id: SessionId, user_id: UserId) -> bool:
        """Delete a session belonging to a user."""
        # Check if session belongs to user first
        session_model = (
            db_session.query(SessionModel)
            .filter(
                SessionModel.id == session_id,
                SessionModel.user_id == user_id,
            )
            .first()
        )

        if not session_model:
            return False

        # Use BaseRepository delete method
        super().delete(db_session, session_id)
        return True
