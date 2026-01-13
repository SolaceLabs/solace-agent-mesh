"""
Session repository implementation using SQLAlchemy.
"""

from sqlalchemy import or_, func
from sqlalchemy.orm import Session as DBSession, joinedload

from solace_agent_mesh.shared.database.base_repository import PaginatedRepository
from solace_agent_mesh.shared.api.pagination import PaginationParams
from solace_agent_mesh.shared.utils.types import SessionId, UserId
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from .entities import Session
from .interfaces import ISessionRepository
from .models import CreateSessionModel, SessionModel, UpdateSessionModel


class SessionRepository(PaginatedRepository[SessionModel, Session], ISessionRepository):
    """SQLAlchemy implementation of session repository using BaseRepository."""

    def __init__(self):
        super().__init__(SessionModel, Session)

    @property
    def entity_name(self) -> str:
        """Return the entity name for error messages."""
        return "session"

    def find_by_user(
        self, session: DBSession, user_id: UserId, pagination: PaginationParams | None = None, project_id: str | None = None
    ) -> list[Session]:
        """Find all sessions for a specific user with optional project filtering."""
        query = session.query(SessionModel).filter(
            SessionModel.user_id == user_id,
            SessionModel.deleted_at.is_(None)  # Exclude soft-deleted sessions
        )

        # Optional project filtering for project-specific views
        if project_id is not None:
            query = query.filter(SessionModel.project_id == project_id)

        # Eager load project relationship
        query = query.options(joinedload(SessionModel.project))
        query = query.order_by(SessionModel.updated_time.desc())

        if pagination:
            query = query.offset(pagination.offset).limit(pagination.page_size)

        models = query.all()
        return [Session.model_validate(model) for model in models]

    def count_by_user(self, session: DBSession, user_id: UserId, project_id: str | None = None) -> int:
        """Count total sessions for a specific user with optional project filtering."""
        query = session.query(SessionModel).filter(
            SessionModel.user_id == user_id,
            SessionModel.deleted_at.is_(None)  # Exclude soft-deleted sessions
        )

        # Optional project filtering for project-specific views
        if project_id is not None:
            query = query.filter(SessionModel.project_id == project_id)

        return query.count()

    def find_user_session(
        self, session: DBSession, session_id: SessionId, user_id: UserId
    ) -> Session | None:
        """Find a specific session belonging to a user."""
        model = (
            session.query(SessionModel)
            .filter(
                SessionModel.id == session_id,
                SessionModel.user_id == user_id,
                SessionModel.deleted_at.is_(None)  # Exclude soft-deleted sessions
            )
            .first()
        )
        return Session.model_validate(model) if model else None

    def save(self, db_session: DBSession, session: Session) -> Session:
        """Save or update a session."""
        existing_model = (
            db_session.query(SessionModel).filter(SessionModel.id == session.id).first()
        )

        if existing_model:
            update_model = UpdateSessionModel(
                name=session.name,
                agent_id=session.agent_id,
                project_id=session.project_id,
                updated_time=session.updated_time,
            )
            return self.update(
                db_session, session.id, update_model.model_dump(exclude_none=True)
            )
        else:
            create_model = CreateSessionModel(
                id=session.id,
                name=session.name,
                user_id=session.user_id,
                agent_id=session.agent_id,
                project_id=session.project_id,
                created_time=session.created_time,
                updated_time=session.updated_time,
            )
            return self.create(db_session, create_model.model_dump())

    def delete(self, db_session: DBSession, session_id: SessionId, user_id: UserId) -> bool:
        """Delete a session belonging to a user."""
        # Check if session belongs to user first
        session_model = (
            db_session.query(SessionModel)
            .filter(
                SessionModel.id == session_id,
                SessionModel.user_id == user_id,
            )
            .first()
        )

        if not session_model:
            return False

        # Use BaseRepository delete method
        super().delete(db_session, session_id)
        return True

    def soft_delete(self, db_session: DBSession, session_id: SessionId, user_id: UserId) -> bool:
        """Soft delete a session belonging to a user."""
        session_model = (
            db_session.query(SessionModel)
            .filter(
                SessionModel.id == session_id,
                SessionModel.user_id == user_id,
                SessionModel.deleted_at.is_(None)
            )
            .first()
        )

        if not session_model:
            return False

        # Perform soft delete
        session_model.deleted_at = now_epoch_ms()
        session_model.deleted_by = user_id
        session_model.updated_time = now_epoch_ms()
        
        db_session.flush()
        return True

    def soft_delete_by_project(self, db_session: DBSession, project_id: str, user_id: UserId) -> int:
        """
        Soft delete all sessions belonging to a specific project.
        Used when cascading project deletion.
        
        Args:
            db_session: Database session
            project_id: The project ID
            user_id: The user ID (for deleted_by tracking)
            
        Returns:
            int: Number of sessions soft deleted
        """
        now = now_epoch_ms()
        
        # Find all non-deleted sessions for this project
        sessions_to_delete = (
            db_session.query(SessionModel)
            .filter(
                SessionModel.project_id == project_id,
                SessionModel.user_id == user_id,
                SessionModel.deleted_at.is_(None)
            )
            .all()
        )
        
        # Soft delete each session
        for session_model in sessions_to_delete:
            session_model.deleted_at = now
            session_model.deleted_by = user_id
            session_model.updated_time = now
        
        db_session.flush()
        return len(sessions_to_delete)

    def move_to_project(
        self, db_session: DBSession, session_id: SessionId, user_id: UserId, new_project_id: str | None
    ) -> Session | None:
        """Move a session to a different project."""
        session_model = (
            db_session.query(SessionModel)
            .filter(
                SessionModel.id == session_id,
                SessionModel.user_id == user_id,
                SessionModel.deleted_at.is_(None)
            )
            .first()
        )

        if not session_model:
            return None

        # Update project_id
        session_model.project_id = new_project_id
        session_model.updated_time = now_epoch_ms()
        
        db_session.flush()
        db_session.refresh(session_model)
        
        return Session.model_validate(session_model)

    def search(
        self,
        db_session: DBSession,
        user_id: UserId,
        query: str,
        pagination: PaginationParams | None = None,
        project_id: str | None = None
    ) -> list[Session]:
        """
        Search sessions by name/title only using ILIKE.
        """
        # Base query - only non-deleted sessions for the user
        base_query = db_session.query(SessionModel).filter(
            SessionModel.user_id == user_id,
            SessionModel.deleted_at.is_(None)
        )

        # Optional project filtering
        if project_id is not None:
            base_query = base_query.filter(SessionModel.project_id == project_id)

        # ILIKE search on session name
        search_pattern = f"%{query}%"
        search_query = base_query.filter(SessionModel.name.ilike(search_pattern))

        # Eager load project relationship
        search_query = search_query.options(joinedload(SessionModel.project))
        search_query = search_query.order_by(SessionModel.updated_time.desc())

        if pagination:
            search_query = search_query.offset(pagination.offset).limit(pagination.page_size)

        models = search_query.all()
        return [Session.model_validate(model) for model in models]

    def count_search_results(
        self,
        db_session: DBSession,
        user_id: UserId,
        query: str,
        project_id: str | None = None
    ) -> int:
        """
        Count search results for pagination (title-only search).
        """
        # Base query - only non-deleted sessions for the user
        base_query = db_session.query(SessionModel).filter(
            SessionModel.user_id == user_id,
            SessionModel.deleted_at.is_(None)
        )

        if project_id is not None:
            base_query = base_query.filter(SessionModel.project_id == project_id)

        # ILIKE search on session name
        search_pattern = f"%{query}%"
        search_query = base_query.filter(SessionModel.name.ilike(search_pattern))

        return search_query.count()
