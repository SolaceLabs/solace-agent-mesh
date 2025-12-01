"""
Skill-related tools for SAM agents.

This module provides tools for agents to interact with the skill learning system:
- skill_read: Read detailed skill procedures
- skill_search: Search for relevant skills
"""

import logging
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext
from google.genai import types as adk_types

from .tool_definition import BuiltinTool
from .registry import tool_registry

logger = logging.getLogger(__name__)

CATEGORY_NAME = "Skill Learning"
CATEGORY_DESCRIPTION = "Tools for accessing learned skills and procedures from successful task executions."


async def skill_read(
    skill_name: str,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Read detailed procedure for a learned skill.
    
    This tool retrieves the full procedure, steps, and guidance for a skill
    that was previously learned from successful task executions.
    
    Args:
        skill_name: The name of the skill to read
        tool_context: The ADK tool context
        
    Returns:
        Dictionary containing:
        - name: Skill name
        - description: Skill description
        - procedure: Full procedure text
        - steps: List of procedure steps
        - tools_used: Tools required for this skill
        - success_criteria: How to know if the skill succeeded
        - examples: Example inputs/outputs
    """
    log_identifier = "[Tool:skill_read]"
    logger.debug("%s Reading skill: %s", log_identifier, skill_name)
    
    try:
        # Get the host component from the invocation context
        invocation_context = tool_context._invocation_context
        if not invocation_context:
            return {
                "status": "error",
                "error": "No invocation context available",
            }
        
        # Try to get the skill injector from the host component
        # The host component is attached to the agent
        agent = invocation_context.agent
        if not agent or not hasattr(agent, "host_component"):
            return {
                "status": "error",
                "error": "Skill learning not available in this context",
            }
        
        host_component = agent.host_component
        
        # Check if skill learning is enabled
        skill_config = host_component.get_config("skill_learning", {})
        if not skill_config.get("enabled", False):
            return {
                "status": "error",
                "error": "Skill learning is not enabled",
            }
        
        # Get the skill injector
        if not hasattr(host_component, "_skill_injector") or not host_component._skill_injector:
            return {
                "status": "error",
                "error": "Skill learning service not initialized",
            }
        
        injector = host_component._skill_injector
        skill_service = injector.skill_service
        
        # Get agent context
        a2a_context = tool_context.state.get("a2a_context", {})
        user_id = a2a_context.get("user_id")
        agent_name = host_component.get_config("agent_name")
        task_id = a2a_context.get("logical_task_id")
        
        # Search for the skill by name
        skills = skill_service.search_skills(
            query=skill_name,
            agent_name=agent_name,
            user_id=user_id,
            limit=1,
        )
        
        if not skills:
            return {
                "status": "not_found",
                "error": f"No skill found with name: {skill_name}",
                "suggestion": "Try using a different skill name or check the Available Skills section.",
            }
        
        skill = skills[0]
        
        # Track skill usage
        if task_id:
            injector._track_skill_usage(task_id, skill.id)
        
        # Format the response
        result = {
            "status": "success",
            "name": skill.name,
            "description": skill.description,
            "procedure": skill.procedure,
        }
        
        # Add steps if available
        if skill.steps:
            result["steps"] = [
                {
                    "order": step.order,
                    "action": step.action,
                    "tool": step.tool_name,
                    "parameters": step.parameters,
                    "expected_output": step.expected_output,
                }
                for step in skill.steps
            ]
        
        # Add tools used
        if skill.tools_used:
            result["tools_used"] = skill.tools_used
        
        # Add success criteria
        if skill.success_criteria:
            result["success_criteria"] = skill.success_criteria
        
        # Add examples if available
        if skill.examples:
            result["examples"] = skill.examples
        
        # Add metadata
        result["metadata"] = {
            "type": skill.skill_type.value if skill.skill_type else "learned",
            "success_rate": f"{skill.success_rate:.1%}" if skill.success_rate else None,
            "usage_count": skill.usage_count,
        }
        
        logger.info(
            "%s Successfully read skill: %s (id=%s)",
            log_identifier,
            skill_name,
            skill.id,
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "%s Error reading skill %s: %s",
            log_identifier,
            skill_name,
            e,
        )
        return {
            "status": "error",
            "error": f"Failed to read skill: {str(e)}",
        }


async def skill_search(
    query: str,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Search for skills matching a query.
    
    This tool searches for skills that match the given query using
    semantic similarity and keyword matching.
    
    Args:
        query: Search query describing the task or skill needed
        tool_context: The ADK tool context
        limit: Maximum number of results to return
        
    Returns:
        Dictionary containing:
        - skills: List of matching skills with summaries
        - total: Total number of matches
    """
    log_identifier = "[Tool:skill_search]"
    logger.debug("%s Searching skills: %s", log_identifier, query)
    
    try:
        # Get the host component from the invocation context
        invocation_context = tool_context._invocation_context
        if not invocation_context:
            return {
                "status": "error",
                "error": "No invocation context available",
            }
        
        agent = invocation_context.agent
        if not agent or not hasattr(agent, "host_component"):
            return {
                "status": "error",
                "error": "Skill learning not available in this context",
            }
        
        host_component = agent.host_component
        
        # Check if skill learning is enabled
        skill_config = host_component.get_config("skill_learning", {})
        if not skill_config.get("enabled", False):
            return {
                "status": "error",
                "error": "Skill learning is not enabled",
            }
        
        # Get the skill injector
        if not hasattr(host_component, "_skill_injector") or not host_component._skill_injector:
            return {
                "status": "error",
                "error": "Skill learning service not initialized",
            }
        
        injector = host_component._skill_injector
        skill_service = injector.skill_service
        
        # Get agent context
        a2a_context = tool_context.state.get("a2a_context", {})
        user_id = a2a_context.get("user_id")
        agent_name = host_component.get_config("agent_name")
        
        # Search for skills
        skills = skill_service.search_skills(
            query=query,
            agent_name=agent_name,
            user_id=user_id,
            limit=limit,
        )
        
        if not skills:
            return {
                "status": "success",
                "skills": [],
                "total": 0,
                "message": "No skills found matching your query.",
            }
        
        # Format results
        skill_summaries = []
        for skill in skills:
            summary = {
                "name": skill.name,
                "description": skill.description,
                "type": skill.skill_type.value if skill.skill_type else "learned",
            }
            
            if skill.success_rate:
                summary["success_rate"] = f"{skill.success_rate:.1%}"
            
            if skill.tools_used:
                summary["tools"] = skill.tools_used[:3]  # First 3 tools
            
            skill_summaries.append(summary)
        
        logger.info(
            "%s Found %d skills for query: %s",
            log_identifier,
            len(skills),
            query,
        )
        
        return {
            "status": "success",
            "skills": skill_summaries,
            "total": len(skills),
            "hint": "Use skill_read(skill_name) to get the full procedure for a skill.",
        }
        
    except Exception as e:
        logger.error(
            "%s Error searching skills: %s",
            log_identifier,
            e,
        )
        return {
            "status": "error",
            "error": f"Failed to search skills: {str(e)}",
        }


# Tool definitions
skill_read_tool_def = BuiltinTool(
    name="skill_read",
    implementation=skill_read,
    description=(
        "Read the detailed procedure for a learned skill. Use this tool when you see a skill "
        "mentioned in the 'Available Skills' section and need the full step-by-step procedure "
        "to accomplish a task. The skill provides proven steps that have worked successfully "
        "in similar situations."
    ),
    category="skill_learning",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:skill:read"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "skill_name": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The name of the skill to read (from the Available Skills section)",
            ),
        },
        required=["skill_name"],
    ),
    examples=[],
)

skill_search_tool_def = BuiltinTool(
    name="skill_search",
    implementation=skill_search,
    description=(
        "Search for skills that match a query. Use this tool to find relevant skills "
        "when you're not sure which skill to use or want to explore available procedures "
        "for a type of task. Returns skill summaries - use skill_read to get full details."
    ),
    category="skill_learning",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:skill:read"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "query": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Search query describing the task or skill you're looking for",
            ),
            "limit": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="Maximum number of results to return (default: 5)",
            ),
        },
        required=["query"],
    ),
    examples=[],
)

# Register tools with the registry
tool_registry.register(skill_read_tool_def)
tool_registry.register(skill_search_tool_def)