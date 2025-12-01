"""
API Router for skill management.

Provides endpoints for:
- Listing and searching skills
- Getting skill details
- Creating and updating skills
- Managing skill sharing
- Submitting feedback
- Import/Export skills
"""

import logging
import re
import yaml
import json
import zipfile
import base64
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from ..dependencies import get_db, get_user_id, get_user_config
from ..shared.types import UserId

log = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response DTOs
# ============================================================================

class SkillStepDTO(BaseModel):
    """A step in a skill procedure."""
    step_number: int
    description: str
    tool_name: Optional[str] = None
    tool_parameters: Optional[dict] = None
    expected_output: Optional[str] = None
    agent_name: Optional[str] = None


class AgentChainNodeDTO(BaseModel):
    """A node in the agent chain."""
    agent_name: str
    order: int
    role: Optional[str] = None
    tools_used: List[str] = Field(default_factory=list)


class SkillCreateRequest(BaseModel):
    """Request to create a new skill."""
    name: str
    description: str
    scope: str = "user"  # user, shared, global
    owner_agent: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    steps: List[SkillStepDTO] = Field(default_factory=list)
    agent_chain: List[AgentChainNodeDTO] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    postconditions: List[str] = Field(default_factory=list)
    metadata: Optional[dict] = None


class SkillUpdateRequest(BaseModel):
    """Request to update a skill."""
    name: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[str] = None
    tags: Optional[List[str]] = None
    steps: Optional[List[SkillStepDTO]] = None
    agent_chain: Optional[List[AgentChainNodeDTO]] = None
    preconditions: Optional[List[str]] = None
    postconditions: Optional[List[str]] = None
    metadata: Optional[dict] = None
    is_active: Optional[bool] = None


class SkillShareRequest(BaseModel):
    """Request to share a skill."""
    target_user_id: Optional[str] = None
    target_agent: Optional[str] = None
    permission: str = "read"  # read, write


class SkillFeedbackRequest(BaseModel):
    """Request to submit feedback on a skill."""
    feedback_type: str  # thumbs_up, thumbs_down, correction, comment
    comment: Optional[str] = None
    correction_data: Optional[dict] = None
    task_id: Optional[str] = None


class SkillResponse(BaseModel):
    """Skill response."""
    id: str
    name: str
    description: str
    type: str
    scope: str
    owner_user_id: Optional[str] = None
    owner_agent: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    steps: List[SkillStepDTO] = Field(default_factory=list)
    agent_chain: List[AgentChainNodeDTO] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    postconditions: List[str] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    usage_count: int = 0
    success_rate: Optional[float] = None
    is_active: bool = True
    created_at: str
    updated_at: str
    metadata: Optional[dict] = None
    markdown_content: Optional[str] = None


class SkillSummaryResponse(BaseModel):
    """Skill summary for listing."""
    id: str
    name: str
    description: str
    type: str
    scope: str
    owner_agent: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    success_rate: Optional[float] = None
    usage_count: int = 0
    is_active: bool = True


class SkillSearchResponse(BaseModel):
    """Search results response."""
    skills: List[SkillSummaryResponse]
    total: int
    page: int
    page_size: int


class SkillFeedbackResponse(BaseModel):
    """Feedback submission response."""
    id: str
    skill_id: str
    feedback_type: str
    created_at: str


# ============================================================================
# Helper Functions
# ============================================================================

def get_skill_service():
    """Get the skill service instance."""
    from ..dependencies import get_skill_service as _get_skill_service
    return _get_skill_service()


