"""
SQLAlchemy-based implementation of ISessionTagRepository.
"""

from typing import Optional
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import and_, func

from ..shared.types import UserId
from .interfaces import ISessionTagRepository
from .entities.session_tag import SessionTag
from .models.session_tag_model import SessionTagModel


class SessionTagRepository(ISessionTagRepository):
    """SQLAlchemy implementation of session tag repository."""

    def find_by_user(self, session: DBSession, user_id: UserId) -> list[SessionTag]:
        """Find all session tags for a specific user."""
        models = (
            session.query(SessionTagModel)
            .filter(SessionTagModel.user_id == user_id)
            .order_by(SessionTagModel.position)
            .all()
        )
        return [self._model_to_entity(model) for model in models]

    def find_by_user_and_tag(self, session: DBSession, user_id: UserId, tag: str) -> Optional[SessionTag]:
        """Find a specific session tag for a user."""
        model = (
            session.query(SessionTagModel)
            .filter(
                and_(
                    SessionTagModel.user_id == user_id,
                    SessionTagModel.tag == tag
                )
            )
            .first()
        )
        return self._model_to_entity(model) if model else None

    def save(self, session: DBSession, session_tag: SessionTag) -> SessionTag:
        """Save or update a session tag."""
        model = (
            session.query(SessionTagModel)
            .filter(SessionTagModel.id == session_tag.id)
            .first()
        )

        if model:
            # Update existing
            model.user_id = session_tag.user_id
            model.tag = session_tag.tag
            model.description = session_tag.description
            model.count = session_tag.count
            model.position = session_tag.position
            model.created_time = session_tag.created_time
            model.updated_time = session_tag.updated_time
        else:
            # Create new
            model = SessionTagModel(
                id=session_tag.id,
                user_id=session_tag.user_id,
                tag=session_tag.tag,
                description=session_tag.description,
                count=session_tag.count,
                position=session_tag.position,
                created_time=session_tag.created_time,
                updated_time=session_tag.updated_time,
            )
            session.add(model)

        session.flush()
        return self._model_to_entity(model)

    def delete(self, session: DBSession, user_id: UserId, tag: str) -> bool:
        """Delete a session tag for a user."""
        deleted_count = (
            session.query(SessionTagModel)
            .filter(
                and_(
                    SessionTagModel.user_id == user_id,
                    SessionTagModel.tag == tag
                )
            )
            .delete()
        )
        return deleted_count > 0

    def get_max_position(self, session: DBSession, user_id: UserId) -> int:
        """Get the maximum position value for a user's tags."""
        result = (
            session.query(func.max(SessionTagModel.position))
            .filter(SessionTagModel.user_id == user_id)
            .scalar()
        )
        return result or 0

    def update_positions_after_delete(self, session: DBSession, user_id: UserId, deleted_position: int) -> None:
        """Update positions of tags after a tag is deleted."""
        session.query(SessionTagModel).filter(
            and_(
                SessionTagModel.user_id == user_id,
                SessionTagModel.position > deleted_position
            )
        ).update({SessionTagModel.position: SessionTagModel.position - 1})

    def adjust_positions(self, session: DBSession, user_id: UserId, old_position: int, new_position: int) -> None:
        """Adjust positions when a tag's position is changed."""
        if old_position == new_position:
            return

        if old_position < new_position:
            # Moving down: decrease positions of tags between old and new position
            session.query(SessionTagModel).filter(
                and_(
                    SessionTagModel.user_id == user_id,
                    SessionTagModel.position > old_position,
                    SessionTagModel.position <= new_position
                )
            ).update({SessionTagModel.position: SessionTagModel.position - 1})
        else:
            # Moving up: increase positions of tags between new and old position
            session.query(SessionTagModel).filter(
                and_(
                    SessionTagModel.user_id == user_id,
                    SessionTagModel.position >= new_position,
                    SessionTagModel.position < old_position
                )
            ).update({SessionTagModel.position: SessionTagModel.position + 1})

    def _model_to_entity(self, model: SessionTagModel) -> SessionTag:
        """Convert SQLAlchemy model to domain entity."""
        return SessionTag(
            id=model.id,
            user_id=model.user_id,
            tag=model.tag,
            description=model.description,
            count=model.count,
            position=model.position,
            created_time=model.created_time,
            updated_time=model.updated_time,
        )