"""Tests for sync/async database URL translation helpers."""

import pytest

from solace_agent_mesh.shared.database.database_helpers import (
    to_async_db_url,
    to_sync_db_url,
)


class TestToAsyncDbUrl:
    @pytest.mark.parametrize(
        "sync_url,expected",
        [
            ("sqlite:///some/path.db", "sqlite+aiosqlite:///some/path.db"),
            ("sqlite:///:memory:", "sqlite+aiosqlite:///:memory:"),
            (
                "postgresql://user:pass@host:5432/db",
                "postgresql+asyncpg://user:pass@host:5432/db",
            ),
            (
                "postgresql+psycopg2://user:pass@host/db",
                "postgresql+asyncpg://user:pass@host/db",
            ),
            ("mysql://user:pass@host/db", "mysql+aiomysql://user:pass@host/db"),
            (
                "mysql+pymysql://user:pass@host/db",
                "mysql+aiomysql://user:pass@host/db",
            ),
        ],
    )
    def test_translates_sync_drivers(self, sync_url, expected):
        assert to_async_db_url(sync_url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            "sqlite+aiosqlite:///some/path.db",
            "postgresql+asyncpg://user:pass@host/db",
            "mysql+asyncmy://user:pass@host/db",
        ],
    )
    def test_async_urls_pass_through(self, url):
        assert to_async_db_url(url) == url

    def test_unknown_backend_passes_through(self):
        url = "mssql+pyodbc://user:pass@dsn"
        assert to_async_db_url(url) == url

    def test_password_preserved(self):
        translated = to_async_db_url("postgresql://user:s3cr%40t@host/db")
        assert "s3cr%40t" in translated


class TestToSyncDbUrl:
    @pytest.mark.parametrize(
        "async_url,expected",
        [
            ("sqlite+aiosqlite:///some/path.db", "sqlite:///some/path.db"),
            (
                "postgresql+asyncpg://user:pass@host:5432/db",
                "postgresql://user:pass@host:5432/db",
            ),
            ("mysql+aiomysql://user:pass@host/db", "mysql://user:pass@host/db"),
        ],
    )
    def test_translates_async_drivers(self, async_url, expected):
        assert to_sync_db_url(async_url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            "sqlite:///some/path.db",
            "postgresql://user:pass@host/db",
            "postgresql+psycopg2://user:pass@host/db",
        ],
    )
    def test_sync_urls_pass_through(self, url):
        assert to_sync_db_url(url) == url

    def test_round_trip(self):
        original = "postgresql://user:pass@host:5432/db?sslmode=require"
        assert to_sync_db_url(to_async_db_url(original)) == original
