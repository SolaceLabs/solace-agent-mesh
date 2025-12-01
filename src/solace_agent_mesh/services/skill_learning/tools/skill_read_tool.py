"""
Skill read tool for progressive disclosure.

This tool allows agents to read full skill details on demand,
implementing Level 2 of the progressive disclosure pattern:

Level 1: Skill summaries injected into system prompt
Level 2: Full skill details retrieved via skill_read tool

This approach:
- Keeps system prompts concise
- Allows agents to get details only when needed
- Reduces token usage
"""

import logging
from typing import Optional, Dict, Any, List, Callable

from ..entities import Skill, SkillType
from ..services import SkillService

logger = logging.getLogger(__name__)


class SkillReadTool:
    """
    Tool for reading full skill details.
    
    This tool is registered with agents to allow them to
    retrieve complete skill information when needed.
    """
    
    # Tool definition for agent registration
    TOOL_NAME = "skill_read"
    TOOL_DESCRIPTION = """Read full details of a skill by ID or name.

Use this tool when you see a relevant skill in your available skills list
and need the complete procedure/steps to follow.

Parameters:
- skill_id: The skill ID (from the skills list)
- skill_name: Alternative - the skill name (if ID not available)

Returns the full skill details including:
- Complete description
- Step-by-step procedure
- Involved agents and tools
- Success rate and usage statistics
"""
    
    TOOL_PARAMETERS = {
        "type": "object",
        "properties": {
            "skill_id": {
                "type": "string",
                "description": "The skill ID to read"
            },
            "skill_name": {
                "type": "string",
                "description": "The skill name to read (alternative to skill_id)"
            }
        },
        "oneOf": [
            {"required": ["skill_id"]},
            {"required": ["skill_name"]}
        ]
    }
    
    def __init__(
        self,
        skill_service: SkillService,
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
        record_usage: bool = True,
    ):
        """
        Initialize the skill read tool.
        
        Args:
            skill_service: Skill service for operations
            agent_name: Agent using this tool
            user_id: User context
            record_usage: Whether to record skill usage
        """
        self.skill_service = skill_service
        self.agent_name = agent_name
        self.user_id = user_id
        self.record_usage = record_usage
    
    def execute(
        self,
        skill_id: Optional[str] = None,
        skill_name: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute the skill read tool.
        
        Args:
            skill_id: The skill ID to read
            skill_name: The skill name to read
            task_id: Optional task ID for usage tracking
            
        Returns:
            Full skill details or error message
        """
        if not skill_id and not skill_name:
            return {
                "error": "Either skill_id or skill_name is required"
            }
        
        # Get the skill
        skill = None
        if skill_id:
            skill = self.skill_service.get_skill(skill_id)
        elif skill_name:
            skill = self.skill_service.get_skill_by_name(skill_name)
        
        if not skill:
            return {
                "error": f"Skill not found: {skill_id or skill_name}"
            }
        
        # Record usage if enabled
        if self.record_usage and self.agent_name and task_id:
            try:
                self.skill_service.record_usage(
                    skill_id=skill.id,
                    task_id=task_id,
                    agent_name=self.agent_name,
                    user_id=self.user_id,
                )
            except Exception as e:
                logger.warning(f"Failed to record skill usage: {e}")
        
        # Return full skill details
        return self._format_skill_response(skill)
    
    def _format_skill_response(self, skill: Skill) -> Dict[str, Any]:
        """Format skill for response."""
        response = {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "type": skill.type,
            "scope": skill.scope,
        }
        
        # Add summary if available
        if skill.summary:
            response["summary"] = skill.summary
        
        # Add content based on skill type
        if skill.type == SkillType.AUTHORED and skill.markdown_content:
            response["content"] = skill.markdown_content
        elif skill.type == SkillType.LEARNED and skill.tool_steps:
            response["steps"] = [
                {
                    "sequence": step.sequence_number,
                    "action": step.action,
                    "agent": step.agent_name,
                    "tool": step.tool_name,
                    "type": step.step_type,
                }
                for step in skill.tool_steps
            ]
        
        # Add agent chain if available
        if skill.agent_chain:
            response["agent_chain"] = [
                {
                    "agent": node.agent_name,
                    "role": node.role,
                    "tools": node.tools_used,
                    "delegates_to": node.delegated_to,
                }
                for node in skill.agent_chain
            ]
        
        # Add involved agents
        if skill.involved_agents:
            response["involved_agents"] = skill.involved_agents
        
        # Add metrics
        success_rate = skill.get_success_rate()
        if success_rate is not None:
            response["success_rate"] = f"{success_rate * 100:.0f}%"
            response["total_uses"] = skill.success_count + skill.failure_count
        
        return response
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """
        Get the tool definition for agent registration.
        
        Returns:
            Tool definition dictionary
        """
        return {
            "name": self.TOOL_NAME,
            "description": self.TOOL_DESCRIPTION,
            "parameters": self.TOOL_PARAMETERS,
        }
    
    def __call__(self, **kwargs) -> Dict[str, Any]:
        """Allow calling the tool directly."""
        return self.execute(**kwargs)


def create_skill_read_tool(
    skill_service: SkillService,
    agent_name: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a skill read tool configuration for agent registration.
    
    This function creates the tool definition and handler that can
    be registered with an agent's tool registry.
    
    Args:
        skill_service: Skill service for operations
        agent_name: Agent using this tool
        user_id: User context
        
    Returns:
        Dictionary with tool definition and handler
    """
    tool = SkillReadTool(
        skill_service=skill_service,
        agent_name=agent_name,
        user_id=user_id,
    )
    
    return {
        "definition": tool.get_tool_definition(),
        "handler": tool.execute,
    }


class SkillSearchTool:
    """
    Tool for searching skills.
    
    This tool allows agents to search for skills beyond
    what's in their system prompt.
    """
    
    TOOL_NAME = "skill_search"
    TOOL_DESCRIPTION = """Search for skills that might help with a task.

Use this tool when you need to find skills related to a specific topic
or task that might not be in your initial skills list.

Parameters:
- query: Search query describing what you're looking for
- limit: Maximum number of results (default: 5)

Returns a list of matching skills with summaries.
"""
    
    TOOL_PARAMETERS = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results",
                "default": 5
            }
        },
        "required": ["query"]
    }
    
    def __init__(
        self,
        skill_service: SkillService,
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """Initialize the skill search tool."""
        self.skill_service = skill_service
        self.agent_name = agent_name
        self.user_id = user_id
    
    def execute(
        self,
        query: str,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Execute the skill search tool.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            Search results
        """
        results = self.skill_service.search_skills(
            query=query,
            agent_name=self.agent_name,
            user_id=self.user_id,
            limit=limit,
        )
        
        skills = [
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "type": skill.type,
                "relevance_score": f"{score * 100:.0f}%",
            }
            for skill, score in results
        ]
        
        return {
            "query": query,
            "results": skills,
            "count": len(skills),
        }
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for agent registration."""
        return {
            "name": self.TOOL_NAME,
            "description": self.TOOL_DESCRIPTION,
            "parameters": self.TOOL_PARAMETERS,
        }
    
    def __call__(self, **kwargs) -> Dict[str, Any]:
        """Allow calling the tool directly."""
        return self.execute(**kwargs)