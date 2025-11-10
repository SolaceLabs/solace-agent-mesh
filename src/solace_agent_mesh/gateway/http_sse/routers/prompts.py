"""
Prompts API router for prompt library feature.
"""

import uuid
from typing import List, Optional, Dict, Any, Literal
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from ..services.prompt_builder_assistant import PromptBuilderAssistant

from ..dependencies import get_db, get_user_id, get_sac_component, get_api_config
from ..repository.models import PromptGroupModel, PromptModel, PromptGroupUserModel
from .dto.prompt_dto import (
    PromptGroupCreate,
    PromptGroupUpdate,
    PromptGroupResponse,
    PromptGroupListResponse,
    PromptCreate,
    PromptResponse,
    PromptBuilderChatRequest,
    PromptBuilderChatResponse,
)
from ..shared import now_epoch_ms
from solace_ai_connector.common.log import log

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent

router = APIRouter()


# ============================================================================
# Permission Helper Functions
# ============================================================================

def get_user_role(db: Session, group_id: str, user_id: str) -> Optional[Literal["owner", "editor", "viewer"]]:
    """
    Get the user's role for a prompt group.
    Returns 'owner' if user owns the group, or their assigned role from prompt_group_users.
    Returns None if user has no access.
    """
    # Check if user is the owner
    group = db.query(PromptGroupModel).filter(
        PromptGroupModel.id == group_id,
        PromptGroupModel.user_id == user_id
    ).first()
    
    if group:
        return "owner"
    
    # Check if user has shared access
    share = db.query(PromptGroupUserModel).filter(
        PromptGroupUserModel.prompt_group_id == group_id,
        PromptGroupUserModel.user_id == user_id
    ).first()
    
    if share:
        return share.role
    
    return None


def check_permission(
    db: Session,
    group_id: str,
    user_id: str,
    required_permission: Literal["read", "write", "delete"]
) -> None:
    """
    Check if user has the required permission for a prompt group.
    Raises HTTPException if permission is denied.
    
    Permission levels:
    - owner: read, write, delete
    - editor: read, write, delete
    - viewer: read only
    """
    role = get_user_role(db, group_id, user_id)
    
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt group not found"
        )
    
    # Check permissions based on role
    if required_permission == "read":
        # All roles can read
        return
    
    if required_permission in ("write", "delete"):
        if role == "viewer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Viewer role cannot {required_permission} this prompt group"
            )
        # owner and editor can write and delete
        return


def check_prompts_enabled(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    api_config: Dict[str, Any] = Depends(get_api_config),
) -> None:
    """
    Dependency to check if prompts feature is enabled.
    Raises HTTPException if prompts are disabled.
    """
    # Check if persistence is enabled (required for prompts)
    persistence_enabled = api_config.get("persistence_enabled", False)
    if not persistence_enabled:
        log.warning("Prompts API called but persistence is not enabled")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Prompts feature requires persistence to be enabled. Please configure session_service.type as 'sql'."
        )
    
    # Check explicit prompt_library config
    prompt_library_config = component.get_config("prompt_library", {})
    if isinstance(prompt_library_config, dict):
        prompts_explicitly_enabled = prompt_library_config.get("enabled", True)
        if not prompts_explicitly_enabled:
            log.warning("Prompts API called but prompt library is explicitly disabled in config")
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Prompt library feature is disabled. Please enable it in the configuration."
            )
    
    # Check frontend_feature_enablement override
    feature_flags = component.get_config("frontend_feature_enablement", {})
    if "promptLibrary" in feature_flags:
        prompts_flag = feature_flags.get("promptLibrary", True)
        if not prompts_flag:
            log.warning("Prompts API called but prompts are disabled via feature flag")
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Prompt library feature is disabled via feature flag."
            )


# ============================================================================
# Prompt Groups Endpoints
# ============================================================================

