"""ADK specific pytest configuration for migration tests."""
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine


@pytest.fixture
def alembic_config(dialect_db) -> Config:
    """
    Create Alembic config for ADK migrations.

    Points to: src/solace_agent_mesh/agent/adk/alembic

    The ADK migration (e2902798564d) adds columns to the `events` table, which
    is owned by google.adk and created via Base.metadata — not by a SAM migration.
    In production, ADK creates the base schema before running Alembic. We replicate
    that here by calling Base.metadata.create_all() before returning the config.

    Args:
        dialect_db: Database URL from parent conftest (parametrized across dialects)

    Returns:
        Alembic Config object configured for ADK
    """
    from google.adk.sessions.database_session_service import Base

    # Create the ADK base schema (sessions, events, app_states, user_states)
    # before Alembic runs — mirrors what ADK does on startup in production.
    engine = create_engine(dialect_db)
    Base.metadata.create_all(engine)
    engine.dispose()

    config = Config()

    # Point to ADK alembic directory
    script_location = str(
        Path(__file__).parent.parent.parent.parent.parent
        / "src" / "solace_agent_mesh" / "agent" / "adk" / "alembic"
    )

    config.set_main_option("script_location", script_location)
    config.set_main_option("sqlalchemy.url", dialect_db)

    # Enable alembic output for debugging (set to True to suppress)
    config.attributes["quiet"] = False

    return config
