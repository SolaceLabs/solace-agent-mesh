# Project Implementation Reconciliation Plan

This document outlines the key mismatches between the `projects` and `sessions` feature implementations. The `sessions` implementation is considered the source of truth, and the `projects` code should be refactored to align with these patterns.

---

### 1. Router Naming and Structure

-   **Mismatch**: The project router is incorrectly named `project_controller.py` and uses function parameters instead of request DTOs.
-   **Session Reference**: `src/solace_agent_mesh/gateway/http_sse/routers/sessions.py`
-   **Project File to Change**: `src/solace_agent_mesh/gateway/http_sse/routers/project_controller.py`
-   **Actions**:
    1.  Rename `project_controller.py` to `projects.py`.
    2.  Update the functions within the router to use the `Depends(get_current_user)` dependency for authentication, matching `sessions.py`.
    3.  Refactor endpoint functions to build request DTOs (e.g., `GetProjectRequest`, `UpdateProjectRequest`) instead of passing individual parameters to the service layer.

---

### 2. Domain Entity and DTO Locations

-   **Mismatch**: The `ProjectDomain` entity and related DTOs (`ProjectFilter`, `ProjectCopyRequest`) are located in the `domain/entities` directory, which is inconsistent with the session implementation where entities are in `repository/entities` and request DTOs are in `routers/dto/requests`.
-   **Session Reference**:
    -   `src/solace_agent_mesh/gateway/http_sse/repository/entities/session.py`
    -   `src/solace_agent_mesh/gateway/http_sse/routers/dto/requests/session_requests.py`
-   **Project Files to Change**:
    -   `src/solace_agent_mesh/gateway/http_sse/domain/entities/project_domain.py`
    -   `src/solace_agent_mesh/gateway/http_sse/routers/dto/requests/project_requests.py`
-   **Actions**:
    1.  Move the `ProjectDomain` class to a new file: `src/solace_agent_mesh/gateway/http_sse/repository/entities/project.py`.
    2.  Move request-related models like `ProjectCopyRequest` and `ProjectFilter` from the domain file to `routers/dto/requests/project_requests.py`.
    3.  Delete the now-empty `domain/entities` directory.

---

### 3. Responsibility for User-Scoped Data Access

-   **Mismatch**: The `ProjectService` contains business logic to check if a user is authorized to access a project *after* fetching it from the database. The `SessionService` delegates this responsibility to the `SessionRepository`, which includes the `user_id` in the database query.
-   **Session Reference**: `src/solace_agent_mesh/gateway/http_sse/repository/session_repository.py` (e.g., `find_user_session` method).
-   **Project Files to Change**:
    -   `src/solace_agent_mesh/gateway/http_sse/services/project_service.py`
    -   `src/solace_agent_mesh/gateway/http_sse/repository/project_repository.py`
-   **Actions**:
    1.  Move the user access validation logic from `ProjectService` into the `ProjectRepository` methods (`get_by_id`, `update`, `delete`). These methods should accept a `user_id` and include it in the `WHERE` clause of their queries.
    2.  Remove the now-redundant access check methods from `ProjectService`.

---

### 4. Response DTO Timestamp Typing

-   **Mismatch**: The `ProjectResponse` DTO in `project_responses.py` incorrectly types `created_at` and `updated_at` as `datetime` objects. Its base class, `BaseTimestampResponse`, is designed to work with integer epoch timestamps, as seen in `SessionResponse`.
-   **Session Reference**: `src/solace_agent_mesh/gateway/http_sse/routers/dto/responses/session_responses.py` (`SessionResponse` class).
-   **Project File to Change**: `src/solace_agent_mesh/gateway/http_sse/routers/dto/responses/project_responses.py`
-   **Actions**:
    1.  Change the type of `created_at` and `updated_at` in `ProjectResponse` from `datetime` to `int` and `Optional[int]` respectively to match the `BaseTimestampResponse` implementation and align with `SessionResponse`.

---

### 5. Service Constructor Dependency Injection

-   **Mismatch**: `ProjectService` receives a simple `app_name` string in its constructor. `SessionService` receives the entire `component` object, which is a more robust DI pattern.
-   **Session Reference**: `src/solace_agent_mesh/gateway/http_sse/services/session_service.py`
-   **Project File to Change**: `src/solace_agent_mesh/gateway/http_sse/services/project_service.py`
-   **Actions**:
    1.  Update the `ProjectService` constructor to accept the `component: "WebUIBackendComponent"` instead of `app_name: str`.
    2.  Inside the service, derive `app_name` and other required dependencies (like `artifact_service`) from the `component` object.
    3.  Update `dependencies.py` where `ProjectService` is instantiated to pass the component.
