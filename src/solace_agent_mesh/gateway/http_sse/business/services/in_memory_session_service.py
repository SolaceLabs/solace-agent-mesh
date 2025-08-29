"""
In-memory session service for backward compatibility when no database is configured.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from solace_ai_connector.common.log import log

from ...shared.enums import MessageType, SenderType, SessionStatus
from ...shared.types import PaginationInfo, SessionId, UserId
from ..domain.session_domain import MessageDomain, SessionDomain, SessionHistoryDomain


class InMemorySessionService:
    """
    In-memory session service for backward compatibility.
    
    This service provides the same interface as SessionService but stores
    data in memory instead of a database. It's used when no database is
    configured to maintain backward compatibility.
    
    Note: Data is not persisted across restarts.
    """

    def __init__(self):
        self._sessions: Dict[SessionId, SessionDomain] = {}
        self._messages: Dict[SessionId, List[MessageDomain]] = {}
        log.info("Initialized in-memory session service (data not persisted)")

    def get_user_sessions(
        self, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> List[SessionDomain]:
        """Get all sessions for a user."""
        user_sessions = [
            session for session in self._sessions.values() 
            if session.user_id == user_id
        ]
        
        # Sort by updated_at descending
        user_sessions.sort(key=lambda s: s.updated_at, reverse=True)
        
        if pagination:
            start = (pagination.page - 1) * pagination.page_size
            end = start + pagination.page_size
            user_sessions = user_sessions[start:end]
        
        return user_sessions

    def get_session(
        self, session_id: SessionId, user_id: UserId
    ) -> SessionDomain | None:
        """Get a specific session if it belongs to the user."""
        session = self._sessions.get(session_id)
        if session and session.user_id == user_id:
            return session
        return None

    def get_session_history(
        self,
        session_id: SessionId,
        user_id: UserId,
        pagination: PaginationInfo | None = None,
    ) -> SessionHistoryDomain | None:
        """Get session with message history."""
        session = self.get_session(session_id, user_id)
        if not session:
            return None
        
        messages = self._messages.get(session_id, [])
        
        # Sort messages by created_at
        messages.sort(key=lambda m: m.created_at)
        
        if pagination:
            start = (pagination.page - 1) * pagination.page_size
            end = start + pagination.page_size
            messages = messages[start:end]
        
        return SessionHistoryDomain(
            session=session,
            messages=messages,
            total_message_count=len(messages),
        )

    def create_session(
        self, user_id: UserId, name: str | None = None, agent_id: str | None = None
    ) -> SessionDomain:
        """Create a new session."""
        if not user_id or user_id.strip() == "":
            raise ValueError(f"user_id cannot be None or empty. Received: {user_id}")

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        session = SessionDomain(
            id=session_id,
            user_id=user_id,
            name=name,
            agent_id=agent_id,
            status=SessionStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            last_activity=now,
        )
        
        self._sessions[session_id] = session
        self._messages[session_id] = []
        
        log.info(f"Created in-memory session {session_id} for user {user_id}")
        return session

    def update_session_name(
        self, session_id: SessionId, user_id: UserId, name: str
    ) -> SessionDomain | None:
        """Update session name."""
        session = self.get_session(session_id, user_id)
        if not session:
            return None
        
        # Validate name using domain rules
        session.update_name(name)
        
        # Update the session in memory
        session.name = name
        session.updated_at = datetime.now(timezone.utc)
        session.last_activity = session.updated_at
        
        self._sessions[session_id] = session
        return session

    def delete_session(self, session_id: SessionId, user_id: UserId) -> bool:
        """Delete a session."""
        session = self.get_session(session_id, user_id)
        if not session:
            return False
        
        # Check business rules
        if not session.can_be_deleted_by_user(user_id):
            return False
        
        # Delete from memory
        del self._sessions[session_id]
        if session_id in self._messages:
            del self._messages[session_id]
        
        log.info(f"Deleted in-memory session {session_id} for user {user_id}")
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
        """Add a message to a session, creating the session if it doesn't exist."""
        if not user_id or user_id.strip() == "":
            raise ValueError(f"user_id cannot be None or empty. Received: {user_id}")

        # Check if session exists
        session = self.get_session(session_id, user_id)
        
        if not session:
            # Session doesn't exist, generate a new session ID
            new_session_id = str(uuid.uuid4())
            log.info(
                f"Session {session_id} not found, creating new in-memory session {new_session_id} for user {user_id}"
            )
            session = self.create_session(
                user_id=user_id,
                name=None,  # Will be auto-generated if needed
                agent_id=agent_id,
            )
            session_id = session.id  # Use the new session ID
            log.info(f"Created new in-memory session {session_id} for user {user_id}")

        message_domain = MessageDomain(
            id=str(uuid.uuid4()),
            session_id=session_id,
            message=message,
            sender_type=sender_type,
            sender_name=sender_name,
            created_at=datetime.now(timezone.utc),
        )

        # Validate using domain rules
        message_domain.validate_message_content()

        # Add to memory
        if session_id not in self._messages:
            self._messages[session_id] = []
        self._messages[session_id].append(message_domain)

        # Update session last_activity
        session.last_activity = datetime.now(timezone.utc)
        session.updated_at = session.last_activity
        self._sessions[session_id] = session

        return message_domain

    def get_total_sessions(self) -> int:
        """Get total number of sessions (for debugging/monitoring)."""
        return len(self._sessions)

    def get_total_messages(self) -> int:
        """Get total number of messages (for debugging/monitoring)."""
        return sum(len(messages) for messages in self._messages.values())