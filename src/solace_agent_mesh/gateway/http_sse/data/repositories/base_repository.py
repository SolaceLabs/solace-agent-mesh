"""
Modern repository interface and implementation using industry standards.
Following the Repository pattern with SQLAlchemy best practices.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Dict, Any
from sqlalchemy.orm import Session

from ...shared.types import PaginationInfo, SortInfo, FilterInfo
from ..persistence.database_service import DatabaseService

T = TypeVar('T')
EntityType = TypeVar('EntityType')


class IBaseRepository(ABC, Generic[T]):
    """Base repository interface defining common operations."""
    
    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[T]:
        """Retrieve an entity by its ID."""
        pass
    
    @abstractmethod
    def get_all(
        self, 
        pagination: Optional[PaginationInfo] = None,
        sort: Optional[SortInfo] = None,
        filters: Optional[List[FilterInfo]] = None
    ) -> List[T]:
        """Retrieve all entities with optional pagination, sorting, and filtering."""
        pass
    
    @abstractmethod
    def create(self, entity_data: Dict[str, Any]) -> T:
        """Create a new entity."""
        pass
    
    @abstractmethod
    def update(self, entity_id: str, entity_data: Dict[str, Any]) -> Optional[T]:
        """Update an existing entity."""
        pass
    
    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """Delete an entity by its ID."""
        pass
    
    @abstractmethod
    def exists(self, entity_id: str) -> bool:
        """Check if an entity exists."""
        pass
    
    @abstractmethod
    def count(self, filters: Optional[List[FilterInfo]] = None) -> int:
        """Count entities with optional filtering."""
        pass


class ModernBaseRepository(IBaseRepository[EntityType], Generic[EntityType]):
    """
    Modern repository implementation using industry-standard patterns.
    
    Features:
    - Automatic transaction management via DatabaseService
    - Separation of read/write operations
    - No manual session management required
    - Clean, testable design
    """
    
    def __init__(self, db_service: DatabaseService, model_class: type):
        self.db_service = db_service
        self.model_class = model_class
    
    def get_by_id(self, entity_id: str) -> Optional[EntityType]:
        """Retrieve an entity by its ID (read-only operation)."""
        with self.db_service.read_only_session() as session:
            return session.query(self.model_class).filter(
                self.model_class.id == entity_id
            ).first()
    
    def get_all(
        self, 
        pagination: Optional[PaginationInfo] = None,
        sort: Optional[SortInfo] = None,
        filters: Optional[List[FilterInfo]] = None
    ) -> List[EntityType]:
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
    
    def create(self, entity_data: Dict[str, Any]) -> EntityType:
        """Create a new entity with automatic transaction management."""
        with self.db_service.session_scope() as session:
            entity = self.model_class(**entity_data)
            session.add(entity)
            session.flush()  # Get ID without committing
            session.refresh(entity)
            return entity
    
    def update(self, entity_id: str, entity_data: Dict[str, Any]) -> Optional[EntityType]:
        """Update an existing entity with automatic transaction management."""
        with self.db_service.session_scope() as session:
            entity = session.query(self.model_class).filter(
                self.model_class.id == entity_id
            ).first()
            
            if not entity:
                return None
            
            for key, value in entity_data.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            
            session.flush()
            session.refresh(entity)
            return entity
    
    def delete(self, entity_id: str) -> bool:
        """Delete an entity by its ID with automatic transaction management."""
        with self.db_service.session_scope() as session:
            entity = session.query(self.model_class).filter(
                self.model_class.id == entity_id
            ).first()
            
            if not entity:
                return False
            
            session.delete(entity)
            return True
    
    def exists(self, entity_id: str) -> bool:
        """Check if an entity exists (read-only operation)."""
        with self.db_service.read_only_session() as session:
            return session.query(self.model_class).filter(
                self.model_class.id == entity_id
            ).first() is not None
    
    def count(self, filters: Optional[List[FilterInfo]] = None) -> int:
        """Count entities with optional filtering (read-only operation)."""
        with self.db_service.read_only_session() as session:
            query = session.query(self.model_class)
            
            if filters:
                query = self._apply_filters(query, filters)
            
            return query.count()
    
    def _apply_filters(self, query, filters: List[FilterInfo]):
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


# Legacy compatibility class - gradually migrate away from this
class BaseRepository(IBaseRepository[EntityType], Generic[EntityType]):
    """
    DEPRECATED: Legacy repository implementation.
    Use ModernBaseRepository instead for new code.
    
    This class is kept for backward compatibility during the migration.
    """
    
    def __init__(self, db: Session, model_class: type):
        self.db = db
        self.model_class = model_class
    
    def get_by_id(self, entity_id: str) -> Optional[EntityType]:
        """Retrieve an entity by its ID."""
        return self.db.query(self.model_class).filter(self.model_class.id == entity_id).first()
    
    def get_all(
        self, 
        pagination: Optional[PaginationInfo] = None,
        sort: Optional[SortInfo] = None,
        filters: Optional[List[FilterInfo]] = None
    ) -> List[EntityType]:
        """Retrieve all entities with optional pagination, sorting, and filtering."""
        query = self.db.query(self.model_class)
        
        # Apply filters
        if filters:
            query = self._apply_filters(query, filters)
        
        # Apply sorting
        if sort:
            query = self._apply_sorting(query, sort)
        
        # Apply pagination
        if pagination:
            query = query.offset((pagination.page - 1) * pagination.page_size).limit(pagination.page_size)
        
        return query.all()
    
    def create(self, entity_data: Dict[str, Any]) -> EntityType:
        """Create a new entity."""
        entity = self.model_class(**entity_data)
        self.db.add(entity)
        # Note: No commit here - transaction managed by caller
        self.db.flush()
        self.db.refresh(entity)
        return entity
    
    def update(self, entity_id: str, entity_data: Dict[str, Any]) -> Optional[EntityType]:
        """Update an existing entity."""
        entity = self.get_by_id(entity_id)
        if not entity:
            return None
        
        for key, value in entity_data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        
        # Note: No commit here - transaction managed by caller
        self.db.flush()
        self.db.refresh(entity)
        return entity
    
    def delete(self, entity_id: str) -> bool:
        """Delete an entity by its ID."""
        entity = self.get_by_id(entity_id)
        if not entity:
            return False
        
        self.db.delete(entity)
        # Note: No commit here - transaction managed by caller
        return True
    
    def exists(self, entity_id: str) -> bool:
        """Check if an entity exists."""
        return self.db.query(self.model_class).filter(self.model_class.id == entity_id).first() is not None
    
    def count(self, filters: Optional[List[FilterInfo]] = None) -> int:
        """Count entities with optional filtering."""
        query = self.db.query(self.model_class)
        
        if filters:
            query = self._apply_filters(query, filters)
        
        return query.count()
    
    def _apply_filters(self, query, filters: List[FilterInfo]):
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