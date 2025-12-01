"""
Skill entity definitions for the SAM Skill Learning System.

This module defines the core data models for skills, including:
- Skill types and scopes
- Agent chain nodes for multi-agent tracking
- Tool steps with agent attribution
- Skill sharing, feedback, and usage tracking
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid
import time


def generate_id() -> str:
    """Generate a unique ID for entities."""
    return str(uuid.uuid4())


def now_epoch_ms() -> int:
    """Get current time as epoch milliseconds."""
    return int(time.time() * 1000)


class SkillType(str, Enum):
    """How the skill was created."""
    LEARNED = "learned"      # Auto-extracted from task execution
    AUTHORED = "authored"    # Manually created by user or admin


class SkillScope(str, Enum):
    """Ownership and visibility of the skill."""
    AGENT = "agent"          # Owned by specific agent
    USER = "user"            # Owned by user, available to all agents
    SHARED = "shared"        # Shared with other users
    GLOBAL = "global"        # System-wide, all agents


class StepType(str, Enum):
    """Type of step in the skill sequence."""
    TOOL_CALL = "tool_call"
    PEER_DELEGATION = "peer_delegation"
    LLM_REASONING = "llm_reasoning"


class AgentToolStep(BaseModel):
    """A single step in a skill's execution sequence."""
    
    id: str = Field(default_factory=generate_id)
    step_type: StepType = Field(..., description="Type of step")
    agent_name: str = Field(..., description="Agent that executed this step")
    tool_name: str = Field(..., description="Tool name from execution history")
    action: str = Field(..., description="Description of what to do")
    parameters_template: Optional[Dict[str, Any]] = Field(
        None, 
        description="Template for tool parameters"
    )
    
    # For peer delegation steps
    delegated_to_agent: Optional[str] = Field(
        None,
        description="Agent that was delegated to"
    )
    delegation_context: Optional[str] = Field(
        None,
        description="Context provided for delegation"
    )
    
    # Ordering
    sequence_number: int = Field(..., description="Order in the sequence")
    parent_step_id: Optional[str] = Field(
        None,
        description="Parent step ID for nested steps"
    )
    
    class Config:
        use_enum_values = True


class AgentChainNode(BaseModel):
    """A node in the agent delegation chain."""
    
    agent_name: str = Field(..., description="Name of the agent")
    task_id: str = Field(..., description="Task ID for this agent")
    parent_task_id: Optional[str] = Field(
        None,
        description="Parent task ID if delegated"
    )
    role: str = Field(
        ..., 
        description="Role: orchestrator, specialist, or leaf"
    )
    tools_used: List[str] = Field(
        default_factory=list,
        description="Tools used by this agent"
    )
    delegated_to: List[str] = Field(
        default_factory=list,
        description="Agents this agent delegated to"
    )


