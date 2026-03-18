from sqlalchemy import TypeDecorator, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.mysql import BINARY
import uuid as uuid_module
import logging

logger = logging.getLogger(__name__)


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
            logger.debug("OptimizedUUID: Using PostgreSQL UUID type")
            impl = dialect.type_descriptor(PG_UUID(as_uuid=False))

        elif dialect_name in ('mysql', 'mariadb'):
            logger.debug(f"OptimizedUUID: Using {dialect_name} BINARY(16) type")
            impl = dialect.type_descriptor(BINARY(16))

        else:
            logger.debug(f"OptimizedUUID: Using {dialect_name} VARCHAR(36) type")
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
                    logger.error(f"Failed to convert bytes to UUID: {e}")
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
