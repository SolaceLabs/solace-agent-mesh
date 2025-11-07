"""Tests for OpenAPI tool configuration types."""
import pytest
from pydantic import ValidationError
from solace_agent_mesh.agent.tools.tool_config_types import OpenApiToolConfig, AnyToolConfig


class TestOpenApiToolConfig:
    """Test OpenApiToolConfig model validation."""

    def test_openapi_config_with_specification_file(self):
        """Test valid config with specification_file."""
        config = {
            "tool_type": "openapi",
            "specification_file": "./petstore.json"
        }
        result = OpenApiToolConfig.model_validate(config)
        assert result.tool_type == "openapi"
        assert result.specification_file == "./petstore.json"
        assert result.specification is None
        assert result.tool_filter is None
        assert result.auth is None

    def test_openapi_config_with_inline_specification(self):
        """Test valid config with inline specification."""
        spec = '{"openapi": "3.0.0"}'
        config = {
            "tool_type": "openapi",
            "specification": spec
        }
        result = OpenApiToolConfig.model_validate(config)
        assert result.tool_type == "openapi"
        assert result.specification == spec
        assert result.specification_file is None

    def test_openapi_config_with_tool_filter(self):
        """Test config with tool_filter list."""
        config = {
            "tool_type": "openapi",
            "specification_file": "./api.json",
            "tool_filter": ["getPet", "createPet"]
        }
        result = OpenApiToolConfig.model_validate(config)
        assert result.tool_filter == ["getPet", "createPet"]

    def test_openapi_config_with_auth(self):
        """Test config with auth configuration."""
        config = {
            "tool_type": "openapi",
            "specification_file": "./api.json",
            "auth": {
                "type": "apikey",
                "in": "query",
                "name": "apikey",
                "value": "test123"
            }
        }
        result = OpenApiToolConfig.model_validate(config)
        assert result.auth["type"] == "apikey"

    def test_openapi_config_with_specification_format(self):
        """Test config with explicit format hint."""
        config = {
            "tool_type": "openapi",
            "specification": "openapi: 3.0.0",
            "specification_format": "yaml"
        }
        result = OpenApiToolConfig.model_validate(config)
        assert result.specification_format == "yaml"

    def test_openapi_config_invalid_tool_type(self):
        """Test that wrong tool_type fails validation."""
        config = {
            "tool_type": "mcp",
            "specification_file": "./api.json"
        }
        with pytest.raises(ValidationError):
            OpenApiToolConfig.model_validate(config)

    def test_anytools_config_includes_openapi(self):
        """Test that AnyToolConfig union includes OpenApiToolConfig."""
        config = {
            "tool_type": "openapi",
            "specification_file": "./api.json"
        }
        from pydantic import TypeAdapter
        adapter = TypeAdapter(AnyToolConfig)
        result = adapter.validate_python(config)
        assert isinstance(result, OpenApiToolConfig)