def _skill_to_response(skill) -> SkillResponse:
    """Convert a skill entity to response DTO."""
    steps = []
    if skill.tool_steps:
        for i, step in enumerate(skill.tool_steps):
            steps.append(SkillStepDTO(
                step_number=step.sequence_number if hasattr(step, 'sequence_number') else i + 1,
                description=step.action if hasattr(step, 'action') else "",
                tool_name=step.tool_name if hasattr(step, 'tool_name') else None,
                tool_parameters=step.parameters_template if hasattr(step, 'parameters_template') else None,
                expected_output=None,
                agent_name=step.agent_name if hasattr(step, 'agent_name') else None,
            ))
    
    agent_chain = []
    if skill.agent_chain:
        for i, node in enumerate(skill.agent_chain):
            agent_chain.append(AgentChainNodeDTO(
                agent_name=node.agent_name,
                order=i + 1,
                role=node.role if hasattr(node, 'role') else None,
                tools_used=node.tools_used or [],
            ))
    
    success_rate = skill.get_success_rate() if hasattr(skill, 'get_success_rate') else None
    if success_rate is None and (skill.success_count + skill.failure_count) > 0:
        success_rate = skill.success_count / (skill.success_count + skill.failure_count)
    
    # Handle timestamps - they are epoch ms integers in the entity
    created_at_str = ""
    if skill.created_at:
        if isinstance(skill.created_at, int):
            from datetime import datetime, timezone
            created_at_str = datetime.fromtimestamp(skill.created_at / 1000, tz=timezone.utc).isoformat()
        else:
            created_at_str = str(skill.created_at)
    
    updated_at_str = ""
    if skill.updated_at:
        if isinstance(skill.updated_at, int):
            from datetime import datetime, timezone
            updated_at_str = datetime.fromtimestamp(skill.updated_at / 1000, tz=timezone.utc).isoformat()
        else:
            updated_at_str = str(skill.updated_at)
    
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        type=skill.type.value if hasattr(skill.type, 'value') else str(skill.type),
        scope=skill.scope.value if hasattr(skill.scope, 'value') else str(skill.scope),
        owner_user_id=skill.owner_user_id,
        owner_agent=skill.owner_agent_name,  # Entity uses owner_agent_name
        tags=[],  # Entity doesn't have tags field
        steps=steps,
        agent_chain=agent_chain,
        preconditions=[],  # Entity doesn't have preconditions field
        postconditions=[],  # Entity doesn't have postconditions field
        success_count=skill.success_count,
        failure_count=skill.failure_count,
        usage_count=skill.success_count + skill.failure_count,  # Derived from counts
        success_rate=success_rate,
        is_active=True,  # Entity doesn't have is_active field
        created_at=created_at_str,
        updated_at=updated_at_str,
        metadata=None,  # Entity doesn't have metadata field
        markdown_content=skill.markdown_content,  # Include markdown content for skill use
    )


