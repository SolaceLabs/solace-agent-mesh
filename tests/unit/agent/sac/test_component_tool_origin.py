#!/usr/bin/env python3
"""
Unit tests for the SamAgentComponent class
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
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


class TestSyncToolsCallback:
    """Test cases for _sync_tools_callback on SamAgentComponent."""

    def _create_component(self):
        """Create a mock SamAgentComponent with log_identifier."""
        component = Mock(spec=SamAgentComponent)
        component.log_identifier = "[Test]"
        # Bind the real methods to our mock
        component._sync_tools_callback = (
            SamAgentComponent._sync_tools_callback.__get__(
                component, SamAgentComponent
            )
        )
        component._ensure_tool_in_tools_dict = (
            SamAgentComponent._ensure_tool_in_tools_dict.__get__(
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

    @patch(
        "src.solace_agent_mesh.agent.sac.component.tool_registry"
    )
    def test_skips_when_no_project_id_and_not_in_registry(self, mock_registry):
        """Callback returns None when no project_id and tool not in registry."""
        mock_registry.get_tool_by_name.return_value = None
        component = self._create_component()
        ctx = self._create_callback_context(project_id=None)
        request = self._create_llm_request()

        result = component._sync_tools_callback(ctx, request)

        assert result is None
        assert "index_search" not in request.tools_dict

    def test_skips_when_index_search_already_declared(self):
        """Callback returns None when index_search declaration already exists."""
        component = self._create_component()
        ctx = self._create_callback_context(project_id="proj-123")
        existing_tool = Mock()
        declaration = adk_types.FunctionDeclaration(
            name="index_search",
            description="Search docs",
            parameters=adk_types.Schema(type=adk_types.Type.OBJECT),
        )
        request = self._create_llm_request(tools_dict={"index_search": existing_tool})
        request.config.tools[0].function_declarations.append(declaration)

        result = component._sync_tools_callback(ctx, request)

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

        result = component._sync_tools_callback(ctx, request)

        assert result is None
        assert "index_search" not in request.tools_dict

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

        result = component._sync_tools_callback(ctx, request)

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

    def test_removes_static_index_search_when_no_project_id(self):
        """Statically-configured index_search declaration is removed when no project_id."""
        component = self._create_component()
        ctx = self._create_callback_context(project_id=None)
        # Simulate stale instructions from a previous project context
        ctx.state["project_tool_instructions"] = "Use index_search to search documents."

        # Simulate index_search loaded from YAML config
        existing_tool = Mock()
        declaration = adk_types.FunctionDeclaration(
            name="index_search",
            description="Search docs",
            parameters=adk_types.Schema(type=adk_types.Type.OBJECT),
        )
        request = self._create_llm_request(tools_dict={"index_search": existing_tool})
        request.config.tools[0].function_declarations.append(declaration)

        result = component._sync_tools_callback(ctx, request)

        assert result is None
        # tools_dict keeps the tool for ADK dispatch safety
        assert "index_search" in request.tools_dict
        # Declaration should be removed so LLM doesn't see it
        for tool_obj in (request.config.tools or []):
            assert not any(
                fd.name == "index_search" for fd in (tool_obj.function_declarations or [])
            )
        # Stale instructions should be cleared so LLM doesn't get citation prompts
        assert ctx.state.get("project_tool_instructions") is None

    def test_removes_static_index_search_when_no_metadata(self):
        """index_search declaration removed when original_message_metadata is absent (structured A2A)."""
        component = self._create_component()
        ctx = Mock(spec=CallbackContext)
        # Structured A2A: a2a_context exists but has no original_message_metadata
        ctx.state = {"a2a_context": {"session_id": "sess-1"}}

        existing_tool = Mock()
        declaration = adk_types.FunctionDeclaration(
            name="index_search",
            description="Search docs",
            parameters=adk_types.Schema(type=adk_types.Type.OBJECT),
        )
        request = self._create_llm_request(tools_dict={"index_search": existing_tool})
        request.config.tools[0].function_declarations.append(declaration)

        result = component._sync_tools_callback(ctx, request)

        assert result is None
        # tools_dict keeps the tool for ADK dispatch safety
        assert "index_search" in request.tools_dict
        # Declaration should be removed
        for tool_obj in (request.config.tools or []):
            assert not any(
                fd.name == "index_search" for fd in (tool_obj.function_declarations or [])
            )

    def test_leaves_other_tools_when_removing_index_search(self):
        """Other tools are untouched when index_search declaration is removed."""
        component = self._create_component()
        ctx = self._create_callback_context(project_id=None)

        other_tool = Mock()
        index_tool = Mock()
        other_decl = adk_types.FunctionDeclaration(
            name="web_request",
            description="Fetch web content",
            parameters=adk_types.Schema(type=adk_types.Type.OBJECT),
        )
        index_decl = adk_types.FunctionDeclaration(
            name="index_search",
            description="Search docs",
            parameters=adk_types.Schema(type=adk_types.Type.OBJECT),
        )
        request = self._create_llm_request(
            tools_dict={"web_request": other_tool, "index_search": index_tool}
        )
        request.config.tools[0].function_declarations.extend([other_decl, index_decl])

        component._sync_tools_callback(ctx, request)

        # Both tools stay in tools_dict for ADK dispatch safety
        assert "web_request" in request.tools_dict
        assert request.tools_dict["web_request"] is other_tool
        assert "index_search" in request.tools_dict
        # Only index_search declaration is removed
        remaining_names = [
            fd.name
            for t in (request.config.tools or [])
            for fd in (t.function_declarations or [])
        ]
        assert "web_request" in remaining_names
        assert "index_search" not in remaining_names

    def test_keeps_static_index_search_when_project_id_present(self):
        """Statically-configured index_search stays when project_id is present."""
        component = self._create_component()
        ctx = self._create_callback_context(project_id="proj-123")
        existing_tool = Mock()
        declaration = adk_types.FunctionDeclaration(
            name="index_search",
            description="Search docs",
            parameters=adk_types.Schema(type=adk_types.Type.OBJECT),
        )
        request = self._create_llm_request(tools_dict={"index_search": existing_tool})
        request.config.tools[0].function_declarations.append(declaration)

        result = component._sync_tools_callback(ctx, request)

        assert result is None
        assert "index_search" in request.tools_dict
        assert request.tools_dict["index_search"] is existing_tool
        # Declaration should still be present
        assert any(
            fd.name == "index_search"
            for t in request.config.tools
            for fd in (t.function_declarations or [])
        )

    @patch(
        "src.solace_agent_mesh.agent.sac.component.tool_registry"
    )
    def test_tools_dict_populated_on_fresh_request_without_project(
        self, mock_registry
    ):
        """When chat moves out of project, tools_dict is rebuilt fresh (no
        index_search). _ensure_tool_in_tools_dict should add it from the
        registry so the ADK can dispatch if LLM calls from history."""
        tool_def = self._create_mock_tool_def()
        mock_registry.get_tool_by_name.return_value = tool_def

        component = self._create_component()
        ctx = self._create_callback_context(project_id=None)
        # Fresh tools_dict — simulates ADK rebuilding from agent.tools
        # where index_search was NOT statically configured
        request = self._create_llm_request()

        component._sync_tools_callback(ctx, request)

        # Declaration should NOT be present — LLM shouldn't see it
        for tool_obj in (request.config.tools or []):
            assert not any(
                fd.name == "index_search"
                for fd in (tool_obj.function_declarations or [])
            )
        # tools_dict should have it — ADK can dispatch if LLM calls from history
        assert "index_search" in request.tools_dict


# ---------------------------------------------------------------------------
# Agent card tool manifest builder
# ---------------------------------------------------------------------------


class _FakeDynamicTool:
    """Simulates a DynamicTool subclass.

    `name` / `description` are still the placeholder values (as they would be
    before _get_declaration() fires), but `tool_name` / `tool_description`
    return the real, user-defined values via properties.
    """

    name = "dynamic_tool_placeholder"
    description = "dynamic_tool_placeholder"

    @property
    def tool_name(self):
        return "my_real_tool"

    @property
    def tool_description(self):
        return "Does something genuinely useful."


class _FakeRegularTool:
    """Simulates a plain BaseTool that has no tool_name / tool_description properties."""

    def __init__(self, name="regular_tool", description="A regular tool."):
        self.name = name
        self.description = description


def _make_manifest_component():
    """Return a bare Mock that satisfies _perform_async_init's attribute accesses."""
    component = Mock()
    component.log_identifier = "[TestAgent]"
    component.agent_name = "test_agent"
    # _async_init_future = None → the signaling branch is skipped (just logs a warning)
    component._async_init_future = None
    # Bind the real async/sync methods so `await _build_tool_manifest(...)` works
    component._build_tool_manifest = lambda tools: SamAgentComponent._build_tool_manifest(component, tools)
    component._get_single_tool_manifest_entry = lambda tool: SamAgentComponent._get_single_tool_manifest_entry(component, tool)
    return component


