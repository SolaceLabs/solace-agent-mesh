"""
Generic, multi-backend database manager for the API testing framework.
"""

import tempfile
import os
from pathlib import Path
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection
from sqlalchemy.engine import Connection
from typing import List, Dict, Type
from abc import ABC, abstractmethod
from sqlalchemy.orm import declarative_base

from sam_test_infrastructure.fastapi_service.webui_backend_factory import (
    WebUIBackendFactory,
)

# Import testcontainers and database drivers
from testcontainers.postgres import PostgresContainer
import psycopg2

# Define the Agent schema using SQLAlchemy's declarative base
Base = declarative_base()

class AgentSessions(Base):
    __tablename__ = 'agent_sessions'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    gateway_session_id = sa.Column(sa.String(255), nullable=False, unique=True)
    agent_name = sa.Column(sa.String(255), nullable=False)
    user_id = sa.Column(sa.String(255), nullable=False)
    session_data = sa.Column(sa.Text)
    created_at = sa.Column(sa.DateTime, default=sa.func.current_timestamp())
    updated_at = sa.Column(sa.DateTime, default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp())

class AgentMessages(Base):
    __tablename__ = 'agent_messages'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    gateway_session_id = sa.Column(sa.String(255), sa.ForeignKey('agent_sessions.gateway_session_id'), nullable=False)
    role = sa.Column(sa.String(50), nullable=False)
    content = sa.Column(sa.Text, nullable=False)
    timestamp = sa.Column(sa.DateTime, default=sa.func.current_timestamp())


class DatabaseProvider(ABC):
    """Abstract base class for a database provider."""
    
    @abstractmethod
    def setup(self, agent_names: List[str], **kwargs):
        """Setup databases. Kwargs allow provider-specific configuration."""
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
    
    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Return the database type (sqlite, postgresql, mysql)."""
        pass


class SqliteProvider(DatabaseProvider):
    """A database provider that uses temporary SQLite files."""

    def __init__(self):
        self._sync_engines: Dict[str, sa.Engine] = {}
        self._async_engines: Dict[str, AsyncEngine] = {}
        self._agent_temp_dir = tempfile.TemporaryDirectory()

    def setup(self, agent_names: List[str], db_url: str = None, engine: sa.Engine = None, **kwargs):
        # Setup Gateway - support both old and new calling patterns
        if engine is not None and db_url is not None:
            # Legacy mode - use provided engine and URL
            self._sync_engines["gateway"] = engine
            self._async_engines["gateway"] = create_async_engine(
                db_url.replace("sqlite:", "sqlite+aiosqlite:")
            )
        else:
            # New mode - create our own temporary SQLite
            temp_path = Path(self._agent_temp_dir.name) / "gateway.db"
            gateway_url = f"sqlite:///{temp_path}"
            self._sync_engines["gateway"] = sa.create_engine(
                gateway_url,
                connect_args={"check_same_thread": False}
            )
            self._async_engines["gateway"] = create_async_engine(
                f"sqlite+aiosqlite:///{temp_path}"
            )
            Base.metadata.create_all(self._sync_engines["gateway"])

        # Setup Agents
        agent_temp_path = Path(self._agent_temp_dir.name)
        for name in agent_names:
            agent_path = agent_temp_path / f"agent_{name}.db"
            agent_sync_engine = sa.create_engine(
                f"sqlite:///{agent_path}",
                connect_args={"check_same_thread": False}
            )
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

    @property
    def provider_type(self) -> str:
        return "sqlite"


class PostgreSQLProvider(DatabaseProvider):
    """A database provider that uses testcontainers PostgreSQL."""

    def __init__(self):
        self._sync_engines: Dict[str, sa.Engine] = {}
        self._async_engines: Dict[str, AsyncEngine] = {}
        self._container = None
        self._base_url = None

    def setup(self, agent_names: List[str], **kwargs):
        # Start PostgreSQL container
        self._container = PostgresContainer("postgres:15")
        self._container.start()
        
        # Get connection details
        host = self._container.get_container_host_ip()
        port = self._container.get_exposed_port(5432)
        user = self._container.username
        password = self._container.password
        database = self._container.dbname
        
        self._base_url = f"postgresql://{user}:{password}@{host}:{port}"
        
        # Setup Gateway database
        gateway_url = f"{self._base_url}/{database}"
        gateway_async_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
        
        self._sync_engines["gateway"] = sa.create_engine(gateway_url, pool_pre_ping=True)
        self._async_engines["gateway"] = create_async_engine(gateway_async_url)
        
        # Create tables in gateway database
        Base.metadata.create_all(self._sync_engines["gateway"])
        
        # Setup Agent databases
        for name in agent_names:
            agent_db_name = f"agent_{name.lower()}"
            self._create_database(agent_db_name)
            
            agent_url = f"{self._base_url}/{agent_db_name}"
            agent_async_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{agent_db_name}"
            
            self._sync_engines[name] = sa.create_engine(agent_url, pool_pre_ping=True)
            self._async_engines[name] = create_async_engine(agent_async_url)
            
            # Create tables in agent database
            Base.metadata.create_all(self._sync_engines[name])

    def _create_database(self, db_name: str):
        """Create a new database in the PostgreSQL container."""
        # Connect to the default database to create new ones
        host = self._container.get_container_host_ip()
        port = self._container.get_exposed_port(5432)
        
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=self._container.username,
            password=self._container.password,
            database=self._container.dbname
        )
        conn.autocommit = True
        
        with conn.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE "{db_name}"')
        
        conn.close()

    def teardown(self):
        # Clean up WebUIBackendFactory if it exists
        if hasattr(self, '_webui_factory'):
            self._webui_factory.teardown()
        
        for engine in self._sync_engines.values():
            engine.dispose()

        import asyncio
        async def dispose_async():
            for engine in self._async_engines.values():
                await engine.dispose()

        asyncio.run(dispose_async())
        
        if self._container:
            self._container.stop()

    @property
    def provider_type(self) -> str:
        return "postgresql"

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


class DatabaseProviderFactory:
    """Factory for creating database providers based on configuration."""
    
    PROVIDERS = {
        "sqlite": SqliteProvider,
        "postgresql": PostgreSQLProvider,
    }
    
    @classmethod
    def create_provider(cls, provider_type: str) -> DatabaseProvider:
        """Create a database provider instance."""
        if provider_type is None:
            raise ValueError("provider_type is required")
        
        provider_type = provider_type.lower()
        
        if provider_type not in cls.PROVIDERS:
            raise ValueError(f"Unknown provider type: {provider_type}. Available: {list(cls.PROVIDERS.keys())}")
        
        return cls.PROVIDERS[provider_type]()
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of available database providers."""
        return list(cls.PROVIDERS.keys())


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
