"""
Integration test for agent cards API alphabetical sorting.

This test programmatically creates multiple agent cards with display names in
random order, registers them, and verifies the /agentCards endpoint returns
them in alphabetical order.
"""

from a2a.types import AgentCapabilities, AgentCard, AgentExtension, AgentSkill
from fastapi.testclient import TestClient

from solace_agent_mesh.common.agent_registry import AgentRegistry


def test_agent_cards_endpoint_returns_alphabetically_sorted_agents(
    api_client: TestClient,
    api_client_factory,
):
    """
    Test that the /agentCards endpoint returns agents sorted alphabetically by display name.

    This test:
    1. Creates multiple test agents with display names intentionally out of order
    2. Registers them in the agent registry (simulating agent discovery)
    3. Calls the /agentCards API endpoint
    4. Verifies the returned agents are in alphabetical order by display name (case-insensitive)
    """

    # Set up a real AgentRegistry for this test
    agent_registry = AgentRegistry()
    api_client_factory.mock_component.get_agent_registry.return_value = agent_registry

    # Create test agent cards with display names in intentionally weird order
    # Testing various edge cases: mixed case, special chars, numbers, spaces, etc.
    test_agents = [
        {
            "name": "zebra_agent",
            "display_name": "Zebra Agent",  # Should be near end
            "description": "Handles zebra tasks",
        },
        {
            "name": "apple_agent",
            "display_name": "Apple Agent",  # Should be early
            "description": "Handles apple tasks",
        },
        {
            "name": "mango_agent",
            "display_name": "Mango Agent",  # Middle
            "description": "Handles mango tasks",
        },
        {
            "name": "banana_agent",
            "display_name": "banana agent",  # Lowercase - tests case-insensitive
            "description": "Handles banana tasks",
        },
        {
            "name": "number_agent",
            "display_name": "123 Agent",  # Number prefix
            "description": "Handles number tasks",
        },
        {
            "name": "caps_agent",
            "display_name": "ALPHA AGENT",  # All caps - should sort with 'A'
            "description": "Handles alpha tasks",
        },
        {
            "name": "special_agent",
            "display_name": "Café Agent",  # Accented character (é)
            "description": "Handles café tasks",
        },
        {
            "name": "emoji_agent",
            "display_name": "🚀 Rocket Agent",  # Emoji prefix
            "description": "Handles rocket tasks",
        },
        {
            "name": "underscore_agent",
            "display_name": "_Internal Agent",  # Underscore prefix
            "description": "Handles internal tasks",
        },
        {
            "name": "space_agent",
            "display_name": "  Spaces Agent",  # Leading spaces
            "description": "Handles space tasks",
        },
        {
            "name": "hyphen_agent",
            "display_name": "Data-Driven Agent",  # Hyphen in middle
            "description": "Handles data tasks",
        },
        {
            "name": "mixed_agent",
            "display_name": "MiXeD CaSe",  # Mixed case throughout
            "description": "Handles mixed tasks",
        },
        {
            "name": "unicode_agent",
            "display_name": "Ñoño Agent",  # Spanish ñ character
            "description": "Handles unicode tasks",
        },
        {
            "name": "chinese_agent",
            "display_name": "中文 Agent",  # Chinese characters
            "description": "Handles Chinese tasks",
        },
        {
            "name": "paren_agent",
            "display_name": "Beta (v2)",  # Parentheses
            "description": "Handles beta tasks",
        },
        {
            "name": "dot_agent",
            "display_name": "API.Client",  # Dot in middle
            "description": "Handles API tasks",
        },
        {
            "name": "zero_agent",
            "display_name": "000 Zero",  # Leading zeros
            "description": "Handles zero tasks",
        },
        {
            "name": "multi_emoji_agent",
            "display_name": "🎨✨ Creative",  # Multiple emojis
            "description": "Handles creative tasks",
        },
        {
            "name": "ampersand_agent",
            "display_name": "A&B Agent",  # Ampersand
            "description": "Handles A&B tasks",
        },
        {
            "name": "at_agent",
            "display_name": "@Mention Agent",  # @ symbol
            "description": "Handles mention tasks",
        },
    ]

    # Clear any existing agents from registry to ensure clean test
    for agent_name in list(agent_registry._items.keys()):
        agent_registry.remove_agent(agent_name)

    # Register test agents in the registry
    for test_agent in test_agents:
        # Create agent card with display name extension
        extensions = [
            AgentExtension(
                uri="https://solace.com/a2a/extensions/display-name",
                description="Display name for UI",
                params={"display_name": test_agent["display_name"]},
            )
        ]

        capabilities = AgentCapabilities(extensions=extensions)

        agent_card = AgentCard(
            name=test_agent["name"],
            description=test_agent["description"],
            version="1.0.0",
            url="http://localhost:8000",
            capabilities=capabilities,
            default_input_modes=["text/plain"],
            default_output_modes=["text/plain"],
            skills=[
                AgentSkill(
                    id=f"{test_agent['name']}_skill",
                    name=f"{test_agent['display_name']} Skill",
                    description=f"Primary skill for {test_agent['display_name']}",
                    tags=["test"],
                )
            ],
        )

        # Add to registry
        agent_registry.add_or_update_agent(agent_card)

    # Call the /agentCards API endpoint
    response = api_client.get("/api/v1/agentCards")
    assert response.status_code == 200

    agents = response.json()

    # Expected order: alphabetical by display name (case-insensitive)
    # Python's sort() with .lower() will sort in this order
    expected_display_names = [
        "  Spaces Agent",      # Leading spaces (space < alphanumeric)
        "000 Zero",            # Numbers first
        "123 Agent",           # Numbers
        "@Mention Agent",      # @ symbol
        "_Internal Agent",     # Underscore (comes before letters in ASCII)
        "A&B Agent",           # Ampersand
        "ALPHA AGENT",         # 'A' (all caps, case-insensitive)
        "API.Client",          # 'A' with dot
        "Apple Agent",         # 'A'
        "banana agent",        # 'b' (lowercase, case-insensitive)
        "Beta (v2)",           # 'B' with parentheses
        "Café Agent",          # 'C' with accent (é)
        "Data-Driven Agent",   # 'D' with hyphen
        "Mango Agent",         # 'M'
        "MiXeD CaSe",          # 'M' (mixed case)
        "Zebra Agent",         # 'Z'
        "Ñoño Agent",          # 'Ñ' (Spanish - sorts after Z)
        "中文 Agent",          # Chinese characters
        "🎨✨ Creative",       # Emojis (sort after ASCII)
        "🚀 Rocket Agent",     # Emoji
    ]

    # Extract actual agent names from response (in order)
    actual_order = [agent["name"] for agent in agents]

    # Build expected agent internal names in the same order
    expected_order = [
        "space_agent",         # "  Spaces Agent"
        "zero_agent",          # "000 Zero"
        "number_agent",        # "123 Agent"
        "at_agent",            # "@Mention Agent"
        "underscore_agent",    # "_Internal Agent"
        "ampersand_agent",     # "A&B Agent"
        "caps_agent",          # "ALPHA AGENT"
        "dot_agent",           # "API.Client"
        "apple_agent",         # "Apple Agent"
        "banana_agent",        # "banana agent"
        "paren_agent",         # "Beta (v2)"
        "special_agent",       # "Café Agent"
        "hyphen_agent",        # "Data-Driven Agent"
        "mango_agent",         # "Mango Agent"
        "mixed_agent",         # "MiXeD CaSe"
        "zebra_agent",         # "Zebra Agent"
        "unicode_agent",       # "Ñoño Agent"
        "chinese_agent",       # "中文 Agent"
        "multi_emoji_agent",   # "🎨✨ Creative"
        "emoji_agent",         # "🚀 Rocket Agent"
    ]

    # Verify the order matches
    assert actual_order == expected_order, (
        f"Agents are not in expected alphabetical order by display name.\n"
        f"Expected order by display name: {expected_display_names}\n"
        f"Expected internal names: {expected_order}\n"
        f"Actual agent names returned: {actual_order}"
    )

    # Cleanup: remove test agents from registry
    for test_agent in test_agents:
        agent_registry.remove_agent(test_agent["name"])
