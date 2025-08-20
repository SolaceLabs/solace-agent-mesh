import logging
import uuid

from ..data.persistence.database_service import DatabaseService
from .models import ChatMessage
from .models import Session as DbSession
from .persistence_service import PersistenceService


class DatabasePersistenceService(PersistenceService):
    """Implementation of PersistenceService that stores data in a database."""

    def __init__(self, db_url: str):
        self.db_service = DatabaseService(db_url)
        self.logger = logging.getLogger(__name__)
        self.engine = self.db_service.engine

    def store_chat_message(
        self,
        session_id: str,
        message: dict,
        user_id: str | None = None,
        agent_id: str | None = None,
    ):
        """
        Store a chat message in the database.

        Args:
            session_id: ID of the session to store the message in
            message: Message dictionary containing message, sender_type, sender_name
            user_id: ID of the user (for session creation if needed)
            agent_id: ID of the agent (for session creation/update if needed)

        Returns:
            dict: {"message_id": str, "session_id": str} - IDs of created message and session
        """
        with self.db_service.session_scope() as session:
            self.logger.info("Storing chat message for session %s", session_id)

            # Check if session exists
            db_session = session.query(DbSession).filter_by(id=session_id).first()
            if not db_session:
                if not user_id:
                    raise ValueError(
                        f"Session {session_id} not found and no user_id provided for creation"
                    )

                # Generate a new session ID to prevent resurrection of deleted sessions
                new_session_id = str(uuid.uuid4())

                self.logger.warning(
                    "Session %s not found. Creating new session %s for user %s.",
                    session_id,
                    new_session_id,
                    user_id,
                )
                db_session = DbSession(
                    id=new_session_id, user_id=user_id, agent_id=agent_id
                )
                session.add(db_session)

                # Update session_id to the new one for message creation
                session_id = new_session_id

            elif not db_session.agent_id and agent_id:
                self.logger.info(
                    "Hydrating agent_id for session %s with agent %s",
                    session_id,
                    agent_id,
                )
                db_session.agent_id = agent_id

            message_id = str(uuid.uuid4())
            db_message = ChatMessage(
                id=message_id,
                session_id=session_id,
                message=message["message"],
                sender_type=message["sender_type"],
                sender_name=message["sender_name"],
            )
            session.add(db_message)

            self.logger.info("Chat message stored successfully: %s", message_id)
            return {"message_id": message_id, "session_id": session_id}

    def get_chat_history(self, session_id: str) -> list:
        """Get chat history for a session."""
        with self.db_service.read_only_session() as session:
            messages = (
                session.query(ChatMessage)
                .filter_by(session_id=session_id)
                .order_by(ChatMessage.created_at)
                .all()
            )
            return [msg.to_dict() for msg in messages]

    def create_session(
        self, session_id: str, user_id: str, agent_id: str | None = None
    ):
        """Create a new session."""
        with self.db_service.session_scope() as session:
            self.logger.info("Creating session %s for user %s", session_id, user_id)
            new_session = DbSession(id=session_id, user_id=user_id, agent_id=agent_id)
            session.add(new_session)
            self.logger.info(
                "Successfully created session %s for user %s", session_id, user_id
            )
            return {
                "id": new_session.id,
                "created_at": new_session.created_at.isoformat(),
            }

    def get_sessions(self, user_id: str | None = None) -> list:
        """Get all sessions, optionally filtered by user."""
        with self.db_service.read_only_session() as session:
            query = session.query(DbSession)
            if user_id:
                query = query.filter_by(user_id=user_id)
            sessions = query.order_by(DbSession.updated_at.desc()).all()
            return [s.to_dict() for s in sessions]

    def get_session(self, session_id: str) -> dict | None:
        """Get a specific session by ID."""
        with self.db_service.read_only_session() as session:
            db_session = session.query(DbSession).filter_by(id=session_id).first()
            if db_session:
                return db_session.to_dict()
            return None

    def update_session(self, session_id: str, name: str) -> dict | None:
        """Update session name."""
        with self.db_service.session_scope() as session:
            db_session = session.query(DbSession).filter_by(id=session_id).first()
            if db_session:
                db_session.name = name
                return db_session.to_dict()
            return None

    def delete_session(self, session_id: str):
        """Delete a session and all associated chat messages."""
        with self.db_service.session_scope() as session:
            self.logger.info("Deleting session %s and associated messages", session_id)

            # Check if session exists before deletion
            db_session = session.query(DbSession).filter_by(id=session_id).first()
            if not db_session:
                self.logger.warning("Session %s not found for deletion", session_id)
                return

            # Delete all chat messages associated with the session first
            messages_deleted = (
                session.query(ChatMessage).filter_by(session_id=session_id).delete()
            )
            self.logger.info(
                "Deleted %d messages for session %s", messages_deleted, session_id
            )

            # Then delete the session itself
            session.delete(db_session)

            self.logger.info("Successfully deleted session %s", session_id)

    def create_session_with_message(
        self,
        session_id: str,
        user_id: str,
        agent_id: str | None = None,
        initial_message: dict | None = None,
        session_name: str | None = None,
    ) -> dict:
        """Atomically create a session with an optional initial message."""
        with self.db_service.session_scope() as session:
            self.logger.info(
                "Creating session %s for user %s with initial message",
                session_id,
                user_id,
            )

            # Check if session already exists
            existing_session = session.query(DbSession).filter_by(id=session_id).first()
            if existing_session:
                raise ValueError(
                    f"Session {session_id} already exists for user {existing_session.user_id}"
                )

            new_session = DbSession(
                id=session_id, user_id=user_id, agent_id=agent_id, name=session_name
            )
            session.add(new_session)

            message_id = None
            if initial_message:
                message_content = initial_message.get("message")
                if not message_content:
                    raise ValueError("Initial message content is required")

                chat_message = ChatMessage(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    message=message_content,
                    sender_type=initial_message.get("sender_type", "user"),
                    sender_name=initial_message.get("sender_name", user_id),
                )
                session.add(chat_message)
                message_id = chat_message.id

                self.logger.info(
                    "Created initial message %s for session %s", message_id, session_id
                )

            self.logger.info(
                "Successfully created session %s for user %s", session_id, user_id
            )

            return {
                "id": new_session.id,
                "user_id": new_session.user_id,
                "agent_id": new_session.agent_id,
                "name": new_session.name,
                "created_at": new_session.created_at.isoformat(),
                "initial_message_id": message_id,
            }
