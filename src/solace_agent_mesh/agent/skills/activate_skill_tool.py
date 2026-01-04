"""
Built-in tool for activating skills at runtime.

When called, this tool loads the full skill content and any tools
defined in skill.sam.yaml, making them available for the session.
"""

import logging
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext
from google.genai import types as adk_types

from ..tools.tool_definition import BuiltinTool
from ..tools.registry import tool_registry
from .loader import load_full_skill

log = logging.getLogger(__name__)

CATEGORY_NAME = "Skills Management"
CATEGORY_DESCRIPTION = "Tools for managing and activating agent skills."


async def activate_skill(
    skill_name: str,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Activates a skill by loading its full content and tools.

    Once activated, the skill's context is added to the system prompt
    and any tools defined in skill.sam.yaml become available.

    Args:
        skill_name: The name of the skill to activate.
        tool_context: ADK tool context (injected automatically).
        tool_config: Optional tool configuration.

    Returns:
        Dictionary with activation status and skill summary.
    """
    log_id = f"[ActivateSkill:{skill_name}]"

    if not tool_context:
        log.error("%s ToolContext is missing.", log_id)
        return {"status": "error", "message": "ToolContext is missing."}

    try:
        # Get host component
        inv_context = tool_context._invocation_context
        if not inv_context:
            return {"status": "error", "message": "InvocationContext is not available."}

        host_component = getattr(inv_context.agent, "host_component", None)

        if not host_component:
            return {"status": "error", "message": "Host component not available."}

        # Check if skill exists in catalog
        skill_catalog = getattr(host_component, "_skill_catalog", {})
        if skill_name not in skill_catalog:
            available = list(skill_catalog.keys())
            return {
                "status": "error",
                "message": f"Skill '{skill_name}' not found. Available skills: {available}",
            }

        catalog_entry = skill_catalog[skill_name]

        # Get current task context
        a2a_context = tool_context.state.get("a2a_context", {})
        logical_task_id = a2a_context.get("logical_task_id", "unknown")

        with host_component.active_tasks_lock:
            task_context = host_component.active_tasks.get(logical_task_id)

        if not task_context:
            return {"status": "error", "message": "Task context not found."}

        # Check if already activated
        if not hasattr(task_context, "_activated_skills"):
            task_context._activated_skills = {}

        if skill_name in task_context._activated_skills:
            return {
                "status": "already_activated",
                "message": f"Skill '{skill_name}' is already active in this session.",
                "skill_name": skill_name,
            }

        # Load full skill
        log.info("%s Loading full skill content...", log_id)
        activated_skill = load_full_skill(catalog_entry, host_component)

        # Store in task context
        task_context._activated_skills[skill_name] = activated_skill

        log.info(
            "%s Skill activated successfully. Tools loaded: %d",
            log_id,
            len(activated_skill.tools),
        )

        # Build response with skill content preview
        content_preview = activated_skill.full_content
        if len(content_preview) > 1000:
            content_preview = content_preview[:1000] + "\n\n... (content truncated)"

        tool_names = activated_skill.get_tool_names()

        return {
            "status": "success",
            "message": f"Skill '{skill_name}' activated successfully.",
            "skill_name": skill_name,
            "tools_loaded": len(activated_skill.tools),
            "tool_names": tool_names if tool_names else None,
            "skill_instructions": content_preview,
        }

    except Exception as e:
        log.exception("%s Failed to activate skill: %s", log_id, e)
        return {"status": "error", "message": f"Failed to activate skill: {e}"}


# Tool definition
activate_skill_tool_def = BuiltinTool(
    name="activate_skill",
    implementation=activate_skill,
    description=(
        "Activates a skill to gain access to its specialized context and tools. "
        "Use this when you need capabilities from a specific skill listed in the "
        "Available Skills section. Once activated, the skill's instructions are "
        "added to your context and any tools it provides become available."
    ),
    category="skills",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=[],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "skill_name": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The name of the skill to activate.",
            ),
        },
        required=["skill_name"],
    ),
    examples=[
        {
            "input": {"skill_name": "code-review"},
            "output": {
                "status": "success",
                "message": "Skill 'code-review' activated.",
                "tools_loaded": 2,
            },
        }
    ],
)

# Register the tool
tool_registry.register(activate_skill_tool_def)
