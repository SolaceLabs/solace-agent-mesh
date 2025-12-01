"""
Prompt enhancer for skill-aware agent prompts.

This module provides utilities to enhance agent prompts with
skill information, implementing the progressive disclosure pattern.
"""

import logging
from typing import Optional, List, Dict, Any

from ..services import SkillService
from ..entities import Skill, SkillType, SkillScope

logger = logging.getLogger(__name__)


class PromptEnhancer:
    """
    Enhances agent prompts with skill information.
    
    This class provides methods to:
    - Add skill summaries to system prompts
    - Format skills for different prompt styles
    - Generate skill-aware instructions
    """
    
    # Default skill section template
    DEFAULT_SKILL_SECTION = """
## Available Skills

You have access to learned skills that can help you complete tasks more effectively.
These skills represent successful patterns from previous task executions.

{skill_list}

### Using Skills

To use a skill:
1. Review the skill summaries above to find relevant skills
2. Call the `skill_read` tool with the skill name to get full details
3. Follow the skill's procedure steps to complete the task

Skills are ranked by relevance and success rate. Prefer using skills with higher success rates.
"""

    # Compact skill section for limited context
    COMPACT_SKILL_SECTION = """
## Skills Available

{skill_list}

Use `skill_read(skill_name)` for full details.
"""

    def __init__(
        self,
        skill_service: SkillService,
        max_skills: int = 10,
        compact_mode: bool = False,
    ):
        """
        Initialize the prompt enhancer.
        
        Args:
            skill_service: The skill service instance
            max_skills: Maximum skills to include
            compact_mode: Use compact formatting
        """
        self.skill_service = skill_service
        self.max_skills = max_skills
        self.compact_mode = compact_mode
    
    def enhance_system_prompt(
        self,
        base_prompt: str,
        agent_name: str,
        user_id: Optional[str] = None,
        task_context: Optional[str] = None,
        include_tool_instructions: bool = True,
    ) -> str:
        """
        Enhance a system prompt with skill information.
        
        Args:
            base_prompt: The base system prompt
            agent_name: The agent name
            user_id: Optional user ID
            task_context: Optional task context for relevance
            include_tool_instructions: Include skill_read tool instructions
            
        Returns:
            Enhanced system prompt
        """
        # Get relevant skills
        skills = self._get_relevant_skills(
            agent_name=agent_name,
            user_id=user_id,
            task_context=task_context,
        )
        
        if not skills:
            return base_prompt
        
        # Format skill section
        skill_section = self._format_skill_section(
            skills=skills,
            include_tool_instructions=include_tool_instructions,
        )
        
        # Append to base prompt
        return f"{base_prompt}\n\n{skill_section}"
    
    def _get_relevant_skills(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
        task_context: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get relevant skills for the context."""
        try:
            return self.skill_service.get_skill_summaries_for_prompt(
                agent_name=agent_name,
                user_id=user_id,
                task_context=task_context,
                limit=self.max_skills,
            )
        except Exception as e:
            logger.warning(f"Failed to get skills: {e}")
            return []
    
    def _format_skill_section(
        self,
        skills: List[Dict[str, Any]],
        include_tool_instructions: bool = True,
    ) -> str:
        """Format the skill section for the prompt."""
        if not skills:
            return ""
        
        # Format skill list
        skill_lines = []
        for skill in skills:
            line = self._format_skill_line(skill)
            skill_lines.append(line)
        
        skill_list = "\n".join(skill_lines)
        
        # Use appropriate template
        if self.compact_mode:
            return self.COMPACT_SKILL_SECTION.format(skill_list=skill_list)
        else:
            section = self.DEFAULT_SKILL_SECTION.format(skill_list=skill_list)
            
            if not include_tool_instructions:
                # Remove tool instructions section
                section = section.split("### Using Skills")[0].strip()
            
            return section
    
    def _format_skill_line(self, skill: Dict[str, Any]) -> str:
        """Format a single skill line."""
        name = skill.get("name", "Unknown")
        description = skill.get("description", "")
        success_rate = skill.get("success_rate")
        skill_type = skill.get("type", "learned")
        scope = skill.get("scope", "global")
        
        # Build the line
        line = f"- **{name}**"
        
        # Add type indicator
        if skill_type == "authored":
            line += " [📝]"  # Authored skill
        
        # Add scope indicator
        if scope == "agent":
            line += " [🤖]"  # Agent-specific
        elif scope == "user":
            line += " [👤]"  # User-specific
        
        # Add description
        if description:
            line += f": {description}"
        
        # Add success rate
        if success_rate is not None:
            line += f" ({int(success_rate * 100)}% success)"
        
        return line
    
    def get_skill_tool_definition(self) -> Dict[str, Any]:
        """
        Get the skill_read tool definition for agent registration.
        
        Returns:
            Tool definition dictionary
        """
        return {
            "name": "skill_read",
            "description": (
                "Read the full details of a learned skill. "
                "Use this to get step-by-step procedures for completing tasks. "
                "Pass either skill_id or skill_name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_id": {
                        "type": "string",
                        "description": "The unique ID of the skill",
                    },
                    "skill_name": {
                        "type": "string",
                        "description": "The name of the skill",
                    },
                },
                "required": [],
            },
        }
    
    def get_skill_search_tool_definition(self) -> Dict[str, Any]:
        """
        Get the skill_search tool definition for agent registration.
        
        Returns:
            Tool definition dictionary
        """
        return {
            "name": "skill_search",
            "description": (
                "Search for skills that match a query. "
                "Use this to find relevant skills for a task."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query describing the task or skill needed",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        }


class TaskContextAnalyzer:
    """
    Analyzes task context to improve skill matching.
    
    This class extracts key information from task descriptions
    to improve skill relevance scoring.
    """
    
    def __init__(self):
        """Initialize the analyzer."""
        self._keyword_patterns = {
            "create": ["create", "make", "build", "generate", "new"],
            "search": ["search", "find", "look", "query", "get"],
            "update": ["update", "modify", "change", "edit", "fix"],
            "delete": ["delete", "remove", "clear", "clean"],
            "analyze": ["analyze", "review", "check", "examine", "inspect"],
            "report": ["report", "summarize", "list", "show", "display"],
        }
    
    def extract_keywords(self, task_description: str) -> List[str]:
        """
        Extract keywords from a task description.
        
        Args:
            task_description: The task description
            
        Returns:
            List of extracted keywords
        """
        if not task_description:
            return []
        
        keywords = []
        task_lower = task_description.lower()
        
        # Check for action patterns
        for action, patterns in self._keyword_patterns.items():
            for pattern in patterns:
                if pattern in task_lower:
                    keywords.append(action)
                    break
        
        # Extract potential tool/service names
        # Look for capitalized words or words with special characters
        words = task_description.split()
        for word in words:
            # Skip common words
            if len(word) < 3:
                continue
            
            # Check for potential names (capitalized, contains special chars)
            if word[0].isupper() or "-" in word or "_" in word:
                keywords.append(word.lower().strip(".,!?"))
        
        return list(set(keywords))
    
    def get_task_category(self, task_description: str) -> Optional[str]:
        """
        Determine the category of a task.
        
        Args:
            task_description: The task description
            
        Returns:
            Task category or None
        """
        if not task_description:
            return None
        
        task_lower = task_description.lower()
        
        # Check for action patterns
        for action, patterns in self._keyword_patterns.items():
            for pattern in patterns:
                if pattern in task_lower:
                    return action
        
        return None