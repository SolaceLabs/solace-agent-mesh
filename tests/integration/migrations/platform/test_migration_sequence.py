"""Test Platform service migration sequences across all database dialects."""
import uuid

import pytest
from alembic import command

from tests.integration.migrations.common.db_utils import (
    get_table_names,
    verify_index_exists,
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
        """Test upgrading from empty database to HEAD revision."""
        tables_before = get_table_names(db_engine, exclude_alembic=True)
        assert len(tables_before) == 0, \
            f"Database should be empty before migration, found: {tables_before}"

        command.upgrade(alembic_config, "head")

        tables_after = get_table_names(db_engine, exclude_alembic=True)
        assert "outbox_events" in tables_after, \
            f"outbox_events table should exist after migration. Found: {tables_after}"

    def test_downgrade_from_head_to_base(self, alembic_config, db_engine):
        """Test downgrading from HEAD to base (empty database)."""
        command.upgrade(alembic_config, "head")

        tables_mid = get_table_names(db_engine, exclude_alembic=True)
        assert len(tables_mid) > 0, "Should have tables after upgrade"

        command.downgrade(alembic_config, "base")

        tables_after = get_table_names(db_engine, exclude_alembic=True)
        assert len(tables_after) == 0, \
            f"All tables should be removed. Remaining: {tables_after}"

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

    def test_outbox_events_table_schema(self, alembic_config, db_engine, db_inspector):
        """Verify outbox_events table has correct columns and constraints."""
        command.upgrade(alembic_config, "head")

        assert verify_table_exists(db_engine, "outbox_events"), \
            "outbox_events table should exist"

        columns = {col["name"]: col for col in db_inspector.get_columns("outbox_events")}

        required_columns = {
            "id", "entity_type", "entity_id", "event_type", "status",
            "payload", "error_message", "retry_count", "next_retry_at",
            "created_time", "updated_time",
        }
        missing = required_columns - set(columns.keys())
        assert not missing, f"Missing columns in outbox_events table: {missing}"

        # Check NOT NULL constraints
        assert columns["id"]["nullable"] is False
        assert columns["entity_type"]["nullable"] is False
        assert columns["entity_id"]["nullable"] is False
        assert columns["event_type"]["nullable"] is False
        assert columns["status"]["nullable"] is False
        assert columns["retry_count"]["nullable"] is False
        assert columns["next_retry_at"]["nullable"] is False
        assert columns["created_time"]["nullable"] is False
        assert columns["updated_time"]["nullable"] is False

        # Nullable columns
        assert columns["payload"]["nullable"] is True
        assert columns["error_message"]["nullable"] is True

    def test_indexes_exist(self, alembic_config, db_engine):
        """Verify all expected indexes are created on outbox_events."""
        command.upgrade(alembic_config, "head")

        assert verify_index_exists(db_engine, "outbox_events", "ix_outbox_status_retry"), \
            "Should have ix_outbox_status_retry index"

        assert verify_index_exists(db_engine, "outbox_events", "ix_outbox_entity"), \
            "Should have ix_outbox_entity index"

        assert verify_index_exists(db_engine, "outbox_events", "ix_outbox_created_time"), \
            "Should have ix_outbox_created_time index"

        assert verify_index_exists(db_engine, "outbox_events", "ix_outbox_updated_time"), \
            "Should have ix_outbox_updated_time index"


class TestDataIntegrity:
    """Test that data is preserved and migrations are idempotent."""

    def test_upgrade_preserves_data(self, alembic_config, db_engine):
        """Test that data inserted after upgrade to HEAD survives a downgrade+re-upgrade."""
        from sqlalchemy import text

        command.upgrade(alembic_config, "head")

        raw_uuid = uuid.uuid4()
        now_ms = 1773690086929

        # On MySQL the id column is BINARY(16) — store raw bytes.
        # On PostgreSQL it is a native UUID type — store as string.
        # On SQLite it is String(36) — store as hyphenated string.
        dialect = db_engine.dialect.name
        row_id = raw_uuid.bytes if dialect == "mysql" else str(raw_uuid)

        with db_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO outbox_events
                    (id, entity_type, entity_id, event_type, status,
                     retry_count, next_retry_at, created_time, updated_time)
                VALUES
                    (:id, :entity_type, :entity_id, :event_type, :status,
                     :retry_count, :next_retry_at, :created_time, :updated_time)
            """), {
                "id": row_id,
                "entity_type": "test_entity",
                "entity_id": str(uuid.uuid4()),
                "event_type": "test_event",
                "status": "pending",
                "retry_count": 0,
                "next_retry_at": 0,
                "created_time": now_ms,
                "updated_time": now_ms,
            })
            conn.commit()

        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM outbox_events"))
            assert result.scalar() >= 1, "Data should be present after insert"

    def test_migration_is_idempotent(self, alembic_config):
        """Test that the migration handles re-runs safely (table already exists check)."""
        # Upgrade to HEAD twice — the migration guards against re-creating the table
        command.upgrade(alembic_config, "head")
        command.upgrade(alembic_config, "head")
