"""
Multi-database manager for API testing framework.

Manages separate databases for Gateway (with Alembic migrations) and Agents (with direct schema creation).
"""

import asyncio
import tempfile
from pathlib import Path
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection


class MultiDatabaseManager:
    """Manages Gateway DB (with migrations) + Agent DBs (without migrations) using SQLAlchemy"""

    def __init__(self):
        self.gateway_db_url: str | None = None
        self.agent_db_urls: dict[str, str] = {}
        self.gateway_engine: AsyncEngine | None = None
        self.agent_engines: dict[str, AsyncEngine] = {}
        self._temp_dir: tempfile.TemporaryDirectory | None = None

    async def setup_test_databases(self, agent_names: list[str]):
        """Create Gateway DB and Agent DBs with their respective schemas"""
        self._temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self._temp_dir.name)

        # 1. Create Gateway database and engine
        gateway_db_path = temp_path / "test_gateway.db"
        self.gateway_db_url = f"sqlite+aiosqlite:///{gateway_db_path}"
        self.gateway_engine = self._create_engine(self.gateway_db_url)
        await self._run_gateway_migrations(self.gateway_engine)

        # 2. Create Agent databases and engines
        for agent_name in agent_names:
            agent_db_path = temp_path / f"test_{agent_name.lower()}.db"
            agent_db_url = f"sqlite+aiosqlite:///{agent_db_path}"
            self.agent_db_urls[agent_name] = agent_db_url
            engine = self._create_engine(agent_db_url)
            self.agent_engines[agent_name] = engine
            await self._create_agent_schema(engine)

    def _create_engine(self, db_url: str) -> AsyncEngine:
        """Creates an async SQLAlchemy engine for a given database URL."""
        engine = create_async_engine(db_url)
        # Foreign key pragmas are handled by default in modern aiosqlite
        return engine

    async def _run_gateway_migrations(self, engine: AsyncEngine):
        """Run migrations for Gateway database"""
        async with engine.begin() as conn:
            await conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(32) NOT NULL,
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                )
            """))
            await conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS gateway_sessions (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    agent_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            await conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS gateway_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES gateway_sessions (id)
                )
            """))
            await conn.execute(
                sa.text("INSERT OR REPLACE INTO alembic_version (version_num) VALUES (:ver)"),
                {"ver": "test_migration_001"},
            )

    async def _create_agent_schema(self, engine: AsyncEngine):
        """Create Agent database schema directly"""
        async with engine.begin() as conn:
            await conn.execute(sa.text("""
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
            await conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS agent_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gateway_session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (gateway_session_id) REFERENCES agent_sessions (gateway_session_id)
                )
            """))

    async def get_gateway_connection(self) -> AsyncConnection:
        """Get async connection to Gateway database"""
        if not self.gateway_engine:
            raise ValueError("Gateway database not initialized")
        return await self.gateway_engine.connect()

    async def get_agent_connection(self, agent_name: str) -> AsyncConnection:
        """Get async connection to specific Agent database"""
        if agent_name not in self.agent_engines:
            raise ValueError(f"Agent database for '{agent_name}' not initialized")
        return await self.agent_engines[agent_name].connect()

    async def cleanup_all_databases(self):
        """Clean up all database connections and temporary files"""
        for engine in self.agent_engines.values():
            await engine.dispose()
        if self.gateway_engine:
            await self.gateway_engine.dispose()

        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None

        self.gateway_db_url = None
        self.agent_db_urls.clear()
        self.gateway_engine = None
        self.agent_engines.clear()
