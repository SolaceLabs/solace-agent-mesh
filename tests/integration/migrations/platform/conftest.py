"""Platform service specific pytest configuration for migration tests."""
from pathlib import Path
import pytest
from alembic.config import Config


@pytest.fixture
def alembic_config(dialect_db) -> Config:
    """
    Create Alembic config for Platform service migrations.

    Points to: src/solace_agent_mesh/services/platform/alembic

    Args:
        dialect_db: Database URL from parent conftest (parametrized across dialects)

    Returns:
        Alembic Config object configured for Platform service
    """
    config = Config()

    # Point to Platform service alembic directory
    script_location = str(
        Path(__file__).parent.parent.parent.parent.parent
        / "src" / "solace_agent_mesh" / "services" / "platform" / "alembic"
    )

    config.set_main_option("script_location", script_location)
    config.set_main_option("sqlalchemy.url", dialect_db)

    # Enable alembic output for debugging (set to True to suppress)
    config.attributes["quiet"] = False

    return config