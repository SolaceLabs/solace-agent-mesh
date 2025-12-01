"""
Integration module for skill learning with SAM agents.

This module provides the integration points between the skill learning
system and the SAM agent execution pipeline.

Key components:
- AgentSkillInjector: Injects skills into agent execution
- PromptEnhancer: Enhances system prompts with skill information
- TaskContextAnalyzer: Analyzes task context for skill matching
"""

from .agent_skill_injector import AgentSkillInjector
from .prompt_enhancer import PromptEnhancer, TaskContextAnalyzer

__all__ = [
    "AgentSkillInjector",
    "PromptEnhancer",
    "TaskContextAnalyzer",
]