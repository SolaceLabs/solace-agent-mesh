"""
Session repository implementation using SQLAlchemy.
"""

from sqlalchemy.orm import Session as DBSession

from ..shared.base_repository import PaginatedRepository
from ..shared.types import PaginationInfo, SessionId, UserId
from .entities import Message, Session
from .interfaces import ISessionRepository
from .models import (
    MessageModel,
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
        self, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> list[Session]:
        """Find all sessions for a specific user."""
        query = self.db.query(SessionModel).filter(SessionModel.user_id == user_id)
        query = query.order_by(SessionModel.updated_time.desc())

        if pagination:
            offset = (pagination.page - 1) * pagination.page_size
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

    def find_user_session_with_messages(
        self,
        session_id: SessionId,
        user_id: UserId,
        pagination: PaginationInfo | None = None,
    ) -> tuple[Session, list[Message]] | None:
        """Find a session with its messages."""
        session_model = (
            self.db.query(SessionModel)
            .filter(
                SessionModel.id == session_id,
                SessionModel.user_id == user_id,
            )
            .first()
        )

        if not session_model:
            return None

        message_query = self.db.query(MessageModel).filter(
            MessageModel.session_id == session_id
        )

        if pagination:
            offset = (pagination.page - 1) * pagination.page_size
            message_query = message_query.offset(offset).limit(pagination.page_size)

        message_models = message_query.order_by(MessageModel.created_time.asc()).all()

        session = Session.model_validate(session_model)
        messages = [self._message_model_to_entity(model) for model in message_models]

        return session, messages


    def _message_model_to_entity(self, model: MessageModel) -> Message:
        """Convert SQLAlchemy message model to domain entity."""
        from ..shared.enums import MessageType, SenderType

        return Message(
            id=model.id,
            session_id=model.session_id,
            message=model.message,
            sender_type=SenderType(model.sender_type),
            sender_name=model.sender_name,
            message_type=MessageType.TEXT,  # Default for now
            created_time=model.created_time,
        )
