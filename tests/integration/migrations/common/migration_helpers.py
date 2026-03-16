"""Helper functions for testing Alembic migrations."""

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def get_all_revisions(alembic_config: Config) -> list[str]:
    """
    Get all migration revisions in chronological order (oldest to newest).

    Args:
        alembic_config: Alembic configuration object

    Returns:
        List of revision IDs in order
    """
    script = ScriptDirectory.from_config(alembic_config)
    revisions = []

    for rev in script.walk_revisions("base", "heads"):
        revisions.insert(0, rev.revision)

    return revisions


def upgrade_to_revision(alembic_config: Config, revision: str) -> None:
    """
    Upgrade database to a specific revision.

    Args:
        alembic_config: Alembic configuration object
        revision: Target revision ID or "head"
    """
    command.upgrade(alembic_config, revision)


def downgrade_to_revision(alembic_config: Config, revision: str) -> None:
    """
    Downgrade database to a specific revision.

    Args:
        alembic_config: Alembic configuration object
        revision: Target revision ID or "base"
    """
    command.downgrade(alembic_config, revision)


def get_current_revision(alembic_config: Config) -> str:
    """
    Get the current database revision.

    Args:
        alembic_config: Alembic configuration object

    Returns:
        Current revision ID or None if no migrations applied
    """
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine

    url = alembic_config.get_main_option("sqlalchemy.url")
    engine = create_engine(url)

    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current = context.get_current_revision()

    engine.dispose()
    return current


def verify_migration_sequence(
    alembic_config: Config,
    start_revision: str = "base",
    end_revision: str = "head"
) -> bool:
    """
    Verify that migration sequence can be executed without errors.

    Args:
        alembic_config: Alembic configuration object
        start_revision: Starting revision (default: "base")
        end_revision: Ending revision (default: "head")

    Returns:
        True if successful, raises exception otherwise
    """
    # Ensure we're at start
    downgrade_to_revision(alembic_config, start_revision)

    # Upgrade to end
    upgrade_to_revision(alembic_config, end_revision)

    # Verify we're at end
    current = get_current_revision(alembic_config)

    if end_revision == "head":
        # Get actual head revision
        script = ScriptDirectory.from_config(alembic_config)
        heads = script.get_revisions("heads")
        head_revision = heads[0].revision if heads else None

        if current != head_revision:
            raise AssertionError(
                f"Expected to be at head ({head_revision}), but at {current}"
            )
    elif current != end_revision:
        raise AssertionError(
            f"Expected to be at {end_revision}, but at {current}"
        )

    return True
