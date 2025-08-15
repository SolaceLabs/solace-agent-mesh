import json
import logging
import uuid
from typing import Optional
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError, OperationalError, DataError
from .persistence_service import PersistenceService
from .models import Session as DbSession, ChatMessage, User
from .transaction_manager import (
    TransactionManager, 
    atomic_operation, 
    handle_database_errors,
    TransactionError,
    RetriableTransactionError,
    NonRetriableTransactionError
)


class DatabasePersistenceService(PersistenceService):
    """Implementation of PersistenceService that stores data in a database."""

    def __init__(self, db_url: str):
        # Configure connection pool for better concurrency
        if db_url.startswith('sqlite'):
            # SQLite: Use a larger pool and overflow for testing
            self.engine = create_engine(
                db_url,
                pool_size=20,
                max_overflow=30,
                pool_timeout=60,
                pool_recycle=3600,
                pool_pre_ping=True,
                echo=False  # Set to True for SQL debugging
            )
        else:
            # Other databases: Standard configuration
            self.engine = create_engine(
                db_url,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True
            )
        self.Session = sessionmaker(bind=self.engine)
        self.logger = logging.getLogger(__name__)
        self.transaction_manager = TransactionManager(self.Session)

    def store_chat_message(
        self,
        session_id: str,
        message: dict,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ):
        """
        Store a chat message in the database (public interface).
        
        Args:
            session_id: ID of the session to store the message in
            message: Message dictionary containing message, sender_type, sender_name
            user_id: ID of the user (for session creation if needed)
            agent_id: ID of the agent (for session creation/update if needed)
            
        Returns:
            dict: {"message_id": str, "session_id": str} - IDs of created message and session
        """
        return self._store_chat_message_impl(session_id, message, user_id, agent_id)
    
    @atomic_operation(max_retries=3, timeout=15.0)
    @handle_database_errors()
    def _store_chat_message_impl(
        self,
        session: Session,
        session_id: str,
        message: dict,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ):
        """
        Store a chat message in the database.
        
        Args:
            session: Database session (injected by @atomic_operation)
            session_id: ID of the session to store the message in
            message: Message dictionary containing message, sender_type, sender_name
            user_id: ID of the user (for session creation if needed)
            agent_id: ID of the agent (for session creation/update if needed)
            
        Returns:
            dict: {"message_id": str, "session_id": str} - IDs of created message and session
            
        Raises:
            TransactionError: On database operation failures
        """
        self.logger.info("Storing chat message for session %s", session_id)
        
        # Check if session exists
        db_session = session.query(DbSession).filter_by(id=session_id).first()
        if not db_session:
            if not user_id:
                raise NonRetriableTransactionError(
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
            
        elif not db_session.agent_id and agent_id:  # type: ignore
            self.logger.info(
                "Hydrating agent_id for session %s with agent %s",
                session_id,
                agent_id,
            )
            db_session.agent_id = agent_id  # type: ignore
        
        # Validate message content
        message_content = message.get("message")
        if not message_content:
            raise NonRetriableTransactionError("Message content is required")
        
        # Create the chat message
        chat_message = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            message=message_content,
            sender_type=message.get("sender_type"),
            sender_name=message.get("sender_name"),
        )
        session.add(chat_message)
        
        self.logger.info(
            "Successfully stored message %s for session %s",
            chat_message.id,
            session_id,
        )
        return {"message_id": chat_message.id, "session_id": session_id}

    def get_chat_history(self, session_id: str) -> list:
        """Get chat history for a session (public interface)."""
        return self._get_chat_history_impl(session_id)
    
    @atomic_operation(read_only=True, timeout=10.0)
    @handle_database_errors()
    def _get_chat_history_impl(self, session: Session, session_id: str) -> list:
        """
        Get chat history for a session.
        
        Args:
            session: Database session (injected by @atomic_operation)
            session_id: ID of the session to get history for
            
        Returns:
            List of message dictionaries
        """
        messages = (
            session.query(ChatMessage)
            .filter_by(session_id=session_id)
            .order_by(ChatMessage.created_at)
            .all()
        )
        return [msg.to_dict() for msg in messages]

    def store_user_info(self, user_id: str, info: dict):
        session = self.Session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                user = User(id=user_id, info=json.dumps(info))
                session.add(user)
            else:
                user.info = json.dumps(info)  # type: ignore
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_session(
        self, session_id: str, user_id: str, agent_id: Optional[str] = None
    ):
        self.logger.info("Creating session %s for user %s", session_id, user_id)
        session = self.Session()
        try:
            # Ensure the user exists
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                self.logger.info("User %s not found. Creating new user.", user_id)
                user = User(id=user_id, info="{}")  # Create user with empty info
                session.add(user)

            new_session = DbSession(id=session_id, user_id=user_id, agent_id=agent_id)
            session.add(new_session)
            session.commit()
            self.logger.info(
                "Successfully created session %s for user %s", session_id, user_id
            )
            return {
                "id": new_session.id,
                "created_at": new_session.created_at.isoformat(),
            }
        except Exception:
            self.logger.exception("Error creating session")
            session.rollback()
            raise
        finally:
            session.close()

    def get_sessions(self, user_id: Optional[str] = None) -> list:
        session = self.Session()
        try:
            query = session.query(DbSession)
            if user_id:
                query = query.filter_by(user_id=user_id)
            sessions = query.order_by(DbSession.updated_at.desc()).all()
            return [s.to_dict() for s in sessions]
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session(self, session_id: str) -> Optional[dict]:
        session = self.Session()
        try:
            db_session = session.query(DbSession).filter_by(id=session_id).first()
            if db_session:
                return db_session.to_dict()
            return None
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update_session(self, session_id: str, name: str) -> Optional[dict]:
        session = self.Session()
        try:
            db_session = session.query(DbSession).filter_by(id=session_id).first()
            if db_session:
                db_session.name = name  # type: ignore
                session.commit()
                return db_session.to_dict()
            return None
        except Exception:
            self.logger.exception("Error updating session")
            session.rollback()
            raise
        finally:
            session.close()

    def delete_session(self, session_id: str):
        """Delete a session and all associated data (public interface)."""
        return self._delete_session_impl(session_id)
    
    @atomic_operation(max_retries=2, timeout=20.0)
    @handle_database_errors()
    def _delete_session_impl(self, session: Session, session_id: str):
        """
        Delete a session and all associated chat messages atomically.
        
        Args:
            session: Database session (injected by @atomic_operation)
            session_id: ID of the session to delete
            
        Raises:
            TransactionError: On database operation failures
        """
        self.logger.info("Deleting session %s and associated messages", session_id)
        
        # Check if session exists before deletion
        db_session = session.query(DbSession).filter_by(id=session_id).first()
        if not db_session:
            self.logger.warning("Session %s not found for deletion", session_id)
            return  # Session doesn't exist, consider it already deleted
        
        # Delete all chat messages associated with the session first
        messages_deleted = session.query(ChatMessage).filter_by(session_id=session_id).delete()
        self.logger.info("Deleted %d messages for session %s", messages_deleted, session_id)
        
        # Then delete the session itself
        session.delete(db_session)
        
        self.logger.info("Successfully deleted session %s", session_id)
    
    def create_session_with_message(
        self,
        session_id: str,
        user_id: str,
        agent_id: Optional[str] = None,
        initial_message: Optional[dict] = None,
        session_name: Optional[str] = None
    ) -> dict:
        """
        Atomically create a session with an optional initial message.
        
        Args:
            session_id: ID for the new session
            user_id: ID of the user creating the session
            agent_id: Optional ID of the agent
            initial_message: Optional initial message to store
            session_name: Optional name for the session
            
        Returns:
            dict: Session information with creation timestamp
        """
        return self._create_session_with_message_impl(
            session_id, user_id, agent_id, initial_message, session_name
        )
    
    @atomic_operation(max_retries=3, timeout=25.0)
    @handle_database_errors()
    def _create_session_with_message_impl(
        self,
        session: Session,
        session_id: str,
        user_id: str,
        agent_id: Optional[str] = None,
        initial_message: Optional[dict] = None,
        session_name: Optional[str] = None
    ) -> dict:
        """
        Atomically create a session with an optional initial message.
        
        This ensures that either both the session and message are created,
        or neither is created (atomic operation).
        """
        self.logger.info("Creating session %s for user %s with initial message", session_id, user_id)
        
        # Ensure the user exists
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            self.logger.info("User %s not found. Creating new user.", user_id)
            user = User(id=user_id, info="{}")  # Create user with empty info
            session.add(user)
        
        # Check if session already exists
        existing_session = session.query(DbSession).filter_by(id=session_id).first()
        if existing_session:
            raise NonRetriableTransactionError(
                f"Session {session_id} already exists for user {existing_session.user_id}"
            )
        
        # Create the session
        new_session = DbSession(
            id=session_id, 
            user_id=user_id, 
            agent_id=agent_id,
            name=session_name
        )
        session.add(new_session)
        
        # Create initial message if provided
        message_id = None
        if initial_message:
            message_content = initial_message.get("message")
            if not message_content:
                raise NonRetriableTransactionError("Initial message content is required")
            
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
                "Created initial message %s for session %s", 
                message_id, session_id
            )
        
        self.logger.info("Successfully created session %s for user %s", session_id, user_id)
        
        return {
            "id": new_session.id,
            "user_id": new_session.user_id,
            "agent_id": new_session.agent_id,
            "name": new_session.name,
            "created_at": new_session.created_at.isoformat(),
            "initial_message_id": message_id
        }
