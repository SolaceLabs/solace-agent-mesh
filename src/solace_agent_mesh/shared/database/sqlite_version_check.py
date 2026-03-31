"""
SQLite Version Validation for Database Migrations

This module provides version checking for SQLite databases to ensure
compatibility with required features (e.g., DROP COLUMN support).
"""

import logging
from typing import Tuple

log = logging.getLogger(__name__)

# Minimum SQLite version required (3.35.0 added DROP COLUMN support)
MINIMUM_SQLITE_VERSION: Tuple[int, int, int] = (3, 35, 0)


def check_sqlite_version(database_url: str, service_name: str = "Service") -> None:
    """
    Verify SQLite version supports required features.

    SQLite 3.35.0+ is required for DROP COLUMN support used in migrations.
    See: https://www.sqlite.org/releaselog/3_35_0.html

    Args:
        database_url: Database connection URL
        service_name: Name of the service for logging purposes

    Raises:
        RuntimeError: If SQLite version is below minimum required version
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine.url import make_url

    try:
        # Parse URL and check if it's SQLite
        url = make_url(database_url)
        if not url.drivername.startswith('sqlite'):
            return

        # Check SQLite version
        engine = create_engine(database_url)
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT sqlite_version()")).scalar()
                version_parts = result.split('.')

                # Parse version (e.g., "3.34.1" -> (3, 34, 1))
                major = int(version_parts[0])
                minor = int(version_parts[1])
                patch = int(version_parts[2]) if len(version_parts) > 2 else 0
                current_version = (major, minor, patch)

                if current_version < MINIMUM_SQLITE_VERSION:
                    min_version_str = '.'.join(map(str, MINIMUM_SQLITE_VERSION))
                    raise RuntimeError(
                        f"\n{'='*80}\n"
                        f"INCOMPATIBLE SQLITE VERSION DETECTED\n"
                        f"{'='*80}\n\n"
                        f"Solace Agent Mesh requires SQLite {min_version_str} or higher.\n\n"
                        f"  Current version:  {result}\n"
                        f"  Required version: {min_version_str}+\n\n"
                        f"SQLite 3.35.0+ is required for DROP COLUMN support used in migrations.\n\n"
                        f"RESOLUTION OPTIONS:\n"
                        f"  1. Upgrade SQLite to version {min_version_str} or higher\n"
                        f"  2. Use PostgreSQL\n"
                        f"{'='*80}\n"
                    )

                log.info("[%s] SQLite version check passed: %s", service_name, result)
        finally:
            # Explicitly dispose engine to release connection pool resources
            engine.dispose()

    except RuntimeError:
        raise
    except Exception as e:
        log.warning("[%s] Could not verify SQLite version: %s", service_name, str(e))
        # Don't fail on version check errors, let migrations attempt to run