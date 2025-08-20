"""
Repository interface and implementation using industry standards.
Following the Repository pattern with SQLAlchemy best practices.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from ...shared.types import FilterInfo, PaginationInfo, SortInfo
from ..persistence.database_service import DatabaseService

T = TypeVar("T")
EntityType = TypeVar("EntityType")


class IBaseRepository(ABC, Generic[T]):
    """Base repository interface defining common operations."""

    @abstractmethod
    def get_by_id(self, entity_id: str) -> T | None:
        pass

    @abstractmethod
    def get_all(
        self,
        pagination: PaginationInfo | None = None,
        sort: SortInfo | None = None,
        filters: list[FilterInfo] | None = None,
    ) -> list[T]:
        """Retrieve all entities with optional pagination, sorting, and filtering."""
        pass

    @abstractmethod
    def create(self, entity_data: dict[str, Any]) -> T:
        pass

    @abstractmethod
    def update(self, entity_id: str, entity_data: dict[str, Any]) -> T | None:
        pass

    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        pass

    @abstractmethod
    def exists(self, entity_id: str) -> bool:
        """Check if an entity exists."""
        pass

    @abstractmethod
    def count(self, filters: list[FilterInfo] | None = None) -> int:
        """Count entities with optional filtering."""
        pass


class BaseRepository(IBaseRepository[EntityType], Generic[EntityType]):
    """
    Repository implementation using industry-standard patterns.

    Features:
    - Automatic transaction management via DatabaseService
    - Separation of read/write operations
    - No manual session management required
    - Clean, testable design
    """

    def __init__(self, db_service: DatabaseService, model_class: type):
        self.db_service = db_service
        self.model_class = model_class

    def get_by_id(self, entity_id: str) -> EntityType | None:
        """Retrieve an entity by its ID (read-only operation)."""
        with self.db_service.read_only_session() as session:
            return (
                session.query(self.model_class)
                .filter(self.model_class.id == entity_id)
                .first()
            )

    def get_all(
        self,
        pagination: PaginationInfo | None = None,
        sort: SortInfo | None = None,
        filters: list[FilterInfo] | None = None,
    ) -> list[EntityType]:
        """Retrieve all entities with optional pagination, sorting, and filtering."""
        with self.db_service.read_only_session() as session:
            query = session.query(self.model_class)

            # Apply filters
            if filters:
                query = self._apply_filters(query, filters)

            # Apply sorting
            if sort:
                query = self._apply_sorting(query, sort)

            # Apply pagination
            if pagination:
                offset = (pagination.page - 1) * pagination.page_size
                query = query.offset(offset).limit(pagination.page_size)

            return query.all()

    def create(self, entity_data: dict[str, Any]) -> EntityType:
        with self.db_service.session_scope() as session:
            entity = self.model_class(**entity_data)
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return entity

    def update(self, entity_id: str, entity_data: dict[str, Any]) -> EntityType | None:
        with self.db_service.session_scope() as session:
            entity = (
                session.query(self.model_class)
                .filter(self.model_class.id == entity_id)
                .first()
            )

            if not entity:
                return None

            for key, value in entity_data.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)

            session.flush()
            session.refresh(entity)
            return entity

    def delete(self, entity_id: str) -> bool:
        with self.db_service.session_scope() as session:
            entity = (
                session.query(self.model_class)
                .filter(self.model_class.id == entity_id)
                .first()
            )

            if not entity:
                return False

            session.delete(entity)
            return True

    def exists(self, entity_id: str) -> bool:
        """Check if an entity exists (read-only operation)."""
        with self.db_service.read_only_session() as session:
            return (
                session.query(self.model_class)
                .filter(self.model_class.id == entity_id)
                .first()
                is not None
            )

    def count(self, filters: list[FilterInfo] | None = None) -> int:
        """Count entities with optional filtering (read-only operation)."""
        with self.db_service.read_only_session() as session:
            query = session.query(self.model_class)

            if filters:
                query = self._apply_filters(query, filters)

            return query.count()

    def _apply_filters(self, query, filters: list[FilterInfo]):
        """Apply filtering to the query."""
        for filter_info in filters:
            field = getattr(self.model_class, filter_info.field, None)
            if not field:
                continue

            if filter_info.operator == "eq":
                query = query.filter(field == filter_info.value)
            elif filter_info.operator == "ne":
                query = query.filter(field != filter_info.value)
            elif filter_info.operator == "gt":
                query = query.filter(field > filter_info.value)
            elif filter_info.operator == "lt":
                query = query.filter(field < filter_info.value)
            elif filter_info.operator == "gte":
                query = query.filter(field >= filter_info.value)
            elif filter_info.operator == "lte":
                query = query.filter(field <= filter_info.value)
            elif filter_info.operator == "contains":
                query = query.filter(field.contains(filter_info.value))
            elif filter_info.operator == "in":
                query = query.filter(field.in_(filter_info.value))

        return query

    def _apply_sorting(self, query, sort: SortInfo):
        """Apply sorting to the query."""
        field = getattr(self.model_class, sort.field, None)
        if not field:
            return query

        if sort.direction.lower() == "desc":
            return query.order_by(field.desc())
        else:
            return query.order_by(field.asc())
