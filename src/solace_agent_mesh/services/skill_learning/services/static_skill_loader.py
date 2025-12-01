"""
Static skill loader for loading SKILL.md files.

This service loads authored skills from markdown files in the
skills directory. Skills can be organized by agent or globally.

Supports two formats:
1. Single-file skills: skill-name.SKILL.md
2. Folder-based skills (OpenSkills format):
   skill-name/
     SKILL.md           - Main skill definition
     references/        - Documentation loaded on-demand
     scripts/           - Executable code
     assets/            - Templates and output files

Directory structure:
  skills/
    global/
      skill-name.SKILL.md           # Single-file skill
      complex-skill/                 # Folder-based skill
        SKILL.md
        references/
          api-docs.md
        scripts/
          helper.py
    agents/
      agent-name/
        skill-name.SKILL.md
        folder-skill/
          SKILL.md
    users/
      user-id/
        skill-name.SKILL.md
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
import yaml
import zipfile
from io import BytesIO

from ..entities import (
    Skill,
    SkillType,
    SkillScope,
    generate_id,
    now_epoch_ms,
)

logger = logging.getLogger(__name__)


class StaticSkillLoader:
    """
    Loader for static SKILL.md files.
    
    Supports loading skills from:
    - Global skills directory
    - Agent-specific skills directories
    - User-specific skills directories
    """
    
    # Pattern for skill file names: name.SKILL.md
    SKILL_FILE_PATTERN = re.compile(r"^(.+)\.SKILL\.md$", re.IGNORECASE)
    
    def __init__(
        self,
        skills_directory: str,
        watch_for_changes: bool = False,
    ):
        """
        Initialize the static skill loader.
        
        Args:
            skills_directory: Base directory for skill files
            watch_for_changes: Whether to watch for file changes
        """
        self.skills_directory = Path(skills_directory)
        self.watch_for_changes = watch_for_changes
        
        # Cache of loaded skills by file path
        self._cache: Dict[str, Skill] = {}
        self._file_mtimes: Dict[str, float] = {}
    
    def load_all_skills(self) -> List[Skill]:
        """
        Load all skills from the skills directory.
        
        Returns:
            List of all loaded skills
        """
        skills = []
        
        # Load global skills
        global_dir = self.skills_directory / "global"
        if global_dir.exists():
            skills.extend(self._load_skills_from_directory(
                global_dir, 
                SkillScope.GLOBAL
            ))
        
        # Load agent-specific skills
        agents_dir = self.skills_directory / "agents"
        if agents_dir.exists():
            for agent_dir in agents_dir.iterdir():
                if agent_dir.is_dir():
                    agent_name = agent_dir.name
                    skills.extend(self._load_skills_from_directory(
                        agent_dir,
                        SkillScope.AGENT,
                        owner_agent_name=agent_name,
                    ))
        
        # Load user-specific skills
        users_dir = self.skills_directory / "users"
        if users_dir.exists():
            for user_dir in users_dir.iterdir():
                if user_dir.is_dir():
                    user_id = user_dir.name
                    skills.extend(self._load_skills_from_directory(
                        user_dir,
                        SkillScope.USER,
                        owner_user_id=user_id,
                    ))
        
        logger.info(f"Loaded {len(skills)} static skills from {self.skills_directory}")
        return skills
    
    def load_global_skills(self) -> List[Skill]:
        """
        Load only global skills.
        
        Returns:
            List of global skills
        """
        global_dir = self.skills_directory / "global"
        if not global_dir.exists():
            return []
        
        return self._load_skills_from_directory(global_dir, SkillScope.GLOBAL)
    
    def load_agent_skills(self, agent_name: str) -> List[Skill]:
        """
        Load skills for a specific agent.
        
        Args:
            agent_name: The agent name
            
        Returns:
            List of agent-specific skills
        """
        agent_dir = self.skills_directory / "agents" / agent_name
        if not agent_dir.exists():
            return []
        
        return self._load_skills_from_directory(
            agent_dir,
            SkillScope.AGENT,
            owner_agent_name=agent_name,
        )
    
    def load_user_skills(self, user_id: str) -> List[Skill]:
        """
        Load skills for a specific user.
        
        Args:
            user_id: The user ID
            
        Returns:
            List of user-specific skills
        """
        user_dir = self.skills_directory / "users" / user_id
        if not user_dir.exists():
            return []
        
        return self._load_skills_from_directory(
            user_dir,
            SkillScope.USER,
            owner_user_id=user_id,
        )
    
    def load_skill_file(
        self,
        file_path: str,
        scope: SkillScope = SkillScope.GLOBAL,
        owner_agent_name: Optional[str] = None,
        owner_user_id: Optional[str] = None,
    ) -> Optional[Skill]:
        """
        Load a single skill file.
        
        Args:
            file_path: Path to the skill file
            scope: Skill scope
            owner_agent_name: Optional agent owner
            owner_user_id: Optional user owner
            
        Returns:
            The loaded skill or None if invalid
        """
        path = Path(file_path)
        
        if not path.exists():
            logger.warning(f"Skill file not found: {file_path}")
            return None
        
        # Check cache
        str_path = str(path)
        if self.watch_for_changes:
            mtime = path.stat().st_mtime
            if str_path in self._cache and self._file_mtimes.get(str_path) == mtime:
                return self._cache[str_path]
            self._file_mtimes[str_path] = mtime
        elif str_path in self._cache:
            return self._cache[str_path]
        
        # Parse the file
        skill = self._parse_skill_file(
            path,
            scope,
            owner_agent_name,
            owner_user_id,
        )
        
        if skill:
            self._cache[str_path] = skill
        
        return skill
    
    def _load_skills_from_directory(
        self,
        directory: Path,
        scope: SkillScope,
        owner_agent_name: Optional[str] = None,
        owner_user_id: Optional[str] = None,
    ) -> List[Skill]:
        """Load all skill files and folders from a directory."""
        skills = []
        
        # Load single-file skills (*.SKILL.md)
        for file_path in directory.glob("*.SKILL.md"):
            skill = self.load_skill_file(
                str(file_path),
                scope,
                owner_agent_name,
                owner_user_id,
            )
            if skill:
                skills.append(skill)
        
        # Also check for lowercase extension
        for file_path in directory.glob("*.skill.md"):
            if str(file_path) not in self._cache:
                skill = self.load_skill_file(
                    str(file_path),
                    scope,
                    owner_agent_name,
                    owner_user_id,
                )
                if skill:
                    skills.append(skill)
        
        # Load folder-based skills (OpenSkills format)
        for item in directory.iterdir():
            if item.is_dir():
                # Check if this is a skill folder (contains SKILL.md)
                skill_file = item / "SKILL.md"
                if not skill_file.exists():
                    # Also check lowercase
                    skill_file = item / "skill.md"
                
                if skill_file.exists():
                    skill = self._load_skill_folder(
                        item,
                        scope,
                        owner_agent_name,
                        owner_user_id,
                    )
                    if skill:
                        skills.append(skill)
        
        return skills
    
    def _load_skill_folder(
        self,
        folder_path: Path,
        scope: SkillScope,
        owner_agent_name: Optional[str] = None,
        owner_user_id: Optional[str] = None,
    ) -> Optional[Skill]:
        """
        Load a folder-based skill (OpenSkills format).
        
        Expected structure:
          skill-name/
            SKILL.md           - Main skill definition
            references/        - Documentation (loaded on-demand)
            scripts/           - Executable code
            assets/            - Templates and output files
        """
        # Find the main SKILL.md file
        skill_file = folder_path / "SKILL.md"
        if not skill_file.exists():
            skill_file = folder_path / "skill.md"
        
        if not skill_file.exists():
            logger.warning(f"Skill folder missing SKILL.md: {folder_path}")
            return None
        
        # Check cache
        str_path = str(folder_path)
        if self.watch_for_changes:
            mtime = skill_file.stat().st_mtime
            if str_path in self._cache and self._file_mtimes.get(str_path) == mtime:
                return self._cache[str_path]
            self._file_mtimes[str_path] = mtime
        elif str_path in self._cache:
            return self._cache[str_path]
        
        # Parse the main SKILL.md
        skill = self._parse_skill_file(
            skill_file,
            scope,
            owner_agent_name,
            owner_user_id,
        )
        
        if skill:
            # Store the base directory for resource resolution
            skill.base_directory = str(folder_path)
            
            # Collect bundled resources metadata
            skill.bundled_resources = self._collect_bundled_resources(folder_path)
            
            self._cache[str_path] = skill
        
        return skill
    
    def _collect_bundled_resources(self, folder_path: Path) -> Dict[str, List[str]]:
        """
        Collect metadata about bundled resources in a skill folder.
        
        Returns:
            Dict with keys: references, scripts, assets
        """
        resources = {
            "references": [],
            "scripts": [],
            "assets": [],
        }
        
        # Collect references
        refs_dir = folder_path / "references"
        if refs_dir.exists():
            for f in refs_dir.rglob("*"):
                if f.is_file():
                    resources["references"].append(str(f.relative_to(folder_path)))
        
        # Collect scripts
        scripts_dir = folder_path / "scripts"
        if scripts_dir.exists():
            for f in scripts_dir.rglob("*"):
                if f.is_file():
                    resources["scripts"].append(str(f.relative_to(folder_path)))
        
        # Collect assets
        assets_dir = folder_path / "assets"
        if assets_dir.exists():
            for f in assets_dir.rglob("*"):
                if f.is_file():
                    resources["assets"].append(str(f.relative_to(folder_path)))
        
        return resources
    
    def load_skill_resource(
        self,
        skill: Skill,
        resource_path: str,
    ) -> Optional[str]:
        """
        Load a bundled resource from a skill folder.
        
        Args:
            skill: The skill entity
            resource_path: Relative path to the resource (e.g., "references/api.md")
            
        Returns:
            The resource content as string, or None if not found
        """
        if not skill.base_directory:
            logger.warning(f"Skill {skill.name} has no base directory")
            return None
        
        full_path = Path(skill.base_directory) / resource_path
        
        if not full_path.exists():
            logger.warning(f"Resource not found: {full_path}")
            return None
        
        if not full_path.is_file():
            logger.warning(f"Resource is not a file: {full_path}")
            return None
        
        # Security check: ensure path is within skill folder
        try:
            full_path.resolve().relative_to(Path(skill.base_directory).resolve())
        except ValueError:
            logger.error(f"Security: Resource path escapes skill folder: {resource_path}")
            return None
        
        try:
            return full_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read resource {full_path}: {e}")
            return None
    
    def _parse_skill_file(
        self,
        file_path: Path,
        scope: SkillScope,
        owner_agent_name: Optional[str] = None,
        owner_user_id: Optional[str] = None,
    ) -> Optional[Skill]:
        """
        Parse a SKILL.md file into a Skill entity.
        
        Expected format:
        ```
        ---
        name: skill-name
        description: When to use this skill
        tags: [tag1, tag2]
        ---
        
        # Skill Content
        
        Markdown content describing the skill...
        ```
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read skill file {file_path}: {e}")
            return None
        
        # Extract skill name from filename
        match = self.SKILL_FILE_PATTERN.match(file_path.name)
        if match:
            file_skill_name = match.group(1)
        else:
            file_skill_name = file_path.stem.replace(".SKILL", "").replace(".skill", "")
        
        # Parse frontmatter if present
        frontmatter = {}
        markdown_content = content
        
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    markdown_content = parts[2].strip()
                except yaml.YAMLError as e:
                    logger.warning(f"Failed to parse frontmatter in {file_path}: {e}")
        
        # Get skill name (frontmatter overrides filename)
        name = frontmatter.get("name", file_skill_name)
        
        # Get description (required)
        description = frontmatter.get("description")
        if not description:
            # Try to extract from first paragraph
            lines = markdown_content.split("\n")
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    description = line[:200]  # Limit length
                    break
        
        if not description:
            description = f"Skill: {name}"
        
        # Create the skill
        skill = Skill(
            id=generate_id(),
            name=name,
            description=description,
            type=SkillType.AUTHORED,
            scope=scope,
            owner_agent_name=owner_agent_name,
            owner_user_id=owner_user_id,
            markdown_content=markdown_content,
            created_at=now_epoch_ms(),
            updated_at=now_epoch_ms(),
        )
        
        # Add optional fields from frontmatter
        if "summary" in frontmatter:
            skill.summary = frontmatter["summary"]
        if "involved_agents" in frontmatter:
            skill.involved_agents = frontmatter["involved_agents"]
        if "complexity_score" in frontmatter:
            skill.complexity_score = frontmatter["complexity_score"]
        
        logger.debug(f"Loaded skill '{name}' from {file_path}")
        return skill
    
    def reload_all(self) -> List[Skill]:
        """
        Clear cache and reload all skills.
        
        Returns:
            List of all reloaded skills
        """
        self._cache.clear()
        self._file_mtimes.clear()
        return self.load_all_skills()
    
    def get_cached_skills(self) -> List[Skill]:
        """
        Get all currently cached skills.
        
        Returns:
            List of cached skills
        """
        return list(self._cache.values())
    
    def create_skill_file(
        self,
        skill: Skill,
        directory: Optional[str] = None,
    ) -> str:
        """
        Create a SKILL.md file from a Skill entity.
        
        Args:
            skill: The skill to save
            directory: Optional directory (defaults based on scope)
            
        Returns:
            Path to the created file
        """
        # Determine directory
        if directory:
            target_dir = Path(directory)
        elif skill.scope == SkillScope.GLOBAL:
            target_dir = self.skills_directory / "global"
        elif skill.scope == SkillScope.AGENT and skill.owner_agent_name:
            target_dir = self.skills_directory / "agents" / skill.owner_agent_name
        elif skill.scope in (SkillScope.USER, SkillScope.SHARED) and skill.owner_user_id:
            target_dir = self.skills_directory / "users" / skill.owner_user_id
        else:
            target_dir = self.skills_directory / "global"
        
        # Create directory if needed
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Create frontmatter
        frontmatter = {
            "name": skill.name,
            "description": skill.description,
        }
        if skill.summary:
            frontmatter["summary"] = skill.summary
        if skill.involved_agents:
            frontmatter["involved_agents"] = skill.involved_agents
        if skill.complexity_score:
            frontmatter["complexity_score"] = skill.complexity_score
        
        # Build file content
        content_parts = [
            "---",
            yaml.dump(frontmatter, default_flow_style=False).strip(),
            "---",
            "",
        ]
        
        if skill.markdown_content:
            content_parts.append(skill.markdown_content)
        else:
            # Generate markdown from tool steps
            content_parts.append(f"# {skill.name}")
            content_parts.append("")
            content_parts.append(skill.description)
            
            if skill.tool_steps:
                content_parts.append("")
                content_parts.append("## Steps")
                content_parts.append("")
                for step in skill.tool_steps:
                    content_parts.append(f"{step.sequence_number}. **{step.action}**")
                    content_parts.append(f"   - Agent: {step.agent_name}")
                    content_parts.append(f"   - Tool: {step.tool_name}")
                    content_parts.append("")
        
        content = "\n".join(content_parts)
        
        # Write file
        file_path = target_dir / f"{skill.name}.SKILL.md"
        file_path.write_text(content, encoding="utf-8")
        
        logger.info(f"Created skill file: {file_path}")
        return str(file_path)