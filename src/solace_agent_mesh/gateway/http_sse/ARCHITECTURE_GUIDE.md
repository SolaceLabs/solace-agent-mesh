# Clean Architecture Development Guide

This guide explains how to implement new features in the Solace Agent Mesh HTTP SSE Gateway following clean architecture principles.

## 🏗️ Architecture Overview

The codebase follows **Clean Architecture** with clear separation of concerns:

```
src/solace_agent_mesh/gateway/http_sse/
├── domain/              # Business logic and entities
├── application/         # Use cases and services
├── infrastructure/      # External concerns (database, etc.)
├── api/                # Controllers and DTOs
└── shared/             # Common utilities
```

**Dependency Flow**: `API → Application → Domain ← Infrastructure`

## 📋 Step-by-Step Implementation Guide

### Step 1: Define Domain Entity

**Location**: `domain/entities/`

Create your business entity with validation and behavior:

```python
# domain/entities/user.py
from datetime import datetime, timezone
from pydantic import BaseModel
from ...shared.types import UserId
from ...shared.enums import UserStatus

class User(BaseModel):
    id: UserId
    email: str
    name: str
    status: UserStatus = UserStatus.ACTIVE
    created_at: datetime
    updated_at: datetime | None = None

    def update_name(self, new_name: str) -> None:
        if not new_name or len(new_name.strip()) == 0:
            raise ValueError("User name cannot be empty")
        
        self.name = new_name.strip()
        self.updated_at = datetime.now(timezone.utc)

    def activate(self) -> None:
        self.status = UserStatus.ACTIVE
        self.updated_at = datetime.now(timezone.utc)

    def deactivate(self) -> None:
        self.status = UserStatus.INACTIVE
        self.updated_at = datetime.now(timezone.utc)
```

**Update** `domain/entities/__init__.py`:
```python
from .session import Session, Message, SessionHistory
from .user import User

__all__ = ["Session", "Message", "SessionHistory", "User"]
```

### Step 2: Define Repository Interface

**Location**: `domain/repositories/`

Define what operations your entity needs (interface only):

```python
# domain/repositories/user_repository.py
from abc import ABC, abstractmethod
from typing import List, Optional

from ...shared.types import PaginationInfo, UserId
from ..entities.user import User

class IUserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: UserId) -> Optional[User]:
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    def get_all(self, pagination: Optional[PaginationInfo] = None) -> List[User]:
        pass

    @abstractmethod
    def create(self, user: User) -> User:
        pass

    @abstractmethod
    def update(self, user: User) -> Optional[User]:
        pass

    @abstractmethod
    def delete(self, user_id: UserId) -> bool:
        pass
```

**Update** `domain/repositories/__init__.py`:
```python
from .session_repository import ISessionRepository, IMessageRepository
from .user_repository import IUserRepository

__all__ = ["ISessionRepository", "IMessageRepository", "IUserRepository"]
```

### Step 3: Create Application Service

**Location**: `application/services/`

Implement your business use cases:

```python
# application/services/user_service.py
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from ...domain.entities.user import User
from ...domain.repositories.user_repository import IUserRepository
from ...shared.enums import UserStatus
from ...shared.types import PaginationInfo, UserId

class UserService:
    def __init__(self, user_repository: IUserRepository):
        self.user_repository = user_repository

    def get_user_by_id(self, user_id: UserId) -> Optional[User]:
        return self.user_repository.get_by_id(user_id)

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.user_repository.get_by_email(email)

    def get_all_users(self, pagination: Optional[PaginationInfo] = None) -> List[User]:
        return self.user_repository.get_all(pagination)

    def create_user(self, email: str, name: str, user_id: Optional[str] = None) -> User:
        if not email or not email.strip():
            raise ValueError("Email cannot be empty")
        
        if not name or not name.strip():
            raise ValueError("Name cannot be empty")

        # Check if user already exists
        existing_user = self.user_repository.get_by_email(email)
        if existing_user:
            raise ValueError(f"User with email {email} already exists")

        if not user_id:
            user_id = str(uuid.uuid4())

        now = datetime.now(timezone.utc)
        user = User(
            id=user_id,
            email=email.strip().lower(),
            name=name.strip(),
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

        return self.user_repository.create(user)

    def update_user_name(self, user_id: UserId, name: str) -> Optional[User]:
        user = self.user_repository.get_by_id(user_id)
        if not user:
            return None

        user.update_name(name)
        return self.user_repository.update(user)

    def deactivate_user(self, user_id: UserId) -> Optional[User]:
        user = self.user_repository.get_by_id(user_id)
        if not user:
            return None

        user.deactivate()
        return self.user_repository.update(user)
```

**Update** `application/services/__init__.py`:
```python
from .session_service import SessionService
from .user_service import UserService

__all__ = ["SessionService", "UserService"]
```

