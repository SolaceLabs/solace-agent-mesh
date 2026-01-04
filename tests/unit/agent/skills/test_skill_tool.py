"""
Unit tests for src/solace_agent_mesh/agent/skills/skill_tool.py

Tests the SkillTool class and create_skill_tool factory function.
"""

from unittest.mock import Mock, AsyncMock
import pytest

from src.solace_agent_mesh.agent.skills.skill_tool import (
    SkillTool,
    create_skill_tool,
    _map_type,
)
from google.genai import types as adk_types


class TestMapType:
    """Tests for the _map_type helper function"""

    def test_string_type(self):
        """Test mapping 'string' to Type.STRING"""
        assert _map_type("string") == adk_types.Type.STRING

    def test_integer_type(self):
        """Test mapping 'integer' to Type.INTEGER"""
        assert _map_type("integer") == adk_types.Type.INTEGER

    def test_number_type(self):
        """Test mapping 'number' to Type.NUMBER"""
        assert _map_type("number") == adk_types.Type.NUMBER

    def test_boolean_type(self):
        """Test mapping 'boolean' to Type.BOOLEAN"""
        assert _map_type("boolean") == adk_types.Type.BOOLEAN

    def test_array_type(self):
        """Test mapping 'array' to Type.ARRAY"""
        assert _map_type("array") == adk_types.Type.ARRAY

    def test_object_type(self):
        """Test mapping 'object' to Type.OBJECT"""
        assert _map_type("object") == adk_types.Type.OBJECT

    def test_unknown_type_defaults_to_string(self):
        """Test that unknown types default to STRING"""
        assert _map_type("unknown") == adk_types.Type.STRING

    def test_case_insensitive(self):
        """Test that type mapping is case insensitive"""
        assert _map_type("STRING") == adk_types.Type.STRING
        assert _map_type("Integer") == adk_types.Type.INTEGER


class TestCreateSkillTool:
    """Tests for the create_skill_tool factory function"""

    def test_creates_tool_successfully(self):
        """Test successful tool creation"""
        tool_config = {
            "tool_type": "python",
            "component_module": "tests.integration.test_support.tools",
            "function_name": "echo_tool",
            "name": "echo_tool",
            "description": "Echoes a message",
            "parameters": {
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message to echo",
                    }
                },
                "required": ["message"],
            },
        }

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tool, declaration = create_skill_tool(tool_config, "test-skill", mock_component)

        assert tool is not None
        assert declaration is not None
        assert tool.name == "echo_tool_test-skill"
        assert "Loaded by skill test-skill:" in tool.description

    def test_returns_none_on_invalid_config(self):
        """Test that invalid config returns (None, None)"""
        # Missing required fields
        tool_config = {
            "name": "broken_tool",
        }

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tool, declaration = create_skill_tool(tool_config, "test-skill", mock_component)

        assert tool is None
        assert declaration is None

    def test_returns_none_on_missing_function(self):
        """Test that missing function returns (None, None)"""
        tool_config = {
            "tool_type": "python",
            "component_module": "tests.integration.test_support.tools",
            "function_name": "nonexistent_function",
            "name": "nonexistent",
            "description": "Will fail",
        }

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tool, declaration = create_skill_tool(tool_config, "test-skill", mock_component)

        assert tool is None
        assert declaration is None


