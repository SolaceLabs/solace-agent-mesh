from typing import Any

from pydantic import BaseModel


class PyProjectAuthor(BaseModel):
    name: str | None = None
    email: str | None = None


class PyProjectDetails(BaseModel):
    name: str
    version: str
    description: str | None = None
    authors: list[PyProjectAuthor] | None = None
    plugin_type: str | None = "custom"
    custom_metadata: dict[str, Any] | None = None


class AgentCardSkill(BaseModel):
    name: str
    description: str | None = None


class AgentCard(BaseModel):
    displayName: str | None = None
    shortDescription: str | None = None
    Skill: list[AgentCardSkill] | None = None


class PluginScrapedInfo(BaseModel):
    id: str
    pyproject: PyProjectDetails
    readme_content: str | None = None
    agent_card: AgentCard | None = None
    source_registry_name: str | None = None
    source_registry_location: str
    source_type: str
    plugin_subpath: str
    is_official: bool


class Registry(BaseModel):
    id: str
    path_or_url: str
    name: str | None = None
    filesystem_name: str | None = None  # Sanitized name for filesystem operations
    type: str
    is_default: bool = False
    is_official_source: bool = False
    git_branch: str | None = None
