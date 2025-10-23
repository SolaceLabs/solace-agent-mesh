"""
Unit tests for Pydantic formatting utilities.

Tests the formatting of validation error messages from Pydantic models.
"""

from solace_agent_mesh.common.utils.pydantic_utils import SamConfigBase
from pydantic import Field


class TestPydanticFormatting:
    def test_format_validation_error_message(self):
        from pydantic import ValidationError

        class DummyModel(SamConfigBase):
            required_field: str = Field(..., description="A required field for testing.")

        try:
            DummyModel.model_validate_and_clean({})
        except ValidationError as e:
            message = DummyModel.format_validation_error_message(e, "TestApp", "TestAgent")
            assert "TestApp" in message
            assert "TestAgent" in message
            assert "required_field" in message
            assert "A required field for testing." in message