"""
Base repository classes with proper transaction management.

This module provides base classes for repositories that follow FastAPI best practices
for database session management and transaction handling.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from sqlalchemy.orm import Session

from .exceptions import EntityNotFoundError

T = TypeVar("T")
ModelType = TypeVar("ModelType")
EntityType = TypeVar("EntityType")


class BaseRepository(ABC, Generic[ModelType, EntityType]):
    """
    Abstract base class for repositories with common database operations.

    This base class provides common patterns for database operations
    without manual transaction management, following the principle that
    transactions should be handled at the service/API layer.
    """

    def __init__(self, model_class: type[ModelType], entity_class: type[EntityType]):
        """
        Initialize repository with model and entity classes.

        Args:
            model_class: SQLAlchemy model class
            entity_class: Pydantic entity class
        """
        self.model_class = model_class
        self.entity_class = entity_class

    @property
    @abstractmethod
    def entity_name(self) -> str:
        """Return the entity name for error messages."""
        pass

    def create(self, session: Session, create_data: dict[str, Any]) -> EntityType:
        """
        Create a new entity.

        Args:
            session: Database session (managed externally)
            create_data: Data for creating the entity

        Returns:
            Created entity

        Note:
            This method does NOT commit the transaction.
            Commit/rollback is handled by the service layer.
        """
        model_instance = self.model_class(**create_data)

        session.add(model_instance)
        session.flush()  # Flush to get generated IDs
        session.refresh(model_instance)

        entity = self.entity_class.model_validate(model_instance)

        return entity

    def get_by_id(self, session: Session, entity_id: Any) -> EntityType:
        """
        Get entity by ID.

        Args:
            session: Database session
            entity_id: Entity identifier

        Returns:
            Entity instance

        Raises:
            EntityNotFoundError: If entity not found
        """
        model_instance = (
            session.query(self.model_class)
            .filter(self.model_class.id == str(entity_id))
            .first()
        )

        if not model_instance:
            raise EntityNotFoundError(self.entity_name, entity_id)

        return self.entity_class.model_validate(model_instance)

    def get_all(
        self, session: Session, limit: int | None = None, offset: int | None = None
    ) -> list[EntityType]:
        """
        Get all entities with optional pagination.

        Args:
            session: Database session
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of entities
        """
        query = session.query(self.model_class)

        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        model_instances = query.all()
        return [
            self.entity_class.model_validate(instance) for instance in model_instances
        ]

    def update(
        self, session: Session, entity_id: Any, update_data: dict[str, Any]
    ) -> EntityType:
        """
        Update an entity.

        Args:
            session: Database session
            entity_id: Entity identifier
            update_data: Data to update

        Returns:
            Updated entity

        Raises:
            EntityNotFoundError: If entity not found
        """
        model_instance = (
            session.query(self.model_class)
            .filter(self.model_class.id == str(entity_id))
            .first()
        )

        if not model_instance:
            raise EntityNotFoundError(self.entity_name, entity_id)

        for key, value in update_data.items():
            if value is not None and hasattr(model_instance, key):
                setattr(model_instance, key, value)

        session.flush()  # Flush to validate constraints
        session.refresh(model_instance)

        entity = self.entity_class.model_validate(model_instance)

        return entity

    def delete(self, session: Session, entity_id: Any) -> None:
        """
        Delete an entity.

        Args:
            session: Database session
            entity_id: Entity identifier

        Raises:
            EntityNotFoundError: If entity not found
        """
        model_instance = (
            session.query(self.model_class)
            .filter(self.model_class.id == str(entity_id))
            .first()
        )

        if not model_instance:
            raise EntityNotFoundError(self.entity_name, entity_id)

        session.delete(model_instance)
        session.flush()  # Flush to validate constraints

    def exists(self, session: Session, entity_id: Any) -> bool:
        """
        Check if an entity exists.

        Args:
            session: Database session
            entity_id: Entity identifier

        Returns:
            True if entity exists, False otherwise
        """
        count = (
            session.query(self.model_class)
            .filter(self.model_class.id == str(entity_id))
            .count()
        )

        return count > 0

    def count(self, session: Session) -> int:
        """
        Get total count of entities.

        Args:
            session: Database session

        Returns:
            Total number of entities
        """
        return session.query(self.model_class).count()


class PaginatedRepository(BaseRepository[ModelType, EntityType]):
    """
    Base repository with pagination support.

    Concrete repositories should implement their own pagination methods
    that apply specific filters and ordering before pagination.
    """

    pass


class ValidationMixin:
    """
    Mixin for repositories that need validation logic.
    """

    def validate_create_data(self, create_data: dict[str, Any]) -> None:
        """
        Validate data before creation.

        Args:
            create_data: Data to validate

        Raises:
            ValidationError: If validation fails
        """
        pass

    def validate_update_data(self, update_data: dict[str, Any]) -> None:
        """
        Validate data before update.

        Args:
            update_data: Data to validate

        Raises:
            ValidationError: If validation fails
        """
        pass
