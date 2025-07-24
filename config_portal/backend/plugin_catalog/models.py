from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class PyProjectAuthor(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None


class PyProjectDetails(BaseModel):
    name: str
    version: str
    description: Optional[str] = None
    authors: Optional[List[PyProjectAuthor]] = None
    plugin_type: Optional[str] = "custom"
    custom_metadata: Optional[Dict[str, Any]] = None


class AgentCardSkill(BaseModel):
    name: str
    description: Optional[str] = None


class AgentCard(BaseModel):
    displayName: Optional[str] = None
    shortDescription: Optional[str] = None
    Skill: Optional[List[AgentCardSkill]] = None


class PluginScrapedInfo(BaseModel):
    id: str
    pyproject: PyProjectDetails
    readme_content: Optional[str] = None
    agent_card: Optional[AgentCard] = None
    source_registry_name: Optional[str] = None
    source_registry_location: str
    source_type: str
    plugin_subpath: str
    is_official: bool


class Registry(BaseModel):
    id: str
    path_or_url: str
    name: Optional[str] = None
    type: str
    is_default: bool = False
    is_official_source: bool = False
    git_branch: Optional[str] = None
