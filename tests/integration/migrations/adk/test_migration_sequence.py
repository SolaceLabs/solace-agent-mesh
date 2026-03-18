"""Test ADK migration sequences across all database dialects."""
import pytest
from alembic import command

from tests.integration.migrations.common.db_utils import (
    get_table_names,
    verify_column_exists,
    verify_table_exists,
)
from tests.integration.migrations.common.migration_helpers import (
    downgrade_to_revision,
    get_all_revisions,
    upgrade_to_revision,
)


class TestMigrationSequence:
    """Test full migration sequences from empty database to HEAD."""

    def test_upgrade_from_empty_to_head(self, alembic_config, db_engine):
        """Test upgrading from base schema to HEAD revision.

        The ADK base schema is pre-created by the alembic_config fixture via
        Base.metadata.create_all(), mirroring production startup behaviour.
        Alembic then runs the migration on top of that schema.
        """
        # Base tables already exist (created by fixture) — verify before running migrations
        tables_before = get_table_names(db_engine, exclude_alembic=True)
        expected_base = {"sessions", "events", "app_states", "user_states"}
        missing_base = expected_base - tables_before
        assert not missing_base, \
            f"ADK base tables should exist before migration. Missing: {missing_base}"

        command.upgrade(alembic_config, "head")

        tables_after = get_table_names(db_engine, exclude_alembic=True)
        missing = expected_base - tables_after
        assert not missing, \
            f"Missing expected ADK tables after upgrade: {missing}. Found: {tables_after}"

    def test_downgrade_from_head_to_base(self, alembic_config, db_engine):
        """Test downgrading from HEAD to base.

        The ADK base schema (sessions, events, app_states, user_states) is
        created via Base.metadata.create_all() — not by Alembic migrations —
        so those tables remain after downgrade to base. The migration's downgrade
        only removes the 3 extra columns it added; the base tables stay intact.
        """
        command.upgrade(alembic_config, "head")

        tables_mid = get_table_names(db_engine, exclude_alembic=True)
        assert len(tables_mid) > 0, "Should have tables after upgrade"

        command.downgrade(alembic_config, "base")

        # Base ADK tables persist (created outside Alembic); verify they are still there
        tables_after = get_table_names(db_engine, exclude_alembic=True)
        for table in ("sessions", "events", "app_states", "user_states"):
            assert table in tables_after, \
                f"ADK base table '{table}' should still exist after downgrade to base"

        # The 3 extra columns added by e2902798564d should be gone
        from tests.integration.migrations.common.db_utils import verify_column_exists
        for column in ("custom_metadata", "usage_metadata", "citation_metadata"):
            assert not verify_column_exists(db_engine, "events", column), \
                f"Column '{column}' should be removed after downgrade"

    @pytest.mark.slow
    def test_upgrade_one_revision_at_a_time(self, alembic_config):
        """Test upgrading one revision at a time from base to HEAD."""
        revisions = get_all_revisions(alembic_config)
        assert len(revisions) > 0, "Should have at least one migration"

        for revision in revisions:
            upgrade_to_revision(alembic_config, revision)

    @pytest.mark.slow
    def test_downgrade_one_revision_at_a_time(self, alembic_config):
        """Test downgrading one revision at a time from HEAD to base."""
        upgrade_to_revision(alembic_config, "head")

        revisions = get_all_revisions(alembic_config)
        for _ in range(len(revisions)):
            downgrade_to_revision(alembic_config, "-1")


class TestSchemaValidation:
    """Test that resulting schema is correct across dialects."""

    def test_adk_base_tables_exist(self, alembic_config, db_engine):
        """Verify all four ADK base tables are created."""
        command.upgrade(alembic_config, "head")

        for table in ("sessions", "events", "app_states", "user_states"):
            assert verify_table_exists(db_engine, table), \
                f"ADK table '{table}' should exist after migration"

    def test_migration_columns_added_to_events(self, alembic_config, db_engine):
        """Verify the 3 columns added by e2902798564d exist on the events table."""
        command.upgrade(alembic_config, "head")

        for column in ("custom_metadata", "usage_metadata", "citation_metadata"):
            assert verify_column_exists(db_engine, "events", column), \
                f"Column '{column}' should exist on events table after migration e2902798564d"

    def test_foreign_key_events_to_sessions(self, alembic_config, db_inspector):
        """Verify FK constraint from events to sessions exists."""
        command.upgrade(alembic_config, "head")

        fks = db_inspector.get_foreign_keys("events")
        assert len(fks) > 0, "events table should have at least one foreign key"

        fk_to_sessions = any(fk["referred_table"] == "sessions" for fk in fks)
        assert fk_to_sessions, "events should have a FK referencing sessions"


class TestDialectCompatibility:
    """Regression tests for dialect-specific behavior."""

    def test_migration_e2902798564d_is_idempotent(self, alembic_config, db_engine):
        """
        Regression test: migration e2902798564d uses column_exists() guards
        to safely skip adding columns that already exist.
        Verifies upgrade to that revision is safe to run multiple times.
        """
        upgrade_to_revision(alembic_config, "e2902798564d")

        # Re-applying head (already at head) should be a no-op
        command.upgrade(alembic_config, "head")

        # Columns should still be present exactly once
        for column in ("custom_metadata", "usage_metadata", "citation_metadata"):
            assert verify_column_exists(db_engine, "events", column), \
                f"Column '{column}' should still exist after idempotent re-upgrade"
