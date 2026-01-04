"""
Integration tests for the SAM Skills system.

Tests the full skill loading and activation flow including:
- Skill catalog loading at startup
- activate_skill tool registration
- Dynamic tool injection after skill activation
- Skill instructions injection into system prompt
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest

from solace_agent_mesh.agent.skills import (
    scan_skill_directories,
    load_full_skill,
    generate_skill_catalog_instructions,
    SkillCatalogEntry,
    ActivatedSkill,
)
from solace_agent_mesh.agent.skills.activate_skill_tool import activate_skill
from solace_agent_mesh.agent.tools.registry import tool_registry


pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.agent,
    pytest.mark.skills,
]


@pytest.fixture
def skill_directory(tmp_path):
    """Creates a temporary skill directory with test skills."""
    skills_root = tmp_path / "skills"
    skills_root.mkdir()

    # Create skill without tools
    basic_skill = skills_root / "basic-skill"
    basic_skill.mkdir()
    (basic_skill / "SKILL.md").write_text("""---
name: basic-skill
description: A basic skill without tools for testing
---

# Basic Skill

## Instructions

1. Do step one
2. Do step two
3. Complete the task

## Reference

This is reference material for the skill.
""")

    # Create skill with tools
    tool_skill = skills_root / "tool-skill"
    tool_skill.mkdir()
    (tool_skill / "SKILL.md").write_text("""---
name: tool-skill
description: A skill with custom tools
allowed-tools: custom_tool
---

# Tool Skill

Use the custom_tool to perform operations.
""")
    (tool_skill / "skill.sam.yaml").write_text("""
tools:
  - tool_type: python
    component_module: tests.integration.test_support.tools
    function_name: echo_tool
    name: custom_tool
    description: A custom tool from the skill
    parameters:
      properties:
        message:
          type: string
          description: The message to echo
      required:
        - message
