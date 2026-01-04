"""
SAM Skills system.

Skills provide agents with specialized context and tools that are loaded
on-demand when activated. This package implements Claude Code-compatible
skill loading with SAM-specific tool extensions.

Usage:
    Configure skills in agent YAML:

    ```yaml
    app_config:
      skills:
        paths:
          - ./skills
          - /shared/skills
        auto_discover: true
    ```

    Skill directory structure:

    ```
    my-skill/
    ├── SKILL.md              # Required: Claude Code compatible
    └── skill.sam.yaml        # Optional: SAM-specific tools
    ```
"""

from .types import ActivatedSkill, SkillCatalogEntry
from .loader import (
    scan_skill_directories,
    extract_skill_metadata,
    load_full_skill,
    generate_skill_catalog_instructions,
)

# Import to trigger tool registration
from . import activate_skill_tool  # noqa: F401

__all__ = [
    "ActivatedSkill",
    "SkillCatalogEntry",
    "scan_skill_directories",
    "extract_skill_metadata",
    "load_full_skill",
    "generate_skill_catalog_instructions",
]
