import uuid
from datetime import datetime, timezone

from solace_ai_connector.common.log import log

from ...domain.entities.session import Message, Session, SessionHistory
from ...domain.repositories.session_repository import (
    IMessageRepository,
    ISessionRepository,
)
from ...shared.enums import MessageType, SenderType, SessionStatus
from ...shared.types import PaginationInfo, SessionId, UserId


class SessionService:
    def __init__(
        self,
        session_repository: ISessionRepository,
        message_repository: IMessageRepository,
    ):
        self.session_repository = session_repository
        self.message_repository = message_repository

    def get_user_sessions(
        self, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> list[Session]:
        return self.session_repository.find_by_user(user_id, pagination)

    def get_session(self, session_id: SessionId, user_id: UserId) -> Session | None:
        return self.session_repository.find_user_session(session_id, user_id)

    def get_session_history(
        self,
        session_id: SessionId,
        user_id: UserId,
        pagination: PaginationInfo | None = None,
    ) -> SessionHistory | None:
        result = self.session_repository.find_user_session_with_messages(session_id, user_id, pagination)
        if not result:
            return None

        session, messages = result
        return SessionHistory(
            session=session,
            messages=messages,
            total_message_count=len(messages),
        )

    def create_session(
        self,
        user_id: UserId,
        name: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
    ) -> Session:
        if not user_id or user_id.strip() == "":
            raise ValueError(f"user_id cannot be None or empty. Received: {user_id}")

        if not session_id:
            session_id = str(uuid.uuid4())

        now = datetime.now(timezone.utc)
        session = Session(
            id=session_id,
            user_id=user_id,
            name=name,
            agent_id=agent_id,
            status=SessionStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            last_activity=now,
        )

        return self.session_repository.save(session)

    def update_session_name(
        self, session_id: SessionId, user_id: UserId, name: str
    ) -> Session | None:
        session = self.session_repository.find_user_session(session_id, user_id)
        if not session:
            return None

        session.update_name(name)
        return self.session_repository.save(session)

    def delete_session(self, session_id: SessionId, user_id: UserId) -> bool:
        session = self.session_repository.find_user_session(session_id, user_id)
        if not session:
            return False

        if not session.can_be_deleted_by_user(user_id):
            return False

        return self.session_repository.delete(session_id, user_id)

    def add_message_to_session(
        self,
        session_id: SessionId,
        user_id: UserId,
        message: str,
        sender_type: SenderType,
        sender_name: str,
        agent_id: str | None = None,
    ) -> Message | None:
        if not user_id or user_id.strip() == "":
            raise ValueError(f"user_id cannot be None or empty. Received: {user_id}")

        session = self.session_repository.find_user_session(session_id, user_id)
        if not session:
            log.info(f"Session {session_id} not found for user {user_id}, creating new session")
            session = self.create_session(user_id=user_id, agent_id=agent_id, session_id=session_id)

        if agent_id and not session.agent_id:
            session.agent_id = agent_id
            log.info(f"Updated session {session_id} with agent_id: {agent_id}")

        message_entity = Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            message=message,
            sender_type=sender_type,
            sender_name=sender_name,
            message_type=MessageType.TEXT,
            created_at=datetime.now(timezone.utc),
        )

        message_entity.validate_message_content()

        session.mark_activity()
        self.session_repository.save(session)

        return self.message_repository.save(message_entity)
