from ...domain.entities.session import Message, Session
from ...domain.repositories.session_repository import (
    IMessageRepository,
    ISessionRepository,
)
from ...shared.enums import SenderType, SessionStatus
from ...shared.types import PaginationInfo, SessionId, UserId
from ..persistence.database_service import DatabaseService
from ..persistence.models import MessageModel, SessionModel


class SessionRepository(ISessionRepository):
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    def get_by_id(self, session_id: SessionId) -> Session | None:
        with self.db_service.read_only_session() as session:
            model = (
                session.query(SessionModel)
                .filter(SessionModel.id == session_id)
                .first()
            )
            return self._model_to_entity(model) if model else None

    def get_by_user_id(
        self, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> list[Session]:
        with self.db_service.read_only_session() as session:
            query = session.query(SessionModel).filter(SessionModel.user_id == user_id)

            if pagination:
                offset = (pagination.page - 1) * pagination.page_size
                query = query.offset(offset).limit(pagination.page_size)

            models = query.order_by(SessionModel.updated_at.desc()).all()
            return [self._model_to_entity(model) for model in models]

    def get_user_session(
        self, session_id: SessionId, user_id: UserId
    ) -> Session | None:
        with self.db_service.read_only_session() as session:
            model = (
                session.query(SessionModel)
                .filter(SessionModel.id == session_id, SessionModel.user_id == user_id)
                .first()
            )
            return self._model_to_entity(model) if model else None

    def create(self, session_entity: Session) -> Session:
        with self.db_service.session_scope() as session:
            model = SessionModel(
                id=session_entity.id,
                user_id=session_entity.user_id,
                name=session_entity.name,
                agent_id=session_entity.agent_id,
                created_at=session_entity.created_at,
                updated_at=session_entity.updated_at,
            )
            session.add(model)
            session.flush()
            session.refresh(model)
            return self._model_to_entity(model)

    def update(self, session_entity: Session) -> Session | None:
        with self.db_service.session_scope() as session:
            model = (
                session.query(SessionModel)
                .filter(
                    SessionModel.id == session_entity.id,
                    SessionModel.user_id == session_entity.user_id,
                )
                .first()
            )

            if not model:
                return None

            model.name = session_entity.name
            model.agent_id = session_entity.agent_id
            model.updated_at = session_entity.updated_at

            session.flush()
            session.refresh(model)
            return self._model_to_entity(model)

    def delete(self, session_id: SessionId, user_id: UserId) -> bool:
        with self.db_service.session_scope() as session:
            model = (
                session.query(SessionModel)
                .filter(SessionModel.id == session_id, SessionModel.user_id == user_id)
                .first()
            )

            if not model:
                return False

            session.delete(model)
            return True

    def exists(self, session_id: SessionId) -> bool:
        with self.db_service.read_only_session() as session:
            return (
                session.query(SessionModel)
                .filter(SessionModel.id == session_id)
                .first()
                is not None
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
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    def get_by_session_id(
        self, session_id: SessionId, pagination: PaginationInfo | None = None
    ) -> list[Message]:
        with self.db_service.read_only_session() as session:
            query = session.query(MessageModel).filter(
                MessageModel.session_id == session_id
            )
            query = query.order_by(MessageModel.created_at.asc())

            if pagination:
                offset = (pagination.page - 1) * pagination.page_size
                query = query.offset(offset).limit(pagination.page_size)

            models = query.all()
            return [self._model_to_entity(model) for model in models]

    def create(self, message_entity: Message) -> Message:
        with self.db_service.session_scope() as session:
            model = MessageModel(
                id=message_entity.id,
                session_id=message_entity.session_id,
                message=message_entity.message,
                sender_type=message_entity.sender_type.value,
                sender_name=message_entity.sender_name,
                created_at=message_entity.created_at,
            )
            session.add(model)
            session.flush()
            session.refresh(model)
            return self._model_to_entity(model)

    def delete_by_session_id(self, session_id: SessionId) -> bool:
        with self.db_service.session_scope() as session:
            deleted_count = (
                session.query(MessageModel)
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
