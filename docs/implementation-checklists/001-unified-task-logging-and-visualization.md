# Implementation Checklist: Unified Task Logging and Visualization

This checklist provides a terse summary of the steps outlined in the implementation plan. Use it to track progress during development.

---

### Phase 1: Foundational Changes (Database and Configuration)

- [x] **1.1.** Modify `src/solace_agent_mesh/gateway/http_sse/app.py` to add the `task_logging` configuration block.
- [x] **1.2.** In `app.py`, remove the `feedback_service` configuration block.
- [x] **1.3.** Update `WebUIBackendApp.__init__` to use `session_service.database_url` for Alembic migrations.
- [x] **2.1.** Create `.../repository/models/task_model.py` for `TaskModel`.
- [x] **2.2.** Create `.../repository/models/task_event_model.py` for `TaskEventModel`.
- [x] **2.3.** Create `.../repository/models/feedback_model.py` for `FeedbackModel`.
- [x] **3.1.** Modify `.../alembic/env.py` to import the new models (`TaskModel`, `TaskEventModel`, `FeedbackModel`).
- [ ] **4.1.** Run `alembic revision --autogenerate` to create the database migration script.
- [ ] **4.2.** Review the generated migration script in `alembic/versions/`.

---

### Phase 2: Data Access Layer (Repositories and Entities)

- [x] **1.1.** Create `.../repository/entities/task.py` for the `Task` Pydantic model.
- [x] **1.2.** Create `.../repository/entities/task_event.py` for the `TaskEvent` Pydantic model.
- [x] **1.3.** Create `.../repository/entities/feedback.py` for the `Feedback` Pydantic model.
- [x] **2.1.** Modify `.../repository/interfaces.py` to add the `ITaskRepository` interface.
- [x] **2.2.** In `.../repository/interfaces.py`, add the `IFeedbackRepository` interface.
- [x] **3.1.** Create `.../repository/task_repository.py` to implement `TaskRepository`.
- [x] **3.2.** Create `.../repository/feedback_repository.py` to implement `FeedbackRepository`.

---

### Phase 3: Business Logic (Services)

- [x] **1.1.** Create the `.../http_sse/services/` directory if it doesn't exist.
- [x] **1.2.** Create `.../services/task_logger_service.py`.
- [x] **1.3.** Implement the `TaskLoggerService` class.
- [x] **2.1.** Modify `.../services/feedback_service.py`.
- [x] **2.2.** Update `FeedbackService` constructor to accept an `IFeedbackRepository` dependency.
- [x] **2.3.** Update the `save_feedback` method to use the repository and remove old file-based logic.

---

### Phase 4: Gateway Integration

- [ ] **1.1.** Create `.../components/task_logger_forwarder.py`.
- [ ] **1.2.** Implement the `TaskLoggerForwarderComponent` class, modeled on `VisualizationForwarderComponent`.
- [ ] **2.1.** In `.../http_sse/component.py`, rename `_visualization_message_queue` to `_a2a_message_queue`.
- [ ] **2.2.** Update `VisualizationForwarderComponent` instantiation to use the renamed queue.
- [ ] **2.3.** Update `_visualization_message_processor_loop` to consume from the renamed queue.
- [ ] **3.1.** In `WebUIBackendComponent`, add a `_task_logger_processor_task` attribute and a `_task_logger_loop` method.
- [ ] **3.2.** Create the `_ensure_task_logger_flow_is_running` method.
- [ ] **3.3.** In `_start_fastapi_server` (or a `startup` event), call `_ensure_task_logger_flow_is_running` and start the `_task_logger_loop`.
- [ ] **3.4.** Implement the `_task_logger_loop` to consume messages and call the `TaskLoggerService`.
- [ ] **4.1.** In `WebUIBackendComponent.__init__`, instantiate `TaskLoggerService` and the refactored `FeedbackService`.
- [ ] **4.2.** Add getter methods in `WebUIBackendComponent` for the new services.

---

### Phase 5: API Layer

- [ ] **1.1.** Modify `.../http_sse/dependencies.py` to add `get_task_logger_service` and update `get_feedback_service`.
- [ ] **2.1.** Create `.../http_sse/routers/tasks.py` (or add to the existing one).
- [ ] **2.2.** Implement the `GET /api/v1/tasks` endpoint for listing and searching tasks.
- [ ] **2.3.** Implement the `GET /api/v1/tasks/{task_id}` endpoint for retrieving a single task as a `.stim` file.
- [ ] **3.1.** Locate the `POST /api/v1/feedback` endpoint.
- [ ] **3.2.** Update the feedback request body model to accept `task_id` instead of `message_id`.
- [ ] **3.3.** Update the feedback endpoint implementation to use the new database-backed `FeedbackService`.
- [ ] **4.1.** Modify `.../http_sse/main.py` to include the new endpoints from the `tasks` router.

---

### Phase 6: Deprecation and Cleanup

- [ ] **1.1.** Delete the file `src/solace_agent_mesh/agent/adk/invocation_monitor.py`.
- [ ] **2.1.** In `.../agent/sac/component.py`, remove the `self.invocation_monitor` attribute and its initialization.
- [ ] **2.2.** In `.../agent/sac/component.py`, remove the `cleanup` call for the monitor.
- [ ] **3.1.** In `.../agent/protocol/event_handlers.py`, remove the call to `component.invocation_monitor.log_message_event()`.
