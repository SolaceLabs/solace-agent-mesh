"""
Domain entities for the skill versioning system.

These entities represent the business objects for versioned skills:
- SkillGroup: Container for skill versions
- SkillVersion: Individual version of a skill
- SkillGroupUser: User access to a skill group
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum
import time


def now_epoch_ms() -> int:
    """Get current time as epoch milliseconds."""
    return int(time.time() * 1000)


class SkillType(str, Enum):
    """Type of skill."""
    LEARNED = "learned"
    AUTHORED = "authored"


class SkillScope(str, Enum):
    """Scope of skill visibility."""
    AGENT = "agent"
    USER = "user"
    SHARED = "shared"
    GLOBAL = "global"


class SkillGroupRole(str, Enum):
    """Role for skill group access."""
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


@dataclass
class AgentChainNode:
    """A node in the agent chain representing an agent's involvement."""
    agent_name: str
    task_id: str
    role: str = "specialist"
    tools_used: List[str] = field(default_factory=list)


@dataclass
class AgentToolStep:
    """A step in the skill procedure."""
    step_type: str  # tool_call, delegation, reasoning
    agent_name: str
    tool_name: str
    action: str
    parameters_template: Optional[dict] = None
    sequence_number: int = 1


@dataclass
class SkillVersion:
    """
    Individual version of a skill.
    
    Versions are immutable once created. Each version contains
    the full skill content and metadata.
    """
    id: str
    group_id: str
    version: int
    description: str
    
    # Content
    markdown_content: Optional[str] = None
    agent_chain: Optional[List[AgentChainNode]] = None
    tool_steps: Optional[List[AgentToolStep]] = None
    summary: Optional[str] = None
    
    # Source tracking
    source_task_id: Optional[str] = None
    related_task_ids: Optional[List[str]] = None
    involved_agents: Optional[List[str]] = None
    
    # Embedding for vector search
    embedding: Optional[List[float]] = None
    
    # Quality metrics
    complexity_score: int = 0
    
    # Version metadata
    created_by_user_id: Optional[str] = None
    creation_reason: Optional[str] = None
    
    # Timestamps (epoch ms)
    created_at: int = field(default_factory=now_epoch_ms)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "group_id": self.group_id,
            "version": self.version,
            "description": self.description,
            "markdown_content": self.markdown_content,
            "agent_chain": [
                {
                    "agent_name": node.agent_name,
                    "task_id": node.task_id,
                    "role": node.role,
                    "tools_used": node.tools_used,
                }
                for node in (self.agent_chain or [])
            ] if self.agent_chain else None,
            "tool_steps": [
                {
                    "step_type": step.step_type,
                    "agent_name": step.agent_name,
                    "tool_name": step.tool_name,
                    "action": step.action,
                    "parameters_template": step.parameters_template,
                    "sequence_number": step.sequence_number,
                }
                for step in (self.tool_steps or [])
            ] if self.tool_steps else None,
            "summary": self.summary,
            "source_task_id": self.source_task_id,
            "related_task_ids": self.related_task_ids,
            "involved_agents": self.involved_agents,
            "complexity_score": self.complexity_score,
            "created_by_user_id": self.created_by_user_id,
            "creation_reason": self.creation_reason,
            "created_at": self.created_at,
        }


@dataclass
class SkillGroup:
    """
    Container for skill versions.
    
    A skill group represents a logical skill that can have multiple versions.
    Only one version is "production" (active) at a time.
    """
    id: str
    name: str
    
    # Classification
    type: SkillType
    scope: SkillScope
    
    # Optional fields
    description: Optional[str] = None
    category: Optional[str] = None
    
    # Ownership
    owner_agent_name: Optional[str] = None
    owner_user_id: Optional[str] = None
    
    # Production version reference
    production_version_id: Optional[str] = None
    
    # Status
    is_archived: bool = False
    
    # Timestamps (epoch ms)
    created_at: int = field(default_factory=now_epoch_ms)
    updated_at: int = field(default_factory=now_epoch_ms)
    
    # Relationships (loaded on demand)
    versions: List[SkillVersion] = field(default_factory=list)
    production_version: Optional[SkillVersion] = None
    version_count: int = 0
    
    # Aggregated metrics from production version
    success_count: int = 0
    failure_count: int = 0
    
    def get_success_rate(self) -> Optional[float]:
        """Calculate success rate from counts."""
        total = self.success_count + self.failure_count
        if total == 0:
            return None
        return self.success_count / total
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "type": self.type.value if isinstance(self.type, SkillType) else self.type,
            "scope": self.scope.value if isinstance(self.scope, SkillScope) else self.scope,
            "owner_agent_name": self.owner_agent_name,
            "owner_user_id": self.owner_user_id,
            "production_version_id": self.production_version_id,
            "is_archived": self.is_archived,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version_count": self.version_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "production_version": self.production_version.to_dict() if self.production_version else None,
        }
    
    def to_summary_dict(self) -> dict:
        """Convert to summary dictionary (without full version details)."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "type": self.type.value if isinstance(self.type, SkillType) else self.type,
            "scope": self.scope.value if isinstance(self.scope, SkillScope) else self.scope,
            "owner_agent_name": self.owner_agent_name,
            "is_archived": self.is_archived,
            "version_count": self.version_count,
            "success_rate": self.get_success_rate(),
            "production_version": self.production_version_id,
        }


@dataclass
class SkillGroupUser:
    """
    User access to a skill group.
    
    Tracks which users have access to which skill groups
    with role-based permissions.
    """
    id: str
    skill_group_id: str
    user_id: str
    role: SkillGroupRole
    added_at: int = field(default_factory=now_epoch_ms)
    added_by_user_id: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "skill_group_id": self.skill_group_id,
            "user_id": self.user_id,
            "role": self.role.value if isinstance(self.role, SkillGroupRole) else self.role,
            "added_at": self.added_at,
            "added_by_user_id": self.added_by_user_id,
        }


@dataclass
class CreateSkillGroupRequest:
    """Request to create a new skill group with initial version."""
    name: str
    description: str
    type: SkillType = SkillType.AUTHORED
    scope: SkillScope = SkillScope.USER
    category: Optional[str] = None
    owner_agent_name: Optional[str] = None
    owner_user_id: Optional[str] = None
    
    # Initial version content
    markdown_content: Optional[str] = None
    agent_chain: Optional[List[AgentChainNode]] = None
    tool_steps: Optional[List[AgentToolStep]] = None
    summary: Optional[str] = None
    source_task_id: Optional[str] = None
    involved_agents: Optional[List[str]] = None


@dataclass
class CreateVersionRequest:
    """Request to create a new version of an existing skill."""
    group_id: str
    description: str
    creation_reason: str
    created_by_user_id: Optional[str] = None
    
    # Version content
    markdown_content: Optional[str] = None
    agent_chain: Optional[List[AgentChainNode]] = None
    tool_steps: Optional[List[AgentToolStep]] = None
    summary: Optional[str] = None
    source_task_id: Optional[str] = None
    related_task_ids: Optional[List[str]] = None
    involved_agents: Optional[List[str]] = None
    
    # Whether to set as production
    set_as_production: bool = True