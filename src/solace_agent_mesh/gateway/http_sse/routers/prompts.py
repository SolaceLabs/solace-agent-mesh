"""
Prompts API router for prompt library feature.
"""
from __future__ import annotations

import uuid
from typing import List, Optional, Dict, Any, Literal
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from ..services.prompt_builder_assistant import PromptBuilderAssistant

from ..dependencies import get_db, get_user_id, get_sac_component, get_api_config, get_user_display_name
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
    PromptExportResponse,
    PromptExportData,
    PromptExportMetadata,
    PromptImportRequest,
    PromptImportResponse,
)
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
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
            try:
                # Truncate fields that exceed max length to prevent validation errors
                name = group.name[:255] if group.name and len(group.name) > 255 else group.name
                description = group.description[:1000] if group.description and len(group.description) > 1000 else group.description
                category = group.category[:100] if group.category and len(group.category) > 100 else group.category
                command = group.command[:50] if group.command and len(group.command) > 50 else group.command
                author_name = group.author_name[:255] if group.author_name and len(group.author_name) > 255 else group.author_name
                
                group_dict = {
                    "id": group.id,
                    "name": name,
                    "description": description,
                    "category": category,
                    "command": command,
                    "user_id": group.user_id,
                    "author_name": author_name,
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
                            "name": prod_prompt.name,
                            "description": prod_prompt.description,
                            "category": prod_prompt.category,
                            "command": prod_prompt.command,
                            "created_at": prod_prompt.created_at,
                            "updated_at": prod_prompt.updated_at,
                        }
                
                result.append(PromptGroupResponse(**group_dict))
            except Exception as e:
                # Log the error but continue processing other groups
                log.warning(f"Skipping invalid prompt group {group.id}: {e}")
                continue
        
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
            try:
                # Truncate fields that exceed max length to prevent validation errors
                name = group.name[:255] if group.name and len(group.name) > 255 else group.name
                description = group.description[:1000] if group.description and len(group.description) > 1000 else group.description
                category = group.category[:100] if group.category and len(group.category) > 100 else group.category
                command = group.command[:50] if group.command and len(group.command) > 50 else group.command
                author_name = group.author_name[:255] if group.author_name and len(group.author_name) > 255 else group.author_name
                
                group_dict = {
                    "id": group.id,
                    "name": name,
                    "description": description,
                    "category": category,
                    "command": command,
                    "user_id": group.user_id,
                    "author_name": author_name,
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
                            "name": prod_prompt.name,
                            "description": prod_prompt.description,
                            "category": prod_prompt.category,
                            "command": prod_prompt.command,
                            "created_at": prod_prompt.created_at,
                            "updated_at": prod_prompt.updated_at,
                        }
                
                result_groups.append(PromptGroupResponse(**group_dict))
            except Exception as e:
                # Log the error but continue processing other groups
                log.warning(f"Skipping invalid prompt group {group.id}: {e}")
                continue
        
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
                    "name": prod_prompt.name,
                    "description": prod_prompt.description,
                    "category": prod_prompt.category,
                    "command": prod_prompt.command,
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
    user_display_name: str = Depends(get_user_display_name),
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
            author_name=user_display_name,
            production_prompt_id=None,
            is_shared=False,
            is_pinned=False,
            created_at=now_ms,
            updated_at=now_ms,
        )
        db.add(new_group)
        db.flush()
        
        # Create initial prompt with versioned metadata
        prompt_id = str(uuid.uuid4())
        new_prompt = PromptModel(
            id=prompt_id,
            prompt_text=group_data.initial_prompt,
            name=group_data.name,
            description=group_data.description,
            category=group_data.category,
            command=group_data.command,
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
                name=new_prompt.name,
                description=new_prompt.description,
                category=new_prompt.category,
                command=new_prompt.command,
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
        
        # If initial_prompt is provided, always create a new version
        # This happens when user clicks "Save New Version" button
        if hasattr(group_data, 'initial_prompt') and group_data.initial_prompt:
            # Get next version number
            max_version_result = db.query(func.max(PromptModel.version)).filter(
                PromptModel.group_id == group_id
            ).scalar()
            
            next_version = (max_version_result + 1) if max_version_result else 1
            
            # Create new prompt version
            prompt_id = str(uuid.uuid4())
            now_ms = now_epoch_ms()
            
            # Create new prompt version with current metadata
            new_prompt = PromptModel(
                id=prompt_id,
                prompt_text=group_data.initial_prompt,
                name=group_data.name if group_data.name else group.name,
                description=group_data.description if group_data.description is not None else group.description,
                category=group_data.category if group_data.category is not None else group.category,
                command=group_data.command if group_data.command is not None else group.command,
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
                    "name": prod_prompt.name,
                    "description": prod_prompt.description,
                    "category": prod_prompt.category,
                    "command": prod_prompt.command,
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
                    "name": prod_prompt.name,
                    "description": prod_prompt.description,
                    "category": prod_prompt.category,
                    "command": prod_prompt.command,
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
                name=p.name,
                description=p.description,
                category=p.category,
                command=p.command,
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
        
        # Get current group metadata for the new version
        new_prompt = PromptModel(
            id=prompt_id,
            prompt_text=prompt_data.prompt_text,
            name=group.name,
            description=group.description,
            category=group.category,
            command=group.command,
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
            name=new_prompt.name,
            description=new_prompt.description,
            category=new_prompt.category,
            command=new_prompt.command,
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


@router.patch("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: str,
    prompt_data: PromptCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    _: None = Depends(check_prompts_enabled),
):
    """Update an existing prompt's content (requires write permission)."""
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
        
        # Update prompt text
        prompt.prompt_text = prompt_data.prompt_text
        prompt.updated_at = now_epoch_ms()
        
        db.commit()
        db.refresh(prompt)
        
        return PromptResponse(
            id=prompt.id,
            prompt_text=prompt.prompt_text,
            group_id=prompt.group_id,
            user_id=prompt.user_id,
            version=prompt.version,
            name=prompt.name,
            description=prompt.description,
            category=prompt.category,
            command=prompt.command,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error updating prompt {prompt_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update prompt"
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
            name=prompt.name,
            description=prompt.description,
            category=prompt.category,
            command=prompt.command,
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


# ============================================================================
# Export/Import Endpoints
# ============================================================================

@router.get("/groups/{group_id}/export", response_model=PromptExportResponse)
async def export_prompt_group(
    group_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    user_display_name: str = Depends(get_user_display_name),
    _: None = Depends(check_prompts_enabled),
):
    """
    Export a prompt group's active/production version as a JSON file.
    Returns a downloadable JSON file containing the prompt data.
    Requires read permission on the prompt group.
    """
    try:
        # Check read permission
        check_permission(db, group_id, user_id, "read")
        
        # Fetch the prompt group
        group = db.query(PromptGroupModel).filter(
            PromptGroupModel.id == group_id
        ).first()
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt group not found"
            )
        
        # Fetch the production prompt
        if not group.production_prompt_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active prompt version to export"
            )
        
        prod_prompt = db.query(PromptModel).filter(
            PromptModel.id == group.production_prompt_id
        ).first()
        
        if not prod_prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active prompt version not found"
            )
        
        # Build export data
        # Use author_name if available, otherwise use current user's display name as fallback
        author_name = group.author_name or user_display_name
        
        export_data = PromptExportResponse(
            version="1.0",
            exported_at=now_epoch_ms(),
            prompt=PromptExportData(
                name=group.name,
                description=group.description,
                category=group.category,
                command=group.command,
                prompt_text=prod_prompt.prompt_text,
                metadata=PromptExportMetadata(
                    author_name=author_name,
                    original_version=prod_prompt.version,
                    original_created_at=prod_prompt.created_at
                )
            )
        )
        
        return export_data
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error exporting prompt group {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export prompt"
        )


@router.post("/import", response_model=PromptImportResponse, status_code=status.HTTP_201_CREATED)
async def import_prompt(
    import_request: PromptImportRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id),
    user_display_name: str = Depends(get_user_display_name),
    _: None = Depends(check_prompts_enabled),
):
    """
    Import a prompt from exported JSON data.
    Creates a new prompt group with the imported data.
    Handles command conflicts automatically by generating alternative commands.
    """
    try:
        prompt_data = import_request.prompt_data
        options = import_request.options or PromptImportOptions()
        warnings = []
        
        # Validate export format version
        export_version = prompt_data.get("version", "1.0")
        if export_version != "1.0":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported export format version: {export_version}"
            )
        
        # Extract prompt data
        prompt_info = prompt_data.get("prompt")
        if not prompt_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid export format: missing 'prompt' field"
            )
        
        # Validate required fields
        required_fields = ["name", "prompt_text"]
        for field in required_fields:
            if field not in prompt_info or not prompt_info[field]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid export format: missing required field '{field}'"
                )
        
        # Extract fields with validation
        name = prompt_info["name"]
        # Truncate name if it exceeds max length (255 chars)
        if len(name) > 255:
            original_name = name
            name = name[:252] + "..."
            warnings.append(
                f"Name was truncated from {len(original_name)} to 255 characters"
            )
        
        description = prompt_info.get("description")
        # Truncate description if it exceeds max length (1000 chars)
        if description and len(description) > 1000:
            description = description[:997] + "..."
            warnings.append("Description was truncated to 1000 characters")
        
        category = prompt_info.get("category") if options.preserve_category else None
        # Truncate category if it exceeds max length (100 chars)
        if category and len(category) > 100:
            category = category[:97] + "..."
            warnings.append("Category was truncated to 100 characters")
        
        command = prompt_info.get("command") if options.preserve_command else None
        # Truncate command if it exceeds max length (50 chars)
        if command and len(command) > 50:
            command = command[:50]
            warnings.append("Command was truncated to 50 characters")
        
        prompt_text = prompt_info["prompt_text"]
        # Truncate prompt_text if it exceeds max length (10000 chars)
        if len(prompt_text) > 10000:
            prompt_text = prompt_text[:9997] + "..."
            warnings.append("Prompt text was truncated to 10000 characters")
        
        # Handle command conflicts
        if command:
            original_command = command
            existing = db.query(PromptGroupModel).filter(
                PromptGroupModel.command == command,
                PromptGroupModel.user_id == user_id,
            ).first()
            
            if existing:
                # Generate alternative command
                counter = 2
                while True:
                    new_command = f"{original_command}-{counter}"
                    existing_alt = db.query(PromptGroupModel).filter(
                        PromptGroupModel.command == new_command,
                        PromptGroupModel.user_id == user_id,
                    ).first()
                    if not existing_alt:
                        command = new_command
                        warnings.append(
                            f"Command '/{original_command}' already exists, using '/{command}' instead"
                        )
                        break
                    counter += 1
                    if counter > 100:  # Safety limit
                        command = None
                        warnings.append(
                            f"Could not generate unique command, imported without command"
                        )
                        break
        
        # Create new prompt group
        group_id = str(uuid.uuid4())
        now_ms = now_epoch_ms()
        
        new_group = PromptGroupModel(
            id=group_id,
            name=name,
            description=description,
            category=category,
            command=command,
            user_id=user_id,
            author_name=user_display_name,  # Set to importing user, not original author
            production_prompt_id=None,
            is_shared=False,
            is_pinned=False,
            created_at=now_ms,
            updated_at=now_ms,
        )
        db.add(new_group)
        db.flush()
        
        # Create prompt version with versioned metadata
        prompt_id = str(uuid.uuid4())
        new_prompt = PromptModel(
            id=prompt_id,
            prompt_text=prompt_text,
            name=name,
            description=description,
            category=category,
            command=command,
            group_id=group_id,
            user_id=user_id,
            version=1,  # Start at version 1 for imported prompts
            created_at=now_ms,
            updated_at=now_ms,
        )
        db.add(new_prompt)
        db.flush()
        
        # Set as production prompt
        new_group.production_prompt_id = prompt_id
        new_group.updated_at = now_epoch_ms()
        
        db.commit()
        
        return PromptImportResponse(
            success=True,
            prompt_group_id=group_id,
            warnings=warnings
        )
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error importing prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import prompt: {str(e)}"
        )