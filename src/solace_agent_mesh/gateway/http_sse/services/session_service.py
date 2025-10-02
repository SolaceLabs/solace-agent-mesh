import uuid
from typing import TYPE_CHECKING, Optional

from solace_ai_connector.common.log import log
from sqlalchemy.orm import Session as DbSession

from ..repository import (
    IMessageRepository,
    ISessionRepository,
    Message,
    Session,
    SessionHistory,
)
from ..shared.enums import MessageType, SenderType
from ..shared.types import PaginationInfo, SessionId, UserId
from ..shared import now_epoch_ms
from ..shared.pagination import PaginationParams, PaginatedResponse, get_pagination_or_default

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent


class SessionService:
    def __init__(
        self,
        component: "WebUIBackendComponent" = None,
    ):
        self.component = component

    def _get_repositories(self, db: DbSession):
        """Create repositories for the given database session."""
        from ..repository import SessionRepository, MessageRepository
        session_repository = SessionRepository(db)
        message_repository = MessageRepository(db)
        return session_repository, message_repository

    def is_persistence_enabled(self) -> bool:
        """Checks if the service is configured with a persistent backend."""
        return self.component and self.component.database_url is not None

    def get_user_sessions(
        self,
        db: DbSession,
        user_id: UserId,
        pagination: PaginationParams | None = None
    ) -> PaginatedResponse[Session]:
        """
        Get paginated sessions for a user with full metadata.

        Uses default pagination if none provided (page 1, size 20).
        Returns paginated response with pageNumber, pageSize, nextPage, totalPages, totalCount.
        """
        if not user_id or user_id.strip() == "":
            raise ValueError("User ID cannot be empty")

        pagination = get_pagination_or_default(pagination)
        session_repository, _ = self._get_repositories(db)

        pagination_info = PaginationInfo(
            page=pagination.page_number,
            page_size=pagination.page_size,
            total_items=0,
            total_pages=0,
            has_next=False,
            has_previous=False,
        )

        sessions = session_repository.find_by_user(user_id, pagination_info)
        total_count = session_repository.count_by_user(user_id)

        return PaginatedResponse.create(sessions, total_count, pagination)

    def get_session_details(
        self, db: DbSession, session_id: SessionId, user_id: UserId
    ) -> Session | None:
        if not self._is_valid_session_id(session_id):
            return None

        session_repository, _ = self._get_repositories(db)
        return session_repository.find_user_session(session_id, user_id)

    def get_session_history(
        self,
        db: DbSession,
        session_id: SessionId,
        user_id: UserId,
        pagination: PaginationInfo | None = None,
    ) -> SessionHistory | None:
        if not self._is_valid_session_id(session_id):
            return None

        session_repository, _ = self._get_repositories(db)
        result = session_repository.find_user_session_with_messages(
            session_id, user_id, pagination
        )
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
        db: DbSession,
        user_id: UserId,
        name: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
    ) -> Optional[Session]:
        if not self.is_persistence_enabled():
            log.debug("Persistence is not enabled. Skipping session creation in DB.")
            return None

        if not user_id or user_id.strip() == "":
            raise ValueError("User ID cannot be empty")

        if not session_id:
            session_id = str(uuid.uuid4())

        now_ms = now_epoch_ms()
        session = Session(
            id=session_id,
            user_id=user_id,
            name=name,
            agent_id=agent_id,
            created_time=now_ms,
            updated_time=now_ms,
        )

        session_repository, _ = self._get_repositories(db)
        created_session = session_repository.save(session)
        log.info("Created new session %s for user %s", created_session.id, user_id)

        if not created_session:
            raise ValueError(f"Failed to save session for {session_id}")

        return created_session

    def update_session_name(
        self, db: DbSession, session_id: SessionId, user_id: UserId, name: str
    ) -> Session | None:
        if not self._is_valid_session_id(session_id):
            raise ValueError("Invalid session ID")

        if not name or len(name.strip()) == 0:
            raise ValueError("Session name cannot be empty")

        if len(name.strip()) > 255:
            raise ValueError("Session name cannot exceed 255 characters")

        session_repository, _ = self._get_repositories(db)
        session = session_repository.find_user_session(session_id, user_id)
        if not session:
            return None

        session.update_name(name)
        updated_session = session_repository.save(session)

        log.info("Updated session %s name to '%s'", session_id, name)
        return updated_session

    def delete_session_with_notifications(
        self, db: DbSession, session_id: SessionId, user_id: UserId
    ) -> bool:
        if not self._is_valid_session_id(session_id):
            raise ValueError("Invalid session ID")

        session_repository, _ = self._get_repositories(db)
        session = session_repository.find_user_session(session_id, user_id)
        if not session:
            log.warning(
                "Attempted to delete non-existent session %s by user %s",
                session_id,
                user_id,
            )
            return False

        agent_id = session.agent_id

        if not session.can_be_deleted_by_user(user_id):
            log.warning(
                "User %s not authorized to delete session %s", user_id, session_id
            )
            return False

        deleted = session_repository.delete(session_id, user_id)
        if not deleted:
            return False

        log.info("Session %s deleted successfully by user %s", session_id, user_id)

        if agent_id and self.component:
            self._notify_agent_of_session_deletion(session_id, user_id, agent_id)

        return True

    def add_message_to_session(
        self,
        db: DbSession,
        session_id: SessionId,
        user_id: UserId,
        message: str,
        sender_type: SenderType,
        sender_name: str,
        agent_id: str | None = None,
        message_type: MessageType = MessageType.TEXT,
    ) -> Message:
        if not self._is_valid_session_id(session_id):
            raise ValueError("Invalid session ID")

        if not message or message.strip() == "":
            raise ValueError("Message cannot be empty")

        session_repository, message_repository = self._get_repositories(db)
        session = session_repository.find_user_session(session_id, user_id)
        if not session:
            session = self.create_session(
                db=db,
                user_id=user_id,
                agent_id=agent_id,
                session_id=session_id,
            )

        message_entity = Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            message=message.strip(),
            sender_type=sender_type,
            sender_name=sender_name,
            message_type=message_type,
            created_time=now_epoch_ms(),
        )

        saved_message = message_repository.save(message_entity)

        session.mark_activity()
        session_repository.save(session)

        log.info("Added message to session %s from %s", session_id, sender_name)
        return saved_message

    def _is_valid_session_id(self, session_id: SessionId) -> bool:
        return (
            session_id is not None
            and session_id.strip() != ""
            and session_id not in ["null", "undefined"]
        )

    def _notify_agent_of_session_deletion(
        self, session_id: SessionId, user_id: UserId, agent_id: str
    ) -> None:
        try:
            log.info(
                "Publishing session deletion event for session %s (agent %s, user %s)",
                session_id,
                agent_id,
                user_id,
            )

            if hasattr(self.component, "sam_events"):
                success = self.component.sam_events.publish_session_deleted(
                    session_id=session_id,
                    user_id=user_id,
                    agent_id=agent_id,
                    gateway_id=self.component.gateway_id,
                )

                if success:
                    log.info(
                        "Successfully published session deletion event for session %s",
                        session_id,
                    )
                else:
                    log.warning(
                        "Failed to publish session deletion event for session %s",
                        session_id,
                    )
            else:
                log.warning(
                    "SAM Events not available for session deletion notification"
                )

        except Exception as e:
            log.warning(
                "Failed to publish session deletion event to agent %s: %s",
                agent_id,
                e,
            )