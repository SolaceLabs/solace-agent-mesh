from sqlalchemy.orm import Session as DBSession

from ...domain.entities.session import Message, Session
from ...domain.repositories.session_repository import (
    IMessageRepository,
    ISessionRepository,
)
from ...shared.enums import MessageType, SenderType, SessionStatus
from ...shared.types import PaginationInfo, SessionId, UserId
from ..persistence.models import MessageModel, SessionModel


class SessionRepository(ISessionRepository):
    def __init__(self, db: DBSession):
        self.db = db

    def find_by_user(
        self, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> list[Session]:
        query = self.db.query(SessionModel).filter(SessionModel.user_id == user_id)

        if pagination:
            offset = (pagination.page - 1) * pagination.page_size
            query = query.offset(offset).limit(pagination.page_size)

        models = query.order_by(SessionModel.updated_at.desc()).all()
        return [self._model_to_entity(model) for model in models]

    def find_user_session(
        self, session_id: SessionId, user_id: UserId
    ) -> Session | None:
        model = (
            self.db.query(SessionModel)
            .filter(SessionModel.id == session_id, SessionModel.user_id == user_id)
            .first()
        )
        return self._model_to_entity(model) if model else None

    def save(self, session_entity: Session) -> Session:
        existing_model = (
            self.db.query(SessionModel)
            .filter(
                SessionModel.id == session_entity.id,
                SessionModel.user_id == session_entity.user_id,
            )
            .first()
        )

        if existing_model:
            existing_model.name = session_entity.name
            existing_model.agent_id = session_entity.agent_id
            existing_model.updated_at = session_entity.updated_at
            existing_model.last_activity = session_entity.last_activity
            self.db.flush()
            self.db.refresh(existing_model)
            return self._model_to_entity(existing_model)
        else:
            new_model = SessionModel(
                id=session_entity.id,
                user_id=session_entity.user_id,
                name=session_entity.name,
                agent_id=session_entity.agent_id,
                created_at=session_entity.created_at,
                updated_at=session_entity.updated_at,
            )
            self.db.add(new_model)
            self.db.flush()
            self.db.refresh(new_model)
            return self._model_to_entity(new_model)

    def delete(self, session_id: SessionId, user_id: UserId) -> bool:
        model = (
            self.db.query(SessionModel)
            .filter(SessionModel.id == session_id, SessionModel.user_id == user_id)
            .first()
        )

        if not model:
            return False

        self.db.delete(model)
        return True

    def find_user_session_with_messages(
        self, session_id: SessionId, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> tuple[Session, list[Message]] | None:
        from sqlalchemy.orm import joinedload
        
        session_model = (
            self.db.query(SessionModel)
            .options(joinedload(SessionModel.messages))
            .filter(SessionModel.id == session_id, SessionModel.user_id == user_id)
            .first()
        )
        
        if not session_model:
            return None
            
        session_entity = self._model_to_entity(session_model)
        message_entities = [self._message_model_to_entity(msg) for msg in session_model.messages]
        
        if pagination:
            offset = (pagination.page - 1) * pagination.page_size
            message_entities = message_entities[offset:offset + pagination.page_size]
            
        return session_entity, message_entities

    def _message_model_to_entity(self, model) -> Message:
        return Message(
            id=model.id,
            session_id=model.session_id,
            message=model.message,
            sender_type=SenderType(model.sender_type),
            sender_name=model.sender_name,
            message_type=MessageType.TEXT,
            created_at=model.created_at,
        )

    def _model_to_entity(self, model: SessionModel) -> Session:
        return Session(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            agent_id=model.agent_id,
            status=SessionStatus.ACTIVE,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_activity=model.updated_at,
        )


class MessageRepository(IMessageRepository):
    def __init__(self, db: DBSession):
        self.db = db

    def find_by_session(
        self, session_id: SessionId, pagination: PaginationInfo | None = None
    ) -> list[Message]:
        query = self.db.query(MessageModel).filter(
            MessageModel.session_id == session_id
        )
        query = query.order_by(MessageModel.created_at.asc())

        if pagination:
            offset = (pagination.page - 1) * pagination.page_size
            query = query.offset(offset).limit(pagination.page_size)

        models = query.all()
        return [self._model_to_entity(model) for model in models]

    def save(self, message_entity: Message) -> Message:
        model = MessageModel(
            id=message_entity.id,
            session_id=message_entity.session_id,
            message=message_entity.message,
            sender_type=message_entity.sender_type.value,
            sender_name=message_entity.sender_name,
            created_at=message_entity.created_at,
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def delete_by_session(self, session_id: SessionId) -> bool:
        deleted_count = (
            self.db.query(MessageModel)
            .filter(MessageModel.session_id == session_id)
            .delete()
        )
        return deleted_count > 0

    def _model_to_entity(self, model: MessageModel) -> Message:
        return Message(
            id=model.id,
            session_id=model.session_id,
            message=model.message,
            sender_type=SenderType(model.sender_type),
            sender_name=model.sender_name,
            created_at=model.created_at,
        )
