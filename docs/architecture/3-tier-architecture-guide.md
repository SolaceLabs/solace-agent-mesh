# 3-Tier Architecture & Coding Guide

## Overview

This document outlines the architectural patterns and coding standards for implementing features in the Solace Agent Mesh project, based on the **3-Tiered Architecture** pattern established during the Projects feature implementation.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Layer Responsibilities](#layer-responsibilities)
3. [Data Access Patterns](#data-access-patterns)
4. [Domain Model Guidelines](#domain-model-guidelines)
5. [File Structure & Naming](#file-structure--naming)
6. [Implementation Checklist](#implementation-checklist)
7. [Testing Strategy](#testing-strategy)
8. [Examples](#examples)

---

## Architecture Overview

### 3-Tier Structure

```
┌─────────────────────────────────────────┐
│           PRESENTATION LAYER            │
│                                         │
│  ┌─────────────────┐  ┌────────────────┐ │
│  │   Controllers   │  │      DTOs      │ │
│  │  (HTTP/API)     │  │ (Req/Response) │ │  
│  └─────────────────┘  └────────────────┘ │
└─────────────┬───────────────────────────┘
              │ HTTP Requests/Responses
┌─────────────▼───────────────────────────┐
│            BUSINESS LAYER               │
│                                         │
│  ┌─────────────────┐  ┌────────────────┐ │
│  │    Services     │  │ Domain Models  │ │
│  │ (Orchestration) │  │ (Business Logic│ │
│  └─────────────────┘  └────────────────┘ │
└─────────────┬───────────────────────────┘
              │ Domain Objects
┌─────────────▼───────────────────────────┐
│             DATA LAYER                  │
│                                         │
│  ┌──────────────────┐ ┌────────────────┐ │
│  │   Repositories   │ │ Database Models│ │
│  │  (Data Access)   │ │   (Persistence)│ │  
│  └──────────────────┘ └────────────────┘ │
└─────────────┬───────────────────────────┘
              │ SQL/Database Operations
┌─────────────▼───────────────────────────┐
│            DATABASE                     │
│                                         │
│         Tables & Relations              │
└─────────────────────────────────────────┘
```

### Key Principles

1. **Separation of Concerns** - Each layer has a single, well-defined responsibility
2. **Dependency Inversion** - Higher layers depend on interfaces, not implementations
3. **Single Direction Flow** - Data flows in one direction: Presentation → Business → Data
4. **Interface Segregation** - Use interfaces for repository contracts

---

## Layer Responsibilities

### 🎯 Presentation Layer (Controllers & DTOs)

**Purpose**: Handle HTTP requests/responses, input validation, and API contracts

#### Controllers (`/api/controllers/`)
- Receive and validate HTTP requests
- Convert requests to service calls
- Convert domain objects to HTTP responses
- Handle HTTP status codes and error mapping
- **No business logic** - only HTTP concerns

#### DTOs (`/api/dto/`)
- **Request DTOs**: Define and validate incoming data structure
- **Response DTOs**: Define consistent API response format
- Use Pydantic for automatic validation and serialization

#### Example:
```python
@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    request: CreateProjectRequest,  # ← Input validation
    user_id: str = Depends(get_user_id),  # ← Authentication
    service: ProjectService = Depends(get_project_service)  # ← Business layer
):
    # 1. Call business layer
    project = await service.create_project(request.name, user_id, request.description)
    
    # 2. Convert to response format
    return ProjectResponse(id=project.id, name=project.name, ...)
```

### ⚡ Business Layer (Services & Domain Models)

**Purpose**: Implement business logic, orchestrate operations, and define business rules

#### Services (`/business/services/`)
- **Business orchestration** - coordinate multiple repository calls
- **Cross-entity operations** - operations spanning multiple domain objects
- **Data conversion** - convert between database models and domain models
- **Complex data access** - handle business-specific aggregations
- **Transaction boundaries** - define what operations should be atomic

#### Domain Models (`/business/domain/`)
- **Single entity business rules** - validation, calculations, state changes
- **Business behavior methods** - operations on individual entities
- **Pure business concepts** - independent of database or API structure
- Use Pydantic BaseModel for validation and serialization

#### Example:
```python
class ProjectDomain(BaseModel):
    # Business behavior methods
    def can_be_copied_by_user(self, user_id: str) -> bool:
        return self.is_global and self.template_id is None
    
    def create_copy_for_user(self, user_id: str, name: str) -> 'ProjectDomain':
        if not self.can_be_copied_by_user(user_id):
            raise ValueError("Only templates can be copied")
        return ProjectDomain(...)

class ProjectService:
    # Complex orchestration
    def copy_project_from_template(self, copy_request: ProjectCopyRequest):
        # 1. Get template (repository call)
        template = self.project_repository.get_by_id(copy_request.template_id)
        
        # 2. Convert to domain model
        template_domain = self._model_to_domain(template)
        
        # 3. Use domain business logic
        new_project = template_domain.create_copy_for_user(...)
        
        # 4. Save via repository
        return self.project_repository.create_project(...)
```

### 💾 Data Layer (Repositories)

**Purpose**: Handle all database interactions and data persistence

#### Repositories (`/data/repositories/`)
- **Single-concern operations** - basic CRUD, simple queries
- **Reusable queries** - operations used across multiple services
- **Data access only** - no business logic
- **Interface-based** - define contracts via abstract interfaces

#### Database Models (`/database/models.py`)
- **Persistence structure** - how data is stored in database
- **Relationships and constraints** - foreign keys, indexes
- **Database-specific concerns** - column types, table names

---

## Data Access Patterns

### Decision Matrix: Repository vs Service

| Operation Type | Where to Put It | Example |
|---------------|----------------|---------|
| **Single entity CRUD** | Repository | `get_by_id()`, `create()`, `update()` |
| **Simple filtering** | Repository | `get_by_user_id()`, `get_global_projects()` |
| **Reusable queries** | Repository | `get_user_session()`, `count_template_usage()` |
| **Cross-table aggregations** | Service | `get_session_history()`, `get_project_dashboard()` |
| **Business-specific queries** | Service | Complex reporting, analytics |
| **Performance-critical joins** | Service | Optimized queries with JOINs |

### Repository Pattern
```python
class IProjectRepository(IBaseRepository[Project]):
    @abstractmethod
    def get_user_projects(self, user_id: str) -> List[Project]:
        """Simple, reusable query"""
        pass
    
    @abstractmethod
    def count_template_usage(self, template_id: str) -> int:
        """Atomic operation"""
        pass

class ProjectRepository(BaseRepository[Project], IProjectRepository):
    def get_user_projects(self, user_id: str) -> List[Project]:
        filters = [FilterInfo(field="user_id", operator="eq", value=user_id)]
        return self.get_all(filters=filters)
```

### Service Pattern (Complex Operations)
```python
class ProjectService:
    def get_project_dashboard(self, user_id: str) -> ProjectDashboard:
        """Complex cross-table operation - handle in service"""
        with self.db_service.read_only_session() as session:
            # Complex query spanning multiple tables
            result = session.query(Project, Session, Message).\
                join(Session, Project.id == Session.project_id).\
                join(Message, Session.id == Message.session_id).\
                filter(Project.user_id == user_id).\
                group_by(Project.id)
            
            return ProjectDashboard(...)
```

---

## Domain Model Guidelines

### Use Pydantic BaseModel
```python
class ProjectDomain(BaseModel):
    """Project domain entity with business rules."""
    
    id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_global: bool = False
    created_at: datetime
```

### Business Logic in Domain Models
- **Single entity rules** only
- **Self-contained validation**
- **State manipulation methods**
- **Property calculations**

```python
class ProjectDomain(BaseModel):
    @property
    def is_template(self) -> bool:
        """Business rule about this project"""
        return self.is_global and self.template_id is None
    
    def update_name(self, new_name: str) -> None:
        """Business operation on this project"""
        if not new_name.strip():
            raise ValueError("Name cannot be empty")
        self.name = new_name.strip()
        self.updated_at = datetime.now(timezone.utc)
    
    def can_be_accessed_by_user(self, user_id: str) -> bool:
        """Permission check for this project"""
        return self.is_global or self.user_id == user_id
```

### What NOT to Put in Domain Models
- ❌ Database conversion logic
- ❌ API serialization logic
- ❌ Cross-entity operations
- ❌ Repository dependencies

---

## File Structure & Naming

### Directory Structure
```
src/solace_agent_mesh/gateway/http_sse/
├── api/
│   ├── controllers/
│   │   └── {feature}_controller.py
│   └── dto/
│       ├── requests/
│       │   └── {feature}_requests.py
│       └── responses/
│           └── {feature}_responses.py
├── business/
│   ├── domain/
│   │   └── {feature}_domain.py
│   └── services/
│       └── {feature}_service.py
├── data/
│   └── repositories/
│       └── {feature}_repository.py
├── database/
│   └── models.py
└── infrastructure/
    └── dependency_injection/
        └── __init__.py
```

### Naming Conventions

#### Classes
- **Controllers**: `{Feature}Controller` (e.g., `ProjectController`)
- **Services**: `{Feature}Service` (e.g., `ProjectService`)
- **Repositories**: `{Feature}Repository` + `I{Feature}Repository` interface
- **Domain Models**: `{Feature}Domain` (e.g., `ProjectDomain`)
- **DTOs**: `{Operation}{Feature}Request/Response` (e.g., `CreateProjectRequest`)

#### Methods
- **Controllers**: HTTP verb-based (`create_project`, `get_projects`)
- **Services**: Business operation-based (`copy_project_from_template`)
- **Repositories**: Data operation-based (`get_user_projects`, `create_project`)
- **Domain**: Business behavior-based (`can_be_copied_by_user`, `update_name`)

---

## Implementation Checklist

### For Each New Feature:

#### ✅ 1. Database Layer
- [ ] Add database model to `models.py`
- [ ] Create migration script
- [ ] Define relationships and constraints

#### ✅ 2. Domain Layer
- [ ] Create `{feature}_domain.py` with Pydantic models
- [ ] Add business rule methods
- [ ] Add validation and state manipulation methods
- [ ] Include property calculations

#### ✅ 3. Data Layer
- [ ] Create `I{Feature}Repository` interface
- [ ] Implement `{Feature}Repository` class
- [ ] Add single-concern CRUD operations
- [ ] Add simple, reusable queries

#### ✅ 4. Business Layer
- [ ] Create `{Feature}Service` class
- [ ] Add `_model_to_domain()` conversion method
- [ ] Implement business orchestration methods
- [ ] Handle complex cross-table operations in service

#### ✅ 5. Presentation Layer
- [ ] Create request DTOs in `{feature}_requests.py`
- [ ] Create response DTOs in `{feature}_responses.py`
- [ ] Implement `{Feature}Controller` with HTTP endpoints
- [ ] Add proper error handling and status codes

#### ✅ 6. Infrastructure
- [ ] Add service to dependency injection container
- [ ] Register router in `main.py`
- [ ] Update `__all__` exports

#### ✅ 7. Testing
- [ ] Unit tests for domain models (pure business logic)
- [ ] Unit tests for services (with mocked repositories)
- [ ] Integration tests for controllers (with test database)

---

## Testing Strategy

### Domain Model Testing (Fast, Pure)
```python
def test_project_copying():
    # No dependencies - pure business logic
    template = ProjectDomain(
        id="template-123",
        name="Support Template",
        is_global=True,
        template_id=None
    )
    
    copy = template.create_copy_for_user("user-456", "My Bot")
    
    assert copy.template_id == "template-123"
    assert copy.user_id == "user-456"
```

### Service Testing (Mocked Dependencies)
```python
def test_project_service():
    # Mock repository
    mock_repo = MockProjectRepository()
    service = ProjectService(mock_repo)
    
    # Test business orchestration
    result = service.copy_project_from_template(copy_request)
    
    assert mock_repo.get_by_id_called
    assert result.name == copy_request.new_name
```

### Controller Testing (Integration)
```python
def test_project_controller():
    # Use FastAPI TestClient
    response = client.post("/api/v1/projects", json={"name": "Test Project"})
    
    assert response.status_code == 201
    assert response.json()["name"] == "Test Project"
```

---

## Examples

### Complete Feature Implementation: Projects

#### 1. Domain Model
```python
class ProjectDomain(BaseModel):
    id: str
    name: str = Field(..., min_length=1, max_length=255)
    is_global: bool = False
    
    def can_be_copied_by_user(self, user_id: str) -> bool:
        return self.is_global and self.template_id is None
```

#### 2. Repository Interface & Implementation
```python
class IProjectRepository(IBaseRepository[Project]):
    @abstractmethod
    def get_user_projects(self, user_id: str) -> List[Project]:
        pass

class ProjectRepository(BaseRepository[Project], IProjectRepository):
    def get_user_projects(self, user_id: str) -> List[Project]:
        filters = [FilterInfo(field="user_id", operator="eq", value=user_id)]
        return self.get_all(filters=filters)
```

#### 3. Service
```python
class ProjectService:
    def __init__(self, project_repository: IProjectRepository):
        self.project_repository = project_repository
    
    def create_project(self, name: str, user_id: str) -> ProjectDomain:
        db_project = self.project_repository.create_project(name, user_id)
        return self._model_to_domain(db_project)
    
    def _model_to_domain(self, project) -> ProjectDomain:
        return ProjectDomain(id=project.id, name=project.name, ...)
```

#### 4. Controller
```python
@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    request: CreateProjectRequest,
    user_id: str = Depends(get_user_id),
    service: ProjectService = Depends(get_project_service)
):
    project = await service.create_project(request.name, user_id)
    return ProjectResponse(id=project.id, name=project.name, ...)
```

---

## Key Architectural Decisions

### 1. Repository vs Service for Data Access
- **Simple, reusable operations** → Repository
- **Complex, business-specific aggregations** → Service
- **Performance-critical cross-table queries** → Service

### 2. Domain Model Responsibilities
- **Single entity business logic** only
- **No external dependencies** (database, API, other services)
- **Pydantic BaseModel** for validation and serialization

### 3. Conversion Logic Location
- **Service layer handles all conversions** (database ↔ domain ↔ API)
- **Repository returns raw database models**
- **Controller converts domain models to response DTOs**

### 4. Interface Usage
- **All repositories implement interfaces** for testability
- **Services depend on interfaces, not implementations**
- **Dependency injection manages the wiring**

---

## Future Considerations

### Templates & Shared Artifacts
The established architecture is designed to easily accommodate:

- **Template Management**: Global project templates with versioning
- **Shared Artifacts**: Cross-project artifact sharing with permissions
- **Complex Workflows**: Multi-step business processes
- **Advanced Permissions**: Role-based access control

### Scalability Patterns
- **Domain Services**: For complex cross-aggregate operations
- **Query Objects**: For complex read operations
- **Event Sourcing**: For audit trails and complex state management
- **CQRS**: Separate read/write models for performance

---

This architecture provides a solid foundation for building complex, maintainable features while ensuring clean separation of concerns and high testability.