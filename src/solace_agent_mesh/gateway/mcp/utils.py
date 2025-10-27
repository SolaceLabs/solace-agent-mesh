"""
Utility functions for the MCP Gateway Adapter.
"""

import re
from typing import Optional
from a2a.types import AgentSkill


def sanitize_tool_name(name: str) -> str:
    """
    Sanitize an agent/skill name to be a valid MCP tool name.

    MCP tool names should be alphanumeric with underscores.
    This function:
    - Converts to lowercase
    - Replaces spaces and hyphens with underscores
    - Removes any non-alphanumeric characters except underscores
    - Removes duplicate underscores
    - Ensures it doesn't start with a number

    Args:
        name: The original agent or skill name

    Returns:
        A sanitized tool name suitable for MCP
    """
    # Convert to lowercase
    name = name.lower()

    # Replace spaces and hyphens with underscores
    name = name.replace(" ", "_").replace("-", "_")

    # Remove any character that isn't alphanumeric or underscore
    name = re.sub(r"[^a-z0-9_]", "", name)

    # Remove duplicate underscores
    name = re.sub(r"_+", "_", name)

    # Remove leading/trailing underscores
    name = name.strip("_")

    # Ensure doesn't start with a number
    if name and name[0].isdigit():
        name = f"tool_{name}"

    # Fallback if name is empty
    if not name:
        name = "unnamed_tool"

    return name


def format_agent_skill_description(skill: AgentSkill) -> str:
    """
    Format an AgentSkill into a description for an MCP tool.

    This creates a human-readable description that combines:
    - The skill's description
    - Example usage (if available)
    - Input/output modes (if specified)

    Args:
        skill: The AgentSkill to format

    Returns:
        A formatted description string
    """
    parts = []

    # Main description
    if skill.description:
        parts.append(skill.description)

    # Add examples if available
    if skill.examples and len(skill.examples) > 0:
        parts.append("\nExamples:")
        for idx, example in enumerate(skill.examples[:3], 1):  # Limit to 3 examples
            # Examples might be strings or dicts
            example_text = example if isinstance(example, str) else str(example)
            parts.append(f"  {idx}. {example_text}")

    # Add input/output mode info if present
    modes_info = []
    if skill.input_modes:
        modes_info.append(f"Input modes: {', '.join(skill.input_modes)}")
    if skill.output_modes:
        modes_info.append(f"Output modes: {', '.join(skill.output_modes)}")

    if modes_info:
        parts.append("\n" + " | ".join(modes_info))

    # Add tags if present
    if skill.tags:
        parts.append(f"\nTags: {', '.join(skill.tags)}")

    return "\n".join(parts) if parts else "No description available"


def truncate_text(text: str, max_length: int = 1000) -> str:
    """
    Truncate text to a maximum length, adding ellipsis if needed.

    Args:
        text: The text to truncate
        max_length: Maximum length (default 1000)

    Returns:
        Truncated text with "..." appended if it was truncated
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def create_session_id(prefix: str = "mcp") -> str:
    """
    Create a unique session ID for MCP requests.

    Args:
        prefix: Prefix for the session ID (default "mcp")

    Returns:
        A unique session ID string
    """
    import uuid
    from datetime import datetime

    timestamp = int(datetime.now().timestamp() * 1000)
    unique_id = uuid.uuid4().hex[:8]
    return f"{prefix}-{timestamp}-{unique_id}"


def extract_agent_skill_from_tool_name(
    tool_name: str,
    separator: str = "_"
) -> Optional[tuple[str, str]]:
    """
    Parse a tool name to extract agent name and skill name.

    Assumes format: agent_name_skill_name

    Args:
        tool_name: The MCP tool name
        separator: The separator character (default "_")

    Returns:
        Tuple of (agent_name, skill_name) or None if cannot parse
    """
    parts = tool_name.split(separator)
    if len(parts) < 2:
        return None

    # Assume the last part is the skill, everything before is the agent
    skill_name = parts[-1]
    agent_name = separator.join(parts[:-1])

    return (agent_name, skill_name)