@router.get("/groups/all", response_model=List[PromptGroupResponse])
async def get_all_prompt_groups(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    _: None = Depends(check_prompts_enabled),
):
    """
    Get all prompt groups for quick access (used by "/" command).
    Returns all groups owned by user or shared with them.
    """
    try:
        # Get groups owned by user
        owned_groups = db.query(PromptGroupModel).filter(
            PromptGroupModel.user_id == user_id
        ).all()
        
        # Get groups shared with user
        shared_group_ids = db.query(PromptGroupUserModel.prompt_group_id).filter(
            PromptGroupUserModel.user_id == user_id
        ).all()
        shared_group_ids = [gid[0] for gid in shared_group_ids]
        
        shared_groups = []
        if shared_group_ids:
            shared_groups = db.query(PromptGroupModel).filter(
                PromptGroupModel.id.in_(shared_group_ids)
            ).all()
        
        # Combine and sort
        all_groups = owned_groups + shared_groups
        groups = sorted(
            all_groups,
            key=lambda g: (not g.is_pinned, -g.created_at)
        )
        
        # Fetch production prompts for each group
        result = []
        for group in groups:
            group_dict = {
                "id": group.id,
                "name": group.name,
                "description": group.description,
                "category": group.category,
                "command": group.command,
                "user_id": group.user_id,
                "author_name": group.author_name,
                "production_prompt_id": group.production_prompt_id,
                "is_shared": group.is_shared,
                "is_pinned": group.is_pinned,
                "created_at": group.created_at,
                "updated_at": group.updated_at,
                "production_prompt": None,
            }
            
            if group.production_prompt_id:
                prod_prompt = db.query(PromptModel).filter(
                    PromptModel.id == group.production_prompt_id
                ).first()
                if prod_prompt:
                    group_dict["production_prompt"] = {
                        "id": prod_prompt.id,
                        "prompt_text": prod_prompt.prompt_text,
                        "group_id": prod_prompt.group_id,
                        "user_id": prod_prompt.user_id,
                        "version": prod_prompt.version,
                        "created_at": prod_prompt.created_at,
                        "updated_at": prod_prompt.updated_at,
                    }
            
            result.append(PromptGroupResponse(**group_dict))
        
        return result
    except Exception as e:
        log.error(f"Error fetching all prompt groups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch prompt groups"
        )


