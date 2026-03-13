"""
Database Helper Functions

Provides database utility functions and custom types.
Separated from dependencies.py to avoid circular imports.
"""

import json
import logging
import uuid as uuid_module
from sqlalchemy import Text, TypeDecorator, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.mysql import BINARY
from ..exceptions.exceptions import DataIntegrityError

log = logging.getLogger(__name__)


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


class OptimizedUUID(TypeDecorator):

    impl = String
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dialect_impl_cache = {}

    def load_dialect_impl(self, dialect):
        dialect_name = dialect.name

        if dialect_name in self._dialect_impl_cache:
            return self._dialect_impl_cache[dialect_name]

        if dialect_name == 'postgresql':
            log.debug("OptimizedUUID: Using PostgreSQL UUID type")
            impl = dialect.type_descriptor(PG_UUID(as_uuid=False))

        elif dialect_name in ('mysql', 'mariadb'):
            log.debug(f"OptimizedUUID: Using {dialect_name} BINARY(16) type")
            impl = dialect.type_descriptor(BINARY(16))

        else:
            log.debug(f"OptimizedUUID: Using {dialect_name} VARCHAR(36) type")
            impl = dialect.type_descriptor(String(36))

        self._dialect_impl_cache[dialect_name] = impl
        return impl

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        if not isinstance(value, str):
            raise TypeError(f"OptimizedUUID expects string UUID, got {type(value).__name__}")

        try:
            uuid_obj = uuid_module.UUID(value)
        except ValueError as e:
            raise ValueError(f"Invalid UUID format: {value}") from e

        dialect_name = dialect.name

        if dialect_name in ('mysql', 'mariadb'):
            return uuid_obj.bytes
        else:
            return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        dialect_name = dialect.name

        if dialect_name in ('mysql', 'mariadb'):
            if isinstance(value, bytes):
                try:
                    return str(uuid_module.UUID(bytes=value))
                except Exception as e:
                    log.error(f"Failed to convert bytes to UUID: {e}")
                    raise ValueError(f"Invalid UUID bytes: {value!r}") from e

            return str(value)

        else:
            if isinstance(value, uuid_module.UUID):
                return str(value)
            return str(value)

    def compare_values(self, x, y):
        x_str = str(x) if x is not None else None
        y_str = str(y) if y is not None else None
        return x_str == y_str

    def coerce_compared_value(self, op, value):
        if value is not None:
            return self.impl
        else:
            return self