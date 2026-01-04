"""
Skill discovery and loading utilities.

This module handles:
- Scanning directories for skill definitions (SKILL.md files)
- Extracting metadata from YAML frontmatter
- Loading full skill content and tools on activation
"""

import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import yaml

from .types import ActivatedSkill, SkillCatalogEntry

if TYPE_CHECKING:
    from google.adk.tools import BaseTool
    from google.genai import types as adk_types

    from ..sac.component import SamAgentComponent

log = logging.getLogger(__name__)

SKILL_MD_FILENAME = "SKILL.md"
SKILL_SAM_YAML_FILENAME = "skill.sam.yaml"


def scan_skill_directories(
    paths: List[str],
    base_path: Optional[str] = None,
    auto_discover: bool = True,
) -> Dict[str, SkillCatalogEntry]:
    """
    Scans configured paths for skill directories.

    A valid skill directory contains a SKILL.md file with YAML frontmatter
    containing at least 'name' and 'description' fields.

    Args:
        paths: List of paths to scan for skills.
        base_path: Base path for resolving relative paths.
        auto_discover: If True, recursively scan subdirectories.

    Returns:
        Dictionary mapping skill names to their catalog entries.
    """
    catalog: Dict[str, SkillCatalogEntry] = {}

    for path in paths:
        # Resolve relative paths
        if not os.path.isabs(path) and base_path:
            path = os.path.join(base_path, path)

        if not os.path.exists(path):
            log.warning("Skill path does not exist: %s", path)
            continue

        if auto_discover:
            # Recursively find all SKILL.md files
            for root, _dirs, files in os.walk(path):
                if SKILL_MD_FILENAME in files:
                    entry = extract_skill_metadata(root)
                    if entry:
                        if entry.name in catalog:
                            log.warning(
                                "Duplicate skill name '%s' found at %s. "
                                "Using first occurrence at %s.",
                                entry.name,
                                root,
                                catalog[entry.name].path,
                            )
                        else:
                            catalog[entry.name] = entry
                            log.debug("Discovered skill '%s' at %s", entry.name, root)
        else:
            # Only check immediate subdirectories
            for item in os.listdir(path):
                skill_dir = os.path.join(path, item)
                if os.path.isdir(skill_dir):
                    skill_md = os.path.join(skill_dir, SKILL_MD_FILENAME)
                    if os.path.exists(skill_md):
                        entry = extract_skill_metadata(skill_dir)
                        if entry and entry.name not in catalog:
                            catalog[entry.name] = entry
                            log.debug("Discovered skill '%s' at %s", entry.name, skill_dir)

    return catalog


def extract_skill_metadata(skill_path: str) -> Optional[SkillCatalogEntry]:
    """
    Extracts metadata from a skill directory.

    Reads the YAML frontmatter from SKILL.md to get name, description,
    and optional allowed-tools.

    Args:
        skill_path: Path to the skill directory.

    Returns:
        SkillCatalogEntry with metadata, or None if invalid.
    """
    skill_md_path = os.path.join(skill_path, SKILL_MD_FILENAME)

    if not os.path.exists(skill_md_path):
        return None

    try:
        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse YAML frontmatter
        metadata, _body = parse_yaml_frontmatter(content)

        if not metadata:
            log.warning(
                "Skill at %s has no YAML frontmatter. Skipping.", skill_path
            )
            return None

        # Validate required fields
        name = metadata.get("name")
        description = metadata.get("description")

        if not name:
            log.warning(
                "Skill at %s missing required 'name' field in frontmatter. Skipping.",
                skill_path,
            )
            return None

        if not description:
            log.warning(
                "Skill at %s missing required 'description' field in frontmatter. Skipping.",
                skill_path,
            )
            return None

        # Parse optional allowed-tools
        allowed_tools = None
        allowed_tools_str = metadata.get("allowed-tools")
        if allowed_tools_str:
            if isinstance(allowed_tools_str, str):
                allowed_tools = [t.strip() for t in allowed_tools_str.split(",")]
            elif isinstance(allowed_tools_str, list):
                allowed_tools = allowed_tools_str

        # Check for SAM tools file
        sam_yaml_path = os.path.join(skill_path, SKILL_SAM_YAML_FILENAME)
        has_sam_tools = os.path.exists(sam_yaml_path)

        return SkillCatalogEntry(
            name=name,
            description=description,
            path=skill_path,
            has_sam_tools=has_sam_tools,
            allowed_tools=allowed_tools,
        )

    except Exception as e:
        log.error("Failed to extract metadata from %s: %s", skill_path, e)
        return None


