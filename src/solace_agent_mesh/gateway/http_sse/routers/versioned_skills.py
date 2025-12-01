
"""
API Router for versioned skill management.

Provides endpoints for:
- Listing and searching skill groups
- Getting skill group details with versions
- Creating new skills (group + initial version)
- Creating new versions
- Rollback to previous versions
- Managing skill sharing
"""

import logging
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Request as FastAPIRequest
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from ..dependencies import get_db, get_user_id
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
    agent_name: Optional[str] = None


class AgentChainNodeDTO(BaseModel):
    """A node in the agent chain."""
    agent_name: str
    order: int
    role: Optional[str] = None
    tools_used: List[str] = Field(default_factory=list)


class SkillVersionDTO(BaseModel):
    """Skill version response."""
    id: str
    group_id: str
    version: int
    description: str
    markdown_content: Optional[str] = None
    summary: Optional[str] = None
    steps: List[SkillStepDTO] = Field(default_factory=list)
    agent_chain: List[AgentChainNodeDTO] = Field(default_factory=list)
    source_task_id: Optional[str] = None
    related_task_ids: List[str] = Field(default_factory=list)
    involved_agents: List[str] = Field(default_factory=list)
    complexity_score: int = 0
    created_by_user_id: Optional[str] = None
    creation_reason: Optional[str] = None
    created_at: str


class SkillGroupDTO(BaseModel):
    """Skill group response."""
    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    type: str
    scope: str
    owner_agent_name: Optional[str] = None
    owner_user_id: Optional[str] = None
    is_archived: bool = False
    version_count: int = 0
    success_rate: Optional[float] = None
    created_at: str
    updated_at: str
    production_version: Optional[SkillVersionDTO] = None


class SkillGroupSummaryDTO(BaseModel):
    """Skill group summary for listing."""
    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    type: str
    scope: str
    owner_agent_name: Optional[str] = None
    is_archived: bool = False
    version_count: int = 0
    success_rate: Optional[float] = None
    production_version_id: Optional[str] = None


class SkillGroupListResponse(BaseModel):
    """List response for skill groups."""
    skills: List[SkillGroupSummaryDTO]
    total: int
    page: int
    page_size: int


class CreateSkillRequest(BaseModel):
    """Request to create a new skill."""
    name: str
    description: str
    scope: str = "user"  # user, shared, global, agent
    category: Optional[str] = None
    owner_agent: Optional[str] = None
    markdown_content: Optional[str] = None
    summary: Optional[str] = None
    steps: List[SkillStepDTO] = Field(default_factory=list)
    agent_chain: List[AgentChainNodeDTO] = Field(default_factory=list)


class CreateVersionRequest(BaseModel):
    """Request to create a new version."""
    description: str
    creation_reason: str
    markdown_content: Optional[str] = None
    summary: Optional[str] = None
    steps: List[SkillStepDTO] = Field(default_factory=list)
    agent_chain: List[AgentChainNodeDTO] = Field(default_factory=list)
    set_as_production: bool = True


class RollbackRequest(BaseModel):
    """Request to rollback to a version."""
    version_id: str


class ShareSkillRequest(BaseModel):
    """Request to share a skill."""
    target_user_id: str
    role: str = "viewer"  # viewer, editor


# ============================================================================
# Helper Functions
# ============================================================================

def get_versioned_skill_service():
    """Get the versioned skill service instance."""
    from ..dependencies import get_versioned_skill_service as _get_service
    return _get_service()


def _epoch_to_iso(epoch_ms: int) -> str:
    """Convert epoch milliseconds to ISO string."""
    if not epoch_ms:
        return ""
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).isoformat()


