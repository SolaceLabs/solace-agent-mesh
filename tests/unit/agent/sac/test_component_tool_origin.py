#!/usr/bin/env python3
"""
Unit tests for the SamAgentComponent class
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from google.genai import types as adk_types
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest

from src.solace_agent_mesh.agent.sac.component import SamAgentComponent
from src.solace_agent_mesh.agent.tools.tool_definition import BuiltinTool


class TestExtractToolOrigin:
    """Test cases for the _extract_tool_origin static method in SamAgentComponent."""

    def test_extract_tool_origin_with_direct_origin(self):
        """Test _extract_tool_origin when tool has a direct origin attribute."""
        tool = Mock()
        tool.origin = "direct_origin"

        result = SamAgentComponent._extract_tool_origin(tool)
        assert result == "direct_origin"

    def test_extract_tool_origin_with_func_origin(self):
        """Test _extract_tool_origin when tool has a func with origin attribute."""

        tool = Mock()
        tool.origin = None
        tool.func = Mock()
        tool.func.origin = "func_origin"

        result = SamAgentComponent._extract_tool_origin(tool)
        assert result == "func_origin"

    def test_extract_tool_origin_unknown_fallback(self):
        """Test _extract_tool_origin when no origin is found."""
        # Create a mock object that does not have an 'origin' attribute,
        # and its 'func' attribute is None.
        tool = Mock(spec=["func"])
        tool.func = None

        result = SamAgentComponent._extract_tool_origin(tool)
        assert result == "unknown"


class TestInjectProjectToolsCallback:
    """Test cases for _inject_project_tools_callback on SamAgentComponent."""

    def _create_component(self):
        """Create a mock SamAgentComponent with log_identifier."""
        component = Mock(spec=SamAgentComponent)
        component.log_identifier = "[Test]"
        # Bind the real method to our mock
        component._inject_project_tools_callback = (
            SamAgentComponent._inject_project_tools_callback.__get__(
                component, SamAgentComponent
            )
        )
        return component

    def _create_callback_context(self, project_id=None):
        """Create a mock CallbackContext with optional project_id in metadata."""
        ctx = Mock(spec=CallbackContext)
        metadata = {}
        if project_id is not None:
            metadata["project_id"] = project_id
        ctx.state = {
            "a2a_context": {"original_message_metadata": metadata}
        }
        return ctx

    def _create_llm_request(self, tools_dict=None):
        """Create an LlmRequest with config.tools and tools_dict."""
        content = adk_types.Content(role="user", parts=[adk_types.Part(text="Hello")])
        config = adk_types.GenerateContentConfig(
            tools=[adk_types.Tool(function_declarations=[])]
        )
        request = LlmRequest(contents=[content], config=config)
        if tools_dict:
            request.tools_dict = tools_dict
        return request

    def _create_mock_tool_def(self):
        """Create a mock BuiltinTool definition for index_search."""
        tool_def = Mock(spec=BuiltinTool)
        tool_def.name = "index_search"
        tool_def.description = "Search the project document index."
        tool_def.parameters = adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "query": adk_types.Schema(
                    type=adk_types.Type.STRING, description="Search query"
                )
            },
        )
        tool_def.implementation = Mock()
        tool_def.implementation.__name__ = "index_search"
        tool_def.implementation.__doc__ = "Search the project document index."
        tool_def.raw_string_args = []
        tool_def.artifact_args = []
        tool_def.category = "Search"
        tool_def.category_name = "Search"
        tool_def.category_description = "Search tools"
        tool_def.required_scopes = []
        tool_def.examples = []
        return tool_def

    def test_skips_when_no_project_id(self):
        """Callback returns None and does not mutate llm_request when no project_id."""
        component = self._create_component()
        ctx = self._create_callback_context(project_id=None)
        request = self._create_llm_request()

        result = component._inject_project_tools_callback(ctx, request)

        assert result is None
        assert "index_search" not in request.tools_dict

    def test_skips_when_index_search_already_in_tools_dict(self):
        """Callback returns None when index_search is already present."""
        component = self._create_component()
        ctx = self._create_callback_context(project_id="proj-123")
        existing_tool = Mock()
        request = self._create_llm_request(tools_dict={"index_search": existing_tool})

        result = component._inject_project_tools_callback(ctx, request)

        assert result is None
        # The existing tool should remain unchanged
        assert request.tools_dict["index_search"] is existing_tool

    @patch(
        "src.solace_agent_mesh.agent.sac.component.tool_registry"
    )
    def test_skips_when_tool_not_in_registry(self, mock_registry):
        """Callback returns None when index_search is not in the tool registry."""
        mock_registry.get_tool_by_name.return_value = None
        component = self._create_component()
        ctx = self._create_callback_context(project_id="proj-123")
        request = self._create_llm_request()

        result = component._inject_project_tools_callback(ctx, request)

        assert result is None
        assert "index_search" not in request.tools_dict
        mock_registry.get_tool_by_name.assert_called_once_with("index_search")

    @patch(
        "src.solace_agent_mesh.agent.sac.component._generate_tool_instructions_from_registry"
    )
    @patch(
        "src.solace_agent_mesh.agent.sac.component.tool_registry"
    )
    def test_injects_tool_when_project_id_present(
        self, mock_registry, mock_gen_instructions
    ):
        """Callback injects index_search into tools_dict and config.tools."""
        tool_def = self._create_mock_tool_def()
        mock_registry.get_tool_by_name.return_value = tool_def
        mock_gen_instructions.return_value = "Use index_search to search documents."

        component = self._create_component()
        ctx = self._create_callback_context(project_id="proj-123")
        request = self._create_llm_request()

        result = component._inject_project_tools_callback(ctx, request)

        assert result is None

        # Tool should be added to tools_dict
        assert "index_search" in request.tools_dict
        injected = request.tools_dict["index_search"]
        assert injected.name == "index_search"
        assert hasattr(injected, "origin")
        assert injected.origin == "builtin"

        # FunctionDeclaration should be appended to config.tools
        declarations = request.config.tools[0].function_declarations
        assert any(d.name == "index_search" for d in declarations)

        # Instructions should be stored in callback state
        assert ctx.state["project_tool_instructions"] == (
            "Use index_search to search documents."
        )
