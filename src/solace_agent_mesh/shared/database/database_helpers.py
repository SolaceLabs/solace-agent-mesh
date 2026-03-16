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
