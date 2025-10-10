"""
Multi-database manager for API testing framework.

Manages separate databases for Gateway (with Alembic migrations) and Agents (with direct schema creation).
"""

import asyncio
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text


class MultiDatabaseManager:
    """Manages Gateway DB (with migrations) + Agent DBs (without migrations)"""

    def __init__(self):
        self.gateway_db_url: str | None = None
        self.agent_db_urls: dict[str, str] = {}  # agent_name -> database_url
        self.db_engines: dict[str, any] = {}  # Using SQLAlchemy engines
        self._temp_dir: tempfile.TemporaryDirectory | None = None
        self._cleanup_tasks: list[asyncio.Task] = []

    async def setup_test_databases(self, agent_names: list[str]):
        """Create Gateway DB (with migrations) and Agent DBs (direct schema)"""

        # Create temporary directory for test databases
        self._temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self._temp_dir.name)

        # 1. Create Gateway database with Alembic migrations
        gateway_db_path = temp_path / "test_gateway.db"
        self.gateway_db_url = f"sqlite:///{gateway_db_path}"
        await self._create_database(gateway_db_path)
        await self._run_gateway_migrations(gateway_db_path)

        # 2. Create Agent databases (no migrations, direct schema creation)
        for agent_name in agent_names:
            agent_db_path = temp_path / f"test_{agent_name.lower()}.db"
            agent_db_url = f"sqlite:///{agent_db_path}"
            self.agent_db_urls[agent_name] = agent_db_url
            await self._create_database(agent_db_path)
            await self._create_agent_schema(agent_db_path)

    async def _create_database(self, db_path: Path):
        """Create empty SQLite database file"""
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Touch the file to create it
        db_path.touch()

    async def _run_gateway_migrations(self, db_path: Path):
        """Run Alembic migrations ONLY for Gateway database"""
        # For now, create a basic gateway schema manually using SQLAlchemy
        # In a real implementation, this would use actual Alembic migrations
        engine = create_engine(f"sqlite:///{db_path}")

        with engine.connect() as conn:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(32) NOT NULL,
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                )
            """)
            )

            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS gateway_sessions (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    agent_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            )

            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS gateway_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES gateway_sessions (id)
                )
            """)
            )

            # Insert migration version to indicate migrations were run
            conn.execute(
                text(
                    "INSERT OR REPLACE INTO alembic_version (version_num) VALUES (:version)"
                ),
                {"version": "test_migration_001"},
            )

            conn.commit()

    async def _create_agent_schema(self, db_path: Path):
        """Create Agent database schema directly (no Alembic)"""
        # Agents use direct schema creation, not migrations
        engine = create_engine(f"sqlite:///{db_path}")

        with engine.connect() as conn:
            conn.execute(
                text("""
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
            )

            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS agent_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gateway_session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (gateway_session_id) REFERENCES agent_sessions (gateway_session_id)
                )
            """)
            )

            conn.commit()

    def get_gateway_engine(self):
        """Get SQLAlchemy engine for Gateway database"""
        if "gateway" not in self.db_engines:
            if not self.gateway_db_url:
                raise ValueError("Gateway database not initialized")
            self.db_engines["gateway"] = create_engine(self.gateway_db_url)
        return self.db_engines["gateway"]

    def get_agent_engine(self, agent_name: str):
        """Get SQLAlchemy engine for specific Agent database"""
        if agent_name not in self.db_engines:
            if agent_name not in self.agent_db_urls:
                raise ValueError(f"Agent database for '{agent_name}' not initialized")
            self.db_engines[agent_name] = create_engine(self.agent_db_urls[agent_name])
        return self.db_engines[agent_name]

    async def cleanup_all_databases(self):
        """Clean up all database connections and temporary files"""
        # Dispose all database engines
        for engine in self.db_engines.values():
            if engine:
                engine.dispose()
        self.db_engines.clear()

        # Cancel any cleanup tasks
        for task in self._cleanup_tasks:
            if not task.done():
                task.cancel()

        # Clean up temporary directory
        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None

        # Reset state
        self.gateway_db_url = None
        self.agent_db_urls.clear()


class AlembicMigrationRunner:
    """Handles Alembic migrations for Gateway database only"""

    def __init__(self, database_url: str):
        self.database_url = database_url

    async def run_migrations(self, component_type: str):
        """Run Alembic migrations - only valid for 'gateway' component_type"""
        if component_type != "gateway":
            raise ValueError("Alembic migrations only supported for Gateway database")

        # In a real implementation, this would:
        # 1. Load alembic.ini from the solace-agent-mesh package
        # 2. Run alembic upgrade head with the specific database_url
        # For now, we'll implement basic schema creation
        pass


class AgentSchemaCreator:
    """Handles direct schema creation for Agent databases"""

    def __init__(self, database_url: str):
        self.database_url = database_url

    async def create_tables(self):
        """Create agent database tables directly (no migrations)"""
        # This would use whatever method agents use for persistence setup
        # Could be SQLAlchemy metadata.create_all() or direct DDL
        pass