def _version_to_dto(version) -> SkillVersionDTO:
    """Convert a SkillVersion entity to DTO."""
    steps = []
    if version.tool_steps:
        for i, step in enumerate(version.tool_steps):
            steps.append(SkillStepDTO(
                step_number=step.sequence_number if hasattr(step, 'sequence_number') else i + 1,
                description=step.action if hasattr(step, 'action') else "",
                tool_name=step.tool_name if hasattr(step, 'tool_name') else None,
                tool_parameters=step.parameters_template if hasattr(step, 'parameters_template') else None,
                agent_name=step.agent_name if hasattr(step, 'agent_name') else None,
            ))
    
    agent_chain = []
    if version.agent_chain:
        for i, node in enumerate(version.agent_chain):
            agent_chain.append(AgentChainNodeDTO(
                agent_name=node.agent_name,
                order=i + 1,
                role=node.role if hasattr(node, 'role') else None,
                tools_used=node.tools_used or [],
            ))
    
    return SkillVersionDTO(
        id=version.id,
        group_id=version.group_id,
        version=version.version,
        description=version.description,
        markdown_content=version.markdown_content,
        summary=version.summary,
        steps=steps,
        agent_chain=agent_chain,
        source_task_id=version.source_task_id,
        related_task_ids=version.related_task_ids or [],
        involved_agents=version.involved_agents or [],
        complexity_score=version.complexity_score or 0,
        created_by_user_id=version.created_by_user_id,
        creation_reason=version.creation_reason,
        created_at=_epoch_to_iso(version.created_at),
    )


def _group_to_dto(group, include_production: bool = True) -> SkillGroupDTO:
    """Convert a SkillGroup entity to DTO."""
    production_version = None
    if include_production and group.production_version:
        production_version = _version_to_dto(group.production_version)
    
    return SkillGroupDTO(
        id=group.id,
        name=group.name,
        description=group.description,
        category=group.category,
        type=group.type.value if hasattr(group.type, 'value') else str(group.type),
        scope=group.scope.value if hasattr(group.scope, 'value') else str(group.scope),
        owner_agent_name=group.owner_agent_name,
        owner_user_id=group.owner_user_id,
        is_archived=group.is_archived,
        version_count=group.version_count,
        success_rate=group.get_success_rate() if hasattr(group, 'get_success_rate') else None,
        created_at=_epoch_to_iso(group.created_at),
        updated_at=_epoch_to_iso(group.updated_at),
        production_version=production_version,
    )