def _skill_to_summary(skill) -> SkillSummaryResponse:
    """Convert a skill entity to summary DTO."""
    success_rate = skill.get_success_rate() if hasattr(skill, 'get_success_rate') else None
    if success_rate is None and (skill.success_count + skill.failure_count) > 0:
        success_rate = skill.success_count / (skill.success_count + skill.failure_count)
    
    return SkillSummaryResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        type=skill.type.value if hasattr(skill.type, 'value') else str(skill.type),
        scope=skill.scope.value if hasattr(skill.scope, 'value') else str(skill.scope),
        owner_agent=skill.owner_agent_name,  # Entity uses owner_agent_name
        tags=[],  # Entity doesn't have tags field
        success_rate=success_rate,
        usage_count=skill.success_count + skill.failure_count,  # Derived from counts
        is_active=True,  # Entity doesn't have is_active field
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/skills", response_model=SkillSearchResponse, tags=["Skills"])
async def list_skills(
    request: FastAPIRequest,
    query: Optional[str] = Query(None, description="Search query"),
    scope: Optional[str] = Query(None, description="Filter by scope (user, shared, global, agent)"),
    agent: Optional[str] = Query(None, description="Filter by agent name"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    type: Optional[str] = Query(None, description="Filter by type (learned, authored)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    List and search skills.
    
    Returns skills accessible to the current user:
    - User's own skills
    - Skills shared with the user
    - Global skills
    - Agent-specific skills (if agent filter provided)
    """
    log_prefix = "[GET /api/v1/skills] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        skill_service = get_skill_service()
        if skill_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Parse tags (not currently used by SkillService but kept for future)
        tag_list = None
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        
        # Map scope string to enum if provided
        scope_enum = None
        if scope:
            from ....services.skill_learning import SkillScope
            scope_map = {
                "user": SkillScope.USER,
                "shared": SkillScope.SHARED,
                "global": SkillScope.GLOBAL,
                "agent": SkillScope.AGENT,
            }
            scope_enum = scope_map.get(scope)
        
        # Map type string to enum if provided
        type_enum = None
        if type:
            from ....services.skill_learning import SkillType
            type_map = {
                "learned": SkillType.LEARNED,
                "authored": SkillType.AUTHORED,
            }
            type_enum = type_map.get(type)
        
        # Search or list skills
        if query:
            # Search returns list of (skill, score) tuples
            results = skill_service.search_skills(
                query=query,
                user_id=user_id,
                agent_name=agent,
                skill_type=type_enum,
                scope=scope_enum,
                include_global=True,
                limit=page_size,
            )
            skills = [skill for skill, _ in results]
        else:
            # Get all skills for the user/agent
            skills = skill_service.get_skills_for_agent(
                agent_name=agent or "OrchestratorAgent",  # Default to orchestrator
                user_id=user_id,
                include_global=True,
                limit=page_size,
            )
        
        # Total is the number of skills returned (pagination not fully supported yet)
        total = len(skills)
        
        return SkillSearchResponse(
            skills=[_skill_to_summary(s) for s in skills],
            total=total,
            page=page,
            page_size=page_size,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError listing skills: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing skills.",
        )


@router.get("/skills/{skill_id}", response_model=SkillResponse, tags=["Skills"])
async def get_skill(
    skill_id: str,
    request: FastAPIRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Get a skill by ID.
    
    Returns the full skill details including steps and agent chain.
    """
    log_prefix = f"[GET /api/v1/skills/{skill_id}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        skill_service = get_skill_service()
        if skill_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        skill = skill_service.get_skill(skill_id)
        
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{skill_id}' not found.",
            )
        
        return _skill_to_response(skill)
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError getting skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while getting the skill.",
        )


@router.post("/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED, tags=["Skills"])
async def create_skill(
    request: FastAPIRequest,
    payload: SkillCreateRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Create a new skill.
    
    Creates a user-authored skill that can be used by agents.
    """
    log_prefix = "[POST /api/v1/skills] "
    log.info("%sRequest from user %s to create skill: %s", log_prefix, user_id, payload.name)
    
    try:
        skill_service = get_skill_service()
        if skill_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        from ....services.skill_learning import SkillType, SkillScope
        
        # Convert steps DTOs to dict format for service
        tool_steps = []
        for step_dto in payload.steps:
            tool_steps.append({
                "step_type": "tool_call",
                "agent_name": step_dto.agent_name or "unknown",
                "tool_name": step_dto.tool_name or "unknown",
                "action": step_dto.description,
                "parameters_template": step_dto.tool_parameters,
                "sequence_number": step_dto.step_number,
            })
        
        # Convert agent chain DTOs to dict format for service
        agent_chain = []
        for node_dto in payload.agent_chain:
            agent_chain.append({
                "agent_name": node_dto.agent_name,
                "task_id": f"task-{node_dto.order}",  # Placeholder task ID
                "role": node_dto.role or "specialist",
                "tools_used": node_dto.tools_used,
            })
        
        # Map scope string to enum
        scope_map = {
            "user": SkillScope.USER,
            "shared": SkillScope.SHARED,
            "global": SkillScope.GLOBAL,
            "agent": SkillScope.AGENT,
        }
        scope = scope_map.get(payload.scope, SkillScope.USER)
        
        # Use the service's create_skill method with individual parameters
        created_skill = skill_service.create_skill(
            name=payload.name,
            description=payload.description,
            skill_type=SkillType.AUTHORED,
            scope=scope,
            owner_agent_name=payload.owner_agent,
            owner_user_id=user_id,
            markdown_content=None,  # Could be added to DTO if needed
            tool_steps=tool_steps if tool_steps else None,
            agent_chain=agent_chain if agent_chain else None,
        )
        
        return _skill_to_response(created_skill)
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError creating skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the skill.",
        )


@router.put("/skills/{skill_id}", response_model=SkillResponse, tags=["Skills"])
async def update_skill(
    skill_id: str,
    request: FastAPIRequest,
    payload: SkillUpdateRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Update a skill.
    
    Only the skill owner can update a skill.
    """
    log_prefix = f"[PUT /api/v1/skills/{skill_id}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        skill_service = get_skill_service()
        if skill_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Get existing skill
        skill = skill_service.get_skill(skill_id)
        
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{skill_id}' not found.",
            )
        
        # Check ownership
        if skill.owner_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to update this skill.",
            )
        
        # Apply updates to the skill object
        updates = payload.model_dump(exclude_unset=True)
        
        if "name" in updates:
            skill.name = updates["name"]
        if "description" in updates:
            skill.description = updates["description"]
        
        # Handle scope conversion
        if "scope" in updates and updates["scope"] is not None:
            from ....services.skill_learning import SkillScope
            scope_map = {
                "user": SkillScope.USER,
                "shared": SkillScope.SHARED,
                "global": SkillScope.GLOBAL,
                "agent": SkillScope.AGENT,
            }
            skill.scope = scope_map.get(updates["scope"], SkillScope.USER)
        
        # Handle steps conversion to tool_steps
        if "steps" in updates and updates["steps"] is not None:
            from ....services.skill_learning import AgentToolStep, StepType
            tool_steps = []
            for step_dto in updates["steps"]:
                tool_steps.append(AgentToolStep(
                    step_type=StepType.TOOL_CALL,
                    agent_name=step_dto.get("agent_name") or "unknown",
                    tool_name=step_dto.get("tool_name") or "unknown",
                    action=step_dto.get("description") or "",
                    parameters_template=step_dto.get("tool_parameters"),
                    sequence_number=step_dto.get("step_number", 1),
                ))
            skill.tool_steps = tool_steps
        
        # Handle agent_chain conversion
        if "agent_chain" in updates and updates["agent_chain"] is not None:
            from ....services.skill_learning import AgentChainNode
            chain = []
            for node_dto in updates["agent_chain"]:
                chain.append(AgentChainNode(
                    agent_name=node_dto["agent_name"],
                    task_id=f"task-{node_dto.get('order', 1)}",
                    role=node_dto.get("role") or "specialist",
                    tools_used=node_dto.get("tools_used", []),
                ))
            skill.agent_chain = chain
        
        # Update timestamp
        from ....services.skill_learning.entities import now_epoch_ms
        skill.updated_at = now_epoch_ms()
        
        updated_skill = skill_service.update_skill(skill)
        
        return _skill_to_response(updated_skill)
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError updating skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the skill.",
        )


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Skills"])
async def delete_skill(
    skill_id: str,
    request: FastAPIRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Delete a skill.
    
    Only the skill owner can delete a skill.
    """
    log_prefix = f"[DELETE /api/v1/skills/{skill_id}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        skill_service = get_skill_service()
        if skill_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Get existing skill
        skill = skill_service.get_skill(skill_id)
        
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{skill_id}' not found.",
            )
        
        # Check ownership
        if skill.owner_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this skill.",
            )
        
        skill_service.delete_skill(skill_id)
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError deleting skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the skill.",
        )


@router.post("/skills/{skill_id}/share", response_model=dict, tags=["Skills"])
async def share_skill(
    skill_id: str,
    request: FastAPIRequest,
    payload: SkillShareRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Share a skill with another user or agent.
    
    Only the skill owner can share a skill.
    """
    log_prefix = f"[POST /api/v1/skills/{skill_id}/share] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        skill_service = get_skill_service()
        if skill_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Get existing skill
        skill = skill_service.get_skill(skill_id)
        
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{skill_id}' not found.",
            )
        
        # Check ownership
        if skill.owner_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to share this skill.",
            )
        
        # Validate target user
        if not payload.target_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_user_id is required for sharing",
            )
        
        # Create share using the correct method signature
        share = skill_service.share_skill(
            skill_id=skill_id,
            shared_with_user_id=payload.target_user_id,
            shared_by_user_id=user_id,
        )
        
        return {
            "message": "Skill shared successfully",
            "skill_id": share.skill_id if share else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError sharing skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while sharing the skill.",
        )


