"""
Modern database persistence service using industry-standard transaction management.
Replaces the old custom transaction manager with SQLAlchemy best practices.
"""

import json
import logging
import uuid
from typing import Optional, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from .persistence_service import PersistenceService
from .models import Session as DbSession, ChatMessage


class ModernDatabasePersistenceService(PersistenceService):
    """
    Modern implementation of PersistenceService using industry-standard patterns.
    
    Features:
    - SQLAlchemy context managers for automatic transaction handling
    - Proper connection pool configuration
    - No custom transaction manager complexity
    - Clean, maintainable code following industry best practices
    """

    def __init__(self, db_url: str):
        self.logger = logging.getLogger(__name__)
        
        # Industry-standard connection pool configuration
        if db_url.startswith('sqlite'):
            # SQLite: Optimized for testing and development
            self.engine = create_engine(
                db_url,
                pool_size=20,
                max_overflow=30,
                pool_timeout=60,
                pool_recycle=3600,
                pool_pre_ping=True,
                echo=False,
                # SQLite-specific optimizations
                connect_args={"check_same_thread": False}
            )
        else:
            # Production databases: PostgreSQL, MySQL, etc.
            self.engine = create_engine(
                db_url,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True,
                echo=False
            )
        
        self.Session = sessionmaker(bind=self.engine)

    @contextmanager
    def session_scope(self):
        """
        Provide a transactional scope around a series of operations.
        Industry-standard pattern for transaction management.
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Database transaction failed: {e}")
            raise
        finally:
            session.close()

    @contextmanager
    def read_only_session(self):
        """Provide a read-only session for queries."""
        session = self.Session()
        try:
            yield session
        except Exception as e:
            session.rollback()
            self.logger.error(f"Database read operation failed: {e}")
            raise
        finally:
            session.close()

    def store_chat_message(
        self,
        session_id: str,
        message: dict,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Store a chat message in the database using modern transaction management.
        
        Returns:
            dict: {"message_id": str, "session_id": str}
        """
        with self.session_scope() as session:
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
            
            # Validate message content
            message_content = message.get("message")
            if not message_content:
                raise ValueError("Message content is required")
            
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
        """Get chat history for a session."""
        with self.read_only_session() as session:
            messages = (
                session.query(ChatMessage)
                .filter_by(session_id=session_id)
                .order_by(ChatMessage.created_at)
                .all()
            )
            return [msg.to_dict() for msg in messages]


    def create_session(
        self, session_id: str, user_id: str, agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        with self.session_scope() as session:
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

    def get_sessions(self, user_id: Optional[str] = None) -> list:
        """Get sessions, optionally filtered by user."""
        with self.read_only_session() as session:
            query = session.query(DbSession)
            if user_id:
                query = query.filter_by(user_id=user_id)
            sessions = query.order_by(DbSession.updated_at.desc()).all()
            return [s.to_dict() for s in sessions]

    def get_session(self, session_id: str) -> Optional[dict]:
        with self.read_only_session() as session:
            db_session = session.query(DbSession).filter_by(id=session_id).first()
            if db_session:
                return db_session.to_dict()
            return None

    def update_session(self, session_id: str, name: str) -> Optional[dict]:
        with self.session_scope() as session:
            db_session = session.query(DbSession).filter_by(id=session_id).first()
            if db_session:
                db_session.name = name
                return db_session.to_dict()
            return None

    def delete_session(self, session_id: str):
        """Delete a session and all associated chat messages."""
        with self.session_scope() as session:
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
        """
        with self.session_scope() as session:
            self.logger.info("Creating session %s for user %s with initial message", session_id, user_id)
            
            # Check if session already exists
            existing_session = session.query(DbSession).filter_by(id=session_id).first()
            if existing_session:
                raise ValueError(
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