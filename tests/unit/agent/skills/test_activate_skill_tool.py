"""
Unit tests for src/solace_agent_mesh/agent/skills/activate_skill_tool.py

Tests the activate_skill builtin tool functionality including:
- Tool registration in the registry
- Error handling for missing context
- Error handling for nonexistent skills
- Successful skill activation
"""

from unittest.mock import Mock, MagicMock, patch
import pytest

from src.solace_agent_mesh.agent.skills.activate_skill_tool import (
    activate_skill,
    activate_skill_tool_def,
    CATEGORY_NAME,
    CATEGORY_DESCRIPTION,
)
from src.solace_agent_mesh.agent.skills.types import SkillCatalogEntry, ActivatedSkill
from src.solace_agent_mesh.agent.tools.registry import tool_registry


class TestActivateSkillToolDefinition:
    """Tests for the activate_skill tool definition"""

    def test_tool_is_registered(self):
        """Test that activate_skill tool is registered in the registry"""
        tool = tool_registry.get_tool_by_name("activate_skill")
        assert tool is not None
        assert tool.name == "activate_skill"

    def test_tool_definition_properties(self):
        """Test that the tool definition has correct properties"""
        assert activate_skill_tool_def.name == "activate_skill"
        assert activate_skill_tool_def.category == "skills"
        assert activate_skill_tool_def.category_name == CATEGORY_NAME
        assert activate_skill_tool_def.category_description == CATEGORY_DESCRIPTION
        assert "skill_name" in str(activate_skill_tool_def.parameters)

    def test_tool_description_mentions_activation(self):
        """Test that tool description explains skill activation"""
        description = activate_skill_tool_def.description
        assert "skill" in description.lower()
        assert "activate" in description.lower() or "access" in description.lower()


class TestActivateSkill:
    """Tests for the activate_skill function"""

    @pytest.mark.asyncio
    async def test_missing_tool_context(self):
        """Test error when tool_context is missing"""
        result = await activate_skill(skill_name="test-skill", tool_context=None)

        assert result["status"] == "error"
        assert "ToolContext is missing" in result["message"]

    @pytest.mark.asyncio
    async def test_missing_invocation_context(self):
        """Test error when invocation context is not available"""
        mock_context = Mock()
        mock_context._invocation_context = None

        result = await activate_skill(skill_name="test-skill", tool_context=mock_context)

        assert result["status"] == "error"
        assert "InvocationContext is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_missing_host_component(self):
        """Test error when host component is not available"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_inv_context.agent = Mock()
        mock_inv_context.agent.host_component = None
        mock_context._invocation_context = mock_inv_context

        result = await activate_skill(skill_name="test-skill", tool_context=mock_context)

        assert result["status"] == "error"
        assert "Host component not available" in result["message"]

    @pytest.mark.asyncio
    async def test_skill_not_found(self):
        """Test error when skill is not in catalog"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_host = Mock()
        mock_host._skill_catalog = {"other-skill": Mock()}
        mock_inv_context.agent.host_component = mock_host
        mock_context._invocation_context = mock_inv_context
        mock_context.state = {}

        result = await activate_skill(
            skill_name="nonexistent-skill", tool_context=mock_context
        )

        assert result["status"] == "error"
        assert "not found" in result["message"]
        assert "other-skill" in str(result["message"])

    @pytest.mark.asyncio
    async def test_skill_already_activated(self):
        """Test response when skill is already activated"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_host = Mock()
        mock_host._skill_catalog = {
            "test-skill": SkillCatalogEntry(
                name="test-skill",
                description="Test skill",
                path="/path",
            )
        }
        mock_host.active_tasks_lock = MagicMock()
        mock_host.active_tasks_lock.__enter__ = Mock()
        mock_host.active_tasks_lock.__exit__ = Mock()

        mock_task_context = Mock()
        mock_task_context._activated_skills = {"test-skill": Mock()}
        mock_host.active_tasks = {"task-123": mock_task_context}

        mock_inv_context.agent.host_component = mock_host
        mock_context._invocation_context = mock_inv_context
        mock_context.state = {"a2a_context": {"logical_task_id": "task-123"}}

        result = await activate_skill(skill_name="test-skill", tool_context=mock_context)

        assert result["status"] == "already_activated"
        assert "already active" in result["message"]

    @pytest.mark.asyncio
    async def test_successful_activation(self, tmp_path):
        """Test successful skill activation"""
        # Create a real skill directory
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: A test skill
---

# Test Skill Instructions

Follow these steps...
""")

        catalog_entry = SkillCatalogEntry(
            name="test-skill",
            description="A test skill",
            path=str(skill_dir),
            has_sam_tools=False,
        )

        mock_context = Mock()
        mock_inv_context = Mock()
        mock_host = Mock()
        mock_host._skill_catalog = {"test-skill": catalog_entry}
        mock_host.active_tasks_lock = MagicMock()
        mock_host.active_tasks_lock.__enter__ = Mock()
        mock_host.active_tasks_lock.__exit__ = Mock()
        mock_host.log_identifier = "[Test]"

        mock_task_context = Mock()
        mock_task_context._activated_skills = {}
        mock_host.active_tasks = {"task-123": mock_task_context}

        mock_inv_context.agent.host_component = mock_host
        mock_context._invocation_context = mock_inv_context
        mock_context.state = {"a2a_context": {"logical_task_id": "task-123"}}

        result = await activate_skill(skill_name="test-skill", tool_context=mock_context)

        assert result["status"] == "success"
        assert result["skill_name"] == "test-skill"
        assert "tools_loaded" in result
        assert "skill_instructions" in result
        assert "# Test Skill Instructions" in result["skill_instructions"]

        # Verify skill was added to task context
        assert "test-skill" in mock_task_context._activated_skills

    @pytest.mark.asyncio
    async def test_activation_stores_skill_in_task_context(self, tmp_path):
        """Test that activation stores the activated skill in task context"""
        skill_dir = tmp_path / "store-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: store-skill
