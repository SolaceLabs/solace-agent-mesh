"""
Database service with industry-standard transaction management.
Following SQLAlchemy best practices and context manager patterns.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from ..models import Base


class DatabaseService:
    """
    Database service with industry-standard transaction management.

    Uses SQLAlchemy's recommended patterns:
    - Context managers for automatic transaction handling
    - Proper session lifecycle management
    - Optimized connection pooling
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.logger = logging.getLogger(__name__)

        if database_url.startswith("sqlite"):
            self.engine = create_engine(
                database_url,
                echo=False,
                connect_args={
                    "check_same_thread": False,
                },
            )

            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        else:
            self.engine = create_engine(
                database_url,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True,
                echo=False,
            )

        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def create_tables(self):
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


database_service: DatabaseService = None


def get_database_service() -> DatabaseService:
    return database_service
