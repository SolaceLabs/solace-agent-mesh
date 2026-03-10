"""
API routes for share link functionality.
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
import io

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
    ShareUsersResponse,
    BatchAddShareUsersRequest,
    BatchAddShareUsersResponse,
    BatchDeleteShareUsersRequest,
    BatchDeleteShareUsersResponse,
    SharedWithMeItem,
    ForkSharedChatResponse,
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
        # Try request.state.user_id first (legacy)
        if hasattr(request.state, 'user_id') and request.state.user_id:
            return request.state.user_id
        # Try request.state.user dict (set by AuthMiddleware)
        if hasattr(request.state, 'user') and request.state.user:
            return request.state.user.get('id')
        return None
    except Exception:
        return None


def get_optional_user_email(request: Request) -> Optional[str]:
    """
    Get user email if authenticated, None otherwise.
    """
    try:
        # Try request.state.user_email first (legacy)
        if hasattr(request.state, 'user_email') and request.state.user_email:
            return request.state.user_email
        # Try request.state.user dict (set by AuthMiddleware)
        if hasattr(request.state, 'user') and request.state.user:
            return request.state.user.get('email')
        return None
    except Exception:
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


@router.get("/shared-with-me", response_model=List[SharedWithMeItem])
async def list_shared_with_me(
    request: Request,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db),
    share_service: ShareService = Depends(get_share_service)
):
    """
    List all chats that have been shared with the current user.
    
    Returns chats where the user's email/ID appears in the shared_link_users table.
    Uses get_user_id for consistency with other share endpoints.
    """
    try:
        # Try to get email from request state (set by AuthMiddleware)
        user_email = None
        if hasattr(request.state, 'user') and request.state.user:
            user_email = request.state.user.get("email")
        
        # Fall back to user_id (e.g., sam_dev_user in dev mode)
        lookup_key = user_email or user_id
        log.info(f"[shared-with-me] user_id={user_id}, user_email={user_email}, lookup_key={lookup_key}")
        if not lookup_key:
            return []
        
        base_url = get_base_url(request)
        result = share_service.list_shared_with_me(
            db=db,
            user_email=lookup_key,
            base_url=base_url
        )
        log.info(f"[shared-with-me] Found {len(result)} shared chats for {lookup_key}")
        return result
    
    except Exception as e:
        log.error(f"Error listing shared-with-me chats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list shared chats"
        )


@router.post("/{share_id}/fork", response_model=ForkSharedChatResponse)
async def fork_shared_chat(
    share_id: str,
    request: Request,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db),
    share_service: ShareService = Depends(get_share_service)
):
    """
    Fork a shared chat into the user's own sessions.
    
    Creates a new session with copies of all messages from the shared chat.
    The user can then continue the conversation in their own session.
    """
    try:
        # Get email from request state if available
        user_email = None
        if hasattr(request.state, 'user') and request.state.user:
            user_email = request.state.user.get("email")
        
        result = share_service.fork_shared_chat(
            db=db,
            share_id=share_id,
            user_id=user_id,
            user_email=user_email
        )
        
        return result
    
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
    
    except HTTPException:
        raise
    
    except Exception as e:
        log.error(f"Error forking shared chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fork shared chat"
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
        session_view = await share_service.get_shared_session_view(
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
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
        elif "not authorized" in error_msg.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
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
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
        elif "not authorized" in error_msg.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error deleting share link: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete share link"
        )


@router.get("/{share_id}/artifacts/{filename:path}")
async def get_shared_artifact_content(
    share_id: str,
    filename: str,
    request: Request,
    user_id: Optional[str] = Depends(get_optional_user_id),
    user_email: Optional[str] = Depends(get_optional_user_email),
    db: DBSession = Depends(get_db),
    share_service: ShareService = Depends(get_share_service),
    component = Depends(get_sac_component)
):
    """
    Get artifact content from a shared session.
    
    This endpoint allows fetching artifact content for shared sessions
    without requiring full authentication (respects share link access settings).
    
    Access control follows the same rules as view_shared_session:
    - If require_authentication=False: Public access (no login required)
    - If require_authentication=True: Must be authenticated
    - If allowed_domains is set: User's email domain must match
    """
    try:
        # First get the share link to verify access and get the original user_id
        from ..repository.share_repository import ShareRepository
        share_repo = ShareRepository()
        share_link = share_repo.find_by_share_id(db, share_id)
        
        if not share_link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Share link not found"
            )
        
        # Get shared user emails for user-specific access check
        shared_user_emails = share_repo.find_share_user_emails(db, share_id)
        
        # Check access permissions
        can_access, reason = share_link.can_be_accessed_by_user(user_id, user_email, shared_user_emails)
        if not can_access:
            if reason == "authentication_required":
                raise PermissionError("Authentication required to access this artifact")
            else:
                raise PermissionError("Access denied")
        
        # Get the session view to verify the artifact exists
        session_view = await share_service.get_shared_session_view(
            db=db,
            share_id=share_id,
            user_id=user_id,
            user_email=user_email
        )
        
        # Check if the artifact is in the shared session's artifacts
        # Note: artifacts can be either dict or object depending on how the response is constructed
        artifact_info = None
        artifact_mime_type = None
        for artifact in session_view.artifacts:
            if isinstance(artifact, dict):
                if artifact.get("filename") == filename:
                    artifact_info = artifact
                    artifact_mime_type = artifact.get("mime_type")
                    break
            else:
                if artifact.filename == filename:
                    artifact_info = artifact
                    artifact_mime_type = artifact.mime_type
                    break
        
        if not artifact_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact '{filename}' not found in shared session"
            )
        
        # Get the artifact service and load the content
        artifact_service = component.get_shared_artifact_service()
        if not artifact_service:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Artifact service not available"
            )
        
        # Use the session_id and user_id from the share link (original owner)
        session_id = share_link.session_id
        owner_user_id = share_link.user_id
        
        # Get project_id from the session
        from ..repository.session_repository import SessionRepository
        session_repo = SessionRepository()
        session = session_repo.find_user_session(db, session_id, owner_user_id)
        project_id = session.project_id if session else None
        
        # Get app_name from the component
        app_name = component.get_config("name", "A2A_WebUI_App")
        
        # Load the artifact content
        from ....agent.utils.artifact_helpers import load_artifact_content_or_metadata
        
        # Try loading from session first, then from project if that fails
        load_result = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=owner_user_id,
            session_id=session_id,
            filename=filename,
            version="latest",
            load_metadata_only=False,
            return_raw_bytes=True,
        )
        
        # If not found in session and we have a project_id, try loading from project
        if load_result.get("status") != "success" and project_id:
            load_result = await load_artifact_content_or_metadata(
                artifact_service=artifact_service,
                app_name=app_name,
                user_id=owner_user_id,
                session_id=project_id,  # Project artifacts are stored under project_id
                filename=filename,
                version="latest",
                load_metadata_only=False,
                return_raw_bytes=True,
            )
        
        if load_result.get("status") != "success":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Failed to load artifact content: {load_result.get('message', 'Unknown error')}"
            )
        
        # Get raw bytes from the result
        content_bytes = load_result.get("raw_bytes")
        if content_bytes is None:
            # Fallback to content if raw_bytes not available
            content = load_result.get("content")
            if content is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Artifact content not found"
                )
            # Convert content to bytes if it's a string
            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            elif isinstance(content, bytes):
                content_bytes = content
            else:
                content_bytes = str(content).encode("utf-8")
        
        # Determine content type - prefer from load result, then artifact info
        mime_type = load_result.get("mime_type") or artifact_mime_type or "application/octet-stream"
        
        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(content_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Content-Length": str(len(content_bytes)),
            }
        )
    
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
    
    except HTTPException:
        raise
    
    except Exception as e:
        log.error(f"Error fetching shared artifact: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch artifact content"
        )


# Share User Management Endpoints

@router.get("/{share_id}/users", response_model=ShareUsersResponse)
async def get_share_users(
    share_id: str,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db),
    share_service: ShareService = Depends(get_share_service)
):
    """
    Get all users with access to a share link.
    
    Only the owner can view the list of shared users.
    """
    try:
        return share_service.get_share_users(
            db=db,
            share_id=share_id,
            user_id=user_id
        )
    
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting share users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get share users"
        )


@router.post("/{share_id}/users", response_model=BatchAddShareUsersResponse)
async def add_share_users(
    share_id: str,
    request: BatchAddShareUsersRequest,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db),
    share_service: ShareService = Depends(get_share_service)
):
    """
    Add users to a share link.
    
    Only the owner can add users to a share.
    """
    try:
        # Convert request shares to list of dicts with per-user access levels
        user_shares = [
            {"user_email": share.user_email, "access_level": share.access_level}
            for share in request.shares
        ]
        
        return share_service.add_share_users(
            db=db,
            share_id=share_id,
            user_id=user_id,
            user_shares=user_shares
        )
    
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error adding share users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add share users"
        )


@router.delete("/{share_id}/users", response_model=BatchDeleteShareUsersResponse)
async def delete_share_users(
    share_id: str,
    request: BatchDeleteShareUsersRequest,
    user_id: str = Depends(get_user_id),
    db: DBSession = Depends(get_db),
    share_service: ShareService = Depends(get_share_service)
):
    """
    Remove users from a share link.
    
    Only the owner can remove users from a share.
    """
    try:
        return share_service.delete_share_users(
            db=db,
            share_id=share_id,
            user_id=user_id,
            user_emails=request.user_emails
        )
    
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error deleting share users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete share users"
        )