class Skill(BaseModel):
    """
    Unified skill model with agent ownership and feedback tracking.
    
    Skills can be:
    - Learned: Auto-extracted from successful task executions
    - Authored: Manually created as SKILL.md files or via API
    
    Skills have different scopes:
    - Agent: Owned by a specific agent, domain-specific
    - User: Owned by a user, available across agents
    - Shared: User skill shared with other users
    - Global: System-wide, available to all
    """
    
    id: str = Field(default_factory=generate_id)
    name: str = Field(..., description="Skill identifier - hyphen-case")
    description: str = Field(..., description="When to use this skill")
    
    # Classification
    type: SkillType = Field(..., description="How the skill was created")
    scope: SkillScope = Field(..., description="Ownership and visibility")
    
    # Ownership - one of these based on scope
    owner_agent_name: Optional[str] = Field(
        None,
        description="For agent-scoped skills"
    )
    owner_user_id: Optional[str] = Field(
        None,
        description="For user/shared-scoped skills"
    )
    
    # Content - one of these will be populated based on type
    markdown_content: Optional[str] = Field(
        None,
        description="For authored skills - markdown content"
    )
    agent_chain: List[AgentChainNode] = Field(
        default_factory=list,
        description="For learned skills - agent delegation chain"
    )
    tool_steps: List[AgentToolStep] = Field(
        default_factory=list,
        description="For learned skills - execution steps"
    )
    
    # For learned skills
    source_task_id: Optional[str] = Field(
        None,
        description="Task ID this skill was extracted from"
    )
    related_task_ids: List[str] = Field(
        default_factory=list,
        description="Related task IDs"
    )
    involved_agents: List[str] = Field(
        default_factory=list,
        description="Agents involved in this skill"
    )
    summary: Optional[str] = Field(
        None,
        description="Brief summary of the skill workflow"
    )
    
    # Metadata
    created_at: int = Field(
        default_factory=now_epoch_ms,
        description="Creation timestamp (epoch ms)"
    )
    updated_at: int = Field(
        default_factory=now_epoch_ms,
        description="Last update timestamp (epoch ms)"
    )
    
    # Feedback-driven metrics
    success_count: int = Field(
        default=0,
        description="Number of successful uses"
    )
    failure_count: int = Field(
        default=0,
        description="Number of failed uses"
    )
    user_corrections: int = Field(
        default=0,
        description="Number of user corrections"
    )
    last_feedback_at: Optional[int] = Field(
        None,
        description="Last feedback timestamp"
    )
    
    # Refinement tracking
    parent_skill_id: Optional[str] = Field(
        None,
        description="If refined from another skill"
    )
    refinement_reason: Optional[str] = Field(
        None,
        description="Reason for refinement"
    )
    
    # Quality metrics
    complexity_score: int = Field(
        default=0,
        description="Complexity score from extraction"
    )
    
    # Search
    embedding: Optional[List[float]] = Field(
        None,
        description="Embedding vector for semantic search"
    )
    
    # Folder-based skill support (OpenSkills format)
    base_directory: Optional[str] = Field(
        None,
        description="Base directory for folder-based skills"
    )
    bundled_resources: Optional[Dict[str, List[str]]] = Field(
        None,
        description="Bundled resources: references, scripts, assets"
    )
    
    class Config:
        use_enum_values = True
    
    def get_success_rate(self) -> Optional[float]:
        """Calculate success rate if there are uses."""
        total = self.success_count + self.failure_count
        if total == 0:
            return None
        return self.success_count / total
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Return a summary dict for prompt injection (Level 1 disclosure)."""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "scope": self.scope,
        }
        
        if self.owner_agent_name:
            result["owner_agent"] = self.owner_agent_name
        if self.owner_user_id:
            result["owner_user"] = self.owner_user_id
        if self.involved_agents:
            result["agents"] = self.involved_agents
        
        success_rate = self.get_success_rate()
        if success_rate is not None:
            result["success_rate"] = f"{success_rate * 100:.0f}%"
        
        return result
    
    def to_full_dict(self) -> Dict[str, Any]:
        """Return full dict for Level 2 disclosure."""
        return self.model_dump(exclude={"embedding"})


class SkillShare(BaseModel):
    """Represents a skill sharing relationship."""
    
    skill_id: str = Field(..., description="ID of the shared skill")
    shared_with_user_id: str = Field(..., description="User the skill is shared with")
    shared_by_user_id: str = Field(..., description="User who shared the skill")
    shared_at: int = Field(
        default_factory=now_epoch_ms,
        description="When the skill was shared"
    )


class SkillFeedback(BaseModel):
    """Represents feedback on a skill."""
    
    id: str = Field(default_factory=generate_id)
    skill_id: str = Field(..., description="ID of the skill")
    task_id: str = Field(..., description="Task ID where feedback was given")
    user_id: Optional[str] = Field(None, description="User who gave feedback")
    feedback_type: str = Field(
        ..., 
        description="Type: thumbs_up, thumbs_down, correction, explicit_save, user_edit"
    )
    correction_text: Optional[str] = Field(
        None,
        description="Correction details if feedback_type is correction"
    )
    created_at: int = Field(
        default_factory=now_epoch_ms,
        description="When feedback was given"
    )


class SkillUsage(BaseModel):
    """Tracks when a skill is used."""
    
    id: str = Field(default_factory=generate_id)
    skill_id: str = Field(..., description="ID of the skill used")
    task_id: str = Field(..., description="Task ID where skill was used")
    agent_name: str = Field(..., description="Agent that used the skill")
    user_id: Optional[str] = Field(None, description="User who initiated the task")
    used_at: int = Field(
        default_factory=now_epoch_ms,
        description="When the skill was used"
    )


class LearningQueueItem(BaseModel):
    """An item in the learning queue."""
    
    id: str = Field(default_factory=generate_id)
    task_id: str = Field(..., description="Task ID to learn from")
    agent_name: str = Field(..., description="Agent that completed the task")
    user_id: Optional[str] = Field(None, description="User who initiated the task")
    status: str = Field(
        default="pending",
        description="Status: pending, processing, completed, failed"
    )
    queued_at: int = Field(
        default_factory=now_epoch_ms,
        description="When the item was queued"
    )
    started_at: Optional[int] = Field(
        None,
        description="When processing started"
    )
    completed_at: Optional[int] = Field(
        None,
        description="When processing completed"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if failed"
    )
    retry_count: int = Field(
        default=0,
        description="Number of retry attempts"
    )