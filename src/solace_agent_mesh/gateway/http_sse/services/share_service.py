"""
Service for share link business logic.
"""

import logging
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List, Dict, Any
from sqlalchemy.orm import Session as DBSession

from ..repository.share_repository import ShareRepository
from ..repository.entities.share import ShareLink, SharedArtifact, SharedLinkUser
from ..repository.models.share_model import (
    ShareLinkResponse,
    ShareLinkItem,
    SharedSessionView,
    SharedArtifactInfo,
    CreateShareLinkRequest,
    UpdateShareLinkRequest,
    ShareUsersResponse,
    SharedLinkUserInfo,
    BatchAddShareUsersResponse,
    BatchDeleteShareUsersResponse,
    SharedWithMeItem,
    ForkSharedChatResponse,
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
from ....agent.utils.artifact_helpers import get_artifact_info_list

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
            return self._build_share_link_response(existing, base_url, db)
        
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
        return self._build_share_link_response(saved_link, base_url, db)

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
        
        return self._build_share_link_response(share_link, base_url, db)

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
        
        return self._build_share_link_response(updated_link, base_url, db)

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

    async def get_shared_session_view(
        self,
        db: DBSession,
        share_id: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        snapshot_time: Optional[int] = None
    ) -> SharedSessionView:
        """
        Get public view of a shared session.
        
        Args:
            db: Database session
            share_id: Share ID
            user_id: Optional user ID (if authenticated)
            user_email: Optional user email (if authenticated)
            snapshot_time: Optional epoch ms cutoff - only include tasks created at or before this time (for viewers)
        
        Returns:
            SharedSessionView with anonymized data and full artifact info
        
        Raises:
            ValueError: If not found or access denied
        """
        share_link = self.repository.find_by_share_id(db, share_id)
        if not share_link or share_link.is_deleted():
            raise ValueError("Share link not found")
        
        # Owner always has access
        is_owner = user_id and share_link.user_id == user_id
        
        if not is_owner:
            # Get shared user emails for user-specific access check
            shared_user_emails = self.repository.find_share_user_emails(db, share_id)
            
            # Check access permissions
            can_access, reason = share_link.can_be_accessed_by_user(user_id, user_email, shared_user_emails)
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
        from ..repository.session_repository import SessionRepository
        task_repo = ChatTaskRepository()
        session_repo = SessionRepository()
        tasks = task_repo.find_by_session(db, share_link.session_id, share_link.user_id)
        
        # Filter tasks by snapshot_time if set (for viewers)
        if snapshot_time is not None:
            tasks = [t for t in tasks if t.created_time <= snapshot_time]
        
        # Get the session to check for project_id
        session = session_repo.find_user_session(db, share_link.session_id, share_link.user_id)
        project_id = session.project_id if session else None
        
        # Anonymize tasks
        anonymized_tasks = [anonymize_chat_task(task.model_dump()) for task in tasks]
        
        # Get full artifact details from artifact service
        artifact_list: List[SharedArtifactInfo] = []
        artifact_service = None
        
        log.info(f"[ShareService] Loading artifacts - component available: {self.component is not None}")
        
        if self.component:
            # Use get_shared_artifact_service() method which is the correct way to get the artifact service
            artifact_service = self.component.get_shared_artifact_service()
            log.info(f"[ShareService] Artifact service available: {artifact_service is not None}")
            
        if artifact_service:
            try:
                app_name = self.component.get_config("name", "A2A_WebUI_App")
                log.info(f"Loading artifacts for shared session {share_id}, user_id={share_link.user_id}, session_id={share_link.session_id}, project_id={project_id}, app_name={app_name}")
                
                # Load session artifacts
                artifact_infos = await get_artifact_info_list(
                    artifact_service=artifact_service,
                    app_name=app_name,
                    user_id=share_link.user_id,
                    session_id=share_link.session_id
                )
                
                log.info(f"Found {len(artifact_infos)} session artifacts for shared session {share_id}")
                
                # If session is part of a project, also load project artifacts
                if project_id:
                    project_artifact_infos = await get_artifact_info_list(
                        artifact_service=artifact_service,
                        app_name=app_name,
                        user_id=share_link.user_id,
                        session_id=project_id  # Project artifacts are stored under project_id as session_id
                    )
                    log.info(f"Found {len(project_artifact_infos)} project artifacts for shared session {share_id}")
                    
                    # Merge project artifacts with session artifacts (avoid duplicates by filename)
                    existing_filenames = {info.filename for info in artifact_infos}
                    for project_artifact in project_artifact_infos:
                        if project_artifact.filename not in existing_filenames:
                            artifact_infos.append(project_artifact)
                            existing_filenames.add(project_artifact.filename)
                    
                    log.info(f"Total artifacts after merging: {len(artifact_infos)}")
                
                # Convert ArtifactInfo to SharedArtifactInfo
                for info in artifact_infos:
                    artifact_list.append(SharedArtifactInfo(
                        filename=info.filename,
                        mime_type=info.mime_type,
                        size=info.size,
                        last_modified=info.last_modified,
                        version=info.version,
                        version_count=info.version_count,
                        description=info.description,
                        source=info.source
                    ))
                    
                log.debug(f"Loaded {len(artifact_list)} artifacts for shared session {share_id}")
            except Exception as e:
                log.warning(f"Failed to load artifacts for shared session {share_id}: {e}", exc_info=True)
                # Continue without artifacts rather than failing the entire request
        else:
            log.warning(f"No artifact service available for shared session {share_id}")
        
        # Load task events for workflow visualization
        task_events_data = await self._load_task_events_for_session(db, tasks)
        
        return SharedSessionView(
            share_id=share_id,
            title=share_link.title or "Untitled",
            created_time=share_link.created_time,
            access_type=share_link.get_access_type(),
            tasks=anonymized_tasks,
            artifacts=artifact_list,
            task_events=task_events_data,
            is_owner=is_owner,
            session_id=share_link.session_id if is_owner else None,
            snapshot_time=snapshot_time
        )
    
    async def _load_task_events_for_session(
        self,
        db: DBSession,
        tasks: List[Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Load task events for workflow visualization.
        
        Args:
            db: Database session
            tasks: List of chat tasks from the session
        
        Returns:
            Dictionary of task events keyed by task_id, or None if no events found
        """
        from ..repository.task_repository import TaskRepository
        
        task_repo = TaskRepository()
        all_task_events: Dict[str, Any] = {}
        
        try:
            log.info(f"Loading task events for {len(tasks)} chat tasks")
            
            for task in tasks:
                # Try to get the task_id from task_metadata first
                task_id = None
                task_metadata = task.task_metadata
                
                if task_metadata:
                    if isinstance(task_metadata, str):
                        try:
                            task_metadata = json.loads(task_metadata)
                        except:
                            task_metadata = None
                    
                    if task_metadata and isinstance(task_metadata, dict):
                        task_id = task_metadata.get("task_id")
                
                # If no task_id in metadata, try using the chat task's id directly
                # (the chat task id might be the same as the A2A task id)
                if not task_id:
                    task_id = task.id
                
                log.debug(f"Looking up task events for task_id: {task_id}")
                
                # Load task and events from database
                result = task_repo.find_by_id_with_events(db, task_id)
                if not result:
                    log.debug(f"No task events found for task_id: {task_id}")
                    continue
                
                db_task, events = result
                log.debug(f"Found {len(events)} events for task_id: {task_id}")
                
                # Format events for frontend (same format as /tasks/{task_id}/events endpoint)
                formatted_events = self._format_task_events(task_id, events)
                
                all_task_events[task_id] = {
                    "events": formatted_events,
                    "initial_request_text": db_task.initial_request_text or ""
                }
                
                # Also load related child tasks
                related_task_ids = task_repo.find_all_by_parent_chain(db, task_id)
                log.debug(f"Found {len(related_task_ids)} related tasks for task_id: {task_id}")
                
                for related_tid in related_task_ids:
                    if related_tid == task_id or related_tid in all_task_events:
                        continue
                    
                    related_result = task_repo.find_by_id_with_events(db, related_tid)
                    if not related_result:
                        continue
                    
                    related_task, related_events = related_result
                    related_formatted_events = self._format_task_events(related_tid, related_events)
                    
                    all_task_events[related_tid] = {
                        "events": related_formatted_events,
                        "initial_request_text": related_task.initial_request_text or ""
                    }
            
            if not all_task_events:
                log.info("No task events found for any tasks in the session")
                return None
            
            log.info(f"Loaded task events for {len(all_task_events)} tasks")
            return all_task_events
            
        except Exception as e:
            log.warning(f"Failed to load task events: {e}", exc_info=True)
            return None
    
    def _format_task_events(self, task_id: str, events: List[Any]) -> List[Dict[str, Any]]:
        """
        Format task events into A2AEventSSEPayload format for the frontend.
        
        Args:
            task_id: The task ID
            events: List of task event entities
        
        Returns:
            List of formatted events
        """
        formatted_events = []
        
        for event in events:
            # Convert timestamp from epoch milliseconds to ISO 8601
            timestamp_dt = datetime.fromtimestamp(event.created_time / 1000, tz=timezone.utc)
            timestamp_iso = timestamp_dt.isoformat()
            
            # Extract metadata from payload
            payload = event.payload
            message_id = payload.get("id")
            source_entity = "unknown"
            target_entity = "unknown"
            method = "N/A"
            
            # Parse based on direction
            if event.direction == "request":
                method = payload.get("method", "N/A")
                if "params" in payload and "message" in payload.get("params", {}):
                    message = payload["params"]["message"]
                    if isinstance(message, dict) and "metadata" in message:
                        target_entity = message["metadata"].get("agent_name", "unknown")
            elif event.direction in ["status", "response", "error"]:
                if "result" in payload:
                    result = payload["result"]
                    if isinstance(result, dict):
                        if "metadata" in result:
                            source_entity = result["metadata"].get("agent_name", "unknown")
                        if "message" in result:
                            message = result["message"]
                            if isinstance(message, dict) and "metadata" in message:
                                if source_entity == "unknown":
                                    source_entity = message["metadata"].get("agent_name", "unknown")
            
            # Map stored direction to SSE direction format
            direction_map = {
                "request": "request",
                "response": "task",
                "status": "status-update",
                "error": "error_response",
            }
            sse_direction = direction_map.get(event.direction, event.direction)
            
            # Build the A2AEventSSEPayload structure
            formatted_event = {
                "event_type": "a2a_message",
                "timestamp": timestamp_iso,
                "solace_topic": event.topic,
                "direction": sse_direction,
                "source_entity": source_entity,
                "target_entity": target_entity,
                "message_id": message_id,
                "task_id": task_id,
                "payload_summary": {
                    "method": method,
                    "params_preview": None,
                },
                "full_payload": payload,
            }
            formatted_events.append(formatted_event)
        
        return formatted_events

    def _build_share_link_response(self, share_link: ShareLink, base_url: str, db: DBSession = None) -> ShareLinkResponse:
        """Build ShareLinkResponse from entity."""
        # Check if there are shared users to determine access type
        has_shared_users = False
        if db:
            has_shared_users = self.repository.has_shared_users(db, share_link.share_id)
        
        return ShareLinkResponse(
            share_id=share_link.share_id,
            session_id=share_link.session_id,
            title=share_link.title or "Untitled",
            is_public=share_link.is_public,
            require_authentication=share_link.require_authentication,
            allowed_domains=share_link.get_allowed_domains_list(),
            access_type=share_link.get_access_type(has_shared_users),
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

    # Share User Management Methods

    def get_share_users(
        self,
        db: DBSession,
        share_id: str,
        user_id: str
    ) -> ShareUsersResponse:
        """
        Get all users with access to a share link.
        
        Args:
            db: Database session
            share_id: Share ID
            user_id: User ID (must be owner)
        
        Returns:
            ShareUsersResponse with owner and shared users
        
        Raises:
            ValueError: If share not found or user not authorized
        """
        share_link = self.repository.find_by_share_id(db, share_id)
        if not share_link:
            raise ValueError(f"Share link {share_id} not found")
        
        if share_link.user_id != user_id:
            raise ValueError("Not authorized to view share users")
        
        # Get owner email from session service
        from ..services.session_service import SessionService
        session_service = SessionService(self.component)
        session = session_service.get_session_details(db, share_link.session_id, user_id)
        owner_email = session.user_id if session else user_id  # Fallback to user_id
        
        # Get shared users
        shared_users = self.repository.find_share_users(db, share_id)
        
        return ShareUsersResponse(
            share_id=share_id,
            owner_email=owner_email,
            users=[
                SharedLinkUserInfo(
                    user_email=u.user_email,
                    access_level=u.access_level,
                    added_at=u.added_at,
                    original_access_level=u.original_access_level,
                    original_added_at=u.original_added_at,
                )
                for u in shared_users
            ]
        )

    def add_share_users(
        self,
        db: DBSession,
        share_id: str,
        user_id: str,
        user_shares: List[Dict[str, str]]
    ) -> BatchAddShareUsersResponse:
        """
        Add users to a share link.
        
        Args:
            db: Database session
            share_id: Share ID
            user_id: User ID (must be owner)
            user_shares: List of dicts with 'user_email' and optional 'access_level'
        
        Returns:
            BatchAddShareUsersResponse with added users
        
        Raises:
            ValueError: If share not found or user not authorized
        """
        share_link = self.repository.find_by_share_id(db, share_id)
        if not share_link:
            raise ValueError(f"Share link {share_id} not found")
        
        if share_link.user_id != user_id:
            raise ValueError("Not authorized to add share users")
        
        added_users = []
        for share_info in user_shares:
            email = share_info.get("user_email")
            access_level = share_info.get("access_level", "RESOURCE_VIEWER")
            
            if not email:
                continue
            
            # If already shared, update access level if different
            if self.repository.check_user_has_access(db, share_id, email):
                # Update access level if it changed
                existing_user = self.repository.find_share_user_by_email(db, share_id, email)
                if existing_user and existing_user.access_level != access_level:
                    # Update in-place, preserving original share event
                    updated_user = self.repository.update_share_user_access(
                        db=db,
                        share_id=share_id,
                        user_email=email,
                        new_access_level=access_level
                    )
                    if updated_user:
                        added_users.append(SharedLinkUserInfo(
                            user_email=updated_user.user_email,
                            access_level=updated_user.access_level,
                            added_at=updated_user.added_at,
                            original_access_level=updated_user.original_access_level,
                            original_added_at=updated_user.original_added_at,
                        ))
                    log.info(f"Updating access level for {email} on share {share_id}: {existing_user.access_level} -> {access_level}")
                else:
                    log.info(f"User {email} already has access to share {share_id} with same level")
                    continue
            else:
                try:
                    shared_user = self.repository.add_share_user(
                        db=db,
                        share_id=share_id,
                        user_email=email,
                        added_by_user_id=user_id,
                        access_level=access_level
                    )
                    added_users.append(SharedLinkUserInfo(
                        user_email=shared_user.user_email,
                        access_level=shared_user.access_level,
                        added_at=shared_user.added_at,
                        original_access_level=shared_user.original_access_level,
                        original_added_at=shared_user.original_added_at,
                    ))
                    log.info(f"Added user {email} to share {share_id}")
                except Exception as e:
                    log.error(f"Failed to add user {email} to share {share_id}: {e}")
        
        db.commit()
        
        return BatchAddShareUsersResponse(
            added_count=len(added_users),
            users=added_users
        )

    def delete_share_users(
        self,
        db: DBSession,
        share_id: str,
        user_id: str,
        user_emails: List[str]
    ) -> BatchDeleteShareUsersResponse:
        """
        Remove users from a share link.
        
        Args:
            db: Database session
            share_id: Share ID
            user_id: User ID (must be owner)
            user_emails: List of user emails to remove
        
        Returns:
            BatchDeleteShareUsersResponse with count of removed users
        
        Raises:
            ValueError: If share not found or user not authorized
        """
        share_link = self.repository.find_by_share_id(db, share_id)
        if not share_link:
            raise ValueError(f"Share link {share_id} not found")
        
        if share_link.user_id != user_id:
            raise ValueError("Not authorized to remove share users")
        
        deleted_count = self.repository.delete_share_users_batch(db, share_id, user_emails)
        db.commit()
        log.info(f"Removed {deleted_count} users from share {share_id}")
        
        return BatchDeleteShareUsersResponse(deleted_count=deleted_count)

    def check_user_access_to_share(
        self,
        db: DBSession,
        share_id: str,
        user_id: Optional[str],
        user_email: Optional[str]
    ) -> tuple[bool, str]:
        """
        Check if a user can access a share link.
        
        Args:
            db: Database session
            share_id: Share ID
            user_id: User ID (None if not authenticated)
            user_email: User email (None if not authenticated)
        
        Returns:
            Tuple of (can_access: bool, reason: str)
        """
        share_link = self.repository.find_by_share_id(db, share_id)
        if not share_link:
            return (False, "share_not_found")
        
        if share_link.is_deleted():
            return (False, "share_deleted")
        
        # Owner always has access
        if user_id and share_link.user_id == user_id:
            return (True, "owner")
        
        # Get shared user emails for user-specific access check
        shared_user_emails = self.repository.find_share_user_emails(db, share_id)
        
        return share_link.can_be_accessed_by_user(user_id, user_email, shared_user_emails)

    def list_shared_with_me(
        self,
        db: DBSession,
        user_email: str,
        base_url: str = ""
    ) -> List[SharedWithMeItem]:
        """
        List all chats that have been shared with the current user.
        
        Args:
            db: Database session
            user_email: Email of the current user
            base_url: Base URL for building share URLs
        
        Returns:
            List of SharedWithMeItem objects
        """
        if not user_email:
            return []
        
        shares = self.repository.find_shares_for_user_email(db, user_email)
        
        return [
            SharedWithMeItem(
                share_id=s["share_id"],
                title=s["title"],
                owner_email=s["owner_email"],
                access_level=s["access_level"],
                shared_at=s["shared_at"],
                share_url=build_share_url(s["share_id"], base_url),
                session_id=s.get("session_id") if s.get("access_level") == "RESOURCE_EDITOR" else None,
            )
            for s in shares
        ]

    def fork_shared_chat(
        self,
        db: DBSession,
        share_id: str,
        user_id: str,
        user_email: Optional[str] = None
    ) -> ForkSharedChatResponse:
        """
        Fork a shared chat into the user's own sessions.
        Creates a new session with copies of the chat tasks from the shared session.
        
        Args:
            db: Database session
            share_id: Share ID to fork
            user_id: User ID of the person forking
            user_email: User email for access check
        
        Returns:
            ForkSharedChatResponse with new session details
        
        Raises:
            ValueError: If share not found
            PermissionError: If user doesn't have access
        """
        import uuid
        
        # Get the share link
        share_link = self.repository.find_by_share_id(db, share_id)
        if not share_link or share_link.is_deleted():
            raise ValueError("Share link not found")
        
        # Check access permissions
        shared_user_emails = self.repository.find_share_user_emails(db, share_id)
        can_access, reason = share_link.can_be_accessed_by_user(user_id, user_email, shared_user_emails)
        
        # Owner can also fork
        if not can_access and share_link.user_id != user_id:
            if reason == "authentication_required":
                raise PermissionError("Authentication required to fork this chat")
            else:
                raise PermissionError("Access denied")
        
        # Get the original session's chat tasks
        from ..repository.chat_task_repository import ChatTaskRepository
        task_repo = ChatTaskRepository()
        original_tasks = task_repo.find_by_session(db, share_link.session_id, share_link.user_id)
        
        if not original_tasks:
            raise ValueError("No messages found in the shared session")
        
        # Create a new session for the forking user
        from ..services.session_service import SessionService
        session_service = SessionService(self.component)
        
        fork_title = f"{share_link.title or 'Untitled'} (forked)"
        new_session = session_service.create_session(
            db=db,
            user_id=user_id,
            name=fork_title,
        )
        
        if not new_session:
            raise ValueError("Failed to create new session for fork")
        
        # Copy chat tasks to the new session with forked context metadata
        from ..repository.entities.chat_task import ChatTask
        from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
        import json as json_mod
        
        original_session_id = share_link.session_id
        original_owner_id = share_link.user_id
        
        for original_task in original_tasks:
            new_task_id = str(uuid.uuid4())
            now_ms = now_epoch_ms()
            
            # Add forked context info to task metadata so the A2A orchestrator
            # can find the original conversation history
            new_metadata = None
            if original_task.task_metadata:
                try:
                    meta = json_mod.loads(original_task.task_metadata)
                    meta["task_id"] = new_task_id
                    meta["forked_from"] = original_task.id
                    meta["forked_from_session_id"] = original_session_id
                    meta["forked_from_owner_id"] = original_owner_id
                    meta.pop("status", None)
                    new_metadata = json_mod.dumps(meta)
                except (json_mod.JSONDecodeError, TypeError):
                    new_metadata = json_mod.dumps({
                        "task_id": new_task_id,
                        "forked_from": original_task.id,
                        "forked_from_session_id": original_session_id,
                        "forked_from_owner_id": original_owner_id,
                    })
            else:
                new_metadata = json_mod.dumps({
                    "task_id": new_task_id,
                    "forked_from_session_id": original_session_id,
                    "forked_from_owner_id": original_owner_id,
                })
            
            new_task = ChatTask(
                id=new_task_id,
                session_id=new_session.id,
                user_id=user_id,
                user_message=original_task.user_message,
                message_bubbles=original_task.message_bubbles,
                task_metadata=new_metadata,
                created_time=now_ms,
                updated_time=now_ms,
            )
            task_repo.save(db, new_task)
        
        db.commit()
        
        log.info(
            f"User {user_id} forked shared chat {share_id} into new session {new_session.id} "
            f"with {len(original_tasks)} tasks"
        )
        
        return ForkSharedChatResponse(
            session_id=new_session.id,
            session_name=fork_title,
            message=f"Chat forked successfully with {len(original_tasks)} messages"
        )
