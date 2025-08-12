"""
Simple database manager using synchronous SQLite for API testing framework.

A simplified version that uses standard sqlite3 to avoid dependency issues.
"""

import sqlite3
import tempfile
from pathlib import Path


class SimpleDatabaseManager:
    """Manages Gateway DB (with migrations) + Agent DBs (without migrations) using sqlite3"""

    def __init__(self):
        self.gateway_db_path: Path | None = None
        self.agent_db_paths: dict[str, Path] = {}  # agent_name -> database_path
        self._temp_dir: tempfile.TemporaryDirectory | None = None

    def setup_test_databases(self, agent_names: list[str]):
        """Create Gateway DB (with migrations) and Agent DBs (direct schema)"""

        # Create temporary directory for test databases
        self._temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self._temp_dir.name)

        # 1. Create Gateway database with migrations
        self.gateway_db_path = temp_path / "test_gateway.db"
        self._create_database(self.gateway_db_path)
        self._run_gateway_migrations(self.gateway_db_path)

        # 2. Create Agent databases (no migrations, direct schema creation)
        for agent_name in agent_names:
            agent_db_path = temp_path / f"test_{agent_name.lower()}.db"
            self.agent_db_paths[agent_name] = agent_db_path
            self._create_database(agent_db_path)
            self._create_agent_schema(agent_db_path)

    def _create_database(self, db_path: Path):
        """Create empty SQLite database file"""
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Touch the file to create it
        db_path.touch()

    def _run_gateway_migrations(self, db_path: Path):
        """Run migrations for Gateway database"""
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(32) NOT NULL,
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS gateway_sessions (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    agent_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS gateway_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES gateway_sessions (id)
                )
            """)

            # Insert migration version to indicate migrations were run
            conn.execute(
                "INSERT OR REPLACE INTO alembic_version (version_num) VALUES (?)",
                ("test_migration_001",),
            )

            conn.commit()

    def _create_agent_schema(self, db_path: Path):
        """Create Agent database schema directly (no migrations)"""
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gateway_session_id VARCHAR(255) NOT NULL UNIQUE,
                    agent_name VARCHAR(255) NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    session_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gateway_session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (gateway_session_id) REFERENCES agent_sessions (gateway_session_id)
                )
            """)

            conn.commit()

    def get_gateway_connection(self) -> sqlite3.Connection:
        """Get connection to Gateway database"""
        if not self.gateway_db_path:
            raise ValueError("Gateway database not initialized")
        return sqlite3.connect(self.gateway_db_path)

    def get_agent_connection(self, agent_name: str) -> sqlite3.Connection:
        """Get connection to specific Agent database"""
        if agent_name not in self.agent_db_paths:
            raise ValueError(f"Agent database for '{agent_name}' not initialized")
        return sqlite3.connect(self.agent_db_paths[agent_name])

    def cleanup_all_databases(self):
        """Clean up all database connections and temporary files"""
        # Clean up temporary directory
        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None

        # Reset state
        self.gateway_db_path = None
        self.agent_db_paths.clear()
