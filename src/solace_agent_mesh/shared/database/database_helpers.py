"""
Database Helper Functions

Provides database utility functions and custom types.
Separated from dependencies.py to avoid circular imports.
"""

import json
from sqlalchemy import Text, TypeDecorator
from sqlalchemy.engine import URL, make_url
from ..exceptions.exceptions import DataIntegrityError

# ADK 2.x's DatabaseSessionService is async-only (create_async_engine), while
# deployment configs and SAM's own SQLAlchemy usage carry classic sync URLs.
# These maps translate between the two so existing configs keep working.
_ASYNC_DRIVER_BY_BACKEND = {
    "sqlite": "aiosqlite",
    "postgresql": "asyncpg",
    "mysql": "aiomysql",
}
_ASYNC_DRIVERS = {"aiosqlite", "asyncpg", "aiomysql", "asyncmy"}


def to_async_db_url(db_url: str) -> str:
    """Return db_url with an async driver, translating well-known sync drivers.

    URLs already naming an async driver — and backends with no known async
    driver — pass through unchanged.
    """
    url: URL = make_url(db_url)
    backend = url.get_backend_name()
    driver = url.get_driver_name()
    if driver in _ASYNC_DRIVERS:
        return db_url
    async_driver = _ASYNC_DRIVER_BY_BACKEND.get(backend)
    if async_driver is None:
        return db_url
    return url.set(drivername=f"{backend}+{async_driver}").render_as_string(
        hide_password=False
    )


def to_sync_db_url(db_url: str) -> str:
    """Return db_url with the backend's default sync driver.

    Inverse of to_async_db_url, for sync-only consumers (e.g. Alembic).
    """
    url: URL = make_url(db_url)
    if url.get_driver_name() not in _ASYNC_DRIVERS:
        return db_url
    return url.set(drivername=url.get_backend_name()).render_as_string(
        hide_password=False
    )


class SimpleJSON(TypeDecorator):
    """Simple JSON type using Text storage for all databases."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert Python object to JSON string for storage."""
        if value is not None:
            return json.dumps(value, default=self._json_serializer, ensure_ascii=False)
        return value

    def process_result_value(self, value, dialect):
        """Convert JSON string back to Python object."""
        if value is not None and isinstance(value, str):
            try:
                return json.loads(value)
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                raise DataIntegrityError("json_parsing", f"Invalid JSON data in database: {value}") from e
        return value

    @staticmethod
    def _json_serializer(obj):
        """Custom JSON serializer for complex objects."""
        if model_dump := getattr(obj, 'model_dump', None):
            return model_dump()
        elif dict_method := getattr(obj, 'dict', None):
            return dict_method()
        elif obj_dict := getattr(obj, '__dict__', None):
            return obj_dict
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")