def _patch_setup(loaded_tools, scopes_map=None):
    """Context managers that patch load_adk_tools, initialize_adk_agent, and
    initialize_adk_runner so _perform_async_init runs only the manifest builder."""
    return (
        patch(
            "src.solace_agent_mesh.agent.sac.component.load_adk_tools",
            new_callable=AsyncMock,
            return_value=(loaded_tools, [], [], scopes_map or {}),
        ),
        patch(
            "src.solace_agent_mesh.agent.sac.component.initialize_adk_agent",
            return_value=Mock(),
        ),
        patch(
            "src.solace_agent_mesh.agent.sac.component.initialize_adk_runner",
            return_value=Mock(),
        ),
    )


@pytest.mark.asyncio
class TestManifestBuilderDynamicToolFix:
    """_perform_async_init must use tool_name / tool_description for DynamicTool subclasses."""

    async def test_dynamic_tool_real_name_in_manifest(self):
        """Manifest id/name must be tool_name, not the 'dynamic_tool_placeholder' attr."""
        component = _make_manifest_component()
        load_patch, agent_patch, runner_patch = _patch_setup([_FakeDynamicTool()])

        with load_patch, agent_patch, runner_patch:
            await SamAgentComponent._perform_async_init(component)

        assert len(component.agent_card_tool_manifest) == 1
        entry = component.agent_card_tool_manifest[0]
        assert entry["id"] == "my_real_tool"
        assert entry["name"] == "my_real_tool"
        assert "placeholder" not in entry["name"]

    async def test_dynamic_tool_real_description_in_manifest(self):
        """Manifest description must come from tool_description, not the placeholder attr."""
        component = _make_manifest_component()
        load_patch, agent_patch, runner_patch = _patch_setup([_FakeDynamicTool()])

        with load_patch, agent_patch, runner_patch:
            await SamAgentComponent._perform_async_init(component)

        entry = component.agent_card_tool_manifest[0]
        assert entry["description"] == "Does something genuinely useful."
        assert "placeholder" not in entry["description"]

    async def test_dynamic_tool_scopes_resolved_by_real_name(self):
        """required_scopes lookup uses tool_name (not the placeholder) as the key."""
        scopes_map = {"my_real_tool": ["read:data", "write:data"]}
        component = _make_manifest_component()
        load_patch, agent_patch, runner_patch = _patch_setup(
            [_FakeDynamicTool()], scopes_map=scopes_map
        )

        with load_patch, agent_patch, runner_patch:
            await SamAgentComponent._perform_async_init(component)

        entry = component.agent_card_tool_manifest[0]
        assert entry["required_scopes"] == ["read:data", "write:data"]

    async def test_dynamic_tool_no_scopes_when_map_uses_placeholder_key(self):
        """If scopes_map was incorrectly keyed by the placeholder, no scopes are found.

        Documents the contract: the manifest builder looks up by real name, so a
        map keyed by the placeholder returns no scopes (empty list).
        """
        scopes_map = {"dynamic_tool_placeholder": ["should:not:match"]}
        component = _make_manifest_component()
        load_patch, agent_patch, runner_patch = _patch_setup(
            [_FakeDynamicTool()], scopes_map=scopes_map
        )

        with load_patch, agent_patch, runner_patch:
            await SamAgentComponent._perform_async_init(component)

        entry = component.agent_card_tool_manifest[0]
        assert entry["required_scopes"] == []

    async def test_regular_tool_uses_name_attribute(self):
        """Non-DynamicTool tools fall back to the `name` attribute as before."""
        component = _make_manifest_component()
        tool = _FakeRegularTool(name="fetch_data", description="Fetches remote data.")
        load_patch, agent_patch, runner_patch = _patch_setup([tool])

        with load_patch, agent_patch, runner_patch:
            await SamAgentComponent._perform_async_init(component)

        assert len(component.agent_card_tool_manifest) == 1
        entry = component.agent_card_tool_manifest[0]
        assert entry["id"] == "fetch_data"
        assert entry["name"] == "fetch_data"
        assert entry["description"] == "Fetches remote data."

    async def test_mixed_tools_both_resolved_correctly(self):
        """A mix of DynamicTool and regular tools both appear with the correct names."""
        component = _make_manifest_component()
        tools = [_FakeDynamicTool(), _FakeRegularTool(name="plain_tool", description="Plain.")]
        load_patch, agent_patch, runner_patch = _patch_setup(tools)

        with load_patch, agent_patch, runner_patch:
            await SamAgentComponent._perform_async_init(component)

        assert len(component.agent_card_tool_manifest) == 2
        names = {e["name"] for e in component.agent_card_tool_manifest}
        assert names == {"my_real_tool", "plain_tool"}
        assert "dynamic_tool_placeholder" not in names

    async def test_dynamic_tool_null_description_falls_back(self):
        """tool_description returning None produces 'No description available.' in the manifest."""

        class _NullDescTool:
            name = "dynamic_tool_placeholder"
            description = "dynamic_tool_placeholder"

            @property
            def tool_name(self):
                return "no_desc_tool"

            @property
            def tool_description(self):
                return None

        component = _make_manifest_component()
        load_patch, agent_patch, runner_patch = _patch_setup([_NullDescTool()])

        with load_patch, agent_patch, runner_patch:
            await SamAgentComponent._perform_async_init(component)

        entry = component.agent_card_tool_manifest[0]
        assert entry["description"] == "No description available."

    async def test_empty_tool_list_produces_empty_manifest(self):
        """No tools → empty manifest (sanity check, no regression)."""
        component = _make_manifest_component()
        load_patch, agent_patch, runner_patch = _patch_setup([])

        with load_patch, agent_patch, runner_patch:
            await SamAgentComponent._perform_async_init(component)

        assert component.agent_card_tool_manifest == []
