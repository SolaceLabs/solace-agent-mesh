"""Tests for SQLite version checking."""
from unittest.mock import MagicMock, patch

import pytest

from src.solace_agent_mesh.shared.database.sqlite_version_check import (
    check_sqlite_version,
)


class TestSQLiteVersionCheck:
    """Test SQLite version validation before running migrations."""

    def test_old_sqlite_version_shows_error_message(self):
        """Test that SQLite 3.34.1 (RHEL 9.7) raises RuntimeError with clear message."""
        database_url = "sqlite:///test.db"

        with patch("sqlalchemy.create_engine") as mock_create_engine:
            # Mock connection to return SQLite 3.34.1 (RHEL 9.7 default)
            mock_conn = MagicMock()
            mock_conn.execute.return_value.scalar.return_value = "3.34.1"
            mock_engine = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_create_engine.return_value = mock_engine

            with pytest.raises(RuntimeError) as exc_info:
                check_sqlite_version(database_url)

            error_message = str(exc_info.value)
            assert "INCOMPATIBLE SQLITE VERSION DETECTED" in error_message
            assert "3.34.1" in error_message
            assert "3.35.0" in error_message
            assert "DROP COLUMN support" in error_message
            assert "RESOLUTION OPTIONS" in error_message
            assert "PostgreSQL" in error_message

    def test_newer_sqlite_version_runs_successfully(self):
        """Test that SQLite 3.35.0+ passes validation and migrations can run."""
        database_url = "sqlite:///test.db"

        with patch("sqlalchemy.create_engine") as mock_create_engine:
            # Mock connection to return SQLite 3.50.4 (current version)
            mock_conn = MagicMock()
            mock_conn.execute.return_value.scalar.return_value = "3.50.4"
            mock_engine = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_create_engine.return_value = mock_engine

            # Should not raise - migrations can proceed
            check_sqlite_version(database_url)
