# Implementation Plan: Unified Task Logging and Visualization

**Version:** 1.0
**Status:** Proposed
**Related Documents:**
- `docs/features/001-unified-task-logging-and-visualization.md`
- `docs/designs/001-unified-task-logging-and-visualization.md`

This document outlines the step-by-step plan to implement the Unified Task Logging and Visualization feature. The work is divided into distinct phases to ensure a structured and manageable development process.

---

### Phase 1: Foundational Changes (Database and Configuration)

This phase establishes the data schema and configuration hooks for the new services.

1.  **Update Application Configuration:**
    1.1. Modify `src/solace_agent_mesh/gateway/http_sse/app.py` to add the `task_logging` configuration block to `SPECIFIC_APP_SCHEMA_PARAMS`.
    1.2. In the same file, remove the `feedback_service` configuration block, as feedback persistence will now be implicitly enabled by the presence of a `database_url`.
    1.3. Update the `__init__` method of `WebUIBackendApp` to check for the `session_service.database_url` and use it for Alembic migrations, ensuring a single source for the database URL.

2.  **Create Database Models:**
    2.1. Create a new file `src/solace_agent_mesh/gateway/http_sse/repository/models/task_model.py` to define the `TaskModel` for the `tasks` table, as specified in the design document.
    2.2. Create a new file `src/solace_agent_mesh/gateway/http_sse/repository/models/task_event_model.py` to define the `TaskEventModel` for the `task_events` table.
    2.3. Create a new file `src/solace_agent_mesh/gateway/http_sse/repository/models/feedback_model.py` to define the `FeedbackModel` for the `feedback` table, ensuring it includes a `task_id`.

3.  **Update Alembic for Discovery:**
    3.1. Modify `src/solace_agent_mesh/gateway/http_sse/alembic/env.py` to explicitly import `TaskModel`, `TaskEventModel`, and `FeedbackModel`. This ensures Alembic's autogenerate command can detect the new models and create the correct migration script.

4.  **Generate Database Migration:**
    4.1. Execute the command `alembic -c src/solace_agent_mesh/gateway/http_sse/alembic.ini revision --autogenerate -m "add tasks, task_events, and feedback tables"` to create the new migration script.
    4.2. Review the generated script in `alembic/versions/` to confirm it correctly creates the three new tables with all specified columns, constraints, and indexes.

---

### Phase 2: Data Access Layer (Repositories and Entities)

This phase builds the abstraction layer for interacting with the new database tables, following the existing repository pattern.

1.  **Create Domain Entities:**
    1.1. Create a new file `src/solace_agent_mesh/gateway/http_sse/repository/entities/task.py` to define the `Task` Pydantic model.
    1.2. Create a new file `src/solace_agent_mesh/gateway/http_sse/repository/entities/task_event.py` to define the `TaskEvent` Pydantic model.
    1.3. Create a new file `src/solace_agent_mesh/gateway/http_sse/repository/entities/feedback.py` to define the `Feedback` Pydantic model, ensuring it uses `task_id`.

2.  **Define Repository Interfaces:**
    2.1. Modify `src/solace_agent_mesh/gateway/http_sse/repository/interfaces.py` to add the `ITaskRepository` interface with methods for creating tasks and adding events (`create_task`, `add_event`, `find_by_id`, `search`).
    2.2. In the same file, add the `IFeedbackRepository` interface with a `save` method.

3.  **Implement Repositories:**
    3.1. Create a new file `src/solace_agent_mesh/gateway/http_sse/repository/task_repository.py` to implement `TaskRepository` using SQLAlchemy, mirroring the structure of `SessionRepository`.
    3.2. Create a new file `src/solace_agent_mesh/gateway/http_sse/repository/feedback_repository.py` to implement `FeedbackRepository`.

---

### Phase 3: Business Logic (Services)

This phase implements the core business logic that uses the new data access layer.

1.  **Create `TaskLoggerService`:**
    1.1. Create a new directory `src/solace_agent_mesh/gateway/http_sse/services/`.
    1.2. Create a new file `src/solace_agent_mesh/gateway/http_sse/services/task_logger_service.py`.
    1.3. Implement the `TaskLoggerService` class. It will take `ITaskRepository` as a dependency and contain a primary method, `log_event`, which will parse raw A2A messages, determine if a new task record needs to be created in the `tasks` table, and save the event to the `task_events` table.

