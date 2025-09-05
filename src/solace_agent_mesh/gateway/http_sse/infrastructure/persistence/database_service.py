import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def get_database_type(database_url: str) -> str:
    """Get the database type from a database URL."""
    if database_url.startswith("sqlite"):
        return "sqlite"
    elif database_url.startswith("postgresql"):
        return "postgresql"
    else:
        return "unknown"


class DatabaseService:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.logger = logging.getLogger(__name__)

        if database_url.startswith("sqlite"):
            self._setup_sqlite_engine(database_url)
        elif database_url.startswith("postgresql"):
            self._setup_postgresql_engine(database_url)
        else:
            # Fallback for other databases
            self._setup_generic_engine(database_url)

        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def _setup_sqlite_engine(self, database_url: str):
        """Configure SQLite-specific engine settings."""
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

    def _setup_postgresql_engine(self, database_url: str):
        """Configure PostgreSQL-specific engine settings."""
        try:
            import psycopg2
        except ImportError:
            raise ImportError(
                "PostgreSQL support requires psycopg2. Install with: "
                "pip install 'solace-agent-mesh[postgresql]'"
            )

        self.engine = create_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=False,
        )

    def _setup_generic_engine(self, database_url: str):
        """Configure generic database engine settings."""
        self.engine = create_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=False,
        )

    def create_tables(self):
        Base.metadata.create_all(bind=self.engine)

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
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