@router.get("/groups", response_model=PromptGroupListResponse)
async def list_prompt_groups(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    _: None = Depends(check_prompts_enabled),
):
    """
    List all prompt groups accessible to the user (owned or shared).
    Supports pagination, category filtering, and text search.
    """
    try:
        # Get shared group IDs
        shared_group_ids = db.query(PromptGroupUserModel.prompt_group_id).filter(
            PromptGroupUserModel.user_id == user_id
        ).all()
        shared_group_ids = [gid[0] for gid in shared_group_ids]
        
        # Build query for owned or shared groups
        query = db.query(PromptGroupModel).filter(
            or_(
                PromptGroupModel.user_id == user_id,
                PromptGroupModel.id.in_(shared_group_ids) if shared_group_ids else False
            )
        )
        
        if category:
            query = query.filter(PromptGroupModel.category == category)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    PromptGroupModel.name.ilike(search_pattern),
                    PromptGroupModel.description.ilike(search_pattern),
                    PromptGroupModel.command.ilike(search_pattern)
                )
            )
        
        total = query.count()
        groups = query.order_by(
            PromptGroupModel.is_pinned.desc(),  # Pinned first
            PromptGroupModel.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        # Fetch production prompts for each group
        result_groups = []
        for group in groups:
            group_dict = {
                "id": group.id,
                "name": group.name,
                "description": group.description,
                "category": group.category,
                "command": group.command,
                "user_id": group.user_id,
                "author_name": group.author_name,
                "production_prompt_id": group.production_prompt_id,
                "is_shared": group.is_shared,
                "is_pinned": group.is_pinned,
                "created_at": group.created_at,
                "updated_at": group.updated_at,
                "production_prompt": None,
            }
            
            if group.production_prompt_id:
                prod_prompt = db.query(PromptModel).filter(
                    PromptModel.id == group.production_prompt_id
                ).first()
                if prod_prompt:
                    group_dict["production_prompt"] = {
                        "id": prod_prompt.id,
                        "prompt_text": prod_prompt.prompt_text,
                        "group_id": prod_prompt.group_id,
                        "user_id": prod_prompt.user_id,
                        "version": prod_prompt.version,
                        "created_at": prod_prompt.created_at,
                        "updated_at": prod_prompt.updated_at,
                    }
            
            result_groups.append(PromptGroupResponse(**group_dict))
        
        return PromptGroupListResponse(
            groups=result_groups,
            total=total,
            skip=skip,
            limit=limit,
        )
    except Exception as e:
        log.error(f"Error listing prompt groups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list prompt groups"
        )


@router.get("/groups/{group_id}", response_model=PromptGroupResponse)
async def get_prompt_group(
    group_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    _: None = Depends(check_prompts_enabled),
):
    """Get a specific prompt group by ID (requires read permission)."""
    try:
        # Check read permission (works for owner, editor, viewer)
        check_permission(db, group_id, user_id, "read")
        
        group = db.query(PromptGroupModel).filter(
            PromptGroupModel.id == group_id
        ).first()
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt group not found"
            )
        
        group_dict = {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "category": group.category,
            "command": group.command,
            "user_id": group.user_id,
            "author_name": group.author_name,
            "production_prompt_id": group.production_prompt_id,
            "is_shared": group.is_shared,
            "is_pinned": group.is_pinned,
            "created_at": group.created_at,
            "updated_at": group.updated_at,
            "production_prompt": None,
        }
        
        if group.production_prompt_id:
            prod_prompt = db.query(PromptModel).filter(
                PromptModel.id == group.production_prompt_id
            ).first()
            if prod_prompt:
                group_dict["production_prompt"] = {
                    "id": prod_prompt.id,
                    "prompt_text": prod_prompt.prompt_text,
                    "group_id": prod_prompt.group_id,
                    "user_id": prod_prompt.user_id,
                    "version": prod_prompt.version,
                    "created_at": prod_prompt.created_at,
                    "updated_at": prod_prompt.updated_at,
                }
        
        return PromptGroupResponse(**group_dict)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error fetching prompt group {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch prompt group"
        )


