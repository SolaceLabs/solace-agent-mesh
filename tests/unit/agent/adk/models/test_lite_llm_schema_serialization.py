"""Unit tests for LiteLlm schema serialization functionality.

Tests the conversion of Google ADK types.Schema and types.FunctionDeclaration
to the format expected by LiteLLM/OpenAI, ensuring proper handling of:
- Nested Type enums in properties and items
- Array schemas with nested objects
- Functions with no parameters
- Complex nested structures
"""

import pytest
from google.genai import types

from solace_agent_mesh.agent.adk.models.lite_llm import (
    _schema_to_dict,
    _function_declaration_to_tool_param,
)


class TestSchemaToDict:
    """Test _schema_to_dict function for proper Type enum conversion."""

    def test_simple_string_type(self):
        """Test conversion of simple string type schema."""
        schema = types.Schema(type=types.Type.STRING)
        result = _schema_to_dict(schema)

        assert result["type"] == "string"
        assert isinstance(result["type"], str)

    def test_simple_number_type(self):
        """Test conversion of simple number type schema."""
        schema = types.Schema(type=types.Type.NUMBER)
        result = _schema_to_dict(schema)

        assert result["type"] == "number"
        assert isinstance(result["type"], str)

    def test_simple_boolean_type(self):
        """Test conversion of simple boolean type schema."""
        schema = types.Schema(type=types.Type.BOOLEAN)
        result = _schema_to_dict(schema)

        assert result["type"] == "boolean"
        assert isinstance(result["type"], str)

    def test_simple_array_type(self):
        """Test conversion of simple array type schema."""
        schema = types.Schema(type=types.Type.ARRAY)
        result = _schema_to_dict(schema)

        assert result["type"] == "array"
        assert isinstance(result["type"], str)

    def test_simple_object_type(self):
        """Test conversion of simple object type schema."""
        schema = types.Schema(type=types.Type.OBJECT)
        result = _schema_to_dict(schema)

        assert result["type"] == "object"
        assert isinstance(result["type"], str)

    def test_object_with_string_property(self):
        """Test conversion of object with a simple string property."""
        schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(type=types.Type.STRING)
            }
        )
        result = _schema_to_dict(schema)

        assert result["type"] == "object"
        assert "properties" in result
        assert "name" in result["properties"]
        assert result["properties"]["name"]["type"] == "string"
        assert isinstance(result["properties"]["name"]["type"], str)

    def test_object_with_nested_object_property(self):
        """Test conversion of object with nested object property.

        This is the key scenario that was broken before the fix - nested Type
        enums in properties were not being converted.
        """
        schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "user": types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "name": types.Schema(type=types.Type.STRING),
                        "age": types.Schema(type=types.Type.NUMBER)
                    }
                )
            }
        )
        result = _schema_to_dict(schema)

        assert result["type"] == "object"
        assert result["properties"]["user"]["type"] == "object"
        assert result["properties"]["user"]["properties"]["name"]["type"] == "string"
        assert result["properties"]["user"]["properties"]["age"]["type"] == "number"

        # Ensure all are strings, not enums
        assert isinstance(result["properties"]["user"]["type"], str)
        assert isinstance(result["properties"]["user"]["properties"]["name"]["type"], str)
        assert isinstance(result["properties"]["user"]["properties"]["age"]["type"], str)

    def test_array_with_string_items(self):
        """Test conversion of array with string items schema."""
        schema = types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING)
        )
        result = _schema_to_dict(schema)

        assert result["type"] == "array"
        assert "items" in result
        assert result["items"]["type"] == "string"
        assert isinstance(result["items"]["type"], str)

    def test_array_with_object_items(self):
        """Test conversion of array with object items.

        This is another key scenario - array items containing objects with
        Type enums that need conversion.
        """
        schema = types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "id": types.Schema(type=types.Type.STRING),
                    "count": types.Schema(type=types.Type.NUMBER)
                }
            )
        )
        result = _schema_to_dict(schema)

        assert result["type"] == "array"
        assert result["items"]["type"] == "object"
        assert result["items"]["properties"]["id"]["type"] == "string"
        assert result["items"]["properties"]["count"]["type"] == "number"

        # Ensure all are strings, not enums
        assert isinstance(result["items"]["type"], str)
        assert isinstance(result["items"]["properties"]["id"]["type"], str)
        assert isinstance(result["items"]["properties"]["count"]["type"], str)

    def test_array_of_arrays(self):
        """Test conversion of nested array schema."""
        schema = types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(type=types.Type.STRING)
            )
        )
        result = _schema_to_dict(schema)

        assert result["type"] == "array"
        assert result["items"]["type"] == "array"
        assert result["items"]["items"]["type"] == "string"

        # Ensure all are strings
        assert isinstance(result["type"], str)
        assert isinstance(result["items"]["type"], str)
        assert isinstance(result["items"]["items"]["type"], str)

    def test_complex_nested_structure(self):
        """Test conversion of complex nested structure with multiple levels.

        This simulates a realistic MCP tool schema with deeply nested objects
        and arrays.
        """
        schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "users": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "name": types.Schema(type=types.Type.STRING),
                            "emails": types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(type=types.Type.STRING)
                            ),
                            "metadata": types.Schema(
                                type=types.Type.OBJECT,
                                properties={
                                    "created": types.Schema(type=types.Type.STRING),
                                    "active": types.Schema(type=types.Type.BOOLEAN)
                                }
                            )
                        }
                    )
                ),
                "count": types.Schema(type=types.Type.NUMBER)
            }
        )
        result = _schema_to_dict(schema)

        # Verify top level
        assert result["type"] == "object"
        assert isinstance(result["type"], str)

        # Verify users array
        assert result["properties"]["users"]["type"] == "array"
        assert isinstance(result["properties"]["users"]["type"], str)

        # Verify user object in array
        user_schema = result["properties"]["users"]["items"]
        assert user_schema["type"] == "object"
        assert isinstance(user_schema["type"], str)
        assert user_schema["properties"]["name"]["type"] == "string"
        assert isinstance(user_schema["properties"]["name"]["type"], str)

        # Verify emails array
        assert user_schema["properties"]["emails"]["type"] == "array"
        assert isinstance(user_schema["properties"]["emails"]["type"], str)
        assert user_schema["properties"]["emails"]["items"]["type"] == "string"
        assert isinstance(user_schema["properties"]["emails"]["items"]["type"], str)

        # Verify metadata object
        metadata = user_schema["properties"]["metadata"]
        assert metadata["type"] == "object"
        assert isinstance(metadata["type"], str)
        assert metadata["properties"]["created"]["type"] == "string"
        assert isinstance(metadata["properties"]["created"]["type"], str)
        assert metadata["properties"]["active"]["type"] == "boolean"
        assert isinstance(metadata["properties"]["active"]["type"], str)

        # Verify count
        assert result["properties"]["count"]["type"] == "number"
        assert isinstance(result["properties"]["count"]["type"], str)

    def test_schema_with_description(self):
        """Test that descriptions are preserved during conversion."""
        schema = types.Schema(
            type=types.Type.STRING,
            description="A user's name"
        )
        result = _schema_to_dict(schema)

        assert result["type"] == "string"
        assert result["description"] == "A user's name"

    def test_schema_with_required_fields(self):
        """Test that required fields are preserved during conversion."""
        schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(type=types.Type.STRING),
                "email": types.Schema(type=types.Type.STRING)
            },
            required=["name"]
        )
        result = _schema_to_dict(schema)

        assert result["type"] == "object"
        assert result["required"] == ["name"]
        assert result["properties"]["name"]["type"] == "string"
        assert result["properties"]["email"]["type"] == "string"

    def test_mcp_tool_with_integer_enums(self):
        """Test MCP tool schema with integer enums are properly handled.

        MCP servers can provide integer enums which is valid per JSON Schema spec.
        This test ensures the schema normalization handles this without Pydantic errors.
        """
        from solace_agent_mesh.agent.adk.models.lite_llm import _normalize_schema_dict

        # Simulate MCP tool schema with integer enums in nested structure
        mcp_tool_params = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "priority": types.Schema.model_validate(
                    _normalize_schema_dict({"type": "integer", "enum": [3, 7, 14]})
                ),
                "filters": types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "status_codes": types.Schema.model_validate(
                            _normalize_schema_dict({"type": "array", "items": {"type": "integer", "enum": [200, 404, 500]}})
                        )
                    }
                )
            }
        )

        func = types.FunctionDeclaration(
            name="mcp_test_tool",
            description="Test MCP tool with integer enums",
            parameters=mcp_tool_params
        )

        # This should not raise Pydantic validation errors
        result = _function_declaration_to_tool_param(func)

        # Verify enum values are stringified
        assert result["function"]["parameters"]["properties"]["priority"]["enum"] == ["3", "7", "14"]
        assert result["function"]["parameters"]["properties"]["filters"]["properties"]["status_codes"]["items"]["enum"] == ["200", "404", "500"]


