"""
Service for share link business logic.
"""

import logging
import json
from typing import TYPE_CHECKING, Optional, List, Dict, Any
from sqlalchemy.orm import Session as DBSession

from ..repository.share_repository import ShareRepository
from ..repository.entities.share import ShareLink, SharedArtifact
from ..repository.models.share_model import (
    ShareLinkResponse, 
    ShareLinkItem, 
    SharedSessionView,
    CreateShareLinkRequest,
    UpdateShareLinkRequest
)
from ..utils.share_utils import (
    generate_share_id,
    validate_domains_list,
    extract_email_domain,
    anonymize_chat_task,
    build_share_url,
    parse_allowed_domains,
    format_allowed_domains
)
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from solace_agent_mesh.shared.api.pagination import PaginationParams, PaginatedResponse

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent

log = logging.getLogger(__name__)


class ShareService:
    """Service for managing share links."""

    def __init__(self, component: "WebUIBackendComponent" = None):
        self.component = component
        self.repository = ShareRepository()

    def create_share_link(
        self,
        db: DBSession,
        session_id: str,
        user_id: str,
        request: CreateShareLinkRequest,
        base_url: str
    ) -> ShareLinkResponse:
        """
        Create a new share link for a session.
        
        Args:
            db: Database session
            session_id: Session ID to share
            user_id: User ID (owner)
            request: Create request with auth settings
            base_url: Base URL for building share URL
        
        Returns:
            ShareLinkResponse with share details
        
        Raises:
            ValueError: If validation fails
        """
        # Validate session exists and belongs to user
        from ..services.session_service import SessionService
        session_service = SessionService(self.component)
        session = session_service.get_session_details(db, session_id, user_id)
        
        if not session:
            raise ValueError(f"Session {session_id} not found or access denied")
        
        # Check if share link already exists - return it instead of error
        existing = self.repository.find_by_session_id(db, session_id, user_id)
        if existing:
            log.info(f"Share link already exists for session {session_id}, returning existing link")
            return self._build_share_link_response(existing, base_url)
        
        # Validate authentication settings
        if request.allowed_domains and not request.require_authentication:
            raise ValueError("Domain restrictions require authentication to be enabled")
        
        if request.allowed_domains:
            is_valid, error = validate_domains_list(request.allowed_domains)
            if not is_valid:
                raise ValueError(f"Invalid domains: {error}")
        
        # Generate share ID
        share_id = generate_share_id()
        
        # Create share link entity
        now_ms = now_epoch_ms()
        share_link = ShareLink(
            share_id=share_id,
            session_id=session_id,
            user_id=user_id,
            title=session.name or "Untitled Session",
            is_public=True,
            require_authentication=request.require_authentication,
            allowed_domains=format_allowed_domains(request.allowed_domains) if request.allowed_domains else None,
            created_time=now_ms,
            updated_time=now_ms
        )
        
        # Save to database
        saved_link = self.repository.save(db, share_link)
        db.commit()
        
        # Mark session artifacts as public
        self._mark_session_artifacts_public(db, session_id, share_id)
        db.commit()
        
        log.info(f"Created share link {share_id} for session {session_id} by user {user_id}")
        
        # Build response
        return self._build_share_link_response(saved_link, base_url)

    def get_share_link_by_id(
        self,
        db: DBSession,
        share_id: str
    ) -> Optional[ShareLink]:
        """
        Get a share link by its ID.
        
        Args:
            db: Database session
            share_id: Share ID
        
        Returns:
            ShareLink entity or None if not found
        """
        return self.repository.find_by_share_id(db, share_id)

    def get_share_link_for_session(
        self,
        db: DBSession,
        session_id: str,
        user_id: str,
        base_url: str
    ) -> Optional[ShareLinkResponse]:
        """
        Get existing share link for a session.
        
        Args:
            db: Database session
            session_id: Session ID
            user_id: User ID (owner)
            base_url: Base URL for building share URL
        
        Returns:
            ShareLinkResponse or None if not found
        """
        share_link = self.repository.find_by_session_id(db, session_id, user_id)
        if not share_link:
            return None
        
        return self._build_share_link_response(share_link, base_url)

    def list_user_share_links(
        self,
        db: DBSession,
        user_id: str,
        pagination: PaginationParams,
        search: Optional[str] = None,
        base_url: str = ""
    ) -> PaginatedResponse[ShareLinkItem]:
        """
        List share links created by a user.
        
        Args:
            db: Database session
            user_id: User ID
            pagination: Pagination parameters
            search: Optional search query
            base_url: Base URL for building share URLs
        
        Returns:
            Paginated list of share links
        """
        share_links = self.repository.find_by_user(db, user_id, pagination, search)
        total_count = self.repository.count_by_user(db, user_id, search)
        
        # Build response items
        items = []
        for share_link in share_links:
            # Get message count for this session
            from ..repository.chat_task_repository import ChatTaskRepository
            task_repo = ChatTaskRepository()
            tasks = task_repo.find_by_session(db, share_link.session_id, user_id)
            message_count = sum(
                len(json.loads(task.message_bubbles) if isinstance(task.message_bubbles, str) else task.message_bubbles)
                for task in tasks
            )
            
            item = ShareLinkItem(
                share_id=share_link.share_id,
                session_id=share_link.session_id,
                title=share_link.title or "Untitled",
                is_public=share_link.is_public,
                require_authentication=share_link.require_authentication,
                allowed_domains=share_link.get_allowed_domains_list(),
                access_type=share_link.get_access_type(),
                created_time=share_link.created_time,
                message_count=message_count
            )
            items.append(item)
        
        return PaginatedResponse.create(items, total_count, pagination)

    def update_share_link(
        self,
        db: DBSession,
        share_id: str,
        user_id: str,
        request: UpdateShareLinkRequest,
        base_url: str
    ) -> ShareLinkResponse:
        """
        Update share link settings.
        
        Args:
            db: Database session
            share_id: Share ID to update
            user_id: User ID (must be owner)
            request: Update request
            base_url: Base URL for building share URL
        
        Returns:
            Updated ShareLinkResponse
        
        Raises:
            ValueError: If not found or validation fails
        """
        share_link = self.repository.find_by_share_id(db, share_id)
        if not share_link:
            raise ValueError(f"Share link {share_id} not found")
        
        if not share_link.can_be_modified_by_user(user_id):
            raise ValueError("Not authorized to modify this share link")
        
        # Validate new settings
        if request.allowed_domains is not None:
            if request.allowed_domains and not (request.require_authentication if request.require_authentication is not None else share_link.require_authentication):
                raise ValueError("Domain restrictions require authentication to be enabled")
            
            if request.allowed_domains:
                is_valid, error = validate_domains_list(request.allowed_domains)
                if not is_valid:
                    raise ValueError(f"Invalid domains: {error}")
        
        # Update settings
        share_link.update_authentication_settings(
            require_authentication=request.require_authentication,
            allowed_domains=request.allowed_domains
        )
        
        # Save changes
        updated_link = self.repository.save(db, share_link)
        db.commit()
        
        log.info(f"Updated share link {share_id} by user {user_id}")
        
        return self._build_share_link_response(updated_link, base_url)

    def delete_share_link(
        self,
        db: DBSession,
        share_id: str,
        user_id: str
    ) -> bool:
        """
        Delete a share link.
        
        Args:
            db: Database session
            share_id: Share ID to delete
            user_id: User ID (must be owner)
        
        Returns:
            True if deleted successfully
        
        Raises:
            ValueError: If not found or not authorized
        """
        share_link = self.repository.find_by_share_id(db, share_id)
        if not share_link:
            raise ValueError(f"Share link {share_id} not found")
        
        if not share_link.can_be_modified_by_user(user_id):
            raise ValueError("Not authorized to delete this share link")
        
        # Delete artifacts
        self.repository.delete_artifacts_by_share_id(db, share_id)
        
        # Soft delete the share link
        success = self.repository.soft_delete(db, share_id, user_id)
        db.commit()
        
        if success:
            log.info(f"Deleted share link {share_id} by user {user_id}")
        
        return success

    def get_shared_session_view(
        self,
        db: DBSession,
        share_id: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None
    ) -> SharedSessionView:
        """
        Get public view of a shared session.
        
        Args:
            db: Database session
            share_id: Share ID
            user_id: Optional user ID (if authenticated)
            user_email: Optional user email (if authenticated)
        
        Returns:
            SharedSessionView with anonymized data
        
        Raises:
            ValueError: If not found or access denied
        """
        share_link = self.repository.find_by_share_id(db, share_id)
        if not share_link or share_link.is_deleted():
            raise ValueError("Share link not found")
        
        # Check access permissions
        can_access, reason = share_link.can_be_accessed_by_user(user_id, user_email)
        if not can_access:
            if reason == "authentication_required":
                raise PermissionError("Authentication required to view this shared session")
            elif reason == "domain_mismatch":
                allowed = ', '.join(share_link.get_allowed_domains_list())
                raise PermissionError(f"Access restricted to users from: {allowed}")
            else:
                raise PermissionError("Access denied")
        
        # Get session tasks (anonymized)
        from ..repository.chat_task_repository import ChatTaskRepository
        task_repo = ChatTaskRepository()
        tasks = task_repo.find_by_session(db, share_link.session_id, share_link.user_id)
        
        # Anonymize tasks
        anonymized_tasks = [anonymize_chat_task(task.model_dump()) for task in tasks]
        
        # Get artifacts
        artifacts = self.repository.find_artifacts_by_share_id(db, share_id)
        artifact_list = [
            {
                "uri": art.artifact_uri,
                "version": art.artifact_version,
                "is_public": art.is_public
            }
            for art in artifacts
        ]
        
        return SharedSessionView(
            share_id=share_id,
            title=share_link.title or "Untitled",
            created_time=share_link.created_time,
            access_type=share_link.get_access_type(),
            tasks=anonymized_tasks,
            artifacts=artifact_list
        )

    def _build_share_link_response(self, share_link: ShareLink, base_url: str) -> ShareLinkResponse:
        """Build ShareLinkResponse from entity."""
        return ShareLinkResponse(
            share_id=share_link.share_id,
            session_id=share_link.session_id,
            title=share_link.title or "Untitled",
            is_public=share_link.is_public,
            require_authentication=share_link.require_authentication,
            allowed_domains=share_link.get_allowed_domains_list(),
            access_type=share_link.get_access_type(),
            created_time=share_link.created_time,
            share_url=build_share_url(share_link.share_id, base_url)
        )

    def _mark_session_artifacts_public(self, db: DBSession, session_id: str, share_id: str) -> None:
        """
        Mark all artifacts in a session as public and track them.
        
        Args:
            db: Database session
            session_id: Session ID
            share_id: Share ID for tracking
        """
        # This would integrate with SAM's artifact system
        # For now, we'll create a placeholder that can be extended
        log.info(f"Marking artifacts public for session {session_id} (share {share_id})")
        
        # TODO: Integrate with actual artifact service
        # Example:
        # artifact_service = self.component.get_artifact_service()
        # artifacts = artifact_service.list_session_artifacts(session_id)
        # for artifact in artifacts:
        #     artifact_service.mark_public(artifact.uri)
        #     shared_artifact = SharedArtifact(
        #         share_id=share_id,
        #         artifact_uri=artifact.uri,
        #         artifact_version=artifact.version,
        #         is_public=True,
        #         created_time=now_epoch_ms()
        #     )
        #     self.repository.save_artifact(db, shared_artifact)