@router.post("/skills/{skill_id}/feedback", response_model=SkillFeedbackResponse, tags=["Skills"])
async def submit_feedback(
    skill_id: str,
    request: FastAPIRequest,
    payload: SkillFeedbackRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Submit feedback on a skill.
    
    Feedback types:
    - thumbs_up: Positive feedback
    - thumbs_down: Negative feedback
    - correction: Suggest corrections to the skill
    - comment: General comment
    """
    log_prefix = f"[POST /api/v1/skills/{skill_id}/feedback] "
    log.info("%sRequest from user %s, type: %s", log_prefix, user_id, payload.feedback_type)
    
    try:
        skill_service = get_skill_service()
        if skill_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Get existing skill
        skill = skill_service.get_skill(skill_id)
        
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{skill_id}' not found.",
            )
        
        # Task ID is required for feedback
        if not payload.task_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="task_id is required for feedback",
            )
        
        # Submit feedback using the correct method signature
        feedback = skill_service.record_feedback(
            skill_id=skill_id,
            task_id=payload.task_id,
            feedback_type=payload.feedback_type,
            user_id=user_id,
            correction_text=payload.comment,
        )
        
        # Handle timestamp - it's epoch ms integer
        created_at_str = ""
        if feedback.created_at:
            if isinstance(feedback.created_at, int):
                created_at_str = datetime.fromtimestamp(feedback.created_at / 1000, tz=timezone.utc).isoformat()
            else:
                created_at_str = str(feedback.created_at)
        
        return SkillFeedbackResponse(
            id=feedback.id,
            skill_id=feedback.skill_id,
            feedback_type=feedback.feedback_type,
            created_at=created_at_str,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError submitting feedback: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while submitting feedback.",
        )


@router.get("/skills/search/semantic", response_model=SkillSearchResponse, tags=["Skills"])
async def semantic_search_skills(
    request: FastAPIRequest,
    query: str = Query(..., description="Search query"),
    agent: Optional[str] = Query(None, description="Filter by agent name"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Semantic search for skills using embeddings.
    
    Uses vector similarity to find skills that match the query semantically,
    even if they don't contain the exact keywords.
    """
    log_prefix = "[GET /api/v1/skills/search/semantic] "
    log.info("%sRequest from user %s, query: %s", log_prefix, user_id, query)
    
    try:
        skill_service = get_skill_service()
        if skill_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        skills = skill_service.semantic_search(
            query=query,
            user_id=user_id,
            agent_name=agent,
            limit=limit,
        )
        
        return SkillSearchResponse(
            skills=[_skill_to_summary(s) for s in skills],
            total=len(skills),
            page=1,
            page_size=limit,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError in semantic search: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during semantic search.",
        )


@router.get("/skills/agent/{agent_name}", response_model=SkillSearchResponse, tags=["Skills"])
async def get_agent_skills(
    agent_name: str,
    request: FastAPIRequest,
    include_global: bool = Query(True, description="Include global skills"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Get skills for a specific agent.
    
    Returns:
    - Agent-specific skills
    - Optionally includes global skills
    """
    log_prefix = f"[GET /api/v1/skills/agent/{agent_name}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        skill_service = get_skill_service()
        if skill_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        skills = skill_service.get_skills_for_agent(
            agent_name=agent_name,
            user_id=user_id,
            include_global=include_global,
            limit=page_size,
        )
        
        # Total is the number of skills returned (pagination not fully supported yet)
        total = len(skills)
        
        return SkillSearchResponse(
            skills=[_skill_to_summary(s) for s in skills],
            total=total,
            page=page,
            page_size=page_size,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError getting agent skills: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while getting agent skills.",
        )


# ============================================================================
# Import/Export Endpoints
# ============================================================================

class SkillExportResponse(BaseModel):
    """Skill export data."""
    version: str = "1.0"
    exported_at: int
    skill: dict


class SkillImportRequest(BaseModel):
    """Request to import a skill from markdown content."""
    markdown_content: str
    scope: str = "user"  # user, shared, global, agent
    owner_agent: Optional[str] = None


class SkillImportResponse(BaseModel):
    """Response after importing a skill."""
    skill_id: str
    name: str
    message: str
    warnings: List[str] = Field(default_factory=list)
    references_count: int = 0
    scripts_count: int = 0
    assets_count: int = 0


def _parse_skill_markdown(content: str) -> dict:
    """
    Parse a .SKILL.md file content into skill data.
    
    Expected format:
    ---
    name: skill-name
    description: Skill description
    summary: Short summary
    involved_agents:
      - Agent1
      - Agent2
    complexity_score: 30
    ---
    
    # Skill Title
    
    Markdown content...
    """
    # Split frontmatter from content
    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
    
    if not frontmatter_match:
        raise ValueError("Invalid skill format: missing YAML frontmatter (---)")
    
    frontmatter_str = frontmatter_match.group(1)
    markdown_body = frontmatter_match.group(2).strip()
    
    try:
        frontmatter = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML frontmatter: {e}")
    
    if not isinstance(frontmatter, dict):
        raise ValueError("Invalid frontmatter: expected a YAML dictionary")
    
    # Validate required fields
    if not frontmatter.get("name"):
        raise ValueError("Missing required field: name")
    if not frontmatter.get("description"):
        raise ValueError("Missing required field: description")
    
    return {
        "name": frontmatter.get("name"),
        "description": frontmatter.get("description"),
        "summary": frontmatter.get("summary"),
        "involved_agents": frontmatter.get("involved_agents", []),
        "complexity_score": frontmatter.get("complexity_score"),
        "markdown_content": markdown_body,
        "metadata": {
            k: v for k, v in frontmatter.items()
            if k not in ["name", "description", "summary", "involved_agents", "complexity_score"]
        }
    }


def _skill_to_markdown(skill) -> str:
    """
    Convert a skill entity to .SKILL.md format.
    """
    # Build frontmatter
    frontmatter = {
        "name": skill.name,
        "description": skill.description,
    }
    
    if skill.summary:
        frontmatter["summary"] = skill.summary
    
    # Add involved agents from agent_chain
    if skill.agent_chain:
        frontmatter["involved_agents"] = [node.agent_name for node in skill.agent_chain]
    elif skill.owner_agent_name:
        frontmatter["involved_agents"] = [skill.owner_agent_name]
    
    if skill.complexity_score:
        frontmatter["complexity_score"] = skill.complexity_score
    
    # Build markdown content
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    # Use existing markdown content or generate from steps
    if skill.markdown_content:
        body = skill.markdown_content
    else:
        # Generate markdown from steps
        body = f"# {skill.name}\n\n{skill.description}\n"
        
        if skill.tool_steps:
            body += "\n## Steps\n\n"
            for step in skill.tool_steps:
                step_num = step.sequence_number if hasattr(step, 'sequence_number') else 1
                action = step.action if hasattr(step, 'action') else ""
                body += f"{step_num}. {action}\n"
    
    return f"---\n{yaml_str}---\n\n{body}"


def _parse_skill_zip(zip_buffer: BytesIO) -> Dict[str, Any]:
    """
    Parse a Skill Package ZIP file.
    
    A skill package is a folder containing:
    - SKILL.md: Main skill file with YAML frontmatter for metadata and instructions
    - scripts/: Executable code (Python scripts, shell scripts, etc.)
    - resources/: Data files, templates, and other supporting files
    
    Expected structure:
    skill-name/
    ├── SKILL.md              (required - instructions with YAML frontmatter)
    ├── scripts/              (optional - executable code)
    │   └── *.py, *.sh files
    └── resources/            (optional - data files, templates)
        └── any files
    
    Also supports legacy 'references/' and 'assets/' directories.
    
    Returns dict with:
    - skill_data: parsed SKILL.md data
    - scripts: dict of filename -> content
    - resources: dict of filename -> content (text) or base64 (binary)
    """
    try:
        with zipfile.ZipFile(zip_buffer, 'r') as zip_ref:
            namelist = zip_ref.namelist()
            
            # Find SKILL.md - could be at root or in a subdirectory
            skill_md_path = None
            base_dir = ""
            
            for name in namelist:
                if name.endswith('SKILL.md'):
                    skill_md_path = name
                    # Get base directory (everything before SKILL.md)
                    base_dir = name.rsplit('SKILL.md', 1)[0]
                    break
            
            if not skill_md_path:
                raise ValueError("Invalid skill ZIP: missing SKILL.md file")
            
            # Read and parse SKILL.md
            skill_md_content = zip_ref.read(skill_md_path).decode('utf-8')
            skill_data = _parse_skill_markdown(skill_md_content)
            
            # Read bundled resources
            scripts = {}
            resources = {}
            
            for name in namelist:
                # Skip directories and SKILL.md itself
                if name.endswith('/') or name == skill_md_path:
                    continue
                
                # Get relative path from base directory
                if base_dir and name.startswith(base_dir):
                    rel_path = name[len(base_dir):]
                else:
                    rel_path = name
                
                # Categorize by directory
                # Support both 'scripts/' and legacy naming
                if rel_path.startswith('scripts/'):
                    filename = rel_path[len('scripts/'):]
                    if filename:
                        try:
                            scripts[filename] = zip_ref.read(name).decode('utf-8')
                        except UnicodeDecodeError:
                            log.warning(f"Skipping non-text script file: {filename}")
                
                # Support 'resources/', 'references/', and 'assets/' directories
                elif rel_path.startswith('resources/') or rel_path.startswith('references/') or rel_path.startswith('assets/'):
                    # Extract directory prefix
                    dir_prefix = rel_path.split('/')[0] + '/'
                    filename = rel_path[len(dir_prefix):]
                    if filename:
                        try:
                            resources[filename] = zip_ref.read(name).decode('utf-8')
                        except UnicodeDecodeError:
                            # Binary files stored as base64
                            resources[filename] = base64.b64encode(zip_ref.read(name)).decode('ascii')
            
            return {
                "skill_data": skill_data,
                "scripts": scripts,
                "resources": resources,
            }
            
    except zipfile.BadZipFile:
        raise ValueError("Invalid ZIP file")


def _create_skill_zip(skill, scripts: Dict[str, str] = None,
                      resources: Dict[str, Any] = None) -> BytesIO:
    """
    Create a Skill Package ZIP file from a skill.
    
    Structure:
    skill-name/
    ├── SKILL.md              (instructions with YAML frontmatter)
    ├── scripts/              (executable code)
    └── resources/            (data files, templates)
    """
    zip_buffer = BytesIO()
    
    # Sanitize skill name for directory
    safe_name = re.sub(r'[^\w\-]', '-', skill.name)
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add SKILL.md (main skill file with YAML frontmatter)
        skill_md_content = _skill_to_markdown(skill)
        zip_file.writestr(f'{safe_name}/SKILL.md', skill_md_content)
        
        # Add scripts (executable code)
        if scripts:
            for filename, content in scripts.items():
                zip_file.writestr(f'{safe_name}/scripts/{filename}', content)
        
        # Add resources (data files, templates)
        if resources:
            for filename, content in resources.items():
                if isinstance(content, str):
                    # Check if it's base64 encoded binary
                    try:
                        # Try to decode as base64
                        decoded = base64.b64decode(content)
                        zip_file.writestr(f'{safe_name}/resources/{filename}', decoded)
                    except Exception:
                        # It's plain text
                        zip_file.writestr(f'{safe_name}/resources/{filename}', content)
                else:
                    zip_file.writestr(f'{safe_name}/resources/{filename}', content)
    
    zip_buffer.seek(0)
    return zip_buffer


@router.get("/skills/{skill_id}/export", tags=["Skills"])
async def export_skill(
    skill_id: str,
    request: FastAPIRequest,
    format: str = Query("zip", description="Export format: zip, json, or markdown"),
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Export a skill.
    
    Formats:
    - zip: Skill Package ZIP format (folder with SKILL.md + scripts/ + resources/)
    - json: JSON export with metadata
    - markdown: SKILL.md file only
    """
    log_prefix = f"[GET /api/v1/skills/{skill_id}/export] "
    log.info("%sRequest from user %s, format: %s", log_prefix, user_id, format)
    
    try:
        skill_service = get_skill_service()
        if skill_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        skill = skill_service.get_skill(skill_id)
        
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{skill_id}' not found.",
            )
        
        if format == "zip":
            # Export as Skill Package ZIP
            # Get bundled resources if available from skill entity
            scripts = None
            resources = None
            
            if skill.bundled_resources:
                scripts = skill.bundled_resources.get('scripts', {})
                # Combine references, assets, and resources into resources
                resources = {}
                for key in ['resources', 'references', 'assets']:
                    if skill.bundled_resources.get(key):
                        resources.update(skill.bundled_resources[key])
            
            zip_buffer = _create_skill_zip(skill, scripts, resources)
            safe_name = re.sub(r'[^\w\-]', '-', skill.name)
            filename = f"{safe_name}.skill.zip"
            
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                }
            )
            
        elif format == "markdown":
            # Export as SKILL.md file only
            markdown_content = _skill_to_markdown(skill)
            filename = f"{skill.name}.SKILL.md"
            
            return StreamingResponse(
                BytesIO(markdown_content.encode("utf-8")),
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                }
            )
        else:
            # Export as JSON
            skill_response = _skill_to_response(skill)
            export_data = {
                "version": "1.0",
                "exported_at": int(datetime.now(timezone.utc).timestamp() * 1000),
                "skill": skill_response.model_dump(),
            }
            return export_data
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError exporting skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while exporting the skill.",
        )


