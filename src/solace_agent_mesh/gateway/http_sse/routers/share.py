"""
API routes for share link functionality.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel

from ..dependencies import (
    get_db,
    get_user_id,
    get_sac_component,
)
from ..services.share_service import ShareService
from ..repository.models.share_model import (
    CreateShareLinkRequest,
    UpdateShareLinkRequest,
    ShareLinkResponse,
    ShareLinkItem,
    SharedSessionView,
)
from solace_agent_mesh.shared.api.pagination import PaginationParams, PaginatedResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/share", tags=["share"])


class SuccessResponse(BaseModel):
    """Simple success response."""
    success: bool = True
    message: str


def get_share_service(
    component=Depends(get_sac_component)
) -> ShareService:
    """Dependency to get ShareService instance."""
    return ShareService(component)


def get_optional_user_id(request: Request) -> Optional[str]:
    """
    Get user ID if authenticated, None otherwise.
    Does not raise exception if not authenticated.
    """
    try:
        # Try to get user from request state (set by auth middleware)
        if hasattr(request.state, 'user_id'):
            return request.state.user_id
        return None
    except:
        return None


def get_optional_user_email(request: Request) -> Optional[str]:
    """
    Get user email if authenticated, None otherwise.
    """
    try:
        if hasattr(request.state, 'user_email'):
            return request.state.user_email
        return None
    except:
        return None


def get_base_url(request: Request) -> str:
    """Get base URL from request."""
    # Build base URL from request
    scheme = request.url.scheme
    host = request.headers.get('host', request.url.netloc)
    return f"{scheme}://{host}"


@router.post("/{session_id}", response_model=ShareLinkResponse)
async def create_share_link(
    session_id: str,
    request_body: CreateShareLinkRequest,
    request: Request,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db),
    share_service: ShareService = Depends(get_share_service)
):
    """
    Create a public share link for a session.
    
    Body:
    ```json
    {
        "require_authentication": false,
        "allowed_domains": ["company.com", "partner.com"]
    }
    ```
    
    Returns share link with URL.
    """
    try:
        base_url = get_base_url(request)
        share_link = share_service.create_share_link(
            db=db,
            session_id=session_id,
            user_id=user_id,
            request=request_body,
            base_url=base_url
        )
        
        return share_link
    
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        log.error(f"Error creating share link: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create share link"
        )


@router.get("/link/{session_id}", response_model=ShareLinkResponse)
async def get_share_link_for_session(
    session_id: str,
    request: Request,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db),
    share_service: ShareService = Depends(get_share_service)
):
    """
    Get existing share link for a session.
    
    Returns 404 if no share link exists.
    """
    try:
        base_url = get_base_url(request)
        share_link = share_service.get_share_link_for_session(
            db=db,
            session_id=session_id,
            user_id=user_id,
            base_url=base_url
        )
        
        if not share_link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No share link found for this session"
            )
        
        return share_link
    
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting share link: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get share link"
        )


@router.get("/", response_model=PaginatedResponse[ShareLinkItem])
async def list_share_links(
    request: Request,
    pagination: PaginationParams = Depends(),
    search: Optional[str] = None,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db),
    share_service: ShareService = Depends(get_share_service)
):
    """
    List all share links created by the user.
    
    Supports pagination and search by title.
    """
    try:
        base_url = get_base_url(request)
        result = share_service.list_user_share_links(
            db=db,
            user_id=user_id,
            pagination=pagination,
            search=search,
            base_url=base_url
        )
        
        return result
    
    except Exception as e:
        log.error(f"Error listing share links: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list share links"
        )


@router.get("/{share_id}", response_model=SharedSessionView)
async def view_shared_session(
    share_id: str,
    request: Request,
    user_id: Optional[str] = Depends(get_optional_user_id),
    user_email: Optional[str] = Depends(get_optional_user_email),
    db: DBSession = Depends(get_db),
    share_service: ShareService = Depends(get_share_service)
):
    """
    View a shared session by share ID.
    
    Access control:
    - If require_authentication=False: Public access (no login required)
    - If require_authentication=True: Must be authenticated
    - If allowed_domains is set: User's email domain must match
    
    Returns 401 if authentication required but not provided.
    Returns 403 if authenticated but domain doesn't match.
    """
    try:
        session_view = share_service.get_shared_session_view(
            db=db,
            share_id=share_id,
            user_id=user_id,
            user_email=user_email
        )
        
        return session_view
    
    except PermissionError as e:
        error_msg = str(e)
        if "Authentication required" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_msg,
                headers={"WWW-Authenticate": "Bearer"}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    
    except Exception as e:
        log.error(f"Error viewing shared session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to view shared session"
        )


@router.patch("/{share_id}", response_model=ShareLinkResponse)
async def update_share_link(
    share_id: str,
    request_body: UpdateShareLinkRequest,
    request: Request,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db),
    share_service: ShareService = Depends(get_share_service)
):
    """
    Update share link settings including authentication requirements.
    
    Body:
    ```json
    {
        "require_authentication": true,
        "allowed_domains": ["company.com"]
    }
    ```
    """
    try:
        base_url = get_base_url(request)
        updated_link = share_service.update_share_link(
            db=db,
            share_id=share_id,
            user_id=user_id,
            request=request_body,
            base_url=base_url
        )
        
        return updated_link
    
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        log.error(f"Error updating share link: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update share link"
        )


@router.delete("/{share_id}", response_model=SuccessResponse)
async def delete_share_link(
    share_id: str,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db),
    share_service: ShareService = Depends(get_share_service)
):
    """
    Delete a share link.
    
    This will soft-delete the share link and make it inaccessible.
    """
    try:
        success = share_service.delete_share_link(
            db=db,
            share_id=share_id,
            user_id=user_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Share link not found"
            )
        
        return SuccessResponse(
            success=True,
            message="Share link deleted successfully"
        )
    
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error deleting share link: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete share link"
        )