""")

    return skills_root


async def test_activate_skill_tool_is_registered():
    """
    Tests that the activate_skill tool is properly registered in the tool registry.
    """
    scenario_id = "skills_tool_registration_001"
    print(f"\nRunning scenario: {scenario_id}")

    tool = tool_registry.get_tool_by_name("activate_skill")

    assert tool is not None, "activate_skill tool should be registered"
    assert tool.name == "activate_skill"
    assert tool.category == "skills"
    assert "skill_name" in str(tool.parameters)

    print(f"Scenario {scenario_id}: Verified activate_skill tool is registered.")
    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_skill_catalog_loading(skill_directory):
    """
    Tests that skills are properly discovered and loaded into the catalog.
    """
    scenario_id = "skills_catalog_loading_001"
    print(f"\nRunning scenario: {scenario_id}")

    catalog = scan_skill_directories([str(skill_directory)])

    assert len(catalog) == 2, "Should find 2 skills"
    assert "basic-skill" in catalog
    assert "tool-skill" in catalog

    # Verify basic skill metadata
    basic = catalog["basic-skill"]
    assert basic.name == "basic-skill"
    assert "basic skill without tools" in basic.description.lower()
    assert basic.has_sam_tools is False

    # Verify tool skill metadata
    tool = catalog["tool-skill"]
    assert tool.name == "tool-skill"
    assert tool.has_sam_tools is True
    assert tool.allowed_tools == ["custom_tool"]

    print(f"Scenario {scenario_id}: Verified skill catalog loading.")
    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_full_skill_loading(skill_directory):
    """
    Tests loading the full content of a skill (after activation).
    """
    scenario_id = "skills_full_loading_001"
    print(f"\nRunning scenario: {scenario_id}")

    # First scan to get catalog entry
    catalog = scan_skill_directories([str(skill_directory)])
    basic_entry = catalog["basic-skill"]

    # Mock the component (not needed for basic skill without tools)
    mock_component = Mock()
    mock_component.log_identifier = "[Test]"

    # Load full skill
    activated = load_full_skill(basic_entry, mock_component)

    assert isinstance(activated, ActivatedSkill)
    assert activated.name == "basic-skill"
    assert "# Basic Skill" in activated.full_content
    assert "Do step one" in activated.full_content
    assert len(activated.tools) == 0  # No tools for basic skill

    print(f"Scenario {scenario_id}: Verified full skill loading.")
    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_skill_catalog_instructions_generation(skill_directory):
    """
    Tests that skill catalog instructions are properly generated for injection.
    """
    scenario_id = "skills_instructions_generation_001"
    print(f"\nRunning scenario: {scenario_id}")

    catalog = scan_skill_directories([str(skill_directory)])
    instructions = generate_skill_catalog_instructions(catalog)

    # Verify instructions contain activation guidance
    assert "## Available Skills" in instructions
    assert "activate_skill" in instructions

    # Verify all skills are listed
    assert "basic-skill" in instructions
    assert "tool-skill" in instructions

    # Verify descriptions are included
    assert "basic skill without tools" in instructions.lower()
    assert "skill with custom tools" in instructions.lower()

    print(f"Scenario {scenario_id}: Verified skill catalog instructions generation.")
    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_skill_activation_flow(skill_directory):
    """
    Tests the complete skill activation flow via the activate_skill tool.
    """
    scenario_id = "skills_activation_flow_001"
    print(f"\nRunning scenario: {scenario_id}")

    # Set up catalog
    catalog = scan_skill_directories([str(skill_directory)])
    basic_entry = catalog["basic-skill"]

    # Create mock context structure
    mock_context = Mock()
    mock_inv_context = Mock()
    mock_host = Mock()
    mock_host._skill_catalog = catalog
    mock_host.active_tasks_lock = MagicMock()
    mock_host.active_tasks_lock.__enter__ = Mock()
    mock_host.active_tasks_lock.__exit__ = Mock()
    mock_host.log_identifier = "[Test]"

    # Create task context with empty activated skills
    mock_task_context = Mock()
    mock_task_context._activated_skills = {}
    mock_host.active_tasks = {"test-task-id": mock_task_context}

    mock_inv_context.agent.host_component = mock_host
    mock_context._invocation_context = mock_inv_context
    mock_context.state = {"a2a_context": {"logical_task_id": "test-task-id"}}

    # Verify skill is not activated before
    assert len(mock_task_context._activated_skills) == 0

    # Activate the skill
    result = await activate_skill(skill_name="basic-skill", tool_context=mock_context)

    assert result["status"] == "success"
    assert result["skill_name"] == "basic-skill"
    assert "# Basic Skill" in result["skill_instructions"]

    # Verify skill is now in activated skills
    assert "basic-skill" in mock_task_context._activated_skills
    activated = mock_task_context._activated_skills["basic-skill"]
    assert isinstance(activated, ActivatedSkill)
    assert "Do step one" in activated.full_content

    print(f"Scenario {scenario_id}: Verified skill activation flow.")
    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_skill_already_activated_returns_status(skill_directory):
    """
    Tests that activating an already-activated skill returns appropriate status.
    """
    scenario_id = "skills_already_activated_001"
    print(f"\nRunning scenario: {scenario_id}")

    catalog = scan_skill_directories([str(skill_directory)])

    mock_context = Mock()
    mock_inv_context = Mock()
    mock_host = Mock()
    mock_host._skill_catalog = catalog
    mock_host.active_tasks_lock = MagicMock()
    mock_host.active_tasks_lock.__enter__ = Mock()
    mock_host.active_tasks_lock.__exit__ = Mock()
    mock_host.log_identifier = "[Test]"

    # Pre-populate with activated skill
    mock_task_context = Mock()
    mock_task_context._activated_skills = {
        "basic-skill": ActivatedSkill(
            name="basic-skill",
            description="Already activated",
            path="/path",
            full_content="Content",
        )
    }
    mock_host.active_tasks = {"test-task": mock_task_context}

    mock_inv_context.agent.host_component = mock_host
    mock_context._invocation_context = mock_inv_context
    mock_context.state = {"a2a_context": {"logical_task_id": "test-task"}}

    # Try to activate again
    result = await activate_skill(skill_name="basic-skill", tool_context=mock_context)

    assert result["status"] == "already_activated"
    assert "already active" in result["message"]

    print(f"Scenario {scenario_id}: Verified already-activated handling.")
    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_nonexistent_skill_returns_error(skill_directory):
    """
    Tests that trying to activate a nonexistent skill returns an error.
    """
    scenario_id = "skills_nonexistent_error_001"
    print(f"\nRunning scenario: {scenario_id}")

    catalog = scan_skill_directories([str(skill_directory)])

    mock_context = Mock()
    mock_inv_context = Mock()
    mock_host = Mock()
    mock_host._skill_catalog = catalog
    mock_host.log_identifier = "[Test]"

    mock_inv_context.agent.host_component = mock_host
    mock_context._invocation_context = mock_inv_context
    mock_context.state = {}

    result = await activate_skill(
        skill_name="nonexistent-skill", tool_context=mock_context
    )

    assert result["status"] == "error"
    assert "not found" in result["message"]
    # Should list available skills
    assert "basic-skill" in str(result["message"]) or "tool-skill" in str(
        result["message"]
    )

    print(f"Scenario {scenario_id}: Verified nonexistent skill error handling.")
    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_skill_catalog_empty_without_config():
    """
    Tests that skill catalog is empty when no paths are configured.
    """
    scenario_id = "skills_empty_catalog_001"
    print(f"\nRunning scenario: {scenario_id}")

    catalog = scan_skill_directories([])

    assert len(catalog) == 0

    instructions = generate_skill_catalog_instructions(catalog)
    assert instructions == ""

    print(f"Scenario {scenario_id}: Verified empty catalog handling.")
    print(f"Scenario {scenario_id}: Completed successfully.")
