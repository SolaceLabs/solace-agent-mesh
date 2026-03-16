"""Gateway WebUI specific pytest configuration for migration tests."""
from pathlib import Path
import pytest
from alembic.config import Config


@pytest.fixture
def alembic_config(dialect_db) -> Config:
    """
    Create Alembic config for Gateway WebUI migrations.

    Points to: src/solace_agent_mesh/gateway/http_sse/alembic

    Args:
        dialect_db: Database URL from parent conftest (parametrized across dialects)

    Returns:
        Alembic Config object configured for Gateway WebUI
    """
    config = Config()

    # Point to Gateway WebUI alembic directory
    script_location = str(
        Path(__file__).parent.parent.parent.parent.parent
        / "src" / "solace_agent_mesh" / "gateway" / "http_sse" / "alembic"
    )

    config.set_main_option("script_location", script_location)
    config.set_main_option("sqlalchemy.url", dialect_db)

    # Enable alembic output for debugging (set to True to suppress)
    config.attributes["quiet"] = False

    return config