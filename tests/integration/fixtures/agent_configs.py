"""Agent configuration fixtures for integration tests.

This module contains all agent configuration dictionaries and the helper
function for creating agent configs. Extracted from the main integration conftest
to improve maintainability.
"""
import time
import pytest


def create_agent_config(
    test_llm_server,
    mcp_server_harness,
    agent_name,
    description,
    allow_list,
    tools,
    model_suffix,
    session_behavior="RUN_BASED",
    inject_system_purpose=False,
    inject_response_format=False,
):
    """
    Helper function to create agent configuration dictionaries.

    Args:
        test_llm_server: TestLLMServer instance for API base URL
        mcp_server_harness: MCP server connection params
        agent_name: Name of the agent
        description: Agent description for agent card
        allow_list: List of agents this agent can communicate with
        tools: List of tool configurations
        model_suffix: Suffix for model name (for uniqueness)
        session_behavior: "RUN_BASED" or "PERSISTENT"
        inject_system_purpose: Whether to inject system purpose
        inject_response_format: Whether to inject response format

    Returns:
        Agent configuration dictionary
    """
    config = {
        "namespace": "test_namespace",
        "supports_streaming": True,
        "agent_name": agent_name,
        "model": {
            "model": f"openai/test-model-{model_suffix}-{time.time_ns()}",
            "api_base": f"{test_llm_server.url}/v1",
            "api_key": f"fake_test_key_{model_suffix}",
        },
        "session_service": {"type": "memory", "default_behavior": session_behavior},
        "artifact_service": {"type": "test_in_memory"},
        "memory_service": {"type": "memory"},
        "agent_card": {
            "description": description,
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
            "jsonrpc": "2.0",
            "id": "agent_card_pub",
        },
        "agent_card_publishing": {"interval_seconds": 1},
        "agent_discovery": {"enabled": True},
        "inter_agent_communication": {
            "allow_list": allow_list,
            "request_timeout_seconds": 5,
        },
        "tool_output_save_threshold_bytes": 50,
        "tool_output_llm_return_max_bytes": 200,
        "data_tools_config": {
            "max_result_preview_rows": 5,
            "max_result_preview_bytes": 2048,
        },
        "stream_batching_threshold_bytes": 0,
        "tools": tools,
    }

    if inject_system_purpose:
        config["inject_system_purpose"] = True
    if inject_response_format:
        config["inject_response_format"] = True

    return config


def get_test_agent_tools(test_llm_server, mcp_server_harness):
    """Get the full tool configuration for the main test agent."""
    return [
        {
            "tool_type": "python",
            "component_module": "tests.integration.test_support.tools",
            "function_name": "get_weather_tool",
            "component_base_path": ".",
        },
        {"tool_type": "builtin", "tool_name": "convert_file_to_markdown"},
        {"tool_type": "builtin-group", "group_name": "artifact_management"},
        {"tool_type": "builtin-group", "group_name": "data_analysis"},
        {"tool_type": "builtin-group", "group_name": "test"},
        {
            "tool_type": "builtin",
            "tool_name": "web_request",
            "tool_config": {"allow_loopback": True},
        },
        {
            "tool_type": "python",
            "component_module": "solace_agent_mesh.agent.tools.web_tools",
            "function_name": "web_request",
            "tool_name": "web_request_strict",
            "component_base_path": ".",
            "tool_config": {"allow_loopback": False},
        },
        {"tool_type": "builtin", "tool_name": "mermaid_diagram_generator"},
        {
            "tool_type": "builtin",
            "tool_name": "create_image_from_description",
            "tool_config": {
                "model": "dall-e-3",
                "api_key": "fake-api-key",
                "api_base": f"{test_llm_server.url}",
            },
        },
        {
            "tool_type": "builtin",
            "tool_name": "describe_image",
            "tool_config": {
                "model": f"openai/test-model-sam-vision-{time.time_ns()}",
                "api_key": "fake-api-key",
                "api_base": f"{test_llm_server.url}",
            },
        },
        {
            "tool_type": "builtin",
            "tool_name": "describe_audio",
            "tool_config": {
                "model": "whisper-1",
                "api_key": "fake-api-key",
                "api_base": f"{test_llm_server.url}",
            },
        },
        {
            "tool_type": "builtin",
            "tool_name": "edit_image_with_gemini",
            "tool_config": {
                "model": "gemini-2.5-flash-image",
                "pro_model": "gemini-3-pro-image-preview",
                "gemini_api_key": "fake-gemini-api-key",
            },
        },
        {
            "tool_type": "mcp",
            "tool_name": "get_data_stdio",
            "connection_params": mcp_server_harness["stdio"],
        },
        {
            "tool_type": "mcp",
            "tool_name": "get_data_http",
            "connection_params": mcp_server_harness["http"],
        },
        {
            "tool_type": "mcp",
            "tool_name": "get_data_streamable_http",
            "connection_params": mcp_server_harness["streamable_http"],
        },
        {
            "tool_type": "mcp",
            "tool_name_prefix": "prefixed",
            "allow_list": ["get_data_stdio"],
            "connection_params": mcp_server_harness["stdio"],
        },
        {
            "tool_type": "builtin",
            "tool_name": "web_search_google",
            "tool_config": {
                "google_search_api_key": "fake-google-key",
                "google_cse_id": "fake-cse-id",
            },
        },
        {
            "tool_type": "builtin",
            "tool_name": "deep_research",
            "tool_config": {
                "google_search_api_key": "fake-google-key",
                "google_cse_id": "fake-cse-id",
            },
        },
    ]


