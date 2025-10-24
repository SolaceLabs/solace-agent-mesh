"""
Unit tests for Pydantic utilities.

Tests the validation and formatting of validation errors from Pydantic models.
"""

from solace_agent_mesh.common.utils.pydantic_utils import SamConfigBase
from pydantic import Field, ValidationError
from typing import List, Optional


class TestPydanticFormatting:
    "Tests for Pydantic error message formatting utilities."

    def test_format_validation_error_message(self):

        class DummyModel(SamConfigBase):
            required_field: str = Field(..., description="A required field for testing.")
            optional_field: Optional[str] = Field(None, description="An optional field for testing.")
            wrong_type_field: int = Field(..., description="An integer field for testing.")

        try:
            DummyModel.model_validate_and_clean({"wrong_type_field": "not_an_int"})
            assert False, "ValidationError was expected but not raised."
        except ValidationError as e:
            message = DummyModel.format_validation_error_message(e, "TestApp", "TestAgent")
            assert "TestApp" in message
            assert "TestAgent" in message
            assert "app_config.required_field" in message
            assert "A required field for testing." in message
            assert "app_config.optional_field" not in message
            assert "app_config.wrong_type_field" in message
            assert "An integer field for testing." in message
            assert "Input should be a valid integer" in message

    def test_nested_model_error_formatting(self):

        class NestedModel(SamConfigBase):
            nested_field: int = Field(..., description="A nested integer field.")

        class ParentModel(SamConfigBase):
            parent_field: str = Field(..., description="A parent string field.")
            nested: NestedModel = Field(..., description="A nested model.")

        try:
            ParentModel.model_validate_and_clean({
                "parent_field": "valid",
                "nested": {}
            })
            assert False, "ValidationError was expected but not raised."
        except ValidationError as e:
            message = ParentModel.format_validation_error_message(e, "ParentApp")
            assert "Agent Name" not in message
            assert "ParentApp" in message
            assert "app_config.nested.nested_field" in message
            assert "A nested integer field." in message

    def test_array_model_error_formatting(self):

        class ItemModel(SamConfigBase):
            item_field: float = Field(..., description="A float field in the item.")

        class ArrayModel(SamConfigBase):
            items: List[ItemModel] = Field(..., description="A list of item models.")

        try:
            ArrayModel.model_validate_and_clean({
                "items": [{}]
            })
            assert False, "ValidationError was expected but not raised."
        except ValidationError as e:
            message = ArrayModel.format_validation_error_message(e, None, "ArrayAgent")
            assert "UNKNOWN" in message
            assert "ArrayAgent" in message
            assert "app_config.items.0.item_field" in message
            assert "A float field in the item." in message