@router.post("/groups", response_model=PromptGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_group(
    group_data: PromptGroupCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    _: None = Depends(check_prompts_enabled),
):
    """
    Create a new prompt group with an initial prompt.
    The initial prompt is automatically set as the production version.
    """
    try:
        # Check if command already exists
        if group_data.command:
            existing = db.query(PromptGroupModel).filter(
                PromptGroupModel.command == group_data.command,
                PromptGroupModel.user_id == user_id,
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Command '/{group_data.command}' already exists"
                )
        
        # Create prompt group
        group_id = str(uuid.uuid4())
        now_ms = now_epoch_ms()
        
        new_group = PromptGroupModel(
            id=group_id,
            name=group_data.name,
            description=group_data.description,
            category=group_data.category,
            command=group_data.command,
            user_id=user_id,
            author_name=None,  # Can be enhanced to get from user profile
            production_prompt_id=None,
            is_shared=False,
            is_pinned=False,
            created_at=now_ms,
            updated_at=now_ms,
        )
        db.add(new_group)
        db.flush()
        
        # Create initial prompt
        prompt_id = str(uuid.uuid4())
        new_prompt = PromptModel(
            id=prompt_id,
            prompt_text=group_data.initial_prompt,
            group_id=group_id,
            user_id=user_id,
            version=1,
            created_at=now_ms,
            updated_at=now_ms,
        )
        db.add(new_prompt)
        db.flush()
        
        # Set production prompt reference
        new_group.production_prompt_id = prompt_id
        new_group.updated_at = now_epoch_ms()
        
        db.commit()
        db.refresh(new_group)
        
        # Build response
        return PromptGroupResponse(
            id=new_group.id,
            name=new_group.name,
            description=new_group.description,
            category=new_group.category,
            command=new_group.command,
            user_id=new_group.user_id,
            author_name=new_group.author_name,
            production_prompt_id=new_group.production_prompt_id,
            is_shared=new_group.is_shared,
            is_pinned=new_group.is_pinned,
            created_at=new_group.created_at,
            updated_at=new_group.updated_at,
            production_prompt=PromptResponse(
                id=new_prompt.id,
                prompt_text=new_prompt.prompt_text,
                group_id=new_prompt.group_id,
                user_id=new_prompt.user_id,
                version=new_prompt.version,
                created_at=new_prompt.created_at,
                updated_at=new_prompt.updated_at,
            ),
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error creating prompt group: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create prompt group"
        )


@router.patch("/groups/{group_id}", response_model=PromptGroupResponse)
async def update_prompt_group(
    group_id: str,
    group_data: PromptGroupUpdate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    _: None = Depends(check_prompts_enabled),
):
    """Update a prompt group's metadata (requires write permission - owner or editor only)."""
    try:
        # Check write permission (owner or editor only, not viewer)
        check_permission(db, group_id, user_id, "write")
        
        group = db.query(PromptGroupModel).filter(
            PromptGroupModel.id == group_id
        ).first()
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt group not found"
            )
        
        # Check command uniqueness if being updated
        if group_data.command and group_data.command != group.command:
            existing = db.query(PromptGroupModel).filter(
                PromptGroupModel.command == group_data.command,
                PromptGroupModel.user_id == user_id,
                PromptGroupModel.id != group_id,
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Command '/{group_data.command}' already exists"
                )
        
        # Update fields (excluding initial_prompt which is handled separately)
        update_data = group_data.dict(exclude_unset=True, exclude={'initial_prompt'})
        for field, value in update_data.items():
            setattr(group, field, value)
        
        # If prompt text changed, create a new version
        if hasattr(group_data, 'initial_prompt') and group_data.initial_prompt:
            # Get next version number
            max_version_result = db.query(func.max(PromptModel.version)).filter(
                PromptModel.group_id == group_id
            ).scalar()
            
            next_version = (max_version_result + 1) if max_version_result else 1
            
            # Create new prompt version
            prompt_id = str(uuid.uuid4())
            now_ms = now_epoch_ms()
            
            new_prompt = PromptModel(
                id=prompt_id,
                prompt_text=group_data.initial_prompt,
                group_id=group_id,
                user_id=user_id,
                version=next_version,
                created_at=now_ms,
                updated_at=now_ms,
            )
            db.add(new_prompt)
            db.flush()
            
            # Update production prompt reference
            group.production_prompt_id = prompt_id
        
        group.updated_at = now_epoch_ms()
        
        db.commit()
        db.refresh(group)
        
        # Build response
        group_dict = {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "category": group.category,
            "command": group.command,
            "user_id": group.user_id,
            "author_name": group.author_name,
            "production_prompt_id": group.production_prompt_id,
            "is_shared": group.is_shared,
            "is_pinned": group.is_pinned,
            "created_at": group.created_at,
            "updated_at": group.updated_at,
            "production_prompt": None,
        }
        
        if group.production_prompt_id:
            prod_prompt = db.query(PromptModel).filter(
                PromptModel.id == group.production_prompt_id
            ).first()
            if prod_prompt:
                group_dict["production_prompt"] = {
                    "id": prod_prompt.id,
                    "prompt_text": prod_prompt.prompt_text,
                    "group_id": prod_prompt.group_id,
                    "user_id": prod_prompt.user_id,
                    "version": prod_prompt.version,
                    "created_at": prod_prompt.created_at,
                    "updated_at": prod_prompt.updated_at,
                }

        return PromptGroupResponse(**group_dict)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error updating prompt group {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update prompt group"
        )


