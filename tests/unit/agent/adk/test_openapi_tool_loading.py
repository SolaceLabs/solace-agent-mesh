"""Tests for OpenAPI tool loading in setup.py."""
import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from solace_agent_mesh.agent.adk.setup import _load_openapi_tool


@pytest.fixture
def mock_component():
    """Mock SamAgentComponent for testing."""
    component = Mock()
    component.log_identifier = "[TestAgent]"
    return component


@pytest.fixture
def temp_spec_files(tmp_path):
    """Create temporary OpenAPI spec files for testing."""
    # Valid JSON spec
    json_spec = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/test": {
                "get": {
                    "operationId": "getTest",
                    "summary": "Get test"
                }
            }
        }
    }
    json_file = tmp_path / "test_spec.json"
    json_file.write_text(json.dumps(json_spec))

    # Valid YAML spec
    yaml_spec = """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /test:
    get:
      operationId: getTest
      summary: Get test
"""
    yaml_file = tmp_path / "test_spec.yaml"
    yaml_file.write_text(yaml_spec)

    return {
        "json_file": str(json_file),
        "yaml_file": str(yaml_file),
        "json_content": json.dumps(json_spec),
        "yaml_content": yaml_spec
    }


class TestLoadOpenApiToolSpecification:
    """Test specification loading logic."""

    @pytest.mark.asyncio
    async def test_load_openapi_tool_missing_specification(self, mock_component):
        """Test that missing both specification fields raises ValueError."""
        tool_config = {
            "tool_type": "openapi"
        }
        with pytest.raises(ValueError, match="Must specify either 'specification_file' or 'specification'"):
            await _load_openapi_tool(mock_component, tool_config)

    @pytest.mark.asyncio
    async def test_load_openapi_tool_both_specifications(self, mock_component):
        """Test that providing both specification fields raises ValueError."""
        tool_config = {
            "tool_type": "openapi",
            "specification_file": "./test.json",
            "specification": '{"openapi": "3.0.0"}'
        }
        with pytest.raises(ValueError, match="Cannot specify both"):
            await _load_openapi_tool(mock_component, tool_config)

    @pytest.mark.asyncio
    async def test_load_openapi_tool_file_not_found(self, mock_component):
        """Test that missing file raises ValueError."""
        tool_config = {
            "tool_type": "openapi",
            "specification_file": "/nonexistent/file.json"
        }
        with pytest.raises(ValueError, match="specification file not found"):
            await _load_openapi_tool(mock_component, tool_config)

    @pytest.mark.asyncio
    @patch('google.adk.tools.openapi_tool.OpenAPIToolset')
    async def test_load_openapi_tool_with_json_file(self, mock_toolset_class, mock_component, temp_spec_files):
        """Test loading OpenAPI spec from JSON file."""
        mock_toolset_class.return_value = Mock(origin=None)

        tool_config = {
            "tool_type": "openapi",
            "specification_file": temp_spec_files["json_file"]
        }

        result = await _load_openapi_tool(mock_component, tool_config)

        assert len(result) == 3  # tools, builtins, cleanups
        assert len(result[0]) == 1  # one toolset
        mock_toolset_class.assert_called_once()
        call_kwargs = mock_toolset_class.call_args[1]
        assert call_kwargs["spec_str_type"] == "json"
        assert "openapi" in call_kwargs["spec_str"]

    @pytest.mark.asyncio
    @patch('google.adk.tools.openapi_tool.OpenAPIToolset')
    async def test_load_openapi_tool_with_yaml_file(self, mock_toolset_class, mock_component, temp_spec_files):
        """Test loading OpenAPI spec from YAML file."""
        mock_toolset_class.return_value = Mock(origin=None)

        tool_config = {
            "tool_type": "openapi",
            "specification_file": temp_spec_files["yaml_file"]
        }

        result = await _load_openapi_tool(mock_component, tool_config)

        mock_toolset_class.assert_called_once()
        call_kwargs = mock_toolset_class.call_args[1]
        assert call_kwargs["spec_str_type"] == "yaml"

    @pytest.mark.asyncio
    @patch('google.adk.tools.openapi_tool.OpenAPIToolset')
    async def test_load_openapi_tool_with_inline_json(self, mock_toolset_class, mock_component, temp_spec_files):
        """Test loading inline JSON specification."""
        mock_toolset_class.return_value = Mock(origin=None)

        tool_config = {
            "tool_type": "openapi",
            "specification": temp_spec_files["json_content"]
        }

        result = await _load_openapi_tool(mock_component, tool_config)

        mock_toolset_class.assert_called_once()
        call_kwargs = mock_toolset_class.call_args[1]
        assert call_kwargs["spec_str_type"] in ["json", "yaml"]  # Auto-detected

    @pytest.mark.asyncio
    @patch('google.adk.tools.openapi_tool.OpenAPIToolset')
    async def test_load_openapi_tool_with_inline_yaml(self, mock_toolset_class, mock_component, temp_spec_files):
        """Test loading inline YAML specification."""
        mock_toolset_class.return_value = Mock(origin=None)

        tool_config = {
            "tool_type": "openapi",
            "specification": temp_spec_files["yaml_content"]
        }

        result = await _load_openapi_tool(mock_component, tool_config)

        mock_toolset_class.assert_called_once()
        call_kwargs = mock_toolset_class.call_args[1]
        assert call_kwargs["spec_str_type"] == "yaml"

    @pytest.mark.asyncio
    @patch('google.adk.tools.openapi_tool.OpenAPIToolset')
    async def test_load_openapi_tool_with_format_hint(self, mock_toolset_class, mock_component):
        """Test that explicit format hint is used."""
        mock_toolset_class.return_value = Mock(origin=None)

        tool_config = {
            "tool_type": "openapi",
            "specification": '{"openapi": "3.0.0"}',
            "specification_format": "json"
        }

        result = await _load_openapi_tool(mock_component, tool_config)

        call_kwargs = mock_toolset_class.call_args[1]
        assert call_kwargs["spec_str_type"] == "json"


class TestLoadOpenApiToolIntegration:
    """Test integration with load_adk_tools."""

    @pytest.mark.asyncio
    @patch('google.adk.tools.openapi_tool.OpenAPIToolset')
    async def test_load_adk_tools_with_openapi_tool(self, mock_toolset_class, mock_component, temp_spec_files):
        """Test that load_adk_tools correctly loads OpenAPI tools."""
        from solace_agent_mesh.agent.adk.setup import load_adk_tools

        mock_toolset_class.return_value = Mock(origin=None, name="test_tool")
        mock_component.get_config.return_value = [
            {
                "tool_type": "openapi",
                "specification_file": temp_spec_files["json_file"]
            }
        ]

        tools, builtins, cleanups = await load_adk_tools(mock_component)

        # Should have loaded the OpenAPI tool plus internal tools
        assert len(tools) > 0
        assert any(hasattr(t, 'origin') and t.origin == 'openapi' for t in tools)
