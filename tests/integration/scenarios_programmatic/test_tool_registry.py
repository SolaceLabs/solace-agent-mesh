"""
Programmatic integration tests for the BuiltinTool registry.
"""

import pytest
from solace_agent_mesh.agent.tools.registry import tool_registry
from solace_agent_mesh.agent.tools.tool_definition import BuiltinTool
from google.genai import types as adk_types

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.agent,
    pytest.mark.tools
]


async def test_initial_tool_registry_state():
    """
    Tests that the tool_registry is populated with the configured built-in tools
    after the agent component has been initialized.
    """
    scenario_id = "tool_registry_initial_state_001"
    print(f"\nRunning scenario: {scenario_id}")

    web_request_tool = tool_registry.get_tool_by_name("web_request")
    assert web_request_tool is not None
    assert isinstance(web_request_tool, BuiltinTool)
    assert web_request_tool.name == "web_request"
    print(f"Scenario {scenario_id}: Verified 'web_request' tool is registered.")

    expected_artifact_tools = [
        "append_to_artifact",
        "list_artifacts",
        "load_artifact",
        "signal_artifact_for_return",
        "apply_embed_and_create_artifact",
        "extract_content_from_artifact",
        "delete_artifact",
    ]
    for tool_name in expected_artifact_tools:
        tool = tool_registry.get_tool_by_name(tool_name)
        assert (
            tool is not None
        ), f"Tool '{tool_name}' should be registered from the 'artifact_management' group."
        assert tool.category == "artifact_management"
    print(
        f"Scenario {scenario_id}: Verified tools from 'artifact_management' group are registered."
    )

    expected_data_tools = [
        "create_chart_from_plotly_config",
    ]
    for tool_name in expected_data_tools:
        tool = tool_registry.get_tool_by_name(tool_name)
        assert (
            tool is not None
        ), f"Tool '{tool_name}' should be registered from the 'data_analysis' group."
        assert tool.category == "data_analysis"
    print(
        f"Scenario {scenario_id}: Verified tools from 'data_analysis' group are registered."
    )

    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_get_tool_by_name_integration():
    """
    Tests that get_tool_by_name works correctly in an integrated environment.
    """
    scenario_id = "tool_registry_get_by_name_001"
    print(f"\nRunning scenario: {scenario_id}")

    sql_tool = tool_registry.get_tool_by_name("create_chart_from_plotly_config")
    assert sql_tool is not None
    assert isinstance(sql_tool, BuiltinTool)
    assert sql_tool.name == "create_chart_from_plotly_config"
    assert sql_tool.category == "data_analysis"
    print(
        f"Scenario {scenario_id}: Successfully retrieved 'create_chart_from_plotly_config' tool."
    )

    non_existent_tool = tool_registry.get_tool_by_name("non_existent_tool_123")
    assert non_existent_tool is None
    print(f"Scenario {scenario_id}: Verified that a non-existent tool returns None.")

    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_get_tools_by_category_integration():
    """
    Tests that get_tools_by_category works correctly in an integrated environment.
    """
    scenario_id = "tool_registry_get_by_category_001"
    print(f"\nRunning scenario: {scenario_id}")

    web_tools = tool_registry.get_tools_by_category("web")
    assert len(web_tools) == 1
    assert web_tools[0].name == "web_request"
    print(f"Scenario {scenario_id}: Successfully retrieved 'web' category tools.")

    data_analysis_tools = tool_registry.get_tools_by_category("data_analysis")
    expected_data_tool_names = {
        "create_chart_from_plotly_config",
    }
    actual_data_tool_names = {tool.name for tool in data_analysis_tools}
    assert actual_data_tool_names == expected_data_tool_names
    print(
        f"Scenario {scenario_id}: Successfully retrieved 'data_analysis' category tools."
    )

    no_tools = tool_registry.get_tools_by_category("non_existent_category_123")
    assert isinstance(no_tools, list)
    assert len(no_tools) == 0
    print(
        f"Scenario {scenario_id}: Verified that a non-existent category returns an empty list."
    )

    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_peer_tools_are_separate_from_registry():
    """
    Tests that dynamically created PeerAgentTools are not added to the
    BuiltinTool registry.
    """
    scenario_id = "tool_registry_peer_tool_separation_001"
    print(f"\nRunning scenario: {scenario_id}")

    peer_a_tool = tool_registry.get_tool_by_name("peer_TestPeerAgentA")
    assert peer_a_tool is None, "Peer tools should not be in the BuiltinTool registry."

    peer_b_tool = tool_registry.get_tool_by_name("peer_TestPeerAgentB")
    assert peer_b_tool is None, "Peer tools should not be in the BuiltinTool registry."

    print(f"Scenario {scenario_id}: Verified that peer tools are not in the registry.")
    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_registry_clearing(clear_tool_registry_fixture):
    """
    This test verifies that the `clear_tool_registry_fixture` works correctly.
    It explicitly uses the fixture to ensure the registry is empty.
    """
    scenario_id = "tool_registry_clear_fixture_verification_001"
    print(f"\nRunning scenario: {scenario_id}")

    assert (
        len(tool_registry.get_all_tools()) == 0
    ), "Registry should be empty at the start of the test."
    print(f"Scenario {scenario_id}: Confirmed registry is empty initially.")

    async def dummy_impl():
        return "dummy"

    temp_tool = BuiltinTool(
        name="temp_test_tool",
        implementation=dummy_impl,
        description="A temporary tool for testing.",
        parameters=adk_types.Schema(type=adk_types.Type.OBJECT, properties={}),
        category="temp",
    )
    tool_registry.register(temp_tool)
    print(f"Scenario {scenario_id}: Registered a temporary tool.")

    assert tool_registry.get_tool_by_name("temp_test_tool") is not None
    assert len(tool_registry.get_all_tools()) == 1

    print(
        f"Scenario {scenario_id}: Test finished. Fixture will now clear the registry."
    )
    print(f"Scenario {scenario_id}: Completed successfully.")
