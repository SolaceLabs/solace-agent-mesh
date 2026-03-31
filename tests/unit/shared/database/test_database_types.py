import uuid as uuid_module
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from solace_agent_mesh.shared.database.database_types import OptimizedUUID, UUIDStr, coerce_uuid


def make_dialect(name: str) -> MagicMock:
    dialect = MagicMock()
    dialect.name = name
    dialect.type_descriptor = lambda t: t
    return dialect


class TestCoerceUuid:

    def test_none_returns_none(self):
        assert coerce_uuid(None) is None

    def test_bytes_converts_to_hyphenated_string(self):
        original = uuid_module.uuid4()
        result = coerce_uuid(original.bytes)
        assert result == str(original)

    def test_string_passthrough(self):
        test_uuid = str(uuid_module.uuid4())
        assert coerce_uuid(test_uuid) == test_uuid


class TestProcessBindParamBytesHandling:
    """Tests for the bytes-acceptance path added in this PR.

    After session.flush() on MySQL, model.id may be raw bytes. These tests
    confirm that process_bind_param accepts bytes without raising TypeError.
    """

    def test_mysql_accepts_bytes_directly(self):
        uuid_type = OptimizedUUID()
        original = uuid_module.uuid4()
        result = uuid_type.process_bind_param(original.bytes, make_dialect("mysql"))
        assert result == original.bytes

    def test_non_mysql_bytes_converts_to_string(self):
        uuid_type = OptimizedUUID()
        original = uuid_module.uuid4()
        result = uuid_type.process_bind_param(original.bytes, make_dialect("sqlite"))
        assert result == str(original)


class TestUUIDStr:
    """Tests for the UUIDStr annotated Pydantic type.

    Confirms that BeforeValidator(coerce_uuid) is wired correctly so that
    Pydantic model fields typed as UUIDStr coerce bytes to a hyphenated UUID
    string at validation time.
    """

    class _Model(BaseModel):
        id: UUIDStr

    def test_bytes_coerced_to_hyphenated_string(self):
        original = uuid_module.uuid4()
        m = self._Model(id=original.bytes)
        assert m.id == str(original)

    def test_string_passthrough(self):
        original = str(uuid_module.uuid4())
        m = self._Model(id=original)
        assert m.id == original

    def test_none_raises_validation_error(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self._Model(id=None)


class TestCoerceComparedValueRemoved:
    """Regression tests for the coerce_compared_value removal.

    The old override returned self.impl (String) for non-None values, causing
    MySQL filter comparisons to send raw UUID strings instead of bytes.
    The default TypeDecorator behaviour returns self, so comparisons go through
    OptimizedUUID.process_bind_param — verified here.
    """

    def test_coerce_compared_value_returns_self(self):
        uuid_type = OptimizedUUID()
        # Default TypeDecorator.coerce_compared_value returns self for any op/value
        result = uuid_type.coerce_compared_value(None, str(uuid_module.uuid4()))
        assert result is uuid_type

    def test_coerce_compared_value_returns_self_for_none(self):
        uuid_type = OptimizedUUID()
        result = uuid_type.coerce_compared_value(None, None)
        assert result is uuid_type