@router.post("/skills/import", response_model=SkillImportResponse, tags=["Skills"])
async def import_skill(
    request: FastAPIRequest,
    payload: SkillImportRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Import a skill from markdown content.
    
    Accepts .SKILL.md format with YAML frontmatter.
    """
    log_prefix = "[POST /api/v1/skills/import] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        skill_service = get_skill_service()
        if skill_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Parse the markdown content
        try:
            skill_data = _parse_skill_markdown(payload.markdown_content)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        
        from ....services.skill_learning import SkillType, SkillScope
        
        # Map scope string to enum
        scope_map = {
            "user": SkillScope.USER,
            "shared": SkillScope.SHARED,
            "global": SkillScope.GLOBAL,
            "agent": SkillScope.AGENT,
        }
        scope = scope_map.get(payload.scope, SkillScope.USER)
        
        warnings = []
        
        # Create the skill
        created_skill = skill_service.create_skill(
            name=skill_data["name"],
            description=skill_data["description"],
            skill_type=SkillType.AUTHORED,
            scope=scope,
            owner_agent_name=payload.owner_agent or (skill_data["involved_agents"][0] if skill_data["involved_agents"] else None),
            owner_user_id=user_id,
            markdown_content=skill_data["markdown_content"],
            summary=skill_data.get("summary"),
        )
        
        return SkillImportResponse(
            skill_id=created_skill.id,
            name=created_skill.name,
            message="Skill imported successfully",
            warnings=warnings,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError importing skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while importing the skill.",
        )


@router.post("/skills/import/file", response_model=SkillImportResponse, tags=["Skills"])
async def import_skill_file(
    request: FastAPIRequest,
    file: UploadFile = File(..., description="Skill file (.zip, .SKILL.md, or .json)"),
    scope: str = Query("user", description="Skill scope: user, shared, global, agent"),
    owner_agent: Optional[str] = Query(None, description="Owner agent name"),
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Import a skill from an uploaded file.
    
    Accepts:
    - .zip files (skill package with SKILL.md + scripts/ + resources/)
    - .SKILL.md files (single skill file)
    - .json files (exported skill format)
    """
    log_prefix = "[POST /api/v1/skills/import/file] "
    log.info("%sRequest from user %s, filename: %s", log_prefix, user_id, file.filename)
    
    try:
        skill_service = get_skill_service()
        if skill_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Read file content
        content = await file.read()
        
        # Determine file type
        filename = file.filename or ""
        is_zip = filename.endswith(".zip")
        is_markdown = filename.endswith(".SKILL.md") or filename.endswith(".md")
        is_json = filename.endswith(".json")
        
        if not is_zip and not is_markdown and not is_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Please upload a .zip, .SKILL.md, or .json file.",
            )
        
        from ....services.skill_learning import SkillType, SkillScope
        
        # Map scope string to enum
        scope_map = {
            "user": SkillScope.USER,
            "shared": SkillScope.SHARED,
            "global": SkillScope.GLOBAL,
            "agent": SkillScope.AGENT,
        }
        scope_enum = scope_map.get(scope, SkillScope.USER)
        
        warnings = []
        references_count = 0
        scripts_count = 0
        assets_count = 0
        
        if is_zip:
            # Parse ZIP file (skill package format)
            try:
                zip_data = _parse_skill_zip(BytesIO(content))
                skill_data = zip_data["skill_data"]
                references = zip_data.get("references", {})
                scripts = zip_data.get("scripts", {})
                assets = zip_data.get("assets", {})
                
                references_count = len(references)
                scripts_count = len(scripts)
                assets_count = len(assets)
                
                # Build bundled_resources dict
                bundled_resources = {}
                if references:
                    bundled_resources["references"] = references
                if scripts:
                    bundled_resources["scripts"] = scripts
                if assets:
                    bundled_resources["assets"] = assets
                
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                )
            
            # Create the skill with bundled resources
            created_skill = skill_service.create_skill(
                name=skill_data["name"],
                description=skill_data["description"],
                skill_type=SkillType.AUTHORED,
                scope=scope_enum,
                owner_agent_name=owner_agent or (skill_data["involved_agents"][0] if skill_data.get("involved_agents") else None),
                owner_user_id=user_id,
                markdown_content=skill_data["markdown_content"],
                summary=skill_data.get("summary"),
                bundled_resources=bundled_resources if bundled_resources else None,
            )
            
            if references_count > 0:
                warnings.append(f"Imported {references_count} reference file(s)")
            if scripts_count > 0:
                warnings.append(f"Imported {scripts_count} script file(s)")
            if assets_count > 0:
                warnings.append(f"Imported {assets_count} asset file(s)")
                
        elif is_markdown:
            content_str = content.decode("utf-8")
            # Parse markdown content
            try:
                skill_data = _parse_skill_markdown(content_str)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                )
            
            # Create the skill
            created_skill = skill_service.create_skill(
                name=skill_data["name"],
                description=skill_data["description"],
                skill_type=SkillType.AUTHORED,
                scope=scope_enum,
                owner_agent_name=owner_agent or (skill_data["involved_agents"][0] if skill_data.get("involved_agents") else None),
                owner_user_id=user_id,
                markdown_content=skill_data["markdown_content"],
                summary=skill_data.get("summary"),
            )
        else:
            content_str = content.decode("utf-8")
            # Parse JSON content
            try:
                json_data = json.loads(content_str)
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid JSON: {e}",
                )
            
            # Validate JSON format
            if "skill" not in json_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid export format: missing 'skill' field",
                )
            
            skill_json = json_data["skill"]
            
            # Create the skill from JSON data
            created_skill = skill_service.create_skill(
                name=skill_json.get("name"),
                description=skill_json.get("description"),
                skill_type=SkillType.AUTHORED,
                scope=scope_enum,
                owner_agent_name=owner_agent or skill_json.get("owner_agent"),
                owner_user_id=user_id,
                markdown_content=skill_json.get("markdown_content"),
            )
        
        return SkillImportResponse(
            skill_id=created_skill.id,
            name=created_skill.name,
            message="Skill imported successfully",
            warnings=warnings,
            references_count=references_count,
            scripts_count=scripts_count,
            assets_count=assets_count,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError importing skill file: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while importing the skill file.",
        )


@router.post("/skills/sync", response_model=dict, tags=["Skills"])
async def sync_static_skills(
    request: FastAPIRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Sync static skills from the filesystem.
    
    Scans the configured skills directory and imports any new .SKILL.md files.
    """
    log_prefix = "[POST /api/v1/skills/sync] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        skill_service = get_skill_service()
        if skill_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Trigger a sync of static skills
        if hasattr(skill_service, 'sync_static_skills'):
            count = skill_service.sync_static_skills()
        else:
            # Fallback: reload static skills
            count = skill_service.load_static_skills() if hasattr(skill_service, 'load_static_skills') else 0
        
        return {
            "message": f"Synced {count} static skills",
            "count": count,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError syncing static skills: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while syncing static skills.",
        )