def _group_to_summary(group) -> SkillGroupSummaryDTO:
    """Convert a SkillGroup entity to summary DTO."""
    return SkillGroupSummaryDTO(
        id=group.id,
        name=group.name,
        description=group.description,
        category=group.category,
        type=group.type.value if hasattr(group.type, 'value') else str(group.type),
        scope=group.scope.value if hasattr(group.scope, 'value') else str(group.scope),
        owner_agent_name=group.owner_agent_name,
        is_archived=group.is_archived,
        version_count=group.version_count,
        success_rate=group.get_success_rate() if hasattr(group, 'get_success_rate') else None,
        production_version_id=group.production_version_id,
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/skills", response_model=SkillGroupListResponse, tags=["Skills"])
async def list_skills(
    request: FastAPIRequest,
    query: Optional[str] = Query(None, description="Search query"),
    scope: Optional[str] = Query(None, description="Filter by scope"),
    agent: Optional[str] = Query(None, description="Filter by agent name"),
    type: Optional[str] = Query(None, description="Filter by type"),
    include_archived: bool = Query(False, description="Include archived skills"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    List skill groups with optional filters.
    
    Returns skill groups (not individual versions) accessible to the current user.
    
    Note: Returns empty list if skill learning service is not configured.
    """
    log_prefix = "[GET /api/v1/skills] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            # Return empty results when skill service is not configured
            log.debug("%sSkill service not configured, returning empty results", log_prefix)
            return SkillGroupListResponse(
                skills=[],
                total=0,
                page=page,
                page_size=page_size,
            )
        
        from ....services.skill_learning import SkillScope, SkillType
        
        # Map scope string to enum
        scope_enum = None
        if scope:
            scope_map = {
                "user": SkillScope.USER,
                "shared": SkillScope.SHARED,
                "global": SkillScope.GLOBAL,
                "agent": SkillScope.AGENT,
            }
            scope_enum = scope_map.get(scope)
        
        # Map type string to enum
        type_enum = None
        if type:
            type_map = {
                "learned": SkillType.LEARNED,
                "authored": SkillType.AUTHORED,
            }
            type_enum = type_map.get(type)
        
        if query:
            # Search
            results = service.search_skills(
                query=query,
                agent_name=agent,
                user_id=user_id,
                scope=scope_enum,
                skill_type=type_enum,
                include_global=True,
                limit=page_size,
            )
            groups = [group for group, _ in results]
        else:
            # List
            groups = service.list_skills(
                agent_name=agent,
                user_id=user_id,
                scope=scope_enum,
                skill_type=type_enum,
                include_archived=include_archived,
                include_global=True,
                limit=page_size,
                offset=(page - 1) * page_size,
            )
        
        return SkillGroupListResponse(
            skills=[_group_to_summary(g) for g in groups],
            total=len(groups),
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


@router.get("/skills/{group_id}", response_model=SkillGroupDTO, tags=["Skills"])
async def get_skill(
    group_id: str,
    request: FastAPIRequest,
    include_versions: bool = Query(False, description="Include all versions"),
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Get a skill group by ID.
    
    Returns the skill group with its production version.
    """
    log_prefix = f"[GET /api/v1/skills/{group_id}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        group = service.get_skill(group_id, include_versions=include_versions)
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{group_id}' not found.",
            )
        
        return _group_to_dto(group)
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError getting skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while getting the skill.",
        )


@router.post("/skills", response_model=SkillGroupDTO, status_code=status.HTTP_201_CREATED, tags=["Skills"])
async def create_skill(
    request: FastAPIRequest,
    payload: CreateSkillRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Create a new skill.
    
    Creates a skill group with an initial version (v1).
    """
    log_prefix = "[POST /api/v1/skills] "
    log.info("%sRequest from user %s to create skill: %s", log_prefix, user_id, payload.name)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        from ....services.skill_learning import SkillType, SkillScope, AgentChainNode, AgentToolStep
        
        # Map scope string to enum
        scope_map = {
            "user": SkillScope.USER,
            "shared": SkillScope.SHARED,
            "global": SkillScope.GLOBAL,
            "agent": SkillScope.AGENT,
        }
        scope = scope_map.get(payload.scope, SkillScope.USER)
        
        # Convert steps DTOs to entities
        tool_steps = None
        if payload.steps:
            tool_steps = [
                AgentToolStep(
                    step_type="tool_call",
                    agent_name=step.agent_name or "unknown",
                    tool_name=step.tool_name or "unknown",
                    action=step.description,
                    parameters_template=step.tool_parameters,
                    sequence_number=step.step_number,
                )
                for step in payload.steps
            ]
        
        # Convert agent chain DTOs to entities
        agent_chain = None
        if payload.agent_chain:
            agent_chain = [
                AgentChainNode(
                    agent_name=node.agent_name,
                    task_id=f"task-{node.order}",
                    role=node.role or "specialist",
                    tools_used=node.tools_used,
                )
                for node in payload.agent_chain
            ]
        
        group = service.create_skill(
            name=payload.name,
            description=payload.description,
            skill_type=SkillType.AUTHORED,
            scope=scope,
            category=payload.category,
            owner_agent_name=payload.owner_agent,
            owner_user_id=user_id,
            markdown_content=payload.markdown_content,
            tool_steps=tool_steps,
            agent_chain=agent_chain,
            summary=payload.summary,
            created_by_user_id=user_id,
        )
        
        return _group_to_dto(group)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError creating skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the skill.",
        )


@router.delete("/skills/{group_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Skills"])
async def delete_skill(
    group_id: str,
    request: FastAPIRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Delete a skill group (and all its versions).
    
    Only the skill owner can delete a skill.
    """
    log_prefix = f"[DELETE /api/v1/skills/{group_id}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        group = service.get_skill(group_id)
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{group_id}' not found.",
            )
        
        # Check ownership
        if group.owner_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this skill.",
            )
        
        service.delete_skill(group_id)
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError deleting skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the skill.",
        )


