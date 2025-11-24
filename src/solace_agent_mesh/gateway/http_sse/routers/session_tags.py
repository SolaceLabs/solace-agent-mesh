"""
Session tags (bookmarks) API router.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from ..services.session_tag_service import SessionTagService
from ..shared.types import UserId, SessionId
from ..shared.auth_utils import get_current_user
from ..dependencies import get_db_session, get_session_tag_service


router = APIRouter()


class CreateSessionTagRequest(BaseModel):
    """Request model for creating a session tag."""
    tag: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    addToSession: bool = Field(default=False, alias="addToSession")
    sessionId: Optional[str] = Field(None, alias="sessionId")

    class Config:
        populate_by_name = True


class UpdateSessionTagRequest(BaseModel):
    """Request model for updating a session tag."""
    tag: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    position: Optional[int] = Field(None, ge=0)


class UpdateSessionTagsRequest(BaseModel):
    """Request model for updating session tags."""
    tags: list[str] = Field(default_factory=list)


class SessionTagResponse(BaseModel):
    """Response model for a session tag."""
    id: str
    userId: str = Field(alias="userId")
    tag: str
    description: Optional[str] = None
    count: int
    position: int
    createdTime: int = Field(alias="createdTime")
    updatedTime: Optional[int] = Field(alias="updatedTime")

    class Config:
        populate_by_name = True


@router.get("/session-tags", response_model=list[SessionTagResponse])
async def get_session_tags(
    user: dict = Depends(get_current_user),
    db_session: DBSession = Depends(get_db_session),
    session_tag_service: SessionTagService = Depends(get_session_tag_service),
):
    """Get all session tags for the current user."""
    user_id = user.get("id")
    try:
        tags = session_tag_service.get_user_session_tags(db_session, user_id)
        return [
            SessionTagResponse(
                id=tag.id,
                userId=tag.user_id,
                tag=tag.tag,
                description=tag.description,
                count=tag.count,
                position=tag.position,
                createdTime=tag.created_time,
                updatedTime=tag.updated_time,
            )
            for tag in tags
        ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/session-tags", response_model=SessionTagResponse)
async def create_session_tag(
    request: CreateSessionTagRequest,
    user: dict = Depends(get_current_user),
    db_session: DBSession = Depends(get_db_session),
    session_tag_service: SessionTagService = Depends(get_session_tag_service),
):
    """Create a new session tag."""
    user_id = user.get("id")
    try:
        tag = session_tag_service.create_session_tag(
            db_session=db_session,
            user_id=user_id,
            tag=request.tag,
            description=request.description,
            add_to_session=request.addToSession,
            session_id=request.sessionId,
        )
        db_session.commit()
        return SessionTagResponse(
            id=tag.id,
            userId=tag.user_id,
            tag=tag.tag,
            description=tag.description,
            count=tag.count,
            position=tag.position,
            createdTime=tag.created_time,
            updatedTime=tag.updated_time,
        )
    except ValueError as e:
        db_session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db_session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/session-tags/{tag}", response_model=SessionTagResponse)
async def update_session_tag(
    tag: str,
    request: UpdateSessionTagRequest,
    user: dict = Depends(get_current_user),
    db_session: DBSession = Depends(get_db_session),
    session_tag_service: SessionTagService = Depends(get_session_tag_service),
):
    """Update an existing session tag."""
    user_id = user.get("id")
    try:
        updated_tag = session_tag_service.update_session_tag(
            db_session=db_session,
            user_id=user_id,
            old_tag=tag,
            new_tag=request.tag,
            description=request.description,
            position=request.position,
        )
        if not updated_tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        
        db_session.commit()
        return SessionTagResponse(
            id=updated_tag.id,
            userId=updated_tag.user_id,
            tag=updated_tag.tag,
            description=updated_tag.description,
            count=updated_tag.count,
            position=updated_tag.position,
            createdTime=updated_tag.created_time,
            updatedTime=updated_tag.updated_time,
        )
    except ValueError as e:
        db_session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db_session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/session-tags/{tag}")
async def delete_session_tag(
    tag: str,
    user: dict = Depends(get_current_user),
    db_session: DBSession = Depends(get_db_session),
    session_tag_service: SessionTagService = Depends(get_session_tag_service),
):
    """Delete a session tag."""
    user_id = user.get("id")
    try:
        deleted = session_tag_service.delete_session_tag(db_session, user_id, tag)
        if not deleted:
            raise HTTPException(status_code=404, detail="Tag not found")
        db_session.commit()
        return {"message": "Tag deleted successfully"}
    except ValueError as e:
        db_session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db_session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/session-tags/session/{session_id}", response_model=list[str])
async def update_session_tags(
    session_id: SessionId,
    request: UpdateSessionTagsRequest,
    user: dict = Depends(get_current_user),
    db_session: DBSession = Depends(get_db_session),
    session_tag_service: SessionTagService = Depends(get_session_tag_service),
):
    """Update tags for a specific session."""
    user_id = user.get("id")
    try:
        updated_tags = session_tag_service.update_session_tags(
            db_session=db_session,
            user_id=user_id,
            session_id=session_id,
            tags=request.tags,
        )
        db_session.commit()
        return updated_tags
    except ValueError as e:
        db_session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db_session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")