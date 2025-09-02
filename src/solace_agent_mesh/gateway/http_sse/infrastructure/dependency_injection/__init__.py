"""
Simple dependency injection for FastAPI.
"""

from ...business.services.session_service import SessionService
from ...data.persistence.database_service import DatabaseService


def get_database_service() -> DatabaseService:
    """Get database service instance."""
    # This would be initialized from main.py
    from ...main import database_service
    return database_service