def get_peer_agent_tools():
    """Get the tool configuration for peer agents."""
    return [
        {"tool_type": "builtin-group", "group_name": "artifact_management"},
        {"tool_type": "builtin-group", "group_name": "data_analysis"},
    ]


@pytest.fixture(scope="session")
def sam_agent_app_config(test_llm_server, mcp_server_harness):
    """Main test agent configuration."""
    test_agent_tools = get_test_agent_tools(test_llm_server, mcp_server_harness)
    return create_agent_config(
        test_llm_server=test_llm_server,
        mcp_server_harness=mcp_server_harness,
        agent_name="TestAgent",
        description="The main test agent (orchestrator)",
        allow_list=["TestPeerAgentA", "TestPeerAgentB", "TestAgent_Proxied", "TestAgent_Proxied_NoConvert"],
        tools=test_agent_tools,
        model_suffix="sam",
        inject_system_purpose=True,
        inject_response_format=True,
    )


@pytest.fixture(scope="session")
def peer_a_config(test_llm_server, mcp_server_harness):
    """Peer Agent A configuration."""
    return create_agent_config(
        test_llm_server=test_llm_server,
        mcp_server_harness=mcp_server_harness,
        agent_name="TestPeerAgentA",
        description="Peer Agent A, accessible by TestAgent, can access D",
        allow_list=["TestPeerAgentD"],
        tools=get_peer_agent_tools(),
        model_suffix="peerA",
    )


@pytest.fixture(scope="session")
def peer_b_config(test_llm_server, mcp_server_harness):
    """Peer Agent B configuration."""
    return create_agent_config(
        test_llm_server=test_llm_server,
        mcp_server_harness=mcp_server_harness,
        agent_name="TestPeerAgentB",
        description="Peer Agent B, accessible by TestAgent, cannot delegate",
        allow_list=[],
        tools=get_peer_agent_tools(),
        model_suffix="peerB",
    )


@pytest.fixture(scope="session")
def peer_c_config(test_llm_server, mcp_server_harness):
    """Peer Agent C configuration."""
    return create_agent_config(
        test_llm_server=test_llm_server,
        mcp_server_harness=mcp_server_harness,
        agent_name="TestPeerAgentC",
        description="Peer Agent C, not accessible by TestAgent",
        allow_list=[],
        tools=get_peer_agent_tools(),
        model_suffix="peerC",
        session_behavior="PERSISTENT",
    )


@pytest.fixture(scope="session")
def peer_d_config(test_llm_server, mcp_server_harness):
    """Peer Agent D configuration."""
    return create_agent_config(
        test_llm_server=test_llm_server,
        mcp_server_harness=mcp_server_harness,
        agent_name="TestPeerAgentD",
        description="Peer Agent D, accessible by Peer A",
        allow_list=[],
        tools=get_peer_agent_tools(),
        model_suffix="peerD",
    )


