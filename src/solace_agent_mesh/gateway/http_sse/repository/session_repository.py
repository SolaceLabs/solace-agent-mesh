"""
Session repository implementation using SQLAlchemy.
"""

from sqlalchemy.orm import Session as DBSession

from ..shared.types import PaginationInfo, SessionId, UserId
from .entities import Message, Session
from .interfaces import ISessionRepository
from .models import MessageModel, SessionModel


class SessionRepository(ISessionRepository):
    """SQLAlchemy implementation of session repository."""

    def __init__(self, db: DBSession):
        self.db = db

    def find_by_user(
        self, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> list[Session]:
        """Find all sessions for a specific user."""
        query = self.db.query(SessionModel).filter(SessionModel.user_id == user_id)

        if pagination:
            offset = (pagination.page - 1) * pagination.page_size
            query = query.offset(offset).limit(pagination.page_size)

        models = query.order_by(SessionModel.updated_time.desc()).all()
        return [self._model_to_entity(model) for model in models]

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
        return self._model_to_entity(model) if model else None

    def save(self, session: Session) -> Session:
        """Save or update a session."""
        model = (
            self.db.query(SessionModel).filter(SessionModel.id == session.id).first()
        )

        if model:
            # Update existing
            model.name = session.name
            model.agent_id = session.agent_id
            model.updated_time = session.updated_time
        else:
            # Create new
            model = SessionModel(
                id=session.id,
                name=session.name,
                user_id=session.user_id,
                agent_id=session.agent_id,
                created_time=session.created_time,
                updated_time=session.updated_time,
            )
            self.db.add(model)

        self.db.commit()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def delete(self, session_id: SessionId, user_id: UserId) -> bool:
        """Delete a session belonging to a user."""
        result = (
            self.db.query(SessionModel)
            .filter(
                SessionModel.id == session_id,
                SessionModel.user_id == user_id,
            )
            .delete()
        )
        self.db.commit()
        return result > 0

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

        session = self._model_to_entity(session_model)
        messages = [self._message_model_to_entity(model) for model in message_models]

        return session, messages

    def _model_to_entity(self, model: SessionModel) -> Session:
        """Convert SQLAlchemy model to domain entity."""
        return Session(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            agent_id=model.agent_id,
            created_time=model.created_time,
            updated_time=model.updated_time,
        )

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
