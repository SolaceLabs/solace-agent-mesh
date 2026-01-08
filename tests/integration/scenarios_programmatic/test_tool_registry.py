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
