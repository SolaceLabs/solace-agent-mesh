"""
Repository for share link data access operations.
"""

import logging
from typing import Optional, List
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import and_, or_, func

from .models.share_model import SharedLinkModel, SharedArtifactModel
from .entities.share import ShareLink, SharedArtifact
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
