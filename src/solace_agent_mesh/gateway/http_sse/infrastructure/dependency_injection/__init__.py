"""
Simple dependency injection for FastAPI.
"""

from ...business.services.session_service import SessionService
from ...business.services.project_service import ProjectService
from ...data.persistence.database_service import DatabaseService
from ...data.repositories.project_repository import ProjectRepository


def get_database_service() -> DatabaseService:
    """Get database service instance."""
    # This would be initialized from main.py
    from ...main import database_service
    return database_service


def get_session_service() -> SessionService:
    """Get session service instance."""
    return SessionService(db_service=get_database_service())


def get_project_service() -> ProjectService:
    """Get project service instance."""
    db_service = get_database_service()
    project_repository = ProjectRepository(db_service)
    return ProjectService(project_repository)


__all__ = [
    "get_session_service",
    "get_project_service",
]