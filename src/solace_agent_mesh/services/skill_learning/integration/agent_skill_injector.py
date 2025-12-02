"""
Agent skill injector for integrating skills into agent execution.

This module provides the integration point between the skill learning
system and the agent execution pipeline. It:
- Injects relevant skill summaries into agent system prompts
- Registers the skill_read tool with agents
- Tracks skill usage during task execution
"""

import logging
from typing import Optional, List, Dict, Any, Callable, Union, Protocol, runtime_checkable

from ..tools import SkillReadTool, create_skill_read_tool

logger = logging.getLogger(__name__)


@runtime_checkable
class SkillServiceProtocol(Protocol):
    """Protocol for skill services that can be used with AgentSkillInjector."""
    
    def get_skill_summaries_for_prompt(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
        task_context: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get skill summaries for prompt injection."""
        ...
    
    def get_skill(self, skill_id: str) -> Optional[Any]:
        """Get a skill by ID."""
        ...
    
    def get_skill_by_name(
        self,
        name: str,
        agent_name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Any]:
        """Get a skill by name."""
        ...


class AgentSkillInjector:
    """
    Integrates skill learning with agent execution.
    
    This class provides methods to:
    - Get skill summaries for system prompt injection
    - Create skill_read tool instances for agents
    - Track which skills are used during execution
    
    Works with both SkillService (legacy) and VersionedSkillService.
    """
    
    def __init__(
        self,
        skill_service: SkillServiceProtocol,
        max_skills_in_prompt: int = 10,
        enable_skill_tools: bool = True,
    ):
        """
        Initialize the agent skill injector.
        
        Args:
            skill_service: The skill service instance (SkillService or VersionedSkillService)
            max_skills_in_prompt: Maximum skills to inject in prompt
            enable_skill_tools: Whether to enable skill_read tool
        """
        self.skill_service = skill_service
        self.max_skills_in_prompt = max_skills_in_prompt
        self.enable_skill_tools = enable_skill_tools
        
        # Track skill usage per task
        self._task_skill_usage: Dict[str, List[str]] = {}
    
    def get_skills_for_prompt(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
        task_context: Optional[str] = None,
    ) -> str:
        """
        Get skill summaries formatted for system prompt injection.
        
        This implements Level 1 of progressive disclosure - brief
        summaries that help the agent know what skills are available.
        
        Args:
            agent_name: The agent name
            user_id: Optional user ID
            task_context: Optional task context for relevance filtering
            
        Returns:
            Formatted string for system prompt injection
        """
        try:
            summaries = self.skill_service.get_skill_summaries_for_prompt(
                agent_name=agent_name,
                user_id=user_id,
                task_context=task_context,
                limit=self.max_skills_in_prompt,
            )
            
            if not summaries:
                return ""
            
            return self._format_skills_for_prompt(summaries)
            
        except Exception as e:
            logger.warning(f"Failed to get skills for prompt: {e}")
            return ""
    
    def _format_skills_for_prompt(
        self,
        summaries: List[Dict[str, Any]],
    ) -> str:
        """Format skill summaries for system prompt."""
        if not summaries:
            return ""
        
        lines = [
            "",
            "## Available Skills",
            "",
            "You have access to the following learned skills. Use the `skill_read` tool to get full details when needed.",
            "",
        ]
        
        for skill in summaries:
            skill_line = f"- **{skill['name']}**: {skill['description']}"
            
            # Add success rate if available
            if skill.get('success_rate'):
                skill_line += f" (Success: {skill['success_rate']})"
            
            lines.append(skill_line)
        
        lines.append("")
        lines.append("To use a skill, call `skill_read` with the skill name to get the full procedure.")
        lines.append("")
        
        return "\n".join(lines)
    
    def create_skill_tools(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Create skill-related tools for an agent.
        
        Returns tool definitions that can be registered with the agent.
        
        Args:
            agent_name: The agent name
            user_id: Optional user ID
            
        Returns:
            List of tool definitions
        """
        if not self.enable_skill_tools:
            return []
        
        tools = []
        
        # Create skill_read tool
        skill_read = create_skill_read_tool(
            skill_service=self.skill_service,
            agent_name=agent_name,
            user_id=user_id,
        )
        tools.append(skill_read)
        
        return tools
    
    def get_skill_read_handler(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Callable:
        """
        Get a skill_read tool handler for an agent.
        
        Args:
            agent_name: The agent name
            user_id: Optional user ID
            task_id: Optional task ID for usage tracking
            
        Returns:
            Callable handler for the skill_read tool
        """
        tool = SkillReadTool(
            skill_service=self.skill_service,
            agent_name=agent_name,
            user_id=user_id,
            record_usage=True,
        )
        
        def handler(skill_id: Optional[str] = None, skill_name: Optional[str] = None):
            result = tool.execute(
                skill_id=skill_id,
                skill_name=skill_name,
                task_id=task_id,
            )
            
            # Track usage
            if task_id and not result.get("error"):
                self._track_skill_usage(task_id, result.get("id", skill_id or skill_name))
            
            return result
        
        return handler
    
    def _track_skill_usage(self, task_id: str, skill_id: str) -> None:
        """Track skill usage for a task."""
        if task_id not in self._task_skill_usage:
            self._task_skill_usage[task_id] = []
        
        if skill_id not in self._task_skill_usage[task_id]:
            self._task_skill_usage[task_id].append(skill_id)
    
    def get_skills_used_in_task(self, task_id: str) -> List[str]:
        """
        Get skills used in a task.
        
        Args:
            task_id: The task ID
            
        Returns:
            List of skill IDs used
        """
        return self._task_skill_usage.get(task_id, [])
    
    def clear_task_usage(self, task_id: str) -> None:
        """Clear skill usage tracking for a task."""
        self._task_skill_usage.pop(task_id, None)
    
    def on_task_complete(
        self,
        task_id: str,
        success: bool,
        agent_name: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Handle task completion for skill learning.
        
        This method should be called when a task completes to:
        - Update skill usage metrics
        - Queue successful tasks for learning
        
        Args:
            task_id: The task ID
            success: Whether the task succeeded
            agent_name: The agent name
            user_id: Optional user ID
        """
        # Get skills used in this task
        skills_used = self.get_skills_used_in_task(task_id)
        
        # Update skill metrics based on task outcome
        if skills_used:
            from ..feedback import FeedbackProcessor, FeedbackType
            
            processor = FeedbackProcessor(self.skill_service.repository)
            processor.process_task_completion(
                task_id=task_id,
                success=success,
                skill_ids_used=skills_used,
                user_id=user_id,
            )
        
        # Queue successful tasks for learning
        if success:
            try:
                self.skill_service.enqueue_for_learning(
                    task_id=task_id,
                    agent_name=agent_name,
                    user_id=user_id,
                )
            except Exception as e:
                logger.warning(f"Failed to queue task for learning: {e}")
        
        # Clear usage tracking
        self.clear_task_usage(task_id)