def parse_yaml_frontmatter(content: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Extracts YAML frontmatter from markdown content.

    Frontmatter is delimited by '---' at the start and end.

    Args:
        content: Full markdown content.

    Returns:
        Tuple of (metadata dict or None, body content after frontmatter).
    """
    content = content.strip()

    if not content.startswith("---"):
        return None, content

    # Find the closing '---'
    end_index = content.find("---", 3)
    if end_index == -1:
        return None, content

    frontmatter_str = content[3:end_index].strip()
    body = content[end_index + 3 :].strip()

    try:
        metadata = yaml.safe_load(frontmatter_str)
        if not isinstance(metadata, dict):
            return None, content
        return metadata, body
    except yaml.YAMLError as e:
        log.warning("Failed to parse YAML frontmatter: %s", e)
        return None, content


def load_full_skill(
    catalog_entry: SkillCatalogEntry,
    component: "SamAgentComponent",
) -> ActivatedSkill:
    """
    Loads the full skill content and tools.

    Called when a skill is activated via activate_skill tool.

    Args:
        catalog_entry: The skill's catalog metadata.
        component: The host agent component (for tool loading context).

    Returns:
        ActivatedSkill with full content and loaded tools.
    """
    skill_md_path = os.path.join(catalog_entry.path, SKILL_MD_FILENAME)

    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract body (after frontmatter)
    _metadata, body = parse_yaml_frontmatter(content)
    full_content = body

    tools: List["BaseTool"] = []
    declarations: List["adk_types.FunctionDeclaration"] = []

    if catalog_entry.has_sam_tools:
        sam_yaml_path = os.path.join(catalog_entry.path, SKILL_SAM_YAML_FILENAME)
        loaded_tools, loaded_declarations = parse_sam_tools_yaml(
            sam_yaml_path, catalog_entry.name, component
        )
        tools = loaded_tools
        declarations = loaded_declarations

    return ActivatedSkill(
        name=catalog_entry.name,
        description=catalog_entry.description,
        path=catalog_entry.path,
        full_content=full_content,
        tools=tools,
        tool_declarations=declarations,
        allowed_tools=catalog_entry.allowed_tools,
    )


def parse_sam_tools_yaml(
    yaml_path: str,
    skill_name: str,
    component: "SamAgentComponent",
) -> Tuple[List["BaseTool"], List["adk_types.FunctionDeclaration"]]:
    """
    Parses skill.sam.yaml and creates tool instances.

    Tool names are suffixed with skill name to avoid conflicts.
    Descriptions are prefixed with skill source attribution.

    Args:
        yaml_path: Path to skill.sam.yaml file.
        skill_name: Name of the skill (for prefixing).
        component: The host agent component.

    Returns:
        Tuple of (list of tools, list of function declarations).
    """
    from .skill_tool import create_skill_tool

    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    tools: List["BaseTool"] = []
    declarations: List["adk_types.FunctionDeclaration"] = []

    if not config or "tools" not in config:
        return tools, declarations

    for tool_config in config.get("tools", []):
        try:
            tool, declaration = create_skill_tool(tool_config, skill_name, component)
            if tool and declaration:
                tools.append(tool)
                declarations.append(declaration)
        except Exception as e:
            log.error(
                "Failed to create skill tool from config %s: %s",
                tool_config.get("name", "unknown"),
                e,
            )

    return tools, declarations


def generate_skill_catalog_instructions(
    catalog: Dict[str, SkillCatalogEntry],
) -> str:
    """
    Generates the skill catalog text for the system prompt.

    Args:
        catalog: Dictionary of skill names to catalog entries.

    Returns:
        Formatted instruction text listing available skills.
    """
    if not catalog:
        return ""

    lines = [
        "## Available Skills",
        "",
        "You can activate skills to gain specialized capabilities and context.",
        "Use `activate_skill(skill_name)` to load a skill's full context and tools.",
        "",
    ]

    for name, entry in sorted(catalog.items()):
        lines.append(f"### `{name}`")
        lines.append(entry.description)
        lines.append("")

    return "\n".join(lines)
