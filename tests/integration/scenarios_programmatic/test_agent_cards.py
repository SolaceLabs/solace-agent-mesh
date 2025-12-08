"""
Programmatic integration tests for agent card discovery and peer tool creation.
"""

import pytest
import asyncio

from solace_agent_mesh.agent.sac.component import SamAgentComponent
from sam_test_infrastructure.llm_server.server import TestLLMServer
from sam_test_infrastructure.gateway_interface.component import (
    TestGatewayComponent,
)
from .test_helpers import (
    prime_llm_server,
    create_gateway_input_data,
    submit_test_input,
    get_all_task_events,
)

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.agent,
    pytest.mark.delegation
]


async def test_agent_discovery_and_peer_tools_for_main_agent(
    main_agent_component: SamAgentComponent,
    test_gateway_app_instance: TestGatewayComponent,
    test_llm_server: TestLLMServer,
):
    """
    Tests that TestAgent discovers its peers and presents the correct peer tools to the LLM.
    """
    scenario_id = "agent_card_discovery_main_agent_001"
    print(f"\nRunning scenario: {scenario_id}")

    discovered_peers = main_agent_component.peer_agents
    assert (
        "TestPeerAgentA" in discovered_peers
    ), "TestAgent should have discovered TestPeerAgentA"
    assert (
        "TestPeerAgentB" in discovered_peers
    ), "TestAgent should have discovered TestPeerAgentB"
    assert (
        "TestPeerAgentC" not in discovered_peers
    ), "TestAgent should NOT have discovered TestPeerAgentC"
    print(f"Scenario {scenario_id}: Verified agent registry contents.")

    prime_llm_server(
        test_llm_server,
        [{"choices": [{"message": {"role": "assistant", "content": "OK"}}]}],
    )

    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="test_user",
        text_parts_content=["hello"],
        scenario_id=scenario_id,
    )
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    await get_all_task_events(test_gateway_app_instance, task_id, overall_timeout=5.0)

    captured_requests = test_llm_server.get_captured_requests()
    assert len(captured_requests) == 1, "Expected exactly one LLM call"
    llm_request = captured_requests[0]

    tool_names = []
    if llm_request.tools:
        for tool_config in llm_request.tools:
            if tool_config.get("function"):
                tool_names.append(tool_config["function"]["name"])

    print(f"Final list of tool names presented to LLM: {tool_names}")

    assert (
        "peer_TestPeerAgentA" in tool_names
    ), "Peer tool for TestPeerAgentA should be presented to LLM"
    assert (
        "peer_TestPeerAgentB" in tool_names
    ), "Peer tool for TestPeerAgentB should be presented to LLM"
    assert (
        "peer_TestPeerAgentC" not in tool_names
    ), "Peer tool for TestPeerAgentC should NOT be presented"
    assert (
        "peer_TestPeerAgentD" not in tool_names
    ), "Peer tool for TestPeerAgentD should NOT be presented"
    print(f"Scenario {scenario_id}: Verified peer tools presented to LLM.")

    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_agent_discovery_for_peer_a(
    peer_a_component: SamAgentComponent,
    test_gateway_app_instance: TestGatewayComponent,
    test_llm_server: TestLLMServer,
):
    """
    Tests that TestPeerAgentA discovers its downstream peer, TestPeerAgentD.
    """
    scenario_id = "agent_card_discovery_peer_a_001"
    print(f"\nRunning scenario: {scenario_id}")

    discovered_peers = peer_a_component.peer_agents
    assert (
        "TestPeerAgentD" in discovered_peers
    ), "TestPeerAgentA should have discovered TestPeerAgentD"
    print(f"Scenario {scenario_id}: Verified agent registry contents.")

    prime_llm_server(
        test_llm_server,
        [{"choices": [{"message": {"role": "assistant", "content": "OK"}}]}],
    )
    test_input_data = create_gateway_input_data(
        target_agent="TestPeerAgentA",
        user_identity="test_user",
        text_parts_content=["hello"],
        scenario_id=scenario_id,
    )
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    await get_all_task_events(test_gateway_app_instance, task_id, overall_timeout=5.0)

    captured_requests = test_llm_server.get_captured_requests()
    assert len(captured_requests) == 1
    llm_request = captured_requests[0]

    tool_names = []
    if llm_request.tools:
        for tool_config in llm_request.tools:
            if tool_config.get("function"):
                tool_names.append(tool_config["function"]["name"])

    assert (
        "peer_TestPeerAgentD" in tool_names
    ), "Peer tool for TestPeerAgentD should be presented to LLM"
    print(f"Scenario {scenario_id}: Verified peer tools presented to LLM.")

    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_peer_tool_description_matches_agent_card(
    main_agent_component: SamAgentComponent,
    test_gateway_app_instance: TestGatewayComponent,
    test_llm_server: TestLLMServer,
):
    """
    Tests that the description of a dynamically created PeerAgentTool matches
    the description from the discovered peer's AgentCard.
    """
    scenario_id = "peer_tool_description_match_001"
    print(f"\nRunning scenario: {scenario_id}")

    peer_b_card = main_agent_component.peer_agents.get("TestPeerAgentB")
    assert peer_b_card is not None, "TestPeerAgentB card not found in registry"
    expected_description = peer_b_card.description
    assert expected_description, "AgentCard for TestPeerAgentB must have a description"

    prime_llm_server(
        test_llm_server,
        [{"choices": [{"message": {"role": "assistant", "content": "OK"}}]}],
    )
    test_input_data = create_gateway_input_data(
        target_agent="TestAgent",
        user_identity="test_user",
        text_parts_content=["hello"],
        scenario_id=scenario_id,
    )
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )
    await get_all_task_events(test_gateway_app_instance, task_id, overall_timeout=5.0)

    captured_requests = test_llm_server.get_captured_requests()
    assert len(captured_requests) == 1
    llm_request = captured_requests[0]

    peer_b_declaration = None
    if llm_request.tools:
        for tool_config in llm_request.tools:
            if (
                tool_config.get("function")
                and tool_config.get("function", {}).get("name") == "peer_TestPeerAgentB"
            ):
                peer_b_declaration = tool_config["function"]
                break

    assert (
        peer_b_declaration is not None
    ), "Declaration for peer_TestPeerAgentB not found in LLM request"

    actual_description = peer_b_declaration["description"]
    # With enhanced descriptions, the tool description includes the base description
    # and may include a Skills section if the agent has skills
    assert (
        expected_description in actual_description
    ), f"Tool description does not contain expected base description. Expected '{expected_description}' to be in '{actual_description}'"

    # The description should either have skills listed, or just be the base description
    has_skills_section = "**Skills:**" in actual_description
    is_base_only = actual_description.strip() == expected_description.strip()

    assert (
        has_skills_section or is_base_only
    ), f"Tool description should include Skills section if agent has skills, or just base description. Got: '{actual_description}'"
    print(f"Scenario {scenario_id}: Verified tool description contains base description{' and skills' if has_skills_section else ''}.")

    print(f"Scenario {scenario_id}: Completed successfully.")
