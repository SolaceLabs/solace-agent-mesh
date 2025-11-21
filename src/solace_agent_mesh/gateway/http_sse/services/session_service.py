import logging
import uuid
from typing import TYPE_CHECKING, Optional, List, Dict, Any

from sqlalchemy.orm import Session as DbSession

from ..repository import (
    ISessionRepository,
    Session,
)
from ..repository.chat_task_repository import ChatTaskRepository
from ..repository.entities import ChatTask
from ..shared.enums import SenderType
from ..shared.types import SessionId, UserId
from ..shared import now_epoch_ms
from ..shared.pagination import PaginationParams, PaginatedResponse, get_pagination_or_default

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent


class SessionService:
    def __init__(
        self,
        component: "WebUIBackendComponent" = None,
    ):
        self.component = component

    def _get_repositories(self, db: DbSession):
        """Create session repository for the given database session."""
        from ..repository import SessionRepository
        session_repository = SessionRepository()
        return session_repository

    def is_persistence_enabled(self) -> bool:
        """Checks if the service is configured with a persistent backend."""
        return self.component and self.component.database_url is not None

    def get_user_sessions(
        self,
        db: DbSession,
        user_id: UserId,
        pagination: PaginationParams | None = None,
        project_id: str | None = None
    ) -> PaginatedResponse[Session]:
        """
        Get paginated sessions for a user with full metadata including project names.
        Uses default pagination if none provided (page 1, size 20).
        Returns paginated response with pageNumber, pageSize, nextPage, totalPages, totalCount.

        Args:
            db: Database session
            user_id: User ID to filter sessions by
            pagination: Pagination parameters
            project_id: Optional project ID to filter sessions by (for project-specific views)
        """
        if not user_id or user_id.strip() == "":
            raise ValueError("User ID cannot be empty")

        pagination = get_pagination_or_default(pagination)
        session_repository = self._get_repositories(db)

        # Fetch sessions with optional project filtering
        sessions = session_repository.find_by_user(db, user_id, pagination, project_id=project_id)
        total_count = session_repository.count_by_user(db, user_id, project_id=project_id)

        # Enrich sessions with project names
        # Collect unique project IDs
        project_ids = [s.project_id for s in sessions if s.project_id]

        if project_ids:
            # Fetch all projects in one query
            from ..repository.models import ProjectModel
            projects = db.query(ProjectModel).filter(ProjectModel.id.in_(project_ids)).all()
            project_map = {p.id: p.name for p in projects}

            # Map project names to sessions
            for session in sessions:
                if session.project_id:
                    session.project_name = project_map.get(session.project_id)

        return PaginatedResponse.create(sessions, total_count, pagination)

    def get_session_details(
        self, db: DbSession, session_id: SessionId, user_id: UserId
    ) -> Session | None:
        if not self._is_valid_session_id(session_id):
            return None

        session_repository = self._get_repositories(db)
        return session_repository.find_user_session(db, session_id, user_id)

    def create_session(
        self,
        db: DbSession,
        user_id: UserId,
        name: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        project_id: str | None = None,
    ) -> Optional[Session]:
        if not self.is_persistence_enabled():
            log.debug("Persistence is not enabled. Skipping session creation in DB.")
            return None

        if not user_id or user_id.strip() == "":
            raise ValueError("User ID cannot be empty")

        if not session_id:
            session_id = str(uuid.uuid4())

        now_ms = now_epoch_ms()
        session = Session(
            id=session_id,
            user_id=user_id,
            name=name,
            agent_id=agent_id,
            project_id=project_id,
            created_time=now_ms,
            updated_time=now_ms,
        )

        session_repository = self._get_repositories(db)
        created_session = session_repository.save(db, session)
        log.debug("Created new session %s for user %s", created_session.id, user_id)

        if not created_session:
            raise ValueError(f"Failed to save session for {session_id}")

        return created_session

    def update_session_name(
        self, db: DbSession, session_id: SessionId, user_id: UserId, name: str
    ) -> Session | None:
        if not self._is_valid_session_id(session_id):
            raise ValueError("Invalid session ID")

        if not name or len(name.strip()) == 0:
            raise ValueError("Session name cannot be empty")

        if len(name.strip()) > 255:
            raise ValueError("Session name cannot exceed 255 characters")

        session_repository = self._get_repositories(db)
        session = session_repository.find_user_session(db, session_id, user_id)
        if not session:
            return None

        session.update_name(name)
        updated_session = session_repository.save(db, session)

        log.info("Updated session %s name to '%s'", session_id, name)
        return updated_session

    def delete_session_with_notifications(
        self, db: DbSession, session_id: SessionId, user_id: UserId
    ) -> bool:
        if not self._is_valid_session_id(session_id):
            raise ValueError("Invalid session ID")

        session_repository = self._get_repositories(db)
        session = session_repository.find_user_session(db, session_id, user_id)
        if not session:
            log.warning(
                "Attempted to delete non-existent session %s by user %s",
                session_id,
                user_id,
            )
            return False

        agent_id = session.agent_id

        if not session.can_be_deleted_by_user(user_id):
            log.warning(
                "User %s not authorized to delete session %s", user_id, session_id
            )
            return False

        deleted = session_repository.delete(db, session_id, user_id)
        if not deleted:
            return False

        log.info("Session %s deleted successfully by user %s", session_id, user_id)

        if agent_id and self.component:
            self._notify_agent_of_session_deletion(session_id, user_id, agent_id)

        return True

    def soft_delete_session(
        self, db: DbSession, session_id: SessionId, user_id: UserId
    ) -> bool:
        """
        Soft delete a session (mark as deleted without removing from database).
        
        Args:
            db: Database session
            session_id: Session ID to soft delete
            user_id: User ID performing the deletion
            
        Returns:
            bool: True if soft deleted successfully, False otherwise
        """
        if not self._is_valid_session_id(session_id):
            raise ValueError("Invalid session ID")

        session_repository = self._get_repositories(db)
        session = session_repository.find_user_session(db, session_id, user_id)
        if not session:
            log.warning(
                "Attempted to soft delete non-existent session %s by user %s",
                session_id,
                user_id,
            )
            return False

        if not session.can_be_deleted_by_user(user_id):
            log.warning(
                "User %s not authorized to soft delete session %s", user_id, session_id
            )
            return False

        deleted = session_repository.soft_delete(db, session_id, user_id)
        if not deleted:
            return False

        log.info("Session %s soft deleted successfully by user %s", session_id, user_id)
        return True

    def move_session_to_project(
        self, db: DbSession, session_id: SessionId, user_id: UserId, new_project_id: str | None
    ) -> Session | None:
        """
        Move a session to a different project.
        
        Args:
            db: Database session
            session_id: Session ID to move
            user_id: User ID performing the move
            new_project_id: New project ID (or None to remove from project)
            
        Returns:
            Session: Updated session if successful, None otherwise
            
        Raises:
            ValueError: If session or project validation fails
        """
        if not self._is_valid_session_id(session_id):
            raise ValueError("Invalid session ID")

        # Validate project exists and user has access if project_id is provided
        if new_project_id:
            from ..repository.models import ProjectModel
            project = db.query(ProjectModel).filter(
                ProjectModel.id == new_project_id,
                ProjectModel.user_id == user_id,
                ProjectModel.deleted_at.is_(None)
            ).first()
            
            if not project:
                raise ValueError(f"Project {new_project_id} not found or access denied")

        session_repository = self._get_repositories(db)
        updated_session = session_repository.move_to_project(db, session_id, user_id, new_project_id)
        
        if not updated_session:
            log.warning(
                "Failed to move session %s to project %s for user %s",
                session_id,
                new_project_id,
                user_id,
            )
            return None

        log.info(
            "Session %s moved to project %s by user %s",
            session_id,
            new_project_id or "None",
            user_id,
        )
        return updated_session

    def search_sessions(
        self,
        db: DbSession,
        user_id: UserId,
        query: str,
        pagination: PaginationParams | None = None,
        project_id: str | None = None
    ) -> PaginatedResponse[Session]:
        """
        Search sessions by name/title only.

        Args:
            db: Database session
            user_id: User ID to filter sessions by
            query: Search query string
            pagination: Pagination parameters
            project_id: Optional project ID to filter sessions by

        Returns:
            PaginatedResponse[Session]: Paginated search results
        """
        if not user_id or user_id.strip() == "":
            raise ValueError("User ID cannot be empty")

        if not query or query.strip() == "":
            raise ValueError("Search query cannot be empty")

        pagination = get_pagination_or_default(pagination)
        session_repository = self._get_repositories(db)

        # Search sessions
        sessions = session_repository.search(db, user_id, query.strip(), pagination, project_id)
        total_count = session_repository.count_search_results(db, user_id, query.strip(), project_id)

        # Enrich sessions with project names
        project_ids = [s.project_id for s in sessions if s.project_id]

        if project_ids:
            from ..repository.models import ProjectModel
            projects = db.query(ProjectModel).filter(ProjectModel.id.in_(project_ids)).all()
            project_map = {p.id: p.name for p in projects}

            for session in sessions:
                if session.project_id:
                    session.project_name = project_map.get(session.project_id)

        log.info(
            "Search for '%s' by user %s returned %d results (total: %d)",
            query,
            user_id,
            len(sessions),
            total_count,
        )

        return PaginatedResponse.create(sessions, total_count, pagination)

    def save_task(
        self,
        db: DbSession,
        task_id: str,
        session_id: str,
        user_id: str,
        user_message: Optional[str],
        message_bubbles: str,  # JSON string (opaque)
        task_metadata: Optional[str] = None  # JSON string (opaque)
    ) -> ChatTask:
        """
        Save a complete task interaction.
        
        Args:
            db: Database session
            task_id: A2A task ID
            session_id: Session ID
            user_id: User ID
            user_message: Original user input text
            message_bubbles: Array of all message bubbles displayed during this task
            task_metadata: Task-level metadata (status, feedback, agent name, etc.)
            
        Returns:
            Saved ChatTask entity
            
        Raises:
            ValueError: If session not found or validation fails
        """
        # Validate session exists and belongs to user
        session_repository = self._get_repositories(db)
        session = session_repository.find_user_session(db, session_id, user_id)
        if not session:
            raise ValueError(f"Session {session_id} not found for user {user_id}")

        # Create task entity - pass strings directly
        task = ChatTask(
            id=task_id,
            session_id=session_id,
            user_id=user_id,
            user_message=user_message,
            message_bubbles=message_bubbles,  # Already a string
            task_metadata=task_metadata,      # Already a string
            created_time=now_epoch_ms(),
            updated_time=None
        )

        # Save via repository
        task_repo = ChatTaskRepository()
        saved_task = task_repo.save(db, task)

        # Update session activity
        session.mark_activity()
        session_repository.save(db, session)
        
        log.info(f"Saved task {task_id} for session {session_id}")
        return saved_task

    def get_session_tasks(
        self,
        db: DbSession,
        session_id: str,
        user_id: str
    ) -> List[ChatTask]:
        """
        Get all tasks for a session.
        
        Args:
            db: Database session
            session_id: Session ID
            user_id: User ID
            
        Returns:
            List of ChatTask entities in chronological order
            
        Raises:
            ValueError: If session not found
        """
        # Validate session exists and belongs to user
        session_repository = self._get_repositories(db)
        session = session_repository.find_user_session(db, session_id, user_id)
        if not session:
            raise ValueError(f"Session {session_id} not found for user {user_id}")

        # Load tasks
        task_repo = ChatTaskRepository()
        return task_repo.find_by_session(db, session_id, user_id)

    def get_session_messages_from_tasks(
        self,
        db: DbSession,
        session_id: str,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get session messages by flattening task message_bubbles.
        This provides backward compatibility with the old message-based API.
        
        Args:
            db: Database session
            session_id: Session ID
            user_id: User ID
            
        Returns:
            List of message dictionaries flattened from tasks
            
        Raises:
            ValueError: If session not found
        """
        # Load tasks
        tasks = self.get_session_tasks(db, session_id, user_id)
        
        # Flatten message_bubbles from all tasks
        messages = []
        for task in tasks:
            import json
            message_bubbles = json.loads(task.message_bubbles) if isinstance(task.message_bubbles, str) else task.message_bubbles
            
            for bubble in message_bubbles:
                # Determine sender type from bubble type
                bubble_type = bubble.get("type", "agent")
                sender_type = "user" if bubble_type == "user" else "agent"
                
                # Get sender name
                if bubble_type == "user":
                    sender_name = user_id
                else:
                    # Try to get agent name from task metadata, fallback to "agent"
                    sender_name = "agent"
                    if task.task_metadata:
                        task_metadata = json.loads(task.task_metadata) if isinstance(task.task_metadata, str) else task.task_metadata
                        sender_name = task_metadata.get("agent_name", "agent")
                
                # Create message dictionary
                message = {
                    "id": bubble.get("id", str(uuid.uuid4())),
                    "session_id": session_id,
                    "message": bubble.get("text", ""),
                    "sender_type": sender_type,
                    "sender_name": sender_name,
                    "message_type": "text",
                    "created_time": task.created_time
                }
                messages.append(message)
        
        return messages

    def _is_valid_session_id(self, session_id: SessionId) -> bool:
        return (
            session_id is not None
            and session_id.strip() != ""
            and session_id not in ["null", "undefined"]
        )

    def _notify_agent_of_session_deletion(
        self, session_id: SessionId, user_id: UserId, agent_id: str
    ) -> None:
        try:
            log.info(
                "Publishing session deletion event for session %s (agent %s, user %s)",
                session_id,
                agent_id,
                user_id,
            )

            if hasattr(self.component, "sam_events"):
                success = self.component.sam_events.publish_session_deleted(
                    session_id=session_id,
                    user_id=user_id,
                    agent_id=agent_id,
                    gateway_id=self.component.gateway_id,
                )

                if success:
                    log.info(
                        "Successfully published session deletion event for session %s",
                        session_id,
                    )
                else:
                    log.warning(
                        "Failed to publish session deletion event for session %s",
                        session_id,
                    )
            else:
                log.warning(
                    "SAM Events not available for session deletion notification"
                )

        except Exception as e:
            log.warning(
                "Failed to publish session deletion event to agent %s: %s",
                agent_id,
                e,
            )

    async def compress_and_branch_session(
        self,
        db: DbSession,
        source_session_id: SessionId,
        user_id: UserId,
        agent_id: str | None = None,
        branch_name: str | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> tuple[Session, Dict[str, Any], int]:
        """
        Compress a session's conversation history and create a new session with the summary.
        
        This implements the "Compress-and-Branch" pattern where:
        1. The conversation history is compressed into a summary
        2. A new session is created as a child of the current session
        3. The summary is added as the first task in the new session
        4. The original session remains unchanged
        
        Args:
            db: Database session
            source_session_id: The session to compress
            user_id: The user creating the compressed branch
            agent_id: Optional agent ID for the new session
            branch_name: Optional custom name for the branched session
            llm_provider: LLM provider for compression (openai, anthropic, gemini)
            llm_model: Specific model to use
            
        Returns:
            Tuple of (new_session, summary_task_dict, compressed_message_count)
            
        Raises:
            ValueError: If session not found or user not authorized
        """
        if not self._is_valid_session_id(source_session_id):
            raise ValueError("Invalid source session ID")
        
        # 1. Verify source session exists and user owns it
        session_repository = self._get_repositories(db)
        source_session = session_repository.find_user_session(db, source_session_id, user_id)
        if not source_session:
            raise ValueError("Source session not found or access denied")
        
        # 2. Get all tasks from source session to compress
        tasks = self.get_session_tasks(db, source_session_id, user_id)
        if not tasks:
            raise ValueError(f"No tasks found in session {source_session_id}")
        
        # Convert tasks to messages for compression
        messages = self.get_session_messages_from_tasks(db, source_session_id, user_id)
        
        log.info(
            "Found %d tasks (%d messages) to compress in session %s",
            len(tasks),
            len(messages),
            source_session_id,
        )
        
        # 3. Get compression service and generate summary
        from .compression_service import CompressionService
        
        compression_service = CompressionService(
            session_repository,
            self.component,
        )
        
        compression_result = await compression_service.compress_conversation(
            messages=messages,
            session=source_session,
            user_id=user_id,
            compression_type="llm_summary",
            llm_provider=llm_provider,
            llm_model=llm_model,
            db_session=db,
        )
        
        log.info(
            "Generated compression summary for session %s: %d messages compressed",
            source_session_id,
            compression_result.message_count,
        )
        
        # 4. Use source session name if not provided
        if not branch_name:
            branch_name = f"Continued: {source_session.name or 'Chat'}"
        
        # 5. Create new session with compression metadata
        new_session_id = str(uuid.uuid4())
        now_ms = now_epoch_ms()
        
        compression_metadata = {
            "compression_id": compression_result.compression_id,
            "parent_session_id": source_session_id,
            "compressed_message_count": compression_result.message_count,
            "original_token_estimate": compression_result.original_token_estimate,
            "compressed_token_estimate": compression_result.compressed_token_estimate,
            "compression_timestamp": compression_result.compression_timestamp,
            "artifacts": compression_result.artifacts_metadata,
        }
        
        new_session = Session(
            id=new_session_id,
            user_id=user_id,
            name=branch_name,
            agent_id=agent_id or source_session.agent_id,
            project_id=source_session.project_id,
            created_time=now_ms,
            updated_time=now_ms,
            is_compression_branch=True,
            compression_metadata=compression_metadata,
        )
        
        created_session = session_repository.save(db, new_session)
        log.info(
            "Created compression branch session %s from %s",
            new_session_id,
            source_session_id,
        )
        
        # 6. Format and create summary task
        summary_text = self._format_compression_summary(
            compression_result,
            source_session,
        )
        
        # Create a summary task (similar to how tasks are saved)
        summary_task_id = str(uuid.uuid4())
        summary_bubble = {
            "id": str(uuid.uuid4()),
            "type": "system",
            "text": summary_text,
            "timestamp": now_ms,
        }
        
        import json
        task_metadata = {
            "type": "compression_summary",
            "parent_session_id": source_session_id,
            "compressed_message_count": compression_result.message_count,
        }
        
        summary_task = self.save_task(
            db=db,
            task_id=summary_task_id,
            session_id=new_session_id,
            user_id=user_id,
            user_message=None,
            message_bubbles=json.dumps([summary_bubble]),
            task_metadata=json.dumps(task_metadata),
        )
        
        log.info(
            "Added compression summary task to session %s (task_id: %s)",
            new_session_id,
            summary_task_id,
        )
        
        # Return summary as dict for API response
        summary_dict = {
            "id": summary_task_id,
            "session_id": new_session_id,
            "message": summary_text,
            "sender_type": "system",
            "sender_name": "System",
            "created_time": now_ms,
        }
        
        return created_session, summary_dict, compression_result.message_count
    
    def _format_compression_summary(
        self,
        compression_result,
        source_session: Session,
    ) -> str:
        """
        Format the compression summary for display in the new session.
        
        Args:
            compression_result: The CompressionResult from compression service
            source_session: The original session that was compressed
            
        Returns:
            Formatted summary text
        """
        # Format the session date
        from datetime import datetime
        session_date = "Unknown"
        if source_session.created_time:
            try:
                # created_time is in milliseconds
                dt = datetime.fromtimestamp(source_session.created_time / 1000)
                session_date = dt.strftime("%B %d, %Y")  # e.g., "November 21, 2025"
            except Exception:
                session_date = "Unknown"
        
        summary_parts = [
            "📋 **Conversation Summary** (from previous session)",
            "",
            compression_result.summary,
            "",
            "---",
            "",
            "**Context from Previous Session:**",
            f"- Session: {source_session.name or 'Untitled Chat'}",
            f"- Date: {session_date}",
            f"- Messages: {compression_result.message_count}",
            f"- Token savings: ~{compression_result.original_token_estimate - compression_result.compressed_token_estimate} tokens",
        ]
        
        if compression_result.artifacts_metadata:
            summary_parts.append(f"- Artifacts created: {len(compression_result.artifacts_metadata)}")
            summary_parts.append("")
            summary_parts.append("**Files & Artifacts:**")
            for artifact in compression_result.artifacts_metadata:
                summary_parts.append(f"- {artifact['filename']} ({artifact['type']})")
        
        summary_parts.extend([
            "",
            "---",
            "",
            "*You can continue the conversation below. I have context from the previous session.*",
        ])
        
        return "\n".join(summary_parts)
