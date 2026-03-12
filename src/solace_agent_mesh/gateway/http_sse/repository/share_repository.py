"""
Repository for share link data access operations.
"""

import logging
import uuid
from typing import Optional, List
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import and_, or_, func

from .models.share_model import SharedLinkModel, SharedArtifactModel, SharedLinkUserModel
from .entities.share import ShareLink, SharedArtifact, SharedLinkUser
from solace_agent_mesh.shared.api.pagination import PaginationParams
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms

log = logging.getLogger(__name__)


class ShareRepository:
    """Repository for share link operations."""

    def find_by_share_id(self, db: DBSession, share_id: str) -> Optional[ShareLink]:
        """
        Find a share link by its share ID.
        
        Args:
            db: Database session
            share_id: Share ID to find
        
        Returns:
            ShareLink entity or None if not found
        """
        model = db.query(SharedLinkModel).filter(
            SharedLinkModel.share_id == share_id
        ).first()
        
        if not model:
            return None
        
        return ShareLink.model_validate(model)

    def find_by_session_id(self, db: DBSession, session_id: str, user_id: str) -> Optional[ShareLink]:
        """
        Find a share link for a specific session and user.
        
        Args:
            db: Database session
            session_id: Session ID
            user_id: User ID (owner)
        
        Returns:
            ShareLink entity or None if not found
        """
        model = db.query(SharedLinkModel).filter(
            and_(
                SharedLinkModel.session_id == session_id,
                SharedLinkModel.user_id == user_id,
                SharedLinkModel.deleted_at.is_(None)
            )
        ).first()
        
        if not model:
            return None
        
        return ShareLink.model_validate(model)

    def find_by_user(
        self, 
        db: DBSession, 
        user_id: str, 
        pagination: PaginationParams,
        search: Optional[str] = None
    ) -> List[ShareLink]:
        """
        Find share links created by a user with pagination.
        
        Args:
            db: Database session
            user_id: User ID
            pagination: Pagination parameters
            search: Optional search query for title
        
        Returns:
            List of ShareLink entities
        """
        query = db.query(SharedLinkModel).filter(
            and_(
                SharedLinkModel.user_id == user_id,
                SharedLinkModel.deleted_at.is_(None)
            )
        )
        
        # Apply search filter if provided
        if search:
            query = query.filter(
                SharedLinkModel.title.ilike(f"%{search}%")
            )
        
        # Apply pagination
        query = query.order_by(SharedLinkModel.created_time.desc())
        query = query.offset((pagination.page - 1) * pagination.page_size)
        query = query.limit(pagination.page_size)
        
        models = query.all()
        return [ShareLink.model_validate(m) for m in models]

    def count_by_user(self, db: DBSession, user_id: str, search: Optional[str] = None) -> int:
        """
        Count total share links for a user.
        
        Args:
            db: Database session
            user_id: User ID
            search: Optional search query for title
        
        Returns:
            Total count
        """
        query = db.query(func.count(SharedLinkModel.share_id)).filter(
            and_(
                SharedLinkModel.user_id == user_id,
                SharedLinkModel.deleted_at.is_(None)
            )
        )
        
        if search:
            query = query.filter(
                SharedLinkModel.title.ilike(f"%{search}%")
            )
        
        return query.scalar() or 0

    def save(self, db: DBSession, share_link: ShareLink) -> ShareLink:
        """
        Save or update a share link.
        
        Args:
            db: Database session
            share_link: ShareLink entity to save
        
        Returns:
            Saved ShareLink entity
        """
        # Check if exists
        existing = db.query(SharedLinkModel).filter(
            SharedLinkModel.share_id == share_link.share_id
        ).first()
        
        if existing:
            # Update existing
            for key, value in share_link.model_dump().items():
                setattr(existing, key, value)
            db.flush()
            db.refresh(existing)
            return ShareLink.model_validate(existing)
        else:
            # Create new
            model = SharedLinkModel(**share_link.model_dump())
            db.add(model)
            db.flush()
            db.refresh(model)
            return ShareLink.model_validate(model)

    def delete(self, db: DBSession, share_id: str, user_id: str) -> bool:
        """
        Hard delete a share link.
        
        Args:
            db: Database session
            share_id: Share ID to delete
            user_id: User ID (must be owner)
        
        Returns:
            True if deleted, False if not found or not authorized
        """
        result = db.query(SharedLinkModel).filter(
            and_(
                SharedLinkModel.share_id == share_id,
                SharedLinkModel.user_id == user_id
            )
        ).delete()
        
        return result > 0

    def soft_delete(self, db: DBSession, share_id: str, user_id: str) -> bool:
        """
        Soft delete a share link.
        
        Args:
            db: Database session
            share_id: Share ID to delete
            user_id: User ID (must be owner)
        
        Returns:
            True if deleted, False if not found or not authorized
        """
        result = db.query(SharedLinkModel).filter(
            and_(
                SharedLinkModel.share_id == share_id,
                SharedLinkModel.user_id == user_id,
                SharedLinkModel.deleted_at.is_(None)
            )
        ).update({
            'deleted_at': now_epoch_ms(),
            'updated_time': now_epoch_ms()
        })
        
        return result > 0

    # Shared Artifacts methods

    def save_artifact(self, db: DBSession, artifact: SharedArtifact) -> SharedArtifact:
        """
        Save a shared artifact reference.
        
        Args:
            db: Database session
            artifact: SharedArtifact entity
        
        Returns:
            Saved SharedArtifact entity
        """
        model = SharedArtifactModel(**artifact.model_dump(exclude={'id'}))
        db.add(model)
        db.flush()
        db.refresh(model)
        return SharedArtifact.model_validate(model)

    def find_artifacts_by_share_id(self, db: DBSession, share_id: str) -> List[SharedArtifact]:
        """
        Find all artifacts for a share link.
        
        Args:
            db: Database session
            share_id: Share ID
        
        Returns:
            List of SharedArtifact entities
        """
        models = db.query(SharedArtifactModel).filter(
            SharedArtifactModel.share_id == share_id
        ).all()
        
        return [SharedArtifact.model_validate(m) for m in models]

    def delete_artifacts_by_share_id(self, db: DBSession, share_id: str) -> int:
        """
        Delete all artifacts for a share link.
        
        Args:
            db: Database session
            share_id: Share ID
        
        Returns:
            Number of artifacts deleted
        """
        result = db.query(SharedArtifactModel).filter(
            SharedArtifactModel.share_id == share_id
        ).delete()
        
        return result

    # Shared Link Users methods

    def add_share_user(
        self,
        db: DBSession,
        share_id: str,
        user_email: str,
        added_by_user_id: str,
        access_level: str = "RESOURCE_VIEWER"
    ) -> SharedLinkUser:
        """
        Add a user to a share link.
        
        Args:
            db: Database session
            share_id: Share ID
            user_email: Email of user to add
            added_by_user_id: User ID of who is adding
            access_level: Access level for the user
        
        Returns:
            SharedLinkUser entity
        """
        model = SharedLinkUserModel(
            id=str(uuid.uuid4()),
            share_id=share_id,
            user_email=user_email.lower().strip(),
            access_level=access_level,
            added_at=now_epoch_ms(),
            added_by_user_id=added_by_user_id
        )
        db.add(model)
        db.flush()
        db.refresh(model)
        return SharedLinkUser.model_validate(model)

    def update_share_user_access(
        self,
        db: DBSession,
        share_id: str,
        user_email: str,
        new_access_level: str
    ) -> Optional[SharedLinkUser]:
        """
        Update a user's access level, preserving the original share event.
        
        On the first access-level change, copies the current access_level and
        added_at into original_access_level and original_added_at so both the
        original "gave access" and the "changed access" events are available.
        
        Args:
            db: Database session
            share_id: Share ID
            user_email: Email of user to update
            new_access_level: New access level
        
        Returns:
            Updated SharedLinkUser entity, or None if not found
        """
        model = db.query(SharedLinkUserModel).filter(
            and_(
                SharedLinkUserModel.share_id == share_id,
                func.lower(SharedLinkUserModel.user_email) == user_email.lower().strip()
            )
        ).first()

        if not model:
            return None

        # Preserve the very first access level and timestamp (only if not already set)
        if model.original_access_level is None:
            model.original_access_level = model.access_level
        if model.original_added_at is None:
            model.original_added_at = model.added_at

        # Update to the new values
        model.access_level = new_access_level
        model.added_at = now_epoch_ms()

        db.flush()
        db.refresh(model)
        return SharedLinkUser.model_validate(model)

    def find_share_users(self, db: DBSession, share_id: str) -> List[SharedLinkUser]:
        """
        Find all users with access to a share link.
        
        Args:
            db: Database session
            share_id: Share ID
        
        Returns:
            List of SharedLinkUser entities
        """
        models = db.query(SharedLinkUserModel).filter(
            SharedLinkUserModel.share_id == share_id
        ).all()
        
        return [SharedLinkUser.model_validate(m) for m in models]

    def find_share_user_emails(self, db: DBSession, share_id: str) -> List[str]:
        """
        Get list of user emails with access to a share link.
        
        Args:
            db: Database session
            share_id: Share ID
        
        Returns:
            List of user emails
        """
        results = db.query(SharedLinkUserModel.user_email).filter(
            SharedLinkUserModel.share_id == share_id
        ).all()
        
        return [r[0] for r in results]

    def check_user_has_access(self, db: DBSession, share_id: str, user_email: str) -> bool:
        """
        Check if a user has access to a share link.
        
        Args:
            db: Database session
            share_id: Share ID
            user_email: User email to check
        
        Returns:
            True if user has access, False otherwise
        """
        count = db.query(func.count(SharedLinkUserModel.id)).filter(
            and_(
                SharedLinkUserModel.share_id == share_id,
                SharedLinkUserModel.user_email == user_email.lower().strip()
            )
        ).scalar()
        
        return count > 0

    def delete_share_user(self, db: DBSession, share_id: str, user_email: str) -> bool:
        """
        Remove a user's access to a share link.
        
        Args:
            db: Database session
            share_id: Share ID
            user_email: User email to remove
        
        Returns:
            True if deleted, False if not found
        """
        result = db.query(SharedLinkUserModel).filter(
            and_(
                SharedLinkUserModel.share_id == share_id,
                SharedLinkUserModel.user_email == user_email.lower().strip()
            )
        ).delete()
        
        return result > 0

    def delete_share_users_batch(self, db: DBSession, share_id: str, user_emails: List[str]) -> int:
        """
        Remove multiple users' access to a share link.
        
        Args:
            db: Database session
            share_id: Share ID
            user_emails: List of user emails to remove
        
        Returns:
            Number of users removed
        """
        normalized_emails = [e.lower().strip() for e in user_emails]
        result = db.query(SharedLinkUserModel).filter(
            and_(
                SharedLinkUserModel.share_id == share_id,
                SharedLinkUserModel.user_email.in_(normalized_emails)
            )
        ).delete(synchronize_session='fetch')
        
        return result

    def delete_all_share_users(self, db: DBSession, share_id: str) -> int:
        """
        Remove all users' access to a share link.
        
        Args:
            db: Database session
            share_id: Share ID
        
        Returns:
            Number of users removed
        """
        result = db.query(SharedLinkUserModel).filter(
            SharedLinkUserModel.share_id == share_id
        ).delete()
        
        return result

    def has_shared_users(self, db: DBSession, share_id: str) -> bool:
        """
        Check if a share link has any user-specific shares.
        
        Args:
            db: Database session
            share_id: Share ID
        
        Returns:
            True if there are shared users, False otherwise
        """
        count = db.query(func.count(SharedLinkUserModel.id)).filter(
            SharedLinkUserModel.share_id == share_id
        ).scalar()
        
        return count > 0

    def update_user_snapshot_time(self, db: DBSession, share_id: str, user_email: str, new_time: int) -> bool:
        """
        Update the added_at (snapshot time) for a shared user.
        
        Args:
            db: Database session
            share_id: Share ID
            user_email: Email of the user to update
            new_time: New snapshot time in epoch milliseconds
        
        Returns:
            True if updated, False if user not found
        """
        result = db.query(SharedLinkUserModel).filter(
            and_(
                SharedLinkUserModel.share_id == share_id,
                func.lower(SharedLinkUserModel.user_email) == user_email.lower().strip()
            )
        ).update({"added_at": new_time})
        return result > 0

    def find_share_user_by_email(self, db: DBSession, share_id: str, user_email: str) -> Optional[SharedLinkUser]:
        """
        Find a specific shared user by email for a share link.
        
        Args:
            db: Database session
            share_id: Share ID
            user_email: Email of the user to find
        
        Returns:
            SharedLinkUser entity or None if not found
        """
        model = db.query(SharedLinkUserModel).filter(
            and_(
                SharedLinkUserModel.share_id == share_id,
                func.lower(SharedLinkUserModel.user_email) == user_email.lower().strip()
            )
        ).first()
        
        if not model:
            return None
        
        return SharedLinkUser.model_validate(model)

    def check_user_editor_access_to_session(self, db: DBSession, session_id: str, user_email: str) -> bool:
        """
        Check if a user has RESOURCE_EDITOR access to a session via sharing.
        
        Args:
            db: Database session
            session_id: Session ID to check access for
            user_email: Email of the user to check
        
        Returns:
            True if user has editor access, False otherwise
        """
        count = db.query(func.count(SharedLinkUserModel.id)).join(
            SharedLinkModel, SharedLinkModel.share_id == SharedLinkUserModel.share_id
        ).filter(
            and_(
                SharedLinkModel.session_id == session_id,
                SharedLinkModel.deleted_at.is_(None),
                func.lower(SharedLinkUserModel.user_email) == user_email.lower().strip(),
                SharedLinkUserModel.access_level == 'RESOURCE_EDITOR'
            )
        ).scalar()
        return count > 0

    def find_session_owner_for_editor(self, db: DBSession, session_id: str, user_email: str) -> Optional[str]:
        """
        Get the owner user_id of a session where the given user has editor access.
        
        Args:
            db: Database session
            session_id: Session ID
            user_email: Email of the editor user
        
        Returns:
            Owner's user_id if editor access exists, None otherwise
        """
        result = db.query(SharedLinkModel.user_id).join(
            SharedLinkUserModel, SharedLinkModel.share_id == SharedLinkUserModel.share_id
        ).filter(
            and_(
                SharedLinkModel.session_id == session_id,
                SharedLinkModel.deleted_at.is_(None),
                func.lower(SharedLinkUserModel.user_email) == user_email.lower().strip(),
                SharedLinkUserModel.access_level == 'RESOURCE_EDITOR'
            )
        ).first()
        return result[0] if result else None

    def find_shares_for_user_email(self, db: DBSession, user_email: str) -> List[dict]:
        """
        Find all share links that have been shared with a specific user email.
        Joins shared_link_users with shared_links to return share details.
        
        Args:
            db: Database session
            user_email: Email of the user to find shares for
        
        Returns:
            List of dicts with share link details and access info
        """
        from .models.session_model import SessionModel
        
        results = db.query(
            SharedLinkModel.share_id,
            SharedLinkModel.session_id,
            SharedLinkModel.title,
            SharedLinkModel.user_id,  # owner
            SharedLinkModel.created_time,
            SharedLinkUserModel.access_level,
            SharedLinkUserModel.added_at,
            SessionModel.name.label("session_name"),  # Current session name
        ).join(
            SharedLinkUserModel,
            SharedLinkModel.share_id == SharedLinkUserModel.share_id
        ).outerjoin(
            SessionModel,
            and_(
                SessionModel.id == SharedLinkModel.session_id,
                SessionModel.deleted_at.is_(None)
            )
        ).filter(
            and_(
                SharedLinkUserModel.user_email == user_email.lower().strip(),
                SharedLinkModel.deleted_at.is_(None)
            )
        ).order_by(
            SharedLinkUserModel.added_at.desc()
        ).all()
        
        return [
            {
                "share_id": r.share_id,
                "session_id": r.session_id,
                # For editors: show current session name; for viewers: show share link title (snapshot)
                "title": (r.session_name if r.access_level == "RESOURCE_EDITOR" else r.title) or r.title or "Untitled",
                "owner_email": r.user_id,
                "created_time": r.created_time,
                "access_level": r.access_level,
                "shared_at": r.added_at,
            }
            for r in results
        ]