@router.patch("/groups/{group_id}/pin", response_model=PromptGroupResponse)
async def toggle_pin_prompt(
    group_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    _: None = Depends(check_prompts_enabled),
):
    """Toggle pin status for a prompt group (requires write permission)."""
    try:
        # Check write permission
        check_permission(db, group_id, user_id, "write")
        
        group = db.query(PromptGroupModel).filter(
            PromptGroupModel.id == group_id
        ).first()
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt group not found"
            )
        
        # Toggle pin status
        group.is_pinned = not group.is_pinned
        group.updated_at = now_epoch_ms()
        
        db.commit()
        db.refresh(group)
        
        # Build response
        group_dict = {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "category": group.category,
            "command": group.command,
            "user_id": group.user_id,
            "author_name": group.author_name,
            "production_prompt_id": group.production_prompt_id,
            "is_shared": group.is_shared,
            "is_pinned": group.is_pinned,
            "created_at": group.created_at,
            "updated_at": group.updated_at,
            "production_prompt": None,
        }
        
        if group.production_prompt_id:
            prod_prompt = db.query(PromptModel).filter(
                PromptModel.id == group.production_prompt_id
            ).first()
            if prod_prompt:
                group_dict["production_prompt"] = {
                    "id": prod_prompt.id,
                    "prompt_text": prod_prompt.prompt_text,
                    "group_id": prod_prompt.group_id,
                    "user_id": prod_prompt.user_id,
                    "version": prod_prompt.version,
                    "created_at": prod_prompt.created_at,
                    "updated_at": prod_prompt.updated_at,
                }
        
        return PromptGroupResponse(**group_dict)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error toggling pin for prompt group {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle pin status"
        )


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt_group(
    group_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    _: None = Depends(check_prompts_enabled),
):
    """Delete a prompt group and all its prompts (requires delete permission - owner or editor only)."""
    try:
        # Check delete permission
        check_permission(db, group_id, user_id, "delete")
        
        group = db.query(PromptGroupModel).filter(
            PromptGroupModel.id == group_id
        ).first()
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt group not found"
            )
        
        # Delete all prompts in the group (cascade should handle this)
        db.delete(group)
        db.commit()
        
        return None
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error deleting prompt group {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete prompt group"
        )


# ============================================================================
# Prompts Endpoints
# ============================================================================