@pytest.fixture(scope="session")
def compaction_agent_config(test_llm_server, mcp_server_harness):
    """Compaction test agent with auto-summarization enabled."""
    config = create_agent_config(
        test_llm_server=test_llm_server,
        mcp_server_harness=mcp_server_harness,
        agent_name="TestAgentCompaction",
        description="Test agent for session compaction with auto-summarization",
        allow_list=[],
        tools=[{"tool_type": "builtin-group", "group_name": "artifact_management"}],
        model_suffix="compaction",
        session_behavior="PERSISTENT",
    )
    config["auto_summarization"] = {
        "enabled": True,
        "compaction_percentage": 0.30,
    }
    return config


@pytest.fixture(scope="session")
def combined_dynamic_agent_config(test_llm_server, mcp_server_harness):
    """Agent for testing all dynamic tool features."""
    return create_agent_config(
        test_llm_server=test_llm_server,
        mcp_server_harness=mcp_server_harness,
        agent_name="CombinedDynamicAgent",
        description="Agent for testing all dynamic tool features.",
        allow_list=[],
        tools=[
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.single_tool",
                "tool_config": {"greeting_prefix": "Hi there"},
            },
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.provider_tool",
            },
        ],
        model_suffix="dynamic-combined",
    )


@pytest.fixture(scope="session")
def empty_provider_agent_config(test_llm_server, mcp_server_harness):
    """Agent with an empty tool provider."""
    return create_agent_config(
        test_llm_server=test_llm_server,
        mcp_server_harness=mcp_server_harness,
        agent_name="EmptyProviderAgent",
        description="Agent with an empty tool provider.",
        allow_list=[],
        tools=[
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.error_cases",
                "class_name": "EmptyToolProvider",
            }
        ],
        model_suffix="empty-provider",
    )


@pytest.fixture(scope="session")
def docstringless_agent_config(test_llm_server, mcp_server_harness):
    """Agent with a tool that has no docstring."""
    return create_agent_config(
        test_llm_server=test_llm_server,
        mcp_server_harness=mcp_server_harness,
        agent_name="DocstringlessAgent",
        description="Agent with a tool that has no docstring.",
        allow_list=[],
        tools=[
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.error_cases",
                "class_name": "ProviderWithDocstringlessTool",
            }
        ],
        model_suffix="docstringless",
    )


@pytest.fixture(scope="session")
def mixed_discovery_agent_config(test_llm_server, mcp_server_harness):
    """Agent with a module containing both provider and standalone tool."""
    return create_agent_config(
        test_llm_server=test_llm_server,
        mcp_server_harness=mcp_server_harness,
        agent_name="MixedDiscoveryAgent",
        description="Agent with a module containing both provider and standalone tool.",
        allow_list=[],
        tools=[
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.mixed_discovery",
            }
        ],
        model_suffix="mixed-discovery",
    )


@pytest.fixture(scope="session")
def complex_signatures_agent_config(test_llm_server, mcp_server_harness):
    """Agent for testing complex tool signatures."""
    return create_agent_config(
        test_llm_server=test_llm_server,
        mcp_server_harness=mcp_server_harness,
        agent_name="ComplexSignaturesAgent",
        description="Agent for testing complex tool signatures.",
        allow_list=[],
        tools=[
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.complex_signatures",
            }
        ],
        model_suffix="complex-signatures",
    )


@pytest.fixture(scope="session")
def config_context_agent_config(test_llm_server, mcp_server_harness):
    """Agent for testing tool config and context features."""
    return create_agent_config(
        test_llm_server=test_llm_server,
        mcp_server_harness=mcp_server_harness,
        agent_name="ConfigContextAgent",
        description="Agent for testing tool config and context features.",
        allow_list=[],
        tools=[
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.config_and_context",
                "tool_config": {"provider_level": "value1", "tool_specific": "value2"},
            }
        ],
        model_suffix="config-context",
    )


@pytest.fixture(scope="session")
def artifact_content_agent_config(test_llm_server, mcp_server_harness):
    """Agent for testing ArtifactContent type hint artifact pre-loading."""
    return create_agent_config(
        test_llm_server=test_llm_server,
        mcp_server_harness=mcp_server_harness,
        agent_name="ArtifactContentAgent",
        description="Agent for testing ArtifactContent type hint artifact pre-loading.",
        allow_list=[],
        tools=[
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.artifact_content_tools",
            },
            {"tool_type": "builtin-group", "group_name": "artifact_management"},
        ],
        model_suffix="artifact-content",
    )

