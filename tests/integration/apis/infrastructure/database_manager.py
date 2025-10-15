"""
Generic, multi-backend database manager for the API testing framework.
"""

import tempfile
from pathlib import Path
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection
from sqlalchemy.engine import Connection
from typing import List, Dict
from abc import ABC, abstractmethod
from sqlalchemy.orm import declarative_base

from sam_test_infrastructure.fastapi_service.webui_backend_factory import (
    WebUIBackendFactory,
)

# Define the Agent schema using SQLAlchemy's declarative base
Base = declarative_base()

class AgentSessions(Base):
    __tablename__ = 'agent_sessions'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    gateway_session_id = sa.Column(sa.String, nullable=False, unique=True)
    agent_name = sa.Column(sa.String, nullable=False)
    user_id = sa.Column(sa.String, nullable=False)
    session_data = sa.Column(sa.Text)
    created_at = sa.Column(sa.DateTime, default=sa.func.current_timestamp())
    updated_at = sa.Column(sa.DateTime, default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp())

class AgentMessages(Base):
    __tablename__ = 'agent_messages'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    gateway_session_id = sa.Column(sa.String, sa.ForeignKey('agent_sessions.gateway_session_id'), nullable=False)
    role = sa.Column(sa.String(50), nullable=False)
    content = sa.Column(sa.Text, nullable=False)
    timestamp = sa.Column(sa.DateTime, default=sa.func.current_timestamp())


class DatabaseProvider(ABC):
    """Abstract base class for a database provider."""
    @abstractmethod
    def setup(self, agent_names: List[str]):
        pass

    @abstractmethod
    def teardown(self):
        pass

    @abstractmethod
    def get_sync_gateway_engine(self) -> sa.Engine:
        pass

    @abstractmethod
    def get_sync_agent_engine(self, agent_name: str) -> sa.Engine:
        pass

    @abstractmethod
    def get_async_gateway_engine(self) -> AsyncEngine:
        pass

    @abstractmethod
    def get_async_agent_engine(self, agent_name: str) -> AsyncEngine:
        pass


class SqliteProvider(DatabaseProvider):
    """A database provider that uses temporary SQLite files."""

    def __init__(self):
        self._sync_engines: Dict[str, sa.Engine] = {}
        self._async_engines: Dict[str, AsyncEngine] = {}
        self._agent_temp_dir = tempfile.TemporaryDirectory()

    def setup(self, agent_names: List[str], db_url: str, engine: sa.Engine):
        # Setup Gateway
        self._sync_engines["gateway"] = engine
        self._async_engines["gateway"] = create_async_engine(
            db_url.replace("sqlite:", "sqlite+aiosqlite:")
        )

        # Setup Agents
        agent_temp_path = Path(self._agent_temp_dir.name)
        for name in agent_names:
            agent_path = agent_temp_path / f"agent_{name}.db"
            agent_sync_engine = sa.create_engine(f"sqlite:///{agent_path}")
            Base.metadata.create_all(agent_sync_engine)
            self._sync_engines[name] = agent_sync_engine
            self._async_engines[name] = create_async_engine(
                f"sqlite+aiosqlite:///{agent_path}"
            )

    def teardown(self):
        for engine in self._sync_engines.values():
            engine.dispose()

        import asyncio

        async def dispose_async():
            for engine in self._async_engines.values():
                await engine.dispose()

        asyncio.run(dispose_async())
        self._agent_temp_dir.cleanup()

    def get_sync_gateway_engine(self) -> sa.Engine:
        return self._sync_engines["gateway"]

    def get_sync_agent_engine(self, agent_name: str) -> sa.Engine:
        if agent_name not in self._sync_engines:
            raise ValueError(f"Agent database for '{agent_name}' not initialized.")
        return self._sync_engines[agent_name]

    def get_async_gateway_engine(self) -> AsyncEngine:
        return self._async_engines["gateway"]

    def get_async_agent_engine(self, agent_name: str) -> AsyncEngine:
        return self._async_engines[agent_name]


class DatabaseManager:
    """A unified database manager that delegates to a provider."""

    def __init__(self, provider: DatabaseProvider):
        self.provider = provider

    def get_gateway_connection(self) -> Connection:
        return self.provider.get_sync_gateway_engine().connect()

    def get_agent_connection(self, agent_name: str) -> Connection:
        return self.provider.get_sync_agent_engine(agent_name).connect()

    async def get_async_gateway_connection(self) -> AsyncConnection:
        engine = self.provider.get_async_gateway_engine()
        return await engine.connect()

    async def get_async_agent_connection(self, agent_name: str) -> AsyncConnection:
        engine = self.provider.get_async_agent_engine(agent_name)
        return await engine.connect()
