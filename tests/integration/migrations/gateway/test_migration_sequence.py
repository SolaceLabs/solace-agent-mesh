"""Test Gateway WebUI migration sequences across all database dialects."""
import pytest
from alembic import command
from alembic.script import ScriptDirectory

from tests.integration.migrations.common.db_utils import (
    get_table_names,
    verify_table_exists,
    verify_column_exists,
    verify_index_exists,
)
from tests.integration.migrations.common.migration_helpers import (
    get_all_revisions,
    upgrade_to_revision,
    downgrade_to_revision,
)


class TestMigrationSequence:
    """Test full migration sequences from empty database to HEAD."""

    def test_upgrade_from_empty_to_head(self, alembic_config, db_engine):
        """Test upgrading from empty database to HEAD revision."""
        # Verify database is empty
        tables_before = get_table_names(db_engine, exclude_alembic=True)
        assert len(tables_before) == 0, \
            f"Database should be empty before migration, found: {tables_before}"

        # Run all migrations to HEAD
        command.upgrade(alembic_config, "head")

        # Verify key tables exist
        tables_after = get_table_names(db_engine, exclude_alembic=True)

        expected_tables = {
            "sessions",
            "tasks",
            "task_events",
            "feedback",
            "chat_tasks",
            "projects",
            "project_users",
            "prompts",
            "prompt_groups",
            "prompt_group_users",
        }

        missing_tables = expected_tables - tables_after

        assert not missing_tables, \
            f"Missing expected tables: {missing_tables}. Found: {tables_after}"

    def test_downgrade_from_head_to_base(self, alembic_config, db_engine):
        """Test downgrading from HEAD to base (empty database)."""
        # First upgrade to HEAD
        command.upgrade(alembic_config, "head")

        # Verify tables exist
        tables_mid = get_table_names(db_engine, exclude_alembic=True)
        assert len(tables_mid) > 0, "Should have tables after upgrade"

        # Downgrade to base
        command.downgrade(alembic_config, "base")

        # Verify all tables are gone
        tables_after = get_table_names(db_engine, exclude_alembic=True)

        assert len(tables_after) == 0, \
            f"All tables should be removed. Remaining: {tables_after}"

    @pytest.mark.slow
    def test_upgrade_one_revision_at_a_time(self, alembic_config):
        """Test upgrading one revision at a time from base to HEAD."""
        revisions = get_all_revisions(alembic_config)

        assert len(revisions) > 0, "Should have at least one migration"

        # Upgrade one revision at a time
        for revision in revisions:
            upgrade_to_revision(alembic_config, revision)

    @pytest.mark.slow
    def test_downgrade_one_revision_at_a_time(self, alembic_config):
        """Test downgrading one revision at a time from HEAD to base."""
        # First upgrade to HEAD
        upgrade_to_revision(alembic_config, "head")

        revisions = get_all_revisions(alembic_config)

        # Downgrade one revision at a time
        for i in range(len(revisions)):
            downgrade_to_revision(alembic_config, "-1")


