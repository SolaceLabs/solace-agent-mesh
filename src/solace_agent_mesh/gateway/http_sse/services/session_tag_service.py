"""
Service layer for session tag operations.
"""

import uuid
from typing import Optional
from sqlalchemy.orm import Session as DBSession

from solace_ai_connector.common.log import log

from ..repository.interfaces import ISessionTagRepository, ISessionRepository
from ..repository.entities.session_tag import SessionTag
from ..shared.types import UserId, SessionId
from ..shared import now_epoch_ms


class SessionTagService:
    """Service for managing session tags (bookmarks)."""

    def __init__(
        self,
        session_tag_repository: ISessionTagRepository,
        session_repository: ISessionRepository,
    ):
        self.session_tag_repository = session_tag_repository
        self.session_repository = session_repository

    def get_user_session_tags(self, db_session: DBSession, user_id: UserId) -> list[SessionTag]:
        """Get all session tags for a user, sorted by position."""
        if not user_id or user_id.strip() == "":
            raise ValueError("User ID cannot be empty")

        tags = self.session_tag_repository.find_by_user(db_session, user_id)
        # Sort by position
        return sorted(tags, key=lambda x: x.position)

    def create_session_tag(
        self,
        db_session: DBSession,
        user_id: UserId,
        tag: str,
        description: Optional[str] = None,
        add_to_session: bool = False,
        session_id: Optional[SessionId] = None,
    ) -> SessionTag:
        """Create a new session tag."""
        if not user_id or user_id.strip() == "":
            raise ValueError("User ID cannot be empty")

        if not tag or tag.strip() == "":
            raise ValueError("Tag cannot be empty")

        # Check if tag already exists
        existing_tag = self.session_tag_repository.find_by_user_and_tag(db_session, user_id, tag)
        if existing_tag:
            return existing_tag

        # Get next position
        max_position = self.session_tag_repository.get_max_position(db_session, user_id)
        position = max_position + 1

        # Create new tag
        now_ms = now_epoch_ms()
        session_tag = SessionTag(
            id=str(uuid.uuid4()),
            user_id=user_id,
            tag=tag,
            description=description,
            count=1 if add_to_session else 0,
            position=position,
            created_time=now_ms,
            updated_time=now_ms,
        )

        saved_tag = self.session_tag_repository.save(db_session, session_tag)

        # Add tag to session if requested
        if add_to_session and session_id:
            self._add_tag_to_session(db_session, user_id, session_id, tag)

        log.info("Created session tag '%s' for user %s", tag, user_id)
        return saved_tag

    def update_session_tag(
        self,
        db_session: DBSession,
        user_id: UserId,
        old_tag: str,
        new_tag: Optional[str] = None,
        description: Optional[str] = None,
        position: Optional[int] = None,
    ) -> Optional[SessionTag]:
        """Update an existing session tag."""
        if not user_id or user_id.strip() == "":
            raise ValueError("User ID cannot be empty")

        if not old_tag or old_tag.strip() == "":
            raise ValueError("Old tag cannot be empty")

        existing_tag = self.session_tag_repository.find_by_user_and_tag(db_session, user_id, old_tag)
        if not existing_tag:
            return None

        # Check if new tag name conflicts
        if new_tag and new_tag != old_tag:
            conflicting_tag = self.session_tag_repository.find_by_user_and_tag(db_session, user_id, new_tag)
            if conflicting_tag:
                raise ValueError("Tag already exists")

        # Update tag properties
        if new_tag:
            existing_tag.tag = new_tag
        if description is not None:
            existing_tag.description = description
        if position is not None:
            # Adjust positions if needed
            if position != existing_tag.position:
                self.session_tag_repository.adjust_positions(
                    db_session, user_id, existing_tag.position, position
                )
            existing_tag.position = position

        existing_tag.updated_time = now_epoch_ms()

        updated_tag = self.session_tag_repository.save(db_session, existing_tag)
        log.info("Updated session tag '%s' for user %s", old_tag, user_id)
        return updated_tag

    def delete_session_tag(self, db_session: DBSession, user_id: UserId, tag: str) -> bool:
        """Delete a session tag."""
        if not user_id or user_id.strip() == "":
            raise ValueError("User ID cannot be empty")

        if not tag or tag.strip() == "":
            raise ValueError("Tag cannot be empty")

        existing_tag = self.session_tag_repository.find_by_user_and_tag(db_session, user_id, tag)
        if not existing_tag:
            return False

        # Remove this tag from all sessions that have it
        self._remove_tag_from_all_sessions(db_session, user_id, tag)

        # Delete the tag
        deleted = self.session_tag_repository.delete(db_session, user_id, tag)
        if deleted:
            # Update positions of remaining tags
            self.session_tag_repository.update_positions_after_delete(
                db_session, user_id, existing_tag.position
            )
            log.info("Deleted session tag '%s' for user %s and removed from all sessions", tag, user_id)

        return deleted

    def update_session_tags(
        self, db_session: DBSession, user_id: UserId, session_id: SessionId, tags: list[str]
    ) -> list[str]:
        """Update tags for a specific session."""
        if not user_id or user_id.strip() == "":
            raise ValueError("User ID cannot be empty")

        if not session_id or session_id.strip() == "":
            raise ValueError("Session ID cannot be empty")

        # Get current session
        session = self.session_repository.find_user_session(db_session, session_id, user_id)
        if not session:
            raise ValueError("Session not found")

        # Get current tags
        current_tags = session.tags or []
        current_tags_set = set(current_tags)
        new_tags_set = set(tags)

        # Find added and removed tags
        added_tags = new_tags_set - current_tags_set
        removed_tags = current_tags_set - new_tags_set

        # Update tag counts
        for tag in added_tags:
            existing_tag = self.session_tag_repository.find_by_user_and_tag(db_session, user_id, tag)
            if existing_tag:
                existing_tag.increment_count()
                existing_tag.updated_time = now_epoch_ms()
                self.session_tag_repository.save(db_session, existing_tag)

        for tag in removed_tags:
            existing_tag = self.session_tag_repository.find_by_user_and_tag(db_session, user_id, tag)
            if existing_tag:
                existing_tag.decrement_count()
                existing_tag.updated_time = now_epoch_ms()
                self.session_tag_repository.save(db_session, existing_tag)

        # Update the session's tags field
        session.update_tags(tags)
        self.session_repository.save(db_session, session)
        
        log.info("Updated tags for session %s: %s", session_id, tags)
        return tags

    def _add_tag_to_session(self, db_session: DBSession, user_id: UserId, session_id: SessionId, tag: str) -> None:
        """Add a tag to a session (helper method)."""
        session = self.session_repository.find_user_session(db_session, session_id, user_id)
        if session:
            current_tags = session.tags or []
            if tag not in current_tags:
                current_tags.append(tag)
                session.update_tags(current_tags)
                self.session_repository.save(db_session, session)
                log.debug("Adding tag '%s' to session %s for user %s", tag, session_id, user_id)

    def _remove_tag_from_all_sessions(self, db_session: DBSession, user_id: UserId, tag: str) -> None:
        """Remove a tag from all sessions that have it (helper method)."""
        # Get all sessions for the user
        all_sessions = self.session_repository.find_by_user(db_session, user_id, pagination=None)
        
        # Remove the tag from each session that has it
        for session in all_sessions:
            if session.tags and tag in session.tags:
                updated_tags = [t for t in session.tags if t != tag]
                session.update_tags(updated_tags)
                self.session_repository.save(db_session, session)
                log.debug("Removed tag '%s' from session %s", tag, session.id)