@router.get("/groups/{group_id}/prompts", response_model=List[PromptResponse])
async def list_prompts_in_group(
    group_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    _: None = Depends(check_prompts_enabled),
):
    """List all prompt versions in a group (requires read permission)."""
    try:
        # Check read permission
        check_permission(db, group_id, user_id, "read")
        
        group = db.query(PromptGroupModel).filter(
            PromptGroupModel.id == group_id
        ).first()
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt group not found"
            )
        
        prompts = db.query(PromptModel).filter(
            PromptModel.group_id == group_id
        ).order_by(PromptModel.created_at.desc()).all()
        
        return [
            PromptResponse(
                id=p.id,
                prompt_text=p.prompt_text,
                group_id=p.group_id,
                user_id=p.user_id,
                version=p.version,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in prompts
        ]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error listing prompts in group {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list prompts"
        )


@router.post("/groups/{group_id}/prompts", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_version(
    group_id: str,
    prompt_data: PromptCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    _: None = Depends(check_prompts_enabled),
):
    """Create a new prompt version in a group (requires write permission)."""
    try:
        # Check write permission
        check_permission(db, group_id, user_id, "write")
        
        group = db.query(PromptGroupModel).filter(
            PromptGroupModel.id == group_id
        ).first()
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt group not found"
            )
        
        # Get next version number
        max_version_result = db.query(func.max(PromptModel.version)).filter(
            PromptModel.group_id == group_id
        ).scalar()
        
        next_version = (max_version_result + 1) if max_version_result else 1
        
        # Create new prompt
        prompt_id = str(uuid.uuid4())
        now_ms = now_epoch_ms()
        
        new_prompt = PromptModel(
            id=prompt_id,
            prompt_text=prompt_data.prompt_text,
            group_id=group_id,
            user_id=user_id,
            version=next_version,
            created_at=now_ms,
            updated_at=now_ms,
        )
        db.add(new_prompt)
        db.commit()
        db.refresh(new_prompt)
        
        return PromptResponse(
            id=new_prompt.id,
            prompt_text=new_prompt.prompt_text,
            group_id=new_prompt.group_id,
            user_id=new_prompt.user_id,
            version=new_prompt.version,
            created_at=new_prompt.created_at,
            updated_at=new_prompt.updated_at,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error creating prompt version in group {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create prompt version"
        )


@router.patch("/{prompt_id}/make-production", response_model=PromptResponse)
async def make_prompt_production(
    prompt_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    _: None = Depends(check_prompts_enabled),
):
    """Set a prompt as the production version for its group (requires write permission)."""
    try:
        prompt = db.query(PromptModel).filter(
            PromptModel.id == prompt_id
        ).first()
        
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt not found"
            )
        
        # Check write permission on the group
        check_permission(db, prompt.group_id, user_id, "write")
        
        # Update group's production prompt
        group = db.query(PromptGroupModel).filter(
            PromptGroupModel.id == prompt.group_id
        ).first()
        
        if group:
            group.production_prompt_id = prompt_id
            group.updated_at = now_epoch_ms()
            db.commit()
            db.refresh(prompt)
        
        return PromptResponse(
            id=prompt.id,
            prompt_text=prompt.prompt_text,
            group_id=prompt.group_id,
            user_id=prompt.user_id,
            version=prompt.version,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error making prompt {prompt_id} production: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update production prompt"
        )


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    prompt_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    _: None = Depends(check_prompts_enabled),
):
    """Delete a specific prompt version (requires delete permission)."""
    try:
        prompt = db.query(PromptModel).filter(
            PromptModel.id == prompt_id
        ).first()
        
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt not found"
            )
        
        # Check delete permission on the group
        check_permission(db, prompt.group_id, user_id, "delete")
        
        # Check if this is the only prompt in the group
        group = db.query(PromptGroupModel).filter(
            PromptGroupModel.id == prompt.group_id
        ).first()
        
        prompt_count = db.query(PromptModel).filter(
            PromptModel.group_id == prompt.group_id
        ).count()
        
        if prompt_count == 1:
            # Delete the entire group if this is the last prompt
            db.delete(group)
        else:
            # If this was the production prompt, set another as production
            if group and group.production_prompt_id == prompt_id:
                other_prompt = db.query(PromptModel).filter(
                    PromptModel.group_id == prompt.group_id,
                    PromptModel.id != prompt_id,
                ).order_by(PromptModel.created_at.desc()).first()
                
                if other_prompt:
                    group.production_prompt_id = other_prompt.id
                    group.updated_at = now_epoch_ms()
            
            db.delete(prompt)
        
        db.commit()
        return None
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error deleting prompt {prompt_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete prompt"
        )


# ============================================================================
# AI-Assisted Prompt Builder Endpoints
# ============================================================================


@router.get("/chat/init")
async def init_prompt_builder_chat(
    db: Session = Depends(get_db),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
):
    """Initialize the prompt template builder chat"""
    model_config = component.get_config("model", {})
    assistant = PromptBuilderAssistant(db=db, model_config=model_config)
    greeting = assistant.get_initial_greeting()
    return {
        "message": greeting.message,
        "confidence": greeting.confidence
    }


@router.post("/chat", response_model=PromptBuilderChatResponse)
async def prompt_builder_chat(
    request: PromptBuilderChatRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    _: None = Depends(check_prompts_enabled),
):
    """
    Handle conversational prompt template building using LLM.
    
    Uses LLM to:
    1. Analyze user's description or example transcript
    2. Identify variable elements vs fixed instructions
    3. Generate template structure
    4. Suggest variable names and descriptions
    5. Avoid command conflicts with existing prompts
    """
    try:
        # Get model configuration from component
        model_config = component.get_config("model", {})
        
        # Initialize the assistant with database session and model config
        assistant = PromptBuilderAssistant(db=db, model_config=model_config)
        
        # Process the message using real LLM with conflict checking
        response = await assistant.process_message(
            user_message=request.message,
            conversation_history=[msg.dict() for msg in request.conversation_history],
            current_template=request.current_template or {},
            user_id=user_id
        )
        
        return PromptBuilderChatResponse(
            message=response.message,
            template_updates=response.template_updates,
            confidence=response.confidence,
            ready_to_save=response.ready_to_save
        )
        
    except Exception as e:
        log.error(f"Error in prompt builder chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message"
        )