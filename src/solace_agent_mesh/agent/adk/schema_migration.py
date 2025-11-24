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
        # Get paths to alembic directory and config (relative to this file)
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

        # Set the database URL from the service
        # IMPORTANT: Use render_as_string(hide_password=False) to preserve credentials
        # for Alembic. By default, str(url) obscures the password for security.

        log.info(
            "%s BEFORE render - URL with masked password: %s",
            component.log_identifier,
            str(db_service.db_engine.url)  # This masks the password
        )

        db_url = db_service.db_engine.url.render_as_string(hide_password=False)
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        # TEMPORARY DEBUG LOGGING - Remove after debugging credential issues
        url_obj = db_service.db_engine.url
        password = url_obj.password if hasattr(url_obj, 'password') else None
        if password:
            pwd_preview = f"{password[:4]}...{password[-4:]}" if len(password) > 8 else f"{password[:2]}...{password[-2:]}"
            has_special = bool(re.search(r'[@#:/?&=%\s]', password))
        else:
            pwd_preview = "None"
            has_special = False

        log.info(
            "%s Database URL components - dialect: %s, user: %s, password: %s (len:%d, has_special_chars:%s), "
            "host: %s, port: %s, database: %s",
            component.log_identifier,
            url_obj.drivername,
            url_obj.username,
            pwd_preview,
            len(password) if password else 0,
            has_special,
            url_obj.host,
            url_obj.port,
            url_obj.database,
        )

        log.info(
            "%s Running Alembic migrations for ADK schema compatibility...",
            component.log_identifier
        )

        # Run migrations (equivalent to: alembic upgrade head)
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
