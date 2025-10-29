"""
Unit tests for Pydantic utilities.

Tests the validation and formatting of validation errors from Pydantic models.
"""

from solace_agent_mesh.common.utils.pydantic_utils import SamConfigBase
from pydantic import Field, ValidationError


class TestPydanticFormatting:
    """Tests for Pydantic error message formatting utilities."""

    def test_format_validation_error_message(self):

        class DummyModel(SamConfigBase):
            required_field: str = Field(..., description="A required field for testing.")
            optional_field: str | None = Field(None, description="An optional field for testing.")
            wrong_type_field: int = Field(..., description="An integer field for testing.")

        try:
            DummyModel.model_validate_and_clean({"wrong_type_field": "not_an_int"})
            raise AssertionError("ValidationError was expected but not raised.")
        except ValidationError as e:
            message = DummyModel.format_validation_error_message(e, "TestApp", "TestAgent")
            print(message)
            assert message == """
---- Configuration validation failed for TestApp ----

   Agent Name: TestAgent

ERROR 1:
   Missing required field: 'required_field'
   Location: app_config.required_field
   Description: A required field for testing.

ERROR 2:
   Error: Input should be a valid integer, unable to parse string as an integer
   Location: app_config.wrong_type_field
   Description: An integer field for testing.

---- Please update your YAML configuration ----
"""

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
            raise AssertionError("ValidationError was expected but not raised.")
        except ValidationError as e:
            message = ParentModel.format_validation_error_message(e, "ParentApp")
            assert message == """
---- Configuration validation failed for ParentApp ----

ERROR 1:
   Missing required field: 'nested_field'
   Location: app_config.nested.nested_field
   Description: A nested integer field.

---- Please update your YAML configuration ----
"""

    def test_array_model_error_formatting(self):

        class ItemModel(SamConfigBase):
            item_field: float = Field(..., description="A float field in the item.")

        class ArrayModel(SamConfigBase):
            items: list[ItemModel] = Field(..., description="A list of item models.")

        try:
            ArrayModel.model_validate_and_clean({
                "items": [{}]
            })
            raise AssertionError("ValidationError was expected but not raised.")
        except ValidationError as e:
            message = ArrayModel.format_validation_error_message(e, None, "ArrayAgent")
            assert message == """
---- Configuration validation failed for UNKNOWN ----

   Agent Name: ArrayAgent

ERROR 1:
   Missing required field: 'item_field'
   Location: app_config.items.0.item_field
   Description: A float field in the item.

---- Please update your YAML configuration ----
"""

    def test_error_on_optional_field(self):

        class NestedFieldModel(SamConfigBase):
            nested_field: int = Field(..., description="A nested integer field.")

        class OptionalFieldModel(SamConfigBase):
            optional_field: NestedFieldModel | None = Field(None, description="An optional nested field.")

        try:
            OptionalFieldModel.model_validate_and_clean({
                "optional_field": {
                    "nested_field": "not_an_int"
                }
            })
            raise AssertionError("ValidationError was expected but not raised.")
        except ValidationError as e:
            message = OptionalFieldModel.format_validation_error_message(e, "OptionalApp")
            assert message == """
---- Configuration validation failed for OptionalApp ----

ERROR 1:
   Error: Input should be a valid integer, unable to parse string as an integer
   Location: app_config.optional_field.nested_field
   Description: A nested integer field.

---- Please update your YAML configuration ----
"""