class TestSchemaValidation:
    """Test that resulting schema is correct across dialects."""

    def test_sessions_table_schema(self, alembic_config, db_engine, db_inspector):
        """Verify sessions table has correct columns and types."""
        command.upgrade(alembic_config, "head")

        assert verify_table_exists(db_engine, "sessions"), \
            "sessions table should exist"

        columns = {col["name"]: col for col in db_inspector.get_columns("sessions")}

        # Check required columns exist
        required_columns = {
            "id", "name", "user_id", "agent_id",
            "created_time", "updated_time", "project_id"
        }
        actual_columns = set(columns.keys())
        missing = required_columns - actual_columns

        assert not missing, f"Missing columns in sessions table: {missing}"

        # Check NOT NULL constraints
        assert columns["id"]["nullable"] is False
        assert columns["user_id"]["nullable"] is False
        assert columns["created_time"]["nullable"] is False
        assert columns["updated_time"]["nullable"] is False

    def test_tasks_table_schema(self, alembic_config, db_engine, db_inspector):
        """Verify tasks table has correct columns."""
        command.upgrade(alembic_config, "head")

        assert verify_table_exists(db_engine, "tasks"), \
            "tasks table should exist"

        columns = {col["name"]: col for col in db_inspector.get_columns("tasks")}

        required_columns = {
            "id", "user_id", "start_time", "end_time", "status",
            "initial_request_text", "total_input_tokens", "total_output_tokens"
        }
        actual_columns = set(columns.keys())
        missing = required_columns - actual_columns

        assert not missing, f"Missing columns in tasks table: {missing}"

    def test_indexes_exist(self, alembic_config, db_engine):
        """Verify important indexes are created."""
        command.upgrade(alembic_config, "head")

        # Check sessions indexes
        assert verify_index_exists(db_engine, "sessions", "ix_sessions_user_id") or \
               any("user_id" in idx for idx in db_engine.dialect.get_indexes(None, "sessions") if hasattr(db_engine.dialect, 'get_indexes')), \
            "Should have index on sessions.user_id"

        # Check tasks indexes
        assert verify_index_exists(db_engine, "tasks", "ix_tasks_user_id") or \
               any("user_id" in str(idx) for idx in db_engine.dialect.get_indexes(None, "tasks") if hasattr(db_engine.dialect, 'get_indexes')), \
            "Should have index on tasks.user_id"

    def test_foreign_keys_exist(self, alembic_config, db_inspector):
        """Verify foreign key constraints are created."""
        command.upgrade(alembic_config, "head")

        # Check task_events foreign key to tasks
        task_events_fks = db_inspector.get_foreign_keys("task_events")
        assert len(task_events_fks) > 0, "task_events should have foreign key"

        # Verify it points to tasks table
        fk_to_tasks = any(
            fk["referred_table"] == "tasks"
            for fk in task_events_fks
        )
        assert fk_to_tasks, "task_events should have FK to tasks"


class TestDataIntegrity:
    """Test that data is preserved during migrations."""

    def test_upgrade_preserves_data(self, alembic_config, db_engine):
        """Test that upgrading doesn't lose data."""
        from sqlalchemy import text

        # Upgrade to a point where sessions table exists
        upgrade_to_revision(alembic_config, "f6e7d8c9b0a1")

        # Insert test data
        with db_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO sessions (id, name, user_id, agent_id, created_time, updated_time)
                VALUES ('test-1', 'Test Session', 'user-1', 'agent-1', 1234567890000, 1234567890000)
            """))
            conn.commit()

        # Continue upgrading to HEAD
        upgrade_to_revision(alembic_config, "head")

        # Verify sessions table still exists and has data
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM sessions"))
            count = result.scalar()
            assert count >= 1, "Data should be preserved during migration"


class TestDialectCompatibility:
    """Test dialect compatibility fixes - regression tests for resolved issues."""

    def test_text_column_index_on_mysql(self, alembic_config, db_engine):
        """
        Test TEXT column index works on all dialects.

        Regression test for CRITICAL-1: TEXT index without MySQL prefix.
        Verifies ix_tasks_initial_request_text index is created correctly.
        """
        command.upgrade(alembic_config, "98882922fa59")

        assert verify_index_exists(db_engine, "tasks", "ix_tasks_initial_request_text")

    def test_alter_column_without_existing_type(self, alembic_config):
        """
        Test alter_column operations work on all dialects.

        Regression test for CRITICAL-2: Missing existing_type parameter.
        Verifies column alterations in f6e7d8c9b0a1 migration work correctly.
        """
        command.upgrade(alembic_config, "f6e7d8c9b0a1")

    def test_postgresql_update_syntax(self, alembic_config):
        """
        Test UPDATE operations work on all dialects.

        Regression test for CRITICAL-3: PostgreSQL-only UPDATE syntax.
        Verifies dialect-specific UPDATE...FROM/JOIN logic in 20251202 migration.
        """
        command.upgrade(alembic_config, "20251202_versioned_prompt_fields")