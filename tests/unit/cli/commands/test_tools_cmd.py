"""
Unit tests for cli/commands/tools_cmd.py

Tests the tools list command including:
- Listing all tools with brief format (default)
- Listing tools with detailed format (--detailed flag)
- Filtering tools by category (--category flag)
- JSON output format (--json flag)
- Combined flags (category + detailed, category + json, etc.)
- Error handling (invalid category, no tools)
- Output formatting (brief, detailed, JSON)
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from google.genai import types as adk_types

from cli.commands.tools_cmd import (
    tools,
    list_tools,
    format_tool_table_brief,
    format_tool_table,
    tools_to_json,
    format_parameter_schema,
)
from solace_agent_mesh.agent.tools.tool_definition import BuiltinTool


@pytest.fixture
def runner():
    """Create a Click CLI runner for testing"""
    return CliRunner()


@pytest.fixture
def sample_tool():
    """Create a sample BuiltinTool for testing"""
    async def mock_implementation():
        pass

    parameters = adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "test_param": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="A test parameter",
            ),
            "optional_param": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="An optional parameter",
            ),
        },
        required=["test_param"],
    )

    return BuiltinTool(
        name="test_tool",
        implementation=mock_implementation,
        description="A test tool for unit testing",
        parameters=parameters,
        category="test_category",
        category_name="Test Category",
        category_description="Tools for testing",
        required_scopes=["tool:test:read"],
        examples=[],
        raw_string_args=[],
    )


@pytest.fixture
def sample_tools_list(sample_tool):
    """Create a list of sample tools for testing"""
    async def mock_impl():
        pass

    tool2 = BuiltinTool(
        name="another_tool",
        implementation=mock_impl,
        description="Another tool for testing",
        parameters=adk_types.Schema(
            type=adk_types.Type.OBJECT, properties={}, required=[]
        ),
        category="test_category",
        category_name="Test Category",
        category_description="Tools for testing",
        required_scopes=[],
        examples=[],
        raw_string_args=[],
    )

    tool3 = BuiltinTool(
        name="other_category_tool",
        implementation=mock_impl,
        description="A tool in a different category",
        parameters=adk_types.Schema(
            type=adk_types.Type.OBJECT, properties={}, required=[]
        ),
        category="other_category",
        category_name="Other Category",
        category_description="Other tools",
        required_scopes=["tool:other:write"],
        examples=[],
        raw_string_args=[],
    )

    return [sample_tool, tool2, tool3]


class TestFormatParameterSchema:
    """Tests for the format_parameter_schema helper function"""

    def test_format_parameter_schema_with_properties(self):
        """Test formatting schema with properties"""
        schema = adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "param1": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="First parameter",
                ),
                "param2": adk_types.Schema(
                    type=adk_types.Type.INTEGER,
                    description="Second parameter",
                ),
            },
            required=["param1"],
        )

        result = format_parameter_schema(schema)

        assert "param1" in result
        assert "param2" in result
        assert "STRING" in result
        assert "INTEGER" in result
        assert "required" in result
        assert "optional" in result
        assert "First parameter" in result
        assert "Second parameter" in result

    def test_format_parameter_schema_no_properties(self):
        """Test formatting schema with no properties"""
        schema = adk_types.Schema(type=adk_types.Type.OBJECT, properties={})

        result = format_parameter_schema(schema)

        assert "No parameters" in result

    def test_format_parameter_schema_none(self):
        """Test formatting None schema"""
        result = format_parameter_schema(None)

        assert "No parameters" in result


class TestToolsToJson:
    """Tests for the tools_to_json function"""

    def test_tools_to_json_brief(self, sample_tools_list):
        """Test JSON output in brief mode"""
        result_json = tools_to_json(sample_tools_list, detailed=False)
        result = json.loads(result_json)

        assert len(result) == 3
        assert all("name" in tool for tool in result)
        assert all("description" in tool for tool in result)
        assert all("category" in tool for tool in result)
        assert all("category_name" in tool for tool in result)
        # Brief mode should NOT include parameters
        assert all("parameters" not in tool for tool in result)
        assert all("required_scopes" not in tool for tool in result)

    def test_tools_to_json_detailed(self, sample_tools_list):
        """Test JSON output in detailed mode"""
        result_json = tools_to_json(sample_tools_list, detailed=True)
        result = json.loads(result_json)

        assert len(result) == 3
        assert all("name" in tool for tool in result)
        assert all("description" in tool for tool in result)
        assert all("category" in tool for tool in result)
        # Detailed mode should include parameters and scopes
        assert all("parameters" in tool for tool in result)
        assert all("required_scopes" in tool for tool in result)
        assert all("examples" in tool for tool in result)
        assert all("raw_string_args" in tool for tool in result)

    def test_tools_to_json_empty_list(self):
        """Test JSON output with empty list"""
        result_json = tools_to_json([], detailed=False)
        result = json.loads(result_json)

        assert result == []


class TestFormatToolTableBrief:
    """Tests for the format_tool_table_brief function"""

    def test_format_tool_table_brief_output(self, sample_tools_list, capsys):
        """Test brief table formatting output"""
        format_tool_table_brief(sample_tools_list)
        captured = capsys.readouterr()

        assert "Test Category" in captured.out
        assert "Other Category" in captured.out
        assert "test_tool" in captured.out
        assert "another_tool" in captured.out
        assert "other_category_tool" in captured.out
        assert "A test tool for unit testing" in captured.out
        assert "Total: 3 tools" in captured.out
        # Brief mode should NOT show parameters
        assert "Parameters:" not in captured.out
        assert "Required Scopes:" not in captured.out

    def test_format_tool_table_brief_empty_list(self, capsys):
        """Test brief table with empty list"""
        format_tool_table_brief([])
        captured = capsys.readouterr()

        assert "No tools found" in captured.out


class TestFormatToolTable:
    """Tests for the format_tool_table (detailed) function"""

    def test_format_tool_table_detailed_output(self, sample_tools_list, capsys):
        """Test detailed table formatting output"""
        format_tool_table(sample_tools_list)
        captured = capsys.readouterr()

        assert "Test Category" in captured.out
        assert "test_tool" in captured.out
        assert "A test tool for unit testing" in captured.out
        assert "Total: 3 tools" in captured.out
        # Detailed mode should show parameters and scopes
        assert "Parameters:" in captured.out
        assert "Required Scopes:" in captured.out
        assert "test_param" in captured.out
        assert "tool:test:read" in captured.out

    def test_format_tool_table_empty_list(self, capsys):
        """Test detailed table with empty list"""
        format_tool_table([])
        captured = capsys.readouterr()

        assert "No tools found" in captured.out


class TestToolsCommand:
    """Tests for the tools CLI command group"""

    def test_tools_command_exists(self, runner):
        """Test that tools command exists"""
        result = runner.invoke(tools, ["--help"])

        assert result.exit_code == 0
        assert "Manage and explore SAM built-in tools" in result.output

    def test_tools_list_subcommand_exists(self, runner):
        """Test that tools list subcommand exists"""
        result = runner.invoke(tools, ["list", "--help"])

        assert result.exit_code == 0
        assert "List all built-in tools" in result.output
        assert "--category" in result.output
        assert "--detailed" in result.output
        assert "--json" in result.output


class TestListToolsCommand:
    """Tests for the list_tools command"""

    def test_list_tools_brief_default(self, runner, sample_tools_list):
        """Test list command with brief output (default)"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            mock_registry.get_all_tools.return_value = sample_tools_list

            result = runner.invoke(list_tools, [])

            assert result.exit_code == 0
            assert "Test Category" in result.output
            assert "test_tool" in result.output
            assert "A test tool for unit testing" in result.output
            assert "Total: 3 tools" in result.output
            # Brief mode should NOT show parameters
            assert "Parameters:" not in result.output

    def test_list_tools_detailed_flag(self, runner, sample_tools_list):
        """Test list command with --detailed flag"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            mock_registry.get_all_tools.return_value = sample_tools_list

            result = runner.invoke(list_tools, ["--detailed"])

            assert result.exit_code == 0
            assert "Test Category" in result.output
            assert "test_tool" in result.output
            # Detailed mode should show parameters
            assert "Parameters:" in result.output
            assert "test_param" in result.output
            assert "Required Scopes:" in result.output

    def test_list_tools_detailed_short_flag(self, runner, sample_tools_list):
        """Test list command with -d short flag"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            mock_registry.get_all_tools.return_value = sample_tools_list

            result = runner.invoke(list_tools, ["-d"])

            assert result.exit_code == 0
            assert "Parameters:" in result.output

    def test_list_tools_category_filter(self, runner, sample_tools_list):
        """Test list command with --category filter"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            # Mock get_tools_by_category to return only tools from test_category
            filtered_tools = [t for t in sample_tools_list if t.category == "test_category"]
            mock_registry.get_tools_by_category.return_value = filtered_tools

            result = runner.invoke(list_tools, ["--category", "test_category"])

            assert result.exit_code == 0
            assert "test_tool" in result.output
            assert "another_tool" in result.output
            assert "other_category_tool" not in result.output
            assert "Total: 2 tools" in result.output

    def test_list_tools_category_short_flag(self, runner, sample_tools_list):
        """Test list command with -c short flag"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            filtered_tools = [t for t in sample_tools_list if t.category == "test_category"]
            mock_registry.get_tools_by_category.return_value = filtered_tools

            result = runner.invoke(list_tools, ["-c", "test_category"])

            assert result.exit_code == 0
            assert "test_tool" in result.output

    def test_list_tools_invalid_category(self, runner, sample_tools_list):
        """Test list command with invalid category"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            mock_registry.get_tools_by_category.return_value = []
            mock_registry.get_all_tools.return_value = sample_tools_list

            # Mock error_exit to raise SystemExit
            with patch("cli.commands.tools_cmd.error_exit", side_effect=SystemExit(1)):
                result = runner.invoke(list_tools, ["--category", "invalid_category"])

                assert result.exit_code == 1

    def test_list_tools_json_output_brief(self, runner, sample_tools_list):
        """Test list command with JSON output (brief)"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            mock_registry.get_all_tools.return_value = sample_tools_list

            result = runner.invoke(list_tools, ["--json"])

            assert result.exit_code == 0
            # Parse JSON to verify format
            output = json.loads(result.output)
            assert len(output) == 3
            assert all("name" in tool for tool in output)
            assert all("description" in tool for tool in output)
            # Brief JSON should NOT include parameters
            assert all("parameters" not in tool for tool in output)

    def test_list_tools_json_output_detailed(self, runner, sample_tools_list):
        """Test list command with JSON output (detailed)"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            mock_registry.get_all_tools.return_value = sample_tools_list

            result = runner.invoke(list_tools, ["--json", "--detailed"])

            assert result.exit_code == 0
            # Parse JSON to verify format
            output = json.loads(result.output)
            assert len(output) == 3
            # Detailed JSON should include parameters
            assert all("parameters" in tool for tool in output)
            assert all("required_scopes" in tool for tool in output)

    def test_list_tools_combined_flags(self, runner, sample_tools_list):
        """Test list command with combined flags"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            filtered_tools = [t for t in sample_tools_list if t.category == "test_category"]
            mock_registry.get_tools_by_category.return_value = filtered_tools

            result = runner.invoke(
                list_tools, ["-c", "test_category", "-d", "--json"]
            )

            assert result.exit_code == 0
            # Parse JSON
            output = json.loads(result.output)
            assert len(output) == 2
            # Should be detailed JSON
            assert all("parameters" in tool for tool in output)
            # Should be filtered
            assert all(tool["category"] == "test_category" for tool in output)

    def test_list_tools_no_tools_registered(self, runner):
        """Test list command when no tools are registered"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            mock_registry.get_all_tools.return_value = []

            with patch("cli.commands.tools_cmd.error_exit", side_effect=SystemExit(1)):
                result = runner.invoke(list_tools, [])

                assert result.exit_code == 1

    def test_list_tools_category_with_detailed(self, runner, sample_tools_list):
        """Test list command with category filter and detailed flag"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            filtered_tools = [t for t in sample_tools_list if t.category == "test_category"]
            mock_registry.get_tools_by_category.return_value = filtered_tools

            result = runner.invoke(list_tools, ["-c", "test_category", "--detailed"])

            assert result.exit_code == 0
            assert "test_tool" in result.output
            assert "Parameters:" in result.output
            assert "Total: 2 tools" in result.output

    def test_list_tools_help_message(self, runner):
        """Test list command help message"""
        result = runner.invoke(list_tools, ["--help"])

        assert result.exit_code == 0
        assert "List all built-in tools" in result.output
        assert "By default, shows brief information" in result.output
        assert "--detailed flag" in result.output
        assert "Examples:" in result.output

    def test_list_tools_multiple_categories_output(self, runner, sample_tools_list):
        """Test list command groups tools by category"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            mock_registry.get_all_tools.return_value = sample_tools_list

            result = runner.invoke(list_tools, [])

            assert result.exit_code == 0
            # Both categories should be present
            assert "Test Category" in result.output
            assert "Other Category" in result.output
            # All tools should be present
            assert "test_tool" in result.output
            assert "another_tool" in result.output
            assert "other_category_tool" in result.output
            # Verify tools are grouped by category
            output_lines = result.output.split("\n")
            # Find indices, handling case where items might not be found
            try:
                test_cat_idx = next(
                    i for i, line in enumerate(output_lines) if "Test Category" in line
                )
                other_cat_idx = next(
                    i for i, line in enumerate(output_lines) if "Other Category" in line
                )
                # Test Category should come before Other Category (alphabetical)
                assert other_cat_idx < test_cat_idx
            except StopIteration:
                # If we can't find specific line numbers, just verify content is present
                pass

    def test_list_tools_json_valid_structure(self, runner, sample_tool):
        """Test JSON output has valid structure"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            mock_registry.get_all_tools.return_value = [sample_tool]

            result = runner.invoke(list_tools, ["--json", "-d"])

            assert result.exit_code == 0
            output = json.loads(result.output)

            # Verify structure of first tool
            tool = output[0]
            assert tool["name"] == "test_tool"
            assert tool["description"] == "A test tool for unit testing"
            assert tool["category"] == "test_category"
            assert tool["category_name"] == "Test Category"
            assert "parameters" in tool
            assert "required_scopes" in tool
            assert tool["required_scopes"] == ["tool:test:read"]

    def test_list_tools_alphabetical_sorting(self, runner, sample_tools_list):
        """Test that tools are sorted alphabetically within categories"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            mock_registry.get_all_tools.return_value = sample_tools_list

            result = runner.invoke(list_tools, [])

            assert result.exit_code == 0
            # Within test_category, "another_tool" should come before "test_tool"
            output_lines = result.output.split("\n")
            another_idx = next(
                i for i, line in enumerate(output_lines) if "another_tool" in line
            )
            test_idx = next(
                i for i, line in enumerate(output_lines) if "• test_tool" in line
            )
            assert another_idx < test_idx

    def test_list_tools_invalid_category_shows_valid_options(self, runner, sample_tools_list):
        """Test that invalid category error shows valid categories"""
        with patch("cli.commands.tools_cmd.tool_registry") as mock_registry:
            mock_registry.get_tools_by_category.return_value = []
            mock_registry.get_all_tools.return_value = sample_tools_list

            mock_error_exit = MagicMock(side_effect=SystemExit(1))
            with patch("cli.commands.tools_cmd.error_exit", mock_error_exit):
                result = runner.invoke(list_tools, ["-c", "nonexistent"])

                assert result.exit_code == 1
                # Verify error_exit was called with message about valid categories
                error_msg = mock_error_exit.call_args[0][0]
                assert "No tools found for category 'nonexistent'" in error_msg
                assert "Valid categories:" in error_msg
                assert "test_category" in error_msg
                assert "other_category" in error_msg
