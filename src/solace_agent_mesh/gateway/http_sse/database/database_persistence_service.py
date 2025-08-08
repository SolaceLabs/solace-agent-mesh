import json
import logging
import uuid
from typing import Optional
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from .persistence_service import PersistenceService
from .models import Session as DbSession, ChatMessage, User


class DatabasePersistenceService(PersistenceService):
    """Implementation of PersistenceService that stores data in a database."""

    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.logger = logging.getLogger(__name__)

    def store_chat_message(
        self,
        session_id: str,
        message: dict,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ):
        self.logger.info("Storing chat message for session %s", session_id)
        session = self.Session()
        try:
            db_session = session.query(DbSession).filter_by(id=session_id).first()
            if not db_session:
                self.logger.warning(
                    "Session %s not found. Creating new session for user %s.",
                    session_id,
                    user_id,
                )
                db_session = DbSession(
                    id=session_id, user_id=user_id, agent_id=agent_id
                )
                session.add(db_session)
            elif not db_session.agent_id and agent_id:  # type: ignore
                self.logger.info(
                    "Hydrating agent_id for session %s with agent %s",
                    session_id,
                    agent_id,
                )
                db_session.agent_id = agent_id  # type: ignore
            chat_message = ChatMessage(
                id=str(uuid.uuid4()),
                session_id=session_id,
                message=message.get("content"),
                sender_type=message.get("sender_type"),
                sender_name=message.get("sender_name"),
            )
            session.add(chat_message)
            session.commit()
            self.logger.info(
                "Successfully stored message %s for session %s",
                chat_message.id,
                session_id,
            )
            return chat_message.id
        except Exception:
            self.logger.exception("Error storing chat message")
            session.rollback()
            raise
        finally:
            session.close()

    def get_chat_history(self, session_id: str) -> list:
        session = self.Session()
        messages = (
            session.query(ChatMessage)
            .filter_by(session_id=session_id)
            .order_by(ChatMessage.created_at)
            .all()
        )
        session.close()
        return [msg.to_dict() for msg in messages]

    def store_user_info(self, user_id: str, info: dict):
        session = self.Session()
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            user = User(id=user_id, info=json.dumps(info))
            session.add(user)
        else:
            user.info = json.dumps(info)  # type: ignore
        session.commit()
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
        finally:
            session.close()

    def get_session(self, session_id: str) -> Optional[dict]:
        session = self.Session()
        try:
            db_session = session.query(DbSession).filter_by(id=session_id).first()
            if db_session:
                return db_session.to_dict()
            return None
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
        session = self.Session()
        try:
            # First, delete all chat messages associated with the session
            session.query(ChatMessage).filter_by(session_id=session_id).delete()

            # Then, delete the session itself
            db_session = session.query(DbSession).filter_by(id=session_id).first()
            if db_session:
                session.delete(db_session)

            session.commit()
        except Exception:
            self.logger.exception("Error deleting session")
            session.rollback()
            raise
        finally:
            session.close()
