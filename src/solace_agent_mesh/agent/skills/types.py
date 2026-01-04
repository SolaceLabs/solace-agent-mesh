"""
Data types for the SAM Skills system.

Skills provide agents with specialized context and tools that are loaded on-demand
when activated. This module defines the data structures for skill metadata and
activated skill state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.adk.tools import BaseTool
from google.genai import types as adk_types


@dataclass
class SkillCatalogEntry:
    """
    Lightweight metadata for skill catalog display.

    This is loaded at agent startup from SKILL.md frontmatter.
    Only contains metadata needed for the skill catalog in the system prompt.
    """

    name: str
    """Skill identifier from YAML frontmatter."""

    description: str
    """Description of when to use this skill (from YAML frontmatter)."""

    path: str
    """Absolute path to the skill directory."""

    has_sam_tools: bool = False
    """True if skill.sam.yaml exists in the skill directory."""

    allowed_tools: Optional[List[str]] = None
    """Optional list of tools available when skill is active (from YAML frontmatter)."""


@dataclass
class ActivatedSkill:
    """
    Full skill data loaded on activation.

    Contains the complete skill content, loaded tools, and tool declarations.
    Created when `activate_skill` tool is called.
    """

    name: str
    """Skill identifier."""

    description: str
    """Description of when to use this skill."""

    path: str
    """Absolute path to the skill directory."""

    full_content: str
    """Full SKILL.md content (body after frontmatter)."""

    tools: List[BaseTool] = field(default_factory=list)
    """ADK tool instances loaded from skill.sam.yaml."""

    tool_declarations: List[adk_types.FunctionDeclaration] = field(default_factory=list)
    """Pre-built FunctionDeclarations for the tools."""

    allowed_tools: Optional[List[str]] = None
    """Optional list of tools available when skill is active."""

    activation_time: datetime = field(default_factory=datetime.now)
    """When this skill was activated."""

    def get_tool_names(self) -> List[str]:
        """Returns the names of all tools provided by this skill."""
        return [tool.name for tool in self.tools]
