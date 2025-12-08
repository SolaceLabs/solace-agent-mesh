import logging
import uuid
from typing import TYPE_CHECKING, Optional, List, Dict, Any

from sqlalchemy.orm import Session as DbSession

from ..repository import (
    ISessionRepository,
    Session,
)
from ..repository.chat_task_repository import ChatTaskRepository
from ..repository.task_repository import TaskRepository
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
        Get paginated sessions for a user with full metadata including project names and background task status.
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

        # Check for running background tasks in these sessions
        task_repo = TaskRepository()
        session_ids = [s.id for s in sessions]
        
        # Get all running background tasks for this user
        running_bg_tasks = task_repo.find_background_tasks_by_status(db, status=None)
        running_bg_tasks = [
            task for task in running_bg_tasks
            if task.status in [None, "running", "pending"] and task.end_time is None and task.user_id == user_id
        ]
        
        log.info(f"[get_user_sessions] Found {len(running_bg_tasks)} running background tasks for user {user_id}")
        
        # Create a map of session_id -> has_running_background_task
        # Query ChatTaskModel to find which sessions these tasks belong to
        # Also filter out tasks that have been marked as completed in their metadata
        from ..repository.models import ChatTaskModel
        import json
        session_task_map = {}
        if running_bg_tasks:
            task_ids = [task.id for task in running_bg_tasks]
            log.info(f"[get_user_sessions] Looking up chat tasks for task IDs: {task_ids}")
            
            # Query chat tasks for these task IDs
            chat_tasks = db.query(ChatTaskModel).filter(
                ChatTaskModel.id.in_(task_ids),
                ChatTaskModel.user_id == user_id
            ).all()
            
            log.info(f"[get_user_sessions] Found {len(chat_tasks)} chat tasks")
            
            for chat_task in chat_tasks:
                if chat_task.session_id:
                    # Check if task metadata indicates completion
                    is_completed = False
                    if chat_task.task_metadata:
                        try:
                            metadata = json.loads(chat_task.task_metadata) if isinstance(chat_task.task_metadata, str) else chat_task.task_metadata
                            task_status = metadata.get("status")
                            is_completed = task_status in ["completed", "error", "failed"]
                            log.info(f"[get_user_sessions] Task {chat_task.id} metadata status: {task_status}, is_completed: {is_completed}")
                        except Exception as e:
                            log.warning(f"[get_user_sessions] Failed to parse task metadata for {chat_task.id}: {e}")
                    
                    # Only mark session as having running task if task is not completed
                    if not is_completed:
                        session_task_map[chat_task.session_id] = True
                        log.debug(f"[get_user_sessions] Session {chat_task.session_id} has running background task {chat_task.id}")
                    else:
                        log.debug(f"[get_user_sessions] Task {chat_task.id} is completed, not marking session as having running task")
        
        # Add background task status to sessions
        for session in sessions:
            session.has_running_background_task = session_task_map.get(session.id, False)
            if session.has_running_background_task:
                log.info(f"[get_user_sessions] Marking session {session.id} as having running background task")

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

    async def move_session_to_project(
        self, db: DbSession, session_id: SessionId, user_id: UserId, new_project_id: str | None
    ) -> Session | None:
        """
        Move a session to a different project.

        When moving to a project, this also copies all project artifacts to the session
        so they are immediately available without waiting for the next user message.

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

        try:
            db.commit()
            log.info(
                "Session %s moved to project %s by user %s",
                session_id,
                new_project_id or "None",
                user_id,
            )
        except Exception as e:
            db.rollback()
            log.error(
                "Failed to commit session move for session %s: %s",
                session_id,
                e,
            )
            raise

        # Copy project artifacts to session immediately when moving to a project
        if new_project_id and self.component:
            from ..utils.artifact_copy_utils import copy_project_artifacts_to_session
            from ..services.project_service import ProjectService
            from ..dependencies import SessionLocal

            if SessionLocal:
                artifact_db = SessionLocal()
                try:
                    project_service = ProjectService(component=self.component)
                    log_prefix = f"[move_session_to_project session_id={session_id}] "

                    artifacts_copied, _ = await copy_project_artifacts_to_session(
                        project_id=new_project_id,
                        user_id=user_id,
                        session_id=session_id,
                        project_service=project_service,
                        component=self.component,
                        db=artifact_db,
                        log_prefix=log_prefix,
                    )

                    if artifacts_copied > 0:
                        log.info(
                            "%sCopied %d project artifacts to session during move",
                            log_prefix,
                            artifacts_copied,
                        )
                except Exception as e:
                    # Don't fail the move operation if artifact copying fails
                    # The session move has already been committed at this point
                    log.warning(
                        "Failed to copy project artifacts when moving session %s to project %s: %s",
                        session_id,
                        new_project_id,
                        e,
                    )
                finally:
                    artifact_db.close()

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

        # Check for running background tasks in these sessions
        task_repo = TaskRepository()
        session_ids = [s.id for s in sessions]
        
        # Get all running background tasks for this user
        running_bg_tasks = task_repo.find_background_tasks_by_status(db, status=None)
        running_bg_tasks = [
            task for task in running_bg_tasks
            if task.status in [None, "running", "pending"] and task.end_time is None and task.user_id == user_id
        ]
        
        log.info(f"[search_sessions] Found {len(running_bg_tasks)} running background tasks for user {user_id}")
        
        # Create a map of session_id -> has_running_background_task
        # Query ChatTaskModel to find which sessions these tasks belong to
        # Also filter out tasks that have been marked as completed in their metadata
        from ..repository.models import ChatTaskModel
        import json
        session_task_map = {}
        if running_bg_tasks:
            task_ids = [task.id for task in running_bg_tasks]
            log.info(f"[search_sessions] Looking up chat tasks for task IDs: {task_ids}")
            
            # Query chat tasks for these task IDs
            chat_tasks = db.query(ChatTaskModel).filter(
                ChatTaskModel.id.in_(task_ids),
                ChatTaskModel.user_id == user_id
            ).all()
            
            log.info(f"[search_sessions] Found {len(chat_tasks)} chat tasks")
            
            for chat_task in chat_tasks:
                if chat_task.session_id:
                    # Check if task metadata indicates completion
                    is_completed = False
                    if chat_task.task_metadata:
                        try:
                            metadata = json.loads(chat_task.task_metadata) if isinstance(chat_task.task_metadata, str) else chat_task.task_metadata
                            task_status = metadata.get("status")
                            is_completed = task_status in ["completed", "error", "failed"]
                            log.info(f"[search_sessions] Task {chat_task.id} metadata status: {task_status}, is_completed: {is_completed}")
                        except Exception as e:
                            log.warning(f"[search_sessions] Failed to parse task metadata for {chat_task.id}: {e}")
                    
                    # Only mark session as having running task if task is not completed
                    if not is_completed:
                        session_task_map[chat_task.session_id] = True
                        log.info(f"[search_sessions] Session {chat_task.session_id} has running background task {chat_task.id}")
                    else:
                        log.info(f"[search_sessions] Task {chat_task.id} is completed, not marking session as having running task")
        
        # Add background task status to sessions
        for session in sessions:
            session.has_running_background_task = session_task_map.get(session.id, False)
            if session.has_running_background_task:
                log.info(f"[search_sessions] Marking session {session.id} as having running background task")

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