2.  **Refactor `FeedbackService`:**
    2.1. Modify `src/solace_agent_mesh/gateway/http_sse/services/feedback_service.py`.
    2.2. Change its constructor to accept an `IFeedbackRepository` dependency.
    2.3. Update the `save_feedback` method to use the repository to save feedback to the database, removing the old CSV/log logic.

---

### Phase 4: Gateway Integration

This phase wires the new services and data ingestion flow into the main `WebUIBackendComponent`.

1.  **Create `TaskLoggerForwarderComponent`:**
    1.1. Create a new file `src/solace_agent_mesh/gateway/http_sse/components/task_logger_forwarder.py`.
    1.2. This component will be a near-identical copy of `VisualizationForwarderComponent`, designed to forward messages from a `BrokerInput` to a target queue.

2.  **Unify Message Ingestion in `WebUIBackendComponent`:**
    2.1. In `src/solace_agent_mesh/gateway/http_sse/component.py`, rename `_visualization_message_queue` to `_a2a_message_queue`. This queue will now serve as the single source for both the visualization loop and the new task logger loop.
    2.2. Update the `VisualizationForwarderComponent` instantiation to use this renamed queue.
    2.3. Update the `_visualization_message_processor_loop` to consume from the renamed queue.

3.  **Integrate Task Logging Flow:**
    3.1. In `WebUIBackendComponent`, add a new `_task_logger_processor_task` and a method `_task_logger_loop`.
    3.2. Create a new method `_ensure_task_logger_flow_is_running` modeled after the visualization equivalent. This method will create a new internal SAC flow with a `BrokerInput` subscribing to `[namespace]/a2a/>` and the new `TaskLoggerForwarderComponent` targeting the unified `_a2a_message_queue`.
    3.3. In the `_start_fastapi_server` method (or `startup` event), call `_ensure_task_logger_flow_is_running` and start the `_task_logger_loop` as a new asyncio task if `task_logging.enabled` is true.
    3.4. The `_task_logger_loop` will consume messages from `_a2a_message_queue` and pass them to the `TaskLoggerService` for persistence.

4.  **Instantiate Services:**
    4.1. In `WebUIBackendComponent.__init__`, instantiate `TaskLoggerService` and the refactored `FeedbackService`, providing them with their repository dependencies.
    4.2. Add getter methods for these new services so they can be accessed by the dependency injection system.

---

### Phase 5: API Layer

This phase exposes the new functionality through the FastAPI application.

1.  **Update Dependency Injection:**
    1.1. Modify `src/solace_agent_mesh/gateway/http_sse/dependencies.py` to add new provider functions (`get_task_logger_service`, `get_feedback_service`) that retrieve the service instances from the `WebUIBackendComponent`.

2.  **Create `tasks` API Router:**
    2.1. Create a new file `src/solace_agent_mesh/gateway/http_sse/routers/tasks.py`.
    2.2. Implement the `GET /api/v1/tasks` endpoint for listing and searching tasks. This endpoint will use the `TaskLoggerService` (or `TaskRepository` directly) to query the `tasks` table based on the filter parameters.
    2.3. Implement the `GET /api/v1/tasks/{task_id}` endpoint. This will query the `task_events` table for all events for a given task and format them into the `.stim` YAML format for the response.

3.  **Update Feedback API:**
    3.1. Locate the `POST /api/v1/feedback` endpoint (likely in `routers/chat.py` or a similar file).
    3.2. Update the request body model to accept `task_id` instead of `message_id`.
    3.3. Update the endpoint implementation to use the new database-backed `FeedbackService`.

4.  **Integrate New Router:**
    4.1. Modify `src/solace_agent_mesh/gateway/http_sse/main.py` to include and prefix the new `tasks` router.

---

### Phase 6: Deprecation and Cleanup

This final phase removes the old, agent-side logging mechanism.

1.  **Remove `InvocationMonitor`:**
    1.1. Delete the file `src/solace_agent_mesh/agent/adk/invocation_monitor.py`.

2.  **Update `SamAgentComponent`:**
    2.1. In `src/solace_agent_mesh/agent/sac/component.py`, remove the `self.invocation_monitor` attribute and its initialization.
    2.2. Remove the `cleanup` call for the monitor.

3.  **Update `event_handlers`:**
    3.1. In `src/solace_agent_mesh/agent/protocol/event_handlers.py`, remove the call to `component.invocation_monitor.log_message_event()` from the `process_event` function.