description: Skill to test storage
---

# Instructions
""")

        catalog_entry = SkillCatalogEntry(
            name="store-skill",
            description="Skill to test storage",
            path=str(skill_dir),
        )

        mock_context = Mock()
        mock_inv_context = Mock()
        mock_host = Mock()
        mock_host._skill_catalog = {"store-skill": catalog_entry}
        mock_host.active_tasks_lock = MagicMock()
        mock_host.active_tasks_lock.__enter__ = Mock()
        mock_host.active_tasks_lock.__exit__ = Mock()
        mock_host.log_identifier = "[Test]"

        mock_task_context = Mock()
        mock_task_context._activated_skills = {}
        mock_host.active_tasks = {"task-456": mock_task_context}

        mock_inv_context.agent.host_component = mock_host
        mock_context._invocation_context = mock_inv_context
        mock_context.state = {"a2a_context": {"logical_task_id": "task-456"}}

        await activate_skill(skill_name="store-skill", tool_context=mock_context)

        # Verify the skill was stored
        assert "store-skill" in mock_task_context._activated_skills
        stored_skill = mock_task_context._activated_skills["store-skill"]
        assert isinstance(stored_skill, ActivatedSkill)
        assert stored_skill.name == "store-skill"

    @pytest.mark.asyncio
    async def test_task_context_not_found(self):
        """Test error when task context is not in active_tasks"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_host = Mock()
        mock_host._skill_catalog = {
            "test-skill": SkillCatalogEntry(
                name="test-skill",
                description="Test skill",
                path="/path",
            )
        }
        mock_host.active_tasks_lock = MagicMock()
        mock_host.active_tasks_lock.__enter__ = Mock()
        mock_host.active_tasks_lock.__exit__ = Mock()
        mock_host.active_tasks = {}  # Empty - no task context

        mock_inv_context.agent.host_component = mock_host
        mock_context._invocation_context = mock_inv_context
        mock_context.state = {"a2a_context": {"logical_task_id": "nonexistent-task"}}

        result = await activate_skill(skill_name="test-skill", tool_context=mock_context)

        assert result["status"] == "error"
        assert "Task context not found" in result["message"]

    @pytest.mark.asyncio
    async def test_creates_activated_skills_dict_if_missing(self, tmp_path):
        """Test that _activated_skills dict is created if missing from task context"""
        skill_dir = tmp_path / "new-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: new-skill
description: New skill
---

# New Skill
""")

        catalog_entry = SkillCatalogEntry(
            name="new-skill",
            description="New skill",
            path=str(skill_dir),
        )

        mock_context = Mock()
        mock_inv_context = Mock()
        mock_host = Mock()
        mock_host._skill_catalog = {"new-skill": catalog_entry}
        mock_host.active_tasks_lock = MagicMock()
        mock_host.active_tasks_lock.__enter__ = Mock()
        mock_host.active_tasks_lock.__exit__ = Mock()
        mock_host.log_identifier = "[Test]"

        # Task context WITHOUT _activated_skills attribute
        mock_task_context = Mock(spec=[])  # Empty spec = no attributes
        mock_host.active_tasks = {"task-789": mock_task_context}

        mock_inv_context.agent.host_component = mock_host
        mock_context._invocation_context = mock_inv_context
        mock_context.state = {"a2a_context": {"logical_task_id": "task-789"}}

        result = await activate_skill(skill_name="new-skill", tool_context=mock_context)

        assert result["status"] == "success"
        # Verify the dict was created and skill was stored
        assert hasattr(mock_task_context, "_activated_skills")
        assert "new-skill" in mock_task_context._activated_skills

    @pytest.mark.asyncio
    async def test_long_content_is_truncated(self, tmp_path):
        """Test that skill content over 1000 chars is truncated in response"""
        skill_dir = tmp_path / "long-skill"
        skill_dir.mkdir()

        # Create content that's over 1000 characters
        long_content = "# Long Skill\n\n" + ("This is repeated content. " * 100)
        (skill_dir / "SKILL.md").write_text(f"""---
name: long-skill
description: Skill with long content
---

{long_content}
""")

        catalog_entry = SkillCatalogEntry(
            name="long-skill",
            description="Skill with long content",
            path=str(skill_dir),
        )

        mock_context = Mock()
        mock_inv_context = Mock()
        mock_host = Mock()
        mock_host._skill_catalog = {"long-skill": catalog_entry}
        mock_host.active_tasks_lock = MagicMock()
        mock_host.active_tasks_lock.__enter__ = Mock()
        mock_host.active_tasks_lock.__exit__ = Mock()
        mock_host.log_identifier = "[Test]"

        mock_task_context = Mock()
        mock_task_context._activated_skills = {}
        mock_host.active_tasks = {"task-truncate": mock_task_context}

        mock_inv_context.agent.host_component = mock_host
        mock_context._invocation_context = mock_inv_context
        mock_context.state = {"a2a_context": {"logical_task_id": "task-truncate"}}

        result = await activate_skill(skill_name="long-skill", tool_context=mock_context)

        assert result["status"] == "success"
        assert "... (content truncated)" in result["skill_instructions"]
        # Verify truncated content is around 1000 chars + truncation message
        assert len(result["skill_instructions"]) < 1100
