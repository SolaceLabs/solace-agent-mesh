import uuid
from typing import TYPE_CHECKING, Optional

from solace_ai_connector.common.log import log

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

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent


class SessionService:
    def __init__(
        self,
        session_repository: ISessionRepository,
        message_repository: IMessageRepository,
        component: "WebUIBackendComponent" = None,
    ):
        self.session_repository = session_repository
        self.message_repository = message_repository
        self.component = component

    def is_persistence_enabled(self) -> bool:
        """Checks if the service is configured with a persistent backend."""
        # The presence of a database_url on the component is the source of truth
        # for whether SQL persistence is enabled.
        return self.component and self.component.database_url is not None

    def get_user_sessions(
        self, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> list[Session]:
        if not user_id or user_id.strip() == "":
            raise ValueError("User ID cannot be empty")

        return self.session_repository.find_by_user(user_id, pagination)

    def get_session_details(
        self, session_id: SessionId, user_id: UserId
    ) -> Session | None:
        if not self._is_valid_session_id(session_id):
            return None

        return self.session_repository.find_user_session(session_id, user_id)

    def get_session_history(
        self,
        session_id: SessionId,
        user_id: UserId,
        pagination: PaginationInfo | None = None,
    ) -> SessionHistory | None:
        if not self._is_valid_session_id(session_id):
            return None

        result = self.session_repository.find_user_session_with_messages(
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

        # Leave name as None/empty - frontend will generate display name if needed

        now_ms = now_epoch_ms()
        session = Session(
            id=session_id,
            user_id=user_id,
            name=name,
            agent_id=agent_id,
            created_time=now_ms,
            updated_time=now_ms,
        )

        if not session:
            raise ValueError(f"Failed to create session for {session_id}")

        created_session = self.session_repository.save(session)
        log.info("Created new session %s for user %s", created_session.id, user_id)

        if not created_session:
            raise ValueError(f"Failed to save session for {session_id}")

        return created_session

    def update_session_name(
        self, session_id: SessionId, user_id: UserId, name: str
    ) -> Session | None:
        if not self._is_valid_session_id(session_id):
            raise ValueError("Invalid session ID")

        if not name or len(name.strip()) == 0:
            raise ValueError("Session name cannot be empty")

        if len(name.strip()) > 255:
            raise ValueError("Session name cannot exceed 255 characters")

        session = self.session_repository.find_user_session(session_id, user_id)
        if not session:
            return None

        session.update_name(name)
        updated_session = self.session_repository.save(session)

        log.info("Updated session %s name to '%s'", session_id, name)
        return updated_session

    def delete_session_with_notifications(
        self, session_id: SessionId, user_id: UserId
    ) -> bool:
        if not self._is_valid_session_id(session_id):
            raise ValueError("Invalid session ID")

        session = self.session_repository.find_user_session(session_id, user_id)
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

        deleted = self.session_repository.delete(session_id, user_id)
        if not deleted:
            return False

        log.info("Session %s deleted successfully by user %s", session_id, user_id)

        if agent_id and self.component:
            self._notify_agent_of_session_deletion(session_id, user_id, agent_id)

        return True

    def add_message_to_session(
        self,
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

        session = self.session_repository.find_user_session(session_id, user_id)
        if not session:
            session = self.create_session(
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

        saved_message = self.message_repository.save(message_entity)

        session.mark_activity()
        self.session_repository.save(session)

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