class TestSkillTool:
    """Tests for the SkillTool class"""

    def test_init_prefixes_name(self):
        """Test that __init__ creates prefixed tool name"""
        tool_config = {
            "tool_type": "python",
            "component_module": "tests.integration.test_support.tools",
            "function_name": "echo_tool",
            "name": "my_tool",
            "description": "Original description",
        }

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tool = SkillTool("database-skill", tool_config, mock_component)

        assert tool.name == "my_tool_database-skill"
        assert tool.original_name == "my_tool"

    def test_init_prefixes_description(self):
        """Test that __init__ adds skill attribution to description"""
        tool_config = {
            "tool_type": "python",
            "component_module": "tests.integration.test_support.tools",
            "function_name": "echo_tool",
            "name": "my_tool",
            "description": "Does something useful",
        }

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tool = SkillTool("my-skill", tool_config, mock_component)

        assert tool.description == "Loaded by skill my-skill: Does something useful"

    def test_init_uses_function_name_if_name_missing(self):
        """Test that function_name is used if name is not provided"""
        tool_config = {
            "tool_type": "python",
            "component_module": "tests.integration.test_support.tools",
            "function_name": "echo_tool",
            "description": "Test tool",
        }

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tool = SkillTool("test-skill", tool_config, mock_component)

        assert tool.original_name == "echo_tool"
        assert tool.name == "echo_tool_test-skill"

    def test_init_raises_if_no_name_or_function_name(self):
        """Test that ValueError is raised if neither name nor function_name provided"""
        tool_config = {
            "tool_type": "python",
            "component_module": "tests.integration.test_support.tools",
            "description": "Test tool",
        }

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        with pytest.raises(ValueError, match="missing 'name' or 'function_name'"):
            SkillTool("test-skill", tool_config, mock_component)

    def test_init_raises_if_missing_module(self):
        """Test that ValueError is raised if component_module is missing"""
        tool_config = {
            "tool_type": "python",
            "function_name": "some_func",
            "name": "test",
            "description": "Test",
        }

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        with pytest.raises(ValueError, match="missing 'component_module'"):
            SkillTool("test-skill", tool_config, mock_component)

    def test_init_raises_if_unsupported_tool_type(self):
        """Test that ValueError is raised for non-python tool types"""
        tool_config = {
            "tool_type": "mcp",
            "name": "test",
            "description": "Test",
        }

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        with pytest.raises(ValueError, match="only support 'python' tool_type"):
            SkillTool("test-skill", tool_config, mock_component)

    def test_get_declaration(self):
        """Test that _get_declaration returns correct FunctionDeclaration"""
        tool_config = {
            "tool_type": "python",
            "component_module": "tests.integration.test_support.tools",
            "function_name": "echo_tool",
            "name": "echo",
            "description": "Echo tool",
            "parameters": {
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Count",
                        "nullable": True,
                    },
                },
                "required": ["message"],
            },
        }

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tool = SkillTool("test-skill", tool_config, mock_component)
        declaration = tool._get_declaration()

        assert declaration.name == "echo_test-skill"
        assert "Loaded by skill test-skill:" in declaration.description
        assert "message" in declaration.parameters.properties
        assert "count" in declaration.parameters.properties
        assert declaration.parameters.required == ["message"]

    @pytest.mark.asyncio
    async def test_run_async_sync_function(self):
        """Test running a synchronous function via run_async"""
        tool_config = {
            "tool_type": "python",
            "component_module": "tests.integration.test_support.tools",
            "function_name": "echo_tool",
            "name": "echo",
            "description": "Echo tool",
        }

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tool = SkillTool("test-skill", tool_config, mock_component)

        mock_context = Mock()
        mock_context.state = {}

        result = await tool.run_async(
            args={"message": "Hello World"},
            tool_context=mock_context,
        )

        assert result["status"] == "success"
        assert result["echoed_message"] == "Hello World"

    @pytest.mark.asyncio
    async def test_run_async_async_function(self):
        """Test running an async function via run_async"""
        tool_config = {
            "tool_type": "python",
            "component_module": "tests.integration.test_support.tools",
            "function_name": "async_echo_tool",
            "name": "async_echo",
            "description": "Async echo tool",
        }

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tool = SkillTool("test-skill", tool_config, mock_component)

        mock_context = Mock()
        mock_context.state = {}

        result = await tool.run_async(
            args={"message": "Async Hello"},
            tool_context=mock_context,
        )

        assert result["status"] == "success"
        assert result["echoed_message"] == "Async Hello"
        assert result.get("has_context") is True  # tool_context was injected

    @pytest.mark.asyncio
    async def test_run_async_handles_error(self):
        """Test that run_async handles errors gracefully"""
        tool_config = {
            "tool_type": "python",
            "component_module": "tests.integration.test_support.tools",
            "function_name": "echo_tool",
            "name": "echo",
            "description": "Echo tool",
        }

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tool = SkillTool("test-skill", tool_config, mock_component)

        mock_context = Mock()
        mock_context.state = {}

        # Call with wrong argument type - will fail
        result = await tool.run_async(
            args={},  # Missing required 'message' argument
            tool_context=mock_context,
        )

        assert result["status"] == "error"
        assert "failed" in result["message"].lower()