# ============================================================================
# Version Endpoints
# ============================================================================

@router.get("/skills/{group_id}/versions", response_model=List[SkillVersionDTO], tags=["Skills"])
async def list_versions(
    group_id: str,
    request: FastAPIRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    List all versions of a skill.
    
    Returns versions ordered by version number descending (newest first).
    """
    log_prefix = f"[GET /api/v1/skills/{group_id}/versions] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        group = service.get_skill(group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{group_id}' not found.",
            )
        
        versions = service.list_versions(group_id)
        return [_version_to_dto(v) for v in versions]
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError listing versions: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing versions.",
        )


@router.get("/skills/{group_id}/versions/{version_id}", response_model=SkillVersionDTO, tags=["Skills"])
async def get_version(
    group_id: str,
    version_id: str,
    request: FastAPIRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Get a specific version of a skill.
    """
    log_prefix = f"[GET /api/v1/skills/{group_id}/versions/{version_id}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        version = service.get_version(version_id)
        
        if not version or version.group_id != group_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version '{version_id}' not found.",
            )
        
        return _version_to_dto(version)
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError getting version: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while getting the version.",
        )


@router.post("/skills/{group_id}/versions", response_model=SkillVersionDTO, status_code=status.HTTP_201_CREATED, tags=["Skills"])
async def create_version(
    group_id: str,
    request: FastAPIRequest,
    payload: CreateVersionRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Create a new version of a skill.
    
    Only users with edit permission can create versions.
    """
    log_prefix = f"[POST /api/v1/skills/{group_id}/versions] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Check permission
        if not service.can_user_edit(group_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to create versions for this skill.",
            )
        
        from ....services.skill_learning import AgentChainNode, AgentToolStep
        
        # Convert steps DTOs to entities
        tool_steps = None
        if payload.steps:
            tool_steps = [
                AgentToolStep(
                    step_type="tool_call",
                    agent_name=step.agent_name or "unknown",
                    tool_name=step.tool_name or "unknown",
                    action=step.description,
                    parameters_template=step.tool_parameters,
                    sequence_number=step.step_number,
                )
                for step in payload.steps
            ]
        
        # Convert agent chain DTOs to entities
        agent_chain = None
        if payload.agent_chain:
            agent_chain = [
                AgentChainNode(
                    agent_name=node.agent_name,
                    task_id=f"task-{node.order}",
                    role=node.role or "specialist",
                    tools_used=node.tools_used,
                )
                for node in payload.agent_chain
            ]
        
        version = service.create_version(
            group_id=group_id,
            description=payload.description,
            creation_reason=payload.creation_reason,
            created_by_user_id=user_id,
            markdown_content=payload.markdown_content,
            tool_steps=tool_steps,
            agent_chain=agent_chain,
            summary=payload.summary,
            set_as_production=payload.set_as_production,
        )
        
        return _version_to_dto(version)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError creating version: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the version.",
        )


@router.post("/skills/{group_id}/rollback", response_model=SkillGroupDTO, tags=["Skills"])
async def rollback_skill(
    group_id: str,
    request: FastAPIRequest,
    payload: RollbackRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Rollback a skill to a previous version.
    
    This changes the production version pointer without deleting any versions.
    """
    log_prefix = f"[POST /api/v1/skills/{group_id}/rollback] "
    log.info("%sRequest from user %s to rollback to %s", log_prefix, user_id, payload.version_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        # Check permission
        if not service.can_user_edit(group_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to rollback this skill.",
            )
        
        group = service.rollback_to_version(group_id, payload.version_id)
        return _group_to_dto(group)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError rolling back skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while rolling back the skill.",
        )


# ============================================================================
# Sharing Endpoints
# ============================================================================

@router.post("/skills/{group_id}/share", response_model=dict, tags=["Skills"])
async def share_skill(
    group_id: str,
    request: FastAPIRequest,
    payload: ShareSkillRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Share a skill with another user.
    
    Only the skill owner can share a skill.
    """
    log_prefix = f"[POST /api/v1/skills/{group_id}/share] "
    log.info("%sRequest from user %s to share with %s", log_prefix, user_id, payload.target_user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        group = service.get_skill(group_id)
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{group_id}' not found.",
            )
        
        # Check ownership
        if group.owner_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to share this skill.",
            )
        
        from ....services.skill_learning import SkillGroupRole
        
        role_map = {
            "viewer": SkillGroupRole.VIEWER,
            "editor": SkillGroupRole.EDITOR,
        }
        role = role_map.get(payload.role, SkillGroupRole.VIEWER)
        
        service.share_skill(
            group_id=group_id,
            shared_with_user_id=payload.target_user_id,
            shared_by_user_id=user_id,
            role=role,
        )
        
        return {"message": "Skill shared successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError sharing skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while sharing the skill.",
        )


@router.delete("/skills/{group_id}/share/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Skills"])
async def unshare_skill(
    group_id: str,
    target_user_id: str,
    request: FastAPIRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
):
    """
    Remove a user's access to a skill.
    
    Only the skill owner can unshare a skill.
    """
    log_prefix = f"[DELETE /api/v1/skills/{group_id}/share/{target_user_id}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Skill learning service is not available",
            )
        
        group = service.get_skill(group_id)
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill with ID '{group_id}' not found.",
            )
        
        # Check ownership
        if group.owner_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to unshare this skill.",
            )
        
        service.unshare_skill(group_id, target_user_id)
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("%sError unsharing skill: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while unsharing the skill.",
        )


# ============================================================================
# Agent-specific Endpoints
# ============================================================================

@router.get("/skills/agent/{agent_name}", response_model=SkillGroupListResponse, tags=["Skills"])
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
    Get skills available to a specific agent.
    
    Returns agent-specific skills and optionally global skills.
    
    Note: Returns empty list if skill learning service is not configured.
    """
    log_prefix = f"[GET /api/v1/skills/agent/{agent_name}] "
    log.info("%sRequest from user %s", log_prefix, user_id)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            # Return empty results when skill service is not configured
            log.debug("%sSkill service not configured, returning empty results", log_prefix)
            return SkillGroupListResponse(
                skills=[],
                total=0,
                page=page,
                page_size=page_size,
            )
        
        groups = service.get_skills_for_agent(
            agent_name=agent_name,
            user_id=user_id,
            include_global=include_global,
            limit=page_size,
        )
        
        return SkillGroupListResponse(
            skills=[_group_to_summary(g) for g in groups],
            total=len(groups),
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
# Search Endpoints
# ============================================================================

@router.get("/skills/search/semantic", response_model=SkillGroupListResponse, tags=["Skills"])
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
    
    Uses vector similarity to find skills that match the query semantically.
    
    Note: Returns empty list if skill learning service is not configured.
    """
    log_prefix = "[GET /api/v1/skills/search/semantic] "
    log.info("%sRequest from user %s, query: %s", log_prefix, user_id, query)
    
    try:
        service = get_versioned_skill_service()
        if service is None:
            # Return empty results when skill service is not configured
            log.debug("%sSkill service not configured, returning empty results", log_prefix)
            return SkillGroupListResponse(
                skills=[],
                total=0,
                page=1,
                page_size=limit,
            )
        
        results = service.semantic_search(
            query=query,
            agent_name=agent,
            user_id=user_id,
            limit=limit,
        )
        
        groups = [group for group, _ in results]
        
        return SkillGroupListResponse(
            skills=[_group_to_summary(g) for g in groups],
            total=len(groups),
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
