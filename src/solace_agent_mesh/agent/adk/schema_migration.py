"""
ADK Database Schema Migrations

Automatically runs Alembic migrations on agent startup to ensure
database schema compatibility with the installed ADK version.

This uses Google ADK's official migration approach via Alembic's
autogenerate feature to detect and apply schema changes.
"""

import logging
import re
from pathlib import Path
from alembic.config import Config
from alembic import command

log = logging.getLogger(__name__)


def run_migrations(db_service, component):
    """
    Run Alembic database migrations programmatically.

    Executes any pending migrations to ensure the database schema
    matches ADK's model definitions. This is equivalent to running:
        alembic upgrade head

    Args:
        db_service: DatabaseSessionService instance
        component: Component that owns this service (for logging)

    Raises:
        RuntimeError: If migration fails
    """

    try:
        # Get paths to alembic directory and config
        module_dir = Path(__file__).parent
        alembic_ini = module_dir / "alembic.ini"
        alembic_dir = module_dir / "alembic"

        # Verify files exist
        if not alembic_ini.exists():
            log.warning(
                "%s alembic.ini not found at %s, skipping migration",
                component.log_identifier,
                alembic_ini
            )
            return

        if not alembic_dir.exists():
            log.warning(
                "%s alembic/ directory not found at %s, skipping migration",
                component.log_identifier,
                alembic_dir
            )
            return

        # Create Alembic config
        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option("script_location", str(alembic_dir))
        
        # IMPORTANT: Store the engine in config attributes so env.py can access it
        # This avoids URL encoding issues entirely
        alembic_cfg.attributes['connection'] = db_service.db_engine

        log.info(
            "%s Running Alembic migrations for ADK schema compatibility...",
            component.log_identifier
        )

        # Run migrations (equivalent to: alembic upgrade head)
        # Run migrations (env.py will use the engine from attributes)
        command.upgrade(alembic_cfg, "head")

        log.info(
            "%s Database schema migration complete",
            component.log_identifier
        )

    except Exception as e:
        log.error(
            "%s Database migration failed: %s",
            component.log_identifier,
            e
        )
        raise RuntimeError(f"ADK database migration failed: {e}") from e
    