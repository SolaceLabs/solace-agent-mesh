"""
Session business service using industry-standard transaction patterns.
"""

import uuid
from datetime import datetime, timezone

from solace_ai_connector.common.log import log

from ...data.models.session_models import ChatMessage as MessageModel
from ...data.models.session_models import Session as SessionModel
from ...data.persistence.database_service import DatabaseService
from ...shared.enums import MessageType, SenderType, SessionStatus
from ...shared.types import PaginationInfo, SessionId, UserId
from ..domain.session_domain import MessageDomain, SessionDomain, SessionHistoryDomain


class SessionService:
    """
    Session business service using industry-standard transaction management.

    Features:
    - Automatic transaction handling via DatabaseService context managers
    - Clean separation of business logic from data access
    - Atomic operations for complex business transactions
    - No manual session/transaction management required
    """

    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    def get_user_sessions(
        self, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> list[SessionDomain]:
        with self.db_service.read_only_session() as session:
            query = session.query(SessionModel).filter(SessionModel.user_id == user_id)

            if pagination:
                offset = (pagination.page - 1) * pagination.page_size
                query = query.offset(offset).limit(pagination.page_size)

            session_models = query.order_by(SessionModel.updated_at.desc()).all()

            return [self._model_to_domain(model) for model in session_models]

    def get_session(
        self, session_id: SessionId, user_id: UserId
    ) -> SessionDomain | None:
        with self.db_service.read_only_session() as session:
            session_model = (
                session.query(SessionModel)
                .filter(SessionModel.id == session_id, SessionModel.user_id == user_id)
                .first()
            )

            if not session_model:
                return None

            return self._model_to_domain(session_model)

    def get_session_history(
        self,
        session_id: SessionId,
        user_id: UserId,
        pagination: PaginationInfo | None = None,
    ) -> SessionHistoryDomain | None:
        """Get session with message history."""
        with self.db_service.read_only_session() as db_session:
            session_model = (
                db_session.query(SessionModel)
                .filter(SessionModel.id == session_id, SessionModel.user_id == user_id)
                .first()
            )

            if not session_model:
                return None

            session_domain = self._model_to_domain(session_model)

            message_query = (
                db_session.query(MessageModel)
                .filter(MessageModel.session_id == session_id)
                .order_by(MessageModel.created_at)
            )

            if pagination:
                offset = (pagination.page - 1) * pagination.page_size
                message_query = message_query.offset(offset).limit(pagination.page_size)

            message_models = message_query.all()

            messages = []
            for msg_model in message_models:
                message_domain = MessageDomain(
                    id=msg_model.id,
                    session_id=msg_model.session_id,
                    message=msg_model.message,
                    sender_type=SenderType(msg_model.sender_type),
                    sender_name=msg_model.sender_name,
                    message_type=MessageType.TEXT,  # Default for now
                    created_at=msg_model.created_at,
                )
                messages.append(message_domain)

            return SessionHistoryDomain(
                session=session_domain,
                messages=messages,
                total_message_count=len(messages),
            )

    def create_session(
        self, user_id: UserId, name: str | None = None, agent_id: str | None = None
    ) -> SessionDomain:
        # Validate user_id is not None/empty to prevent NULL database entries
        if not user_id or user_id.strip() == "":
            raise ValueError(f"user_id cannot be None or empty. Received: {user_id}")

        session_id = str(uuid.uuid4())

        with self.db_service.session_scope() as db_session:
            session_model = SessionModel(
                id=session_id, user_id=user_id, name=name, agent_id=agent_id
            )
            db_session.add(session_model)
            db_session.flush()
            db_session.refresh(session_model)

            return self._model_to_domain(session_model)

    def update_session_name(
        self, session_id: SessionId, user_id: UserId, name: str
    ) -> SessionDomain | None:
        with self.db_service.session_scope() as db_session:
            session_model = (
                db_session.query(SessionModel)
                .filter(SessionModel.id == session_id, SessionModel.user_id == user_id)
                .first()
            )

            if not session_model:
                return None

            # Validate name using domain rules
            existing_session = self._model_to_domain(session_model)
            existing_session.update_name(name)

            # Update the model
            session_model.name = name
            db_session.flush()
            db_session.refresh(session_model)

            return self._model_to_domain(session_model)

    def delete_session(self, session_id: SessionId, user_id: UserId) -> bool:
        with self.db_service.session_scope() as db_session:
            session_model = (
                db_session.query(SessionModel)
                .filter(SessionModel.id == session_id, SessionModel.user_id == user_id)
                .first()
            )

            if not session_model:
                return False

            # Check business rules
            existing_session = self._model_to_domain(session_model)
            if not existing_session.can_be_deleted_by_user(user_id):
                return False

            # Delete all messages first (cascade should handle this, but be explicit)
            db_session.query(MessageModel).filter(
                MessageModel.session_id == session_id
            ).delete()

            # Delete the session
            db_session.delete(session_model)

            return True

    def add_message_to_session(
        self,
        session_id: SessionId,
        user_id: UserId,
        message: str,
        sender_type: SenderType,
        sender_name: str,
        agent_id: str | None = None,
    ) -> MessageDomain | None:
        """
        Add a message to a session, creating the session if it doesn't exist.

        This is an atomic operation - both session creation and message addition
        happen in a single transaction using industry-standard patterns.

        Note: If session doesn't exist, generates a new session ID to prevent
        reusing deleted session IDs and avoid orphaned data issues.
        """
        # Validate user_id is not None/empty to prevent NULL database entries
        if not user_id or user_id.strip() == "":
            raise ValueError(f"user_id cannot be None or empty. Received: {user_id}")

        with self.db_service.session_scope() as db_session:
            # Check if session exists
            session_model = (
                db_session.query(SessionModel)
                .filter(SessionModel.id == session_id, SessionModel.user_id == user_id)
                .first()
            )

            if not session_model:
                # Session doesn't exist, generate a new session ID to prevent
                # reusing potentially deleted session IDs
                new_session_id = str(uuid.uuid4())
                log.info(
                    f"Session {session_id} not found, creating new session {new_session_id} for user {user_id}"
                )
                session_model = SessionModel(
                    id=new_session_id,
                    user_id=user_id,
                    name=None,  # Will be auto-generated if needed
                    agent_id=agent_id,
                )
                db_session.add(session_model)
                db_session.flush()
                session_id = new_session_id  # Use the new session ID for the message
                log.info(f"Created new session {new_session_id} for user {user_id}")

            message_domain = MessageDomain(
                id=str(uuid.uuid4()),
                session_id=session_id,
                message=message,
                sender_type=sender_type,
                sender_name=sender_name,
                created_at=datetime.now(timezone.utc),  # Use timezone-aware datetime
            )

            # Validate using domain rules
            message_domain.validate_message_content()

            message_model = MessageModel(
                id=message_domain.id,
                session_id=session_id,
                message=message,
                sender_type=sender_type.value,
                sender_name=sender_name,
            )

            db_session.add(message_model)
            db_session.flush()

            # Both session creation (if needed) and message creation are committed together
            return MessageDomain(
                id=message_model.id,
                session_id=session_id,  # Use the actual session_id (may be new)
                message=message_model.message,
                sender_type=SenderType(message_model.sender_type),
                sender_name=message_model.sender_name,
                created_at=message_model.created_at,
            )

    def _model_to_domain(self, model) -> SessionDomain:
        return SessionDomain(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            agent_id=model.agent_id,
            status=SessionStatus.ACTIVE,  # Default for now
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_activity=model.updated_at,  # Use updated_at as last_activity for now
        )