class TestFunctionDeclarationToToolParam:
    """Test _function_declaration_to_tool_param function."""

    def test_function_with_simple_parameters(self):
        """Test function with simple string parameter."""
        func = types.FunctionDeclaration(
            name="get_user",
            description="Get a user by name",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "name": types.Schema(type=types.Type.STRING, description="User name")
                },
                required=["name"]
            )
        )
        result = _function_declaration_to_tool_param(func)

        assert result["type"] == "function"
        assert result["function"]["name"] == "get_user"
        assert result["function"]["description"] == "Get a user by name"
        assert result["function"]["parameters"]["type"] == "object"
        assert result["function"]["parameters"]["properties"]["name"]["type"] == "string"
        assert result["function"]["parameters"]["properties"]["name"]["description"] == "User name"
        assert result["function"]["parameters"]["required"] == ["name"]

    def test_function_with_no_parameters(self):
        """Test function with no parameters provides empty object schema.

        This is required by OpenAI spec - functions must have a parameters object.
        """
        func = types.FunctionDeclaration(
            name="get_time",
            description="Get current time"
        )
        result = _function_declaration_to_tool_param(func)

        assert result["type"] == "function"
        assert result["function"]["name"] == "get_time"
        assert result["function"]["description"] == "Get current time"
        assert result["function"]["parameters"]["type"] == "object"
        assert result["function"]["parameters"]["properties"] == {}

    def test_function_with_nested_object_parameters(self):
        """Test function with nested object parameters.

        This is the scenario that was failing before - nested Type enums
        in function parameters.
        """
        func = types.FunctionDeclaration(
            name="create_user",
            description="Create a new user",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "user": types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "name": types.Schema(type=types.Type.STRING),
                            "age": types.Schema(type=types.Type.NUMBER),
                            "active": types.Schema(type=types.Type.BOOLEAN)
                        },
                        required=["name"]
                    )
                },
                required=["user"]
            )
        )
        result = _function_declaration_to_tool_param(func)

        params = result["function"]["parameters"]
        assert params["type"] == "object"
        assert isinstance(params["type"], str)

        user_schema = params["properties"]["user"]
        assert user_schema["type"] == "object"
        assert isinstance(user_schema["type"], str)
        assert user_schema["properties"]["name"]["type"] == "string"
        assert isinstance(user_schema["properties"]["name"]["type"], str)
        assert user_schema["properties"]["age"]["type"] == "number"
        assert isinstance(user_schema["properties"]["age"]["type"], str)
        assert user_schema["properties"]["active"]["type"] == "boolean"
        assert isinstance(user_schema["properties"]["active"]["type"], str)

    def test_function_with_array_parameters(self):
        """Test function with array parameters containing objects."""
        func = types.FunctionDeclaration(
            name="batch_create_users",
            description="Create multiple users",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "users": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "name": types.Schema(type=types.Type.STRING),
                                "email": types.Schema(type=types.Type.STRING)
                            }
                        )
                    )
                },
                required=["users"]
            )
        )
        result = _function_declaration_to_tool_param(func)

        params = result["function"]["parameters"]
        users_schema = params["properties"]["users"]

        assert users_schema["type"] == "array"
        assert isinstance(users_schema["type"], str)
        assert users_schema["items"]["type"] == "object"
        assert isinstance(users_schema["items"]["type"], str)
        assert users_schema["items"]["properties"]["name"]["type"] == "string"
        assert isinstance(users_schema["items"]["properties"]["name"]["type"], str)
        assert users_schema["items"]["properties"]["email"]["type"] == "string"
        assert isinstance(users_schema["items"]["properties"]["email"]["type"], str)

    def test_function_with_complex_mcp_like_schema(self):
        """Test function with complex schema similar to MCP tools.

        This simulates a realistic MCP filesystem tool with complex parameters.
        """
        func = types.FunctionDeclaration(
            name="search_files",
            description="Search for files matching criteria",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "path": types.Schema(type=types.Type.STRING, description="Base path to search"),
                    "filters": types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "extensions": types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(type=types.Type.STRING),
                                description="File extensions to match"
                            ),
                            "size_range": types.Schema(
                                type=types.Type.OBJECT,
                                properties={
                                    "min": types.Schema(type=types.Type.NUMBER),
                                    "max": types.Schema(type=types.Type.NUMBER)
                                }
                            ),
                            "include_hidden": types.Schema(type=types.Type.BOOLEAN)
                        }
                    )
                },
                required=["path"]
            )
        )
        result = _function_declaration_to_tool_param(func)

        params = result["function"]["parameters"]

        # Verify all Type enums are converted to strings
        assert params["type"] == "object"
        assert isinstance(params["type"], str)

        assert params["properties"]["path"]["type"] == "string"
        assert isinstance(params["properties"]["path"]["type"], str)

        filters = params["properties"]["filters"]
        assert filters["type"] == "object"
        assert isinstance(filters["type"], str)

        extensions = filters["properties"]["extensions"]
        assert extensions["type"] == "array"
        assert isinstance(extensions["type"], str)
        assert extensions["items"]["type"] == "string"
        assert isinstance(extensions["items"]["type"], str)

        size_range = filters["properties"]["size_range"]
        assert size_range["type"] == "object"
        assert isinstance(size_range["type"], str)
        assert size_range["properties"]["min"]["type"] == "number"
        assert isinstance(size_range["properties"]["min"]["type"], str)
        assert size_range["properties"]["max"]["type"] == "number"
        assert isinstance(size_range["properties"]["max"]["type"], str)

        assert filters["properties"]["include_hidden"]["type"] == "boolean"
        assert isinstance(filters["properties"]["include_hidden"]["type"], str)

    def test_function_without_description(self):
        """Test that function without description gets empty string."""
        func = types.FunctionDeclaration(
            name="test_func",
            parameters=types.Schema(type=types.Type.OBJECT)
        )
        result = _function_declaration_to_tool_param(func)

        assert result["function"]["description"] == ""