### Step 4: Create Database Model

**Location**: `infrastructure/persistence/models.py`

Add your SQLAlchemy model to the existing file:

```python
# Add to existing infrastructure/persistence/models.py
class UserModel(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

**Update** `infrastructure/persistence/__init__.py`:
```python
from .database_service import DatabaseService
from .models import Base, SessionModel, MessageModel, UserModel

__all__ = ["DatabaseService", "Base", "SessionModel", "MessageModel", "UserModel"]
```

### Step 5: Implement Repository

**Location**: `infrastructure/repositories/`

Implement the actual database operations:

```python
# infrastructure/repositories/user_repository.py
from typing import List, Optional

from ...domain.entities.user import User
from ...domain.repositories.user_repository import IUserRepository
from ...shared.enums import UserStatus
from ...shared.types import PaginationInfo, UserId
from ..persistence.database_service import DatabaseService
from ..persistence.models import UserModel

class UserRepository(IUserRepository):
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    def get_by_id(self, user_id: UserId) -> Optional[User]:
        with self.db_service.read_only_session() as session:
            model = session.query(UserModel).filter(UserModel.id == user_id).first()
            return self._model_to_entity(model) if model else None

    def get_by_email(self, email: str) -> Optional[User]:
        with self.db_service.read_only_session() as session:
            model = session.query(UserModel).filter(UserModel.email == email.lower()).first()
            return self._model_to_entity(model) if model else None

    def get_all(self, pagination: Optional[PaginationInfo] = None) -> List[User]:
        with self.db_service.read_only_session() as session:
            query = session.query(UserModel)

            if pagination:
                offset = (pagination.page - 1) * pagination.page_size
                query = query.offset(offset).limit(pagination.page_size)

            models = query.order_by(UserModel.created_at.desc()).all()
            return [self._model_to_entity(model) for model in models]

    def create(self, user_entity: User) -> User:
        with self.db_service.session_scope() as session:
            model = UserModel(
                id=user_entity.id,
                email=user_entity.email,
                name=user_entity.name,
                status=user_entity.status.value,
                created_at=user_entity.created_at,
                updated_at=user_entity.updated_at,
            )
            session.add(model)
            session.flush()
            session.refresh(model)
            return self._model_to_entity(model)

    def update(self, user_entity: User) -> Optional[User]:
        with self.db_service.session_scope() as session:
            model = session.query(UserModel).filter(UserModel.id == user_entity.id).first()

            if not model:
                return None

            model.email = user_entity.email
            model.name = user_entity.name
            model.status = user_entity.status.value
            model.updated_at = user_entity.updated_at

            session.flush()
            session.refresh(model)
            return self._model_to_entity(model)

    def delete(self, user_id: UserId) -> bool:
        with self.db_service.session_scope() as session:
            model = session.query(UserModel).filter(UserModel.id == user_id).first()

            if not model:
                return False

            session.delete(model)
            return True

    def _model_to_entity(self, model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            name=model.name,
            status=UserStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
```

**Update** `infrastructure/repositories/__init__.py`:
```python
from .session_repository import SessionRepository, MessageRepository
from .user_repository import UserRepository

__all__ = ["SessionRepository", "MessageRepository", "UserRepository"]
```

### Step 6: Update Dependency Injection

**Location**: `infrastructure/dependency_injection/container.py`

Add your services to the DI container:

```python
# Add these imports to the existing file
from ...application.services.user_service import UserService
from ...domain.repositories.user_repository import IUserRepository
from ...infrastructure.repositories.user_repository import UserRepository

# In the _setup_dependencies method, add:
def _setup_dependencies(self) -> None:
    if self.has_database:
        # ... existing code ...
        
        # Add user repository
        user_repository = UserRepository(database_service)
        self.container.register_singleton(IUserRepository, user_repository)

        # Add user service factory
        def user_service_factory():
            return UserService(user_repository)
        
        self.container.register_factory(UserService, user_service_factory)

# Add getter method
def get_user_service(self) -> UserService | None:
    if not self.has_database:
        return None
    return self.container.get(UserService)
```

### Step 7: Create API DTOs

**Location**: `api/dto/requests/` and `api/dto/responses/`

Create request DTOs:

```python
# api/dto/requests/user_requests.py
from pydantic import BaseModel
from typing import Optional

from ....shared.types import PaginationInfo, UserId

class GetUserRequest(BaseModel):
    user_id: UserId

class GetUsersRequest(BaseModel):
    pagination: Optional[PaginationInfo] = None

class CreateUserRequest(BaseModel):
    email: str
    name: str

class UpdateUserRequest(BaseModel):
    user_id: UserId
    name: str
```

Create response DTOs:

```python
# api/dto/responses/user_responses.py
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

from ....shared.enums import UserStatus
from ....shared.types import PaginationInfo, UserId

class UserResponse(BaseModel):
    id: UserId
    email: str
    name: str
    status: UserStatus
    created_at: datetime
    updated_at: Optional[datetime]

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total_count: int
    pagination: Optional[PaginationInfo] = None
```

### Step 8: Create API Controller

**Location**: `api/controllers/`

Implement your REST endpoints:

```python
# api/controllers/user_controller.py
from fastapi import APIRouter, Body, Depends, HTTPException, status
from solace_ai_connector.common.log import log

from ...application.services.user_service import UserService
from ...dependencies import get_user_service
from ...shared.auth_utils import get_current_user
from ..dto.requests.user_requests import (
    CreateUserRequest,
    GetUserRequest,
    GetUsersRequest,
    UpdateUserRequest,
)
from ..dto.responses.user_responses import UserListResponse, UserResponse

router = APIRouter()

@router.get("/users", response_model=UserListResponse)
async def get_all_users(
    user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    try:
        request_dto = GetUsersRequest()
        users = user_service.get_all_users(pagination=request_dto.pagination)

        user_responses = [
            UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                status=user.status,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            for user in users
        ]

        return UserListResponse(
            users=user_responses,
            total_count=len(user_responses),
            pagination=request_dto.pagination,
        )

    except Exception as e:
        log.error("Error fetching users: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users",
        )

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    try:
        user = user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error fetching user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user",
        )

@router.post("/users", response_model=UserResponse)
async def create_user(
    request: CreateUserRequest,
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    try:
        user = user_service.create_user(
            email=request.email,
            name=request.name,
        )

        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        log.error("Error creating user: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )

@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    name: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    try:
        updated_user = user_service.update_user_name(user_id, name)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return UserResponse(
            id=updated_user.id,
            email=updated_user.email,
            name=updated_user.name,
            status=updated_user.status,
            created_at=updated_user.created_at,
            updated_at=updated_user.updated_at,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("Error updating user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        )
```

### Step 9: Update Dependencies

**Location**: `dependencies.py`

Add your service dependency:

```python
# Add to dependencies.py
from .application.services.user_service import UserService

def get_user_service(
    component: "WebUIBackendComponent" = Depends(get_sac_component),
) -> UserService:
    if (
        hasattr(component, "persistence_service")
        and component.persistence_service is not None
    ):
        container = component.persistence_service.container
        return container.get_user_service()
    else:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="User management requires database configuration.",
        )
```

### Step 10: Register Routes

**Location**: `main.py`

Add your controller to the FastAPI app:

```python
# Add to main.py imports
from .api.controllers.user_controller import router as user_router

# Add to the router registration section
app.include_router(
    user_router, prefix=f"{api_prefix}/users", tags=["Users"]
)
```

### Step 11: Create Database Migration

**Location**: `alembic/versions/`

```bash
# Run this command to generate migration
alembic revision --autogenerate -m "add_users_table"
```

## 🧪 Testing Your Implementation

Test your new API endpoints:

```python
# Test script
import requests

# Test creating a user
response = requests.post("http://localhost:8080/api/v1/users", json={
    "email": "test@example.com",
    "name": "Test User"
})
print("Create user:", response.json())

# Test getting users
response = requests.get("http://localhost:8080/api/v1/users")
print("Get users:", response.json())
```

## ✅ Architecture Checklist

When implementing new features, ensure:

- [ ] **Domain Entity**: Pure business logic, no external dependencies
- [ ] **Repository Interface**: Abstract contracts in domain layer
- [ ] **Application Service**: Orchestrates domain entities and repositories
- [ ] **Infrastructure Repository**: Implements domain interfaces
- [ ] **Database Models**: SQLAlchemy models for persistence
- [ ] **API DTOs**: Request/response models for API layer
- [ ] **API Controller**: REST endpoints using application services
- [ ] **Dependency Injection**: All services registered in DI container
- [ ] **Database Migration**: Alembic migration for schema changes

## 🚫 Common Pitfalls to Avoid

1. **Don't** import infrastructure in domain layer
2. **Don't** import application services in domain layer
3. **Don't** put business logic in controllers
4. **Don't** put database queries in application services
5. **Don't** forget to register services in DI container
6. **Don't** skip validation in domain entities
7. **Don't** expose database models directly in API responses

## 📚 Additional Resources

- **Existing Examples**: Study `Session` implementation for reference
- **Clean Architecture**: Follow the dependency rule strictly
- **Testing**: Create unit tests by mocking repository interfaces
- **Error Handling**: Use domain exceptions and proper HTTP status codes

This guide ensures your new features follow the established clean architecture patterns and maintain consistency with the existing codebase.