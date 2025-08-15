"""
Modern database service with industry-standard transaction management.
Following SQLAlchemy best practices and context manager patterns.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import logging

from ..models import Base


class DatabaseService:
    """
    Modern database service with industry-standard transaction management.
    
    Uses SQLAlchemy's recommended patterns:
    - Context managers for automatic transaction handling
    - Proper session lifecycle management
    - Optimized connection pooling
    """
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.logger = logging.getLogger(__name__)
        
        # Industry-standard connection pool configuration
        if database_url.startswith('sqlite'):
            # SQLite: Optimized for testing and development
            self.engine = create_engine(
                database_url,
                echo=False,
                # SQLite-specific optimizations
                connect_args={"check_same_thread": False}
            )
        else:
            # Production databases: PostgreSQL, MySQL, etc.
            self.engine = create_engine(
                database_url,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True,
                echo=False
            )
        
        self.SessionLocal = sessionmaker(
            autocommit=False, 
            autoflush=False, 
            bind=self.engine
        )
    
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope around a series of operations.
        
        This is the industry-standard pattern for transaction management.
        Automatically handles commit/rollback and session cleanup.
        
        Usage:
            with db_service.session_scope() as session:
                user = User(name="John")
                session.add(user)
                # Automatic commit on success, rollback on exception
        """
        session = self.SessionLocal()
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
    def read_only_session(self) -> Generator[Session, None, None]:
        """
        Provide a read-only session for queries.
        
        Optimized for read operations - no commit needed.
        Automatically handles session cleanup.
        
        Usage:
            with db_service.read_only_session() as session:
                users = session.query(User).all()
        """
        session = self.SessionLocal()
        try:
            yield session
        except Exception as e:
            session.rollback()
            self.logger.error(f"Database read operation failed: {e}")
            raise
        finally:
            session.close()
    
    # Legacy compatibility methods (deprecated - use session_scope instead)
    def get_session(self) -> Generator[Session, None, None]:
        """
        DEPRECATED: Use session_scope() instead.
        Legacy method for backward compatibility.
        """
        self.logger.warning("get_session() is deprecated. Use session_scope() instead.")
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    @contextmanager
    def get_session_context(self) -> Generator[Session, None, None]:
        """
        DEPRECATED: Use session_scope() instead.
        Legacy method for backward compatibility.
        """
        self.logger.warning("get_session_context() is deprecated. Use session_scope() instead.")
        with self.session_scope() as session:
            yield session


# Global database service instance - will be initialized in dependency injection
database_service: DatabaseService = None


def get_database_service() -> DatabaseService:
    """Get the global database service instance."""
    return database_service


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency for getting database session."""
    db_service = get_database_service()
    with db_service.get_session_context() as session:
        yield session