
# Feature Architecture Guide

This guide documents the architectural standards and patterns for implementing features in the Solace Agent Mesh gateway. The **sessions implementation** serves as the source of truth and reference for all new features.

## Table of Contents

1. [3-Tiered Architecture Overview](#3-tiered-architecture-overview)
2. [File Structure and Naming](#file-structure-and-naming)
3. [Router Layer Standards](#router-layer-standards)
4. [Service Layer Standards](#service-layer-standards)
5. [Repository Layer Standards](#repository-layer-standards)
6. [DTO Standards](#dto-standards)
7. [Entity Standards](#entity-standards)
8. [Dependency Injection](#dependency-injection)
9. [Authentication and Authorization](#authentication-and-authorization)
10. [Error Handling](#error-handling)
11. [Field Naming Conventions](#field-naming-conventions)
12. [Timestamp Handling](#timestamp-handling)
13. [Common Patterns and Quirks](#common-patterns-and-quirks)

---

## 3-Tiered Architecture Overview

All features must follow the 3-tiered architecture pattern:

```
Router Layer (HTTP/API) → Service Layer (Business Logic) → Repository Layer (Data Access)
```

### Responsibilities

- **Router**: HTTP request/response handling, authentication, DTO construction
- **Service**: Business logic, validation, orchestration between repositories
- **Repository**: Data access, user-scoped queries, entity mapping

---

## File Structure and Naming

### Router Files
- **Location**: `src/solace_agent_mesh/gateway/http_sse/routers/`
- **Naming**: `{feature_name}.py` (plural form)
- **Example**: `sessions.py`, `projects.py`
- **❌ Avoid**: `session_controller.py`, `project_controller.py`

### Service Files
- **Location**: `src/solace_agent_mesh/gateway/http_sse/services/`
- **Naming**: `{feature_name}_service.py` (singular form)
- **Example**: `session_service.py`, `project_service.py`

### Repository Files
- **Location**: `src/solace_agent_mesh/gateway/http_sse/repository/`
- **Naming**: `{feature_name}_repository.py` (singular form)
- **Example**: `session_repository.py`, `project_repository.py`

### Entity Files
- **Location**: `src/solace_agent_mesh/gateway/http_sse/repository/entities/`
- **Naming**: `{feature_name}.py` (singular form)
- **Class Name**: `{FeatureName}` (singular, PascalCase)
- **Example**: `session.py` → `Session` class, `project.py` → `Project` class

### DTO Files
- **Request DTOs**: `src/solace_agent_mesh/gateway/http_sse/routers/dto/requests/{feature_name}_requests.py`
- **Response DTOs**: `src/solace_agent_mesh/gateway/http_sse/routers/dto/responses/{feature_name}_responses.py`
- **Example**: `session_requests.py`, `session_responses.py`

---

## Router Layer Standards

### File Structure Template

```python
"""
{Feature} API controller using 3-tiered architecture.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from solace_ai_connector.common.log import log

from ..dependencies import get_{feature}_service
from ..services.{feature}_service import {Feature}Service
from ..shared.auth_utils import get_current_user
from .dto.requests.{feature}_requests import (
    Get{Feature}Request,
    Get{Feature}sRequest,
    Update{Feature}Request,
    Delete{Feature}Request,
)
from .dto.responses.{feature}_responses import (
    {Feature}Response,
    {Feature}ListResponse,
)

router = APIRouter()
```

### Authentication Pattern

**✅ Always use this pattern:**

```python
@router.get("/features")
async def get_features(
    user: dict = Depends(get_current_user),
    feature_service: FeatureService = Depends(get_feature_service),
):
    user_id = user.get("id")
    # ... rest of implementation
```

### Request DTO Construction

**✅ Always build request DTOs in the router:**

```python
@router.get("/sessions")
async def get_all_sessions(
    project_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    user_id = user.get("id")
    
    # Build request DTO
    request_dto = GetSessionsRequest(user_id=user_id, project_id=project_id)
    
    # Pass DTO to service
    session_domains = session_service.get_user_sessions(
        user_id=request_dto.user_id,
        pagination=request_dto.pagination,
        project_id=request_dto.project_id,
    )
```

### Form Data Handling

**✅ No aliases in Form parameters (frontend sends snake_case):**

```python
@router.post("/projects")
async def create_project(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    system_prompt: Optional[str] = Form(None),  # ✅ No alias
    file_metadata: Optional[str] = Form(None),  # ✅ No alias
    files: Optional[List[UploadFile]] = File(None),
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
):
```

---

## Service Layer Standards

### Constructor Pattern

**✅ Always accept the component object:**

```python
class SessionService:
    def __init__(
        self,
        session_repository: ISessionRepository,
        message_repository: IMessageRepository,
        component: "WebUIBackendComponent" = None,
    ):
        self.session_repository = session_repository
        self.message_repository = message_repository
        self.component = component
```

### Business Logic Only

**✅ Services should contain business logic, NOT user access validation:**

```python
def get_user_sessions(
    self, user_id: UserId, pagination: PaginationInfo | None = None, project_id: str | None = None
) -> list[Session]:
    if not user_id or user_id.strip() == "":
        raise ValueError("User ID cannot be empty")

    # Delegate to repository with user_id
    sessions = self.session_repository.find_by_user(user_id, pagination)
    
    # Business logic filtering
    sessions = [session for session in sessions if session.project_id == project_id]
    
    return sessions
```

---

## Repository Layer Standards

### User-Scoped Data Access

**✅ Repository methods must include user_id in WHERE clauses:**

```python
def find_user_session(
    self, session_id: SessionId, user_id: UserId
) -> Session | None:
    """Find a specific session belonging to a user."""
    model = (
        self.db.query(SessionModel)
        .filter(
            SessionModel.id == session_id,
            SessionModel.user_id == user_id,  # ✅ User access control at DB level
        )
        .first()
    )
    return self._model_to_entity(model) if model else None
```

### Method Naming Pattern

- `find_by_user(user_id)` - Get all records for a user
- `find_user_{entity}(entity_id, user_id)` - Get specific record for a user
- `save(entity)` - Create or update
- `delete_user_{entity}(entity_id, user_id)` - Delete with user validation

---

## DTO Standards

### Request DTOs

**✅ Always include user_id and entity_id fields:**

```python
class GetSessionRequest(BaseModel):
    """Request DTO for retrieving a specific session."""
    session_id: SessionId
    user_id: UserId  # ✅ Always required

class UpdateSessionRequest(BaseModel):
    """Request DTO for updating session details."""
    session_id: SessionId  # ✅ Set by router
    user_id: UserId        # ✅ Set by router
    name: str = Field(..., min_length=1, max_length=255, description="New session name")
```

### Response DTOs

**✅ Always extend BaseTimestampResponse and use Field aliases:**

```python
class SessionResponse(BaseTimestampResponse):
    """Response DTO for a session."""

    id: SessionId
    user_id: UserId = Field(alias="userId")           # ✅ camelCase alias
    name: str | None = None
    agent_id: str | None = Field(default=None, alias="agentId")
    created_time: int = Field(alias="createdTime")    # ✅ int timestamp
    updated_time: int | None = Field(default=None, alias="updatedTime")
```

**✅ List responses pattern:**

```python
class SessionListResponse(BaseModel):
    """Response DTO for a list of sessions."""

    model_config = ConfigDict(populate_by_name=True)

    sessions: list[SessionResponse]
    pagination: PaginationInfo | None = None
    total_count: int = Field(alias="totalCount")
```

---

## Entity Standards

### Location and Naming

- **Location**: `src/solace_agent_mesh/gateway/http_sse/repository/entities/`
- **File**: `{feature}.py` (singular)
- **Class**: `{Feature}` (singular, PascalCase)

### Entity Structure

```python
"""
Session domain entity.
"""

from dataclasses import dataclass
from typing import Optional

from ...shared.types import SessionId, UserId


@dataclass
class Session:
    """Domain entity representing a chat session."""
    
    id: SessionId
    user_id: UserId
    name: Optional[str] = None
    agent_id: Optional[str] = None
    project_id: Optional[str] = None
    created_time: int = 0
    updated_time: Optional[int] = None
```

---

## Dependency Injection

### Service Registration

**✅ Register services in dependencies.py:**

```python
def get_session_business_service() -> SessionService:
    """Get session business service with dependencies."""
    db = next(get_db())
    session_repository = SessionRepository(db)
    message_repository = MessageRepository(db)
    
    return SessionService(
        session_repository=session_repository,
        message_repository=message_repository,
        component=sac_component_instance,  # ✅ Pass component
    )
```

---

## Authentication and Authorization

### Router Level Authentication

**✅ Always use get_current_user dependency:**

```python
@router.get("/sessions")
async def get_sessions(
    user: dict = Depends(get_current_user),  # ✅ Required
    session_service: SessionService = Depends(get_session_business_service),
):
    user_id = user.get("id")
```

### Repository Level Authorization

**✅ User access control at database query level:**

```python
def find_user_session(self, session_id: SessionId, user_id: UserId) -> Session | None:
    model = (
        self.db.query(SessionModel)
        .filter(
            SessionModel.id == session_id,
            SessionModel.user_id == user_id,  # ✅ Authorization in WHERE clause
        )
        .first()
    )
```

---

## Error Handling

### Standard HTTP Exceptions

```python
try:
    session_domain = session_service.get_session_details(
        session_id=request_dto.session_id, 
        user_id=request_dto.user_id
    )
    
    if not session_domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
        
except Exception as e:
    log.error("Error fetching session for user %s: %s", user_id, e)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to retrieve session",
    )
```

---

## Field Naming Conventions

### Backend (Python)
- **snake_case** for all internal fields
- **snake_case** in entities, services, repositories
- **snake_case** in Form parameters (matches frontend submissions)

### Frontend API (JSON)
- **camelCase** for all API responses
- **snake_case** for API requests (FormData)

### Conversion Pattern

**✅ Request Flow (Frontend → Backend):**
```
Frontend FormData (camelCase) → Router Form params with alias → Internal processing (snake_case)
```

**✅ Response Flow (Backend → Frontend):**
```
Internal data (snake_case) → Response DTO with Field(alias="camelCase") → JSON API (camelCase)
```

### Field Alias Examples

```python
# ✅ Response DTOs - Convert to camelCase
class SessionResponse(BaseTimestampResponse):
    user_id: UserId = Field(alias="userId")
    agent_id: str | None = Field(default=None, alias="agentId")
    created_time: int = Field(alias="createdTime")
    updated_time: int | None = Field(default=None, alias="updatedTime")

# ✅ Form parameters - Use aliases (frontend sends camelCase)
@router.post("/projects")
async def create_project(
    system_prompt: Optional[str] = Form(None, alias="systemPrompt"),
    file_metadata: Optional[str] = Form(None, alias="fileMetadata"),
):

# ✅ Request DTOs - Use snake_case internally (no aliases)
class CreateProjectRequest(BaseModel):
    system_prompt: Optional[str] = Field(None, description="System prompt")
    file_metadata: Optional[str] = Field(None, description="File metadata")
```

---

## Timestamp Handling

### Storage Format
- **Database**: Epoch milliseconds (INTEGER)
- **Entities**: `int` type
- **Response DTOs**: `int` type with automatic ISO conversion

### Response DTO Pattern

**✅ Always use int timestamps with BaseTimestampResponse:**

```python
class SessionResponse(BaseTimestampResponse):
    created_time: int = Field(alias="createdTime")           # ✅ int, not datetime
    updated_time: int | None = Field(default=None, alias="updatedTime")
```

### Automatic Conversion

The `BaseTimestampResponse` automatically converts epoch milliseconds to ISO 8601 strings in JSON output:

```python
# Internal: 1694123456789 (epoch ms)
# JSON API: "2023-09-07T21:30:56.789Z" (ISO string)
```

---

## Common Patterns and Quirks

### 1. Project ID Filtering in Sessions

Sessions are filtered by project_id at the service level for proper segregation:

```python
# Always filter by project_id to ensure proper segregation
# When project_id is None, only return sessions with no project_id (general chat)
# When project_id is specified, only return sessions with that specific project_id
sessions = [session for session in sessions if session.project_id == project_id]
```

### 2. ConfigDict Pattern

**✅ Always include in list response DTOs:**

```python
class SessionListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)  # ✅ Required for alias support
```

### 3. Optional vs Required Fields

**✅ Request DTOs - Required fields for routing:**

```python
class UpdateSessionRequest(BaseModel):
    session_id: SessionId  # ✅ Required - set by router from path
    user_id: UserId        # ✅ Required - set by router from auth
    name: str = Field(..., min_length=1)  # ✅ Required - from request body
```

### 4. Import Organization

**✅ Standard import order:**

```python
# Standard library
from typing import Optional

# Third-party
from fastapi import APIRouter, Depends
from solace_ai_connector.common.log import log

# Local - dependencies
from ..dependencies import get_session_service

# Local - services  
from ..services.session_service import SessionService

# Local - services  
from ..services.session_service import SessionService

# Local - DTOs
from .dto.requests.session_requests import GetSessionRequest
from .dto.responses.session_responses import SessionResponse
```

### 5. Validation Patterns

**✅ Field validation in request DTOs:**

```python
class UpdateSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="New session name")
    description: Optional[str] = Field(None, max_length=1000, description="Session description")
```

### 6. Entity to Response Conversion

**✅ Manual mapping in router (not automatic):**

```python
session_responses = []
for domain in session_domains:
    session_response = SessionResponse(
        id=domain.id,
        user_id=domain.user_id,
        name=domain.name,
        agent_id=domain.agent_id,
        project_id=domain.project_id,
        created_time=domain.created_time,
        updated_time=domain.updated_time,
    )
    session_responses.append(session_response)
```

### 7. Database Session Handling

**✅ Repository constructor pattern:**

```python
class SessionRepository(ISessionRepository):
    def __init__(self, db: DBSession):
        self.db = db  # ✅ Store database session
```

### 8. Logging Standards

**✅ Consistent logging patterns:**

```python
# Info logging for operations
log.info("User %s attempting to fetch session_id: %s", user_id, session_id)

# Error logging with context
log.error("Error fetching sessions for user %s: %s", user_id, e)
```

---

## Migration Checklist

When implementing a new feature or refactoring an existing one, use this checklist:

### File Structure
- [ ] Router named `{feature}.py` (plural)
- [ ] Service named `{feature}_service.py` (singular)
- [ ] Repository named `{feature}_repository.py` (singular)
- [ ] Entity in `repository/entities/{feature}.py` (singular)
- [ ] Request DTOs in `routers/dto/requests/{feature}_requests.py`
- [ ] Response DTOs in `routers/dto/responses/{feature}_responses.py`

### Router Layer
- [ ] Uses `Depends(get_current_user)` for authentication
- [ ] Builds request DTOs instead of passing individual parameters
- [ ] Use aliases in Form parameters (frontend sends camelCase)
- [ ] Proper error handling with HTTPException
- [ ] Consistent logging

### Service Layer
- [ ] Constructor accepts `component: WebUIBackendComponent`
- [ ] Contains business logic only (no user access validation)
- [ ] Delegates data access to repository with user_id

### Repository Layer
- [ ] All user-scoped methods include `user_id` in WHERE clauses
- [ ] Methods named: `find_by_user`, `find_user_{entity}`, etc.
- [ ] Returns domain entities, not database models

### DTOs
- [ ] Request DTOs include required `user_id` and entity ID fields
- [ ] Response DTOs extend `BaseTimestampResponse`
- [ ] Response DTOs use `Field(alias="camelCase")` for frontend
- [ ] Timestamp fields are `int` type, not `datetime`
- [ ] List responses include `ConfigDict(populate_by_name=True)`

### Dependencies
- [ ] Service registered in `dependencies.py`
- [ ] Service receives component instance
- [ ] Proper dependency injection chain

### Entities
- [ ] Located in `repository/entities/`
- [ ] Use `@dataclass` decorator
- [ ] Timestamp fields are `int` type
- [ ] Proper type hints with Optional where needed

---

## Reference Implementation

The **sessions feature** serves as the canonical reference implementation. When in doubt, always refer to:

- [`src/solace_agent_mesh/gateway/http_sse/routers/sessions.py`](src/solace_agent_mesh/gateway/http_sse/routers/sessions.py)
- [`src/solace_agent_mesh/gateway/http_sse/services/session_service.py`](src/solace_agent_mesh/gateway/http_sse/services/session_service.py)
- [`src/solace_agent_mesh/gateway/http_sse/repository/session_repository.py`](src/solace_agent_mesh/gateway/http_sse/repository/session_repository.py)
- [`src/solace_agent_mesh/gateway/http_sse/repository/entities/session.py`](src/solace_agent_mesh/gateway/http_sse/repository/entities/session.py)
- [`src/solace_agent_mesh/gateway/http_sse/routers/dto/requests/session_requests.py`](src/solace_agent_mesh/gateway/http_sse/routers/dto/requests/session_requests.py)
- [`src/solace_agent_mesh/gateway/http_sse/routers/dto/responses/session_responses.py`](src/solace_agent_mesh/gateway/http_sse/routers/dto/responses/session_responses.py)

---

## Anti-Patterns to Avoid

### ❌ Wrong File Naming
```
project_controller.py  # Should be projects.py
ProjectDomain         # Should be Project
```

### ❌ Wrong DTO Location
```
domain/entities/project_domain.py  # Should be repository/entities/project.py
```

### ❌ User Access Validation in Service
```python
# ❌ Don't do this in service
def get_project(self, project_id: str, user_id: str):
    project = self.repository.get_by_id(project_id)
    if project.user_id != user_id:
        raise UnauthorizedError()
```

### ❌ Datetime in Response DTOs
```python
# ❌ Wrong timestamp type
created_at: datetime = Field(alias="createdAt")

# ✅ Correct timestamp type  
created_time: int = Field(alias="createdTime")
```

### ❌ Missing Aliases in Form Parameters
```python
# ❌ Missing aliases (frontend sends camelCase)
system_prompt: str = Form(...)

# ✅ Use aliases to convert from camelCase
system_prompt: str = Form(..., alias="systemPrompt")
```

### ❌ Individual Dependencies in Service Constructor
```python
# ❌ Don't pass individual dependencies
def __init__(self, app_name: str, artifact_service: ArtifactService):

# ✅ Pass component object
def __init__(self, component: WebUIBackendComponent):
```

---

This guide ensures consistency across all features and maintains the high-quality architectural standards established by the sessions implementation.