"""
Simple database manager using SQLAlchemy for API testing framework.

Manages database engines and connections for the Gateway and Agent databases.
"""

import tempfile
from pathlib import Path
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool


class SimpleDatabaseManager:
    """Manages Gateway DB (with migrations) + Agent DBs (without migrations) using SQLAlchemy"""

    def __init__(self):
        self.gateway_db_path: Path | None = None
        self.agent_db_paths: dict[str, Path] = {}
        self.gateway_engine: sa.Engine | None = None
        self.agent_engines: dict[str, sa.Engine] = {}
        self._temp_dir: tempfile.TemporaryDirectory | None = None

    def setup_test_databases(self, agent_names: list[str]):
        """Create Gateway DB and Agent DBs with their respective schemas"""
        self._temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self._temp_dir.name)

        # 1. Create Gateway database and engine
        self.gateway_db_path = temp_path / "test_gateway.db"
        self.gateway_engine = self._create_engine(self.gateway_db_path)
        self._run_gateway_migrations(self.gateway_engine)

        # 2. Create Agent databases and engines
        for agent_name in agent_names:
            agent_db_path = temp_path / f"test_{agent_name.lower()}.db"
            self.agent_db_paths[agent_name] = agent_db_path
            engine = self._create_engine(agent_db_path)
            self.agent_engines[agent_name] = engine
            self._create_agent_schema(engine)

    def _create_engine(self, db_path: Path) -> sa.Engine:
        """Creates a SQLAlchemy engine for a given database path."""
        db_url = f"sqlite:///{db_path}"
        engine = sa.create_engine(
            db_url,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        # Enable foreign keys for SQLite
        @sa.event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        return engine

    def _run_gateway_migrations(self, engine: sa.Engine):
        """Run migrations for Gateway database"""
        with engine.connect() as conn:
            conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(32) NOT NULL,
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                )
            """))
            conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS gateway_sessions (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    agent_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS gateway_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES gateway_sessions (id)
                )
            """))
            conn.execute(
                sa.text("INSERT OR REPLACE INTO alembic_version (version_num) VALUES (:ver)"),
                {"ver": "test_migration_001"},
            )
            if conn.in_transaction():
                conn.commit()

    def _create_agent_schema(self, engine: sa.Engine):
        """Create Agent database schema directly"""
        with engine.connect() as conn:
            conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gateway_session_id VARCHAR(255) NOT NULL UNIQUE,
                    agent_name VARCHAR(255) NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    session_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS agent_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gateway_session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (gateway_session_id) REFERENCES agent_sessions (gateway_session_id)
                )
            """))
            if conn.in_transaction():
                conn.commit()

    def get_gateway_connection(self) -> sa.engine.Connection:
        """Get connection to Gateway database"""
        if not self.gateway_engine:
            raise ValueError("Gateway database not initialized")
        return self.gateway_engine.connect()

    def get_agent_connection(self, agent_name: str) -> sa.engine.Connection:
        """Get connection to specific Agent database"""
        if agent_name not in self.agent_engines:
            raise ValueError(f"Agent database for '{agent_name}' not initialized")
        return self.agent_engines[agent_name].connect()

    def cleanup_all_databases(self):
        """Clean up all database connections and temporary files"""
        for engine in self.agent_engines.values():
            engine.dispose()
        if self.gateway_engine:
            self.gateway_engine.dispose()

        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None

        self.gateway_db_path = None
        self.agent_db_paths.clear()
        self.gateway_engine = None
        self.agent_engines.clear()
