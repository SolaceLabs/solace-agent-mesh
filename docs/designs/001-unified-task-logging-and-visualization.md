# Detailed Design: Unified Task Logging and Visualization

**Version:** 1.0
**Status:** Proposed
**Related Documents:** `docs/features/001-unified-task-logging-and-visualization.md`

## 1. Overview

This document provides the detailed technical design for the "Unified Task Logging and Visualization" feature. The current system's logging is tied to a specific agent (`InvocationMonitor`) and its visualization is ephemeral, leading to incomplete observability.

This design centralizes logging within the WebUI Gateway, creating a robust, database-backed system for recording and replaying all Agent-to-Agent (A2A) communication. The system will function as a "flight data recorder" for the A2A mesh, with two primary capabilities:
-   **The Recorder:** A passive logging service that captures all A2A traffic and persists it to a database.
-   **The Player:** A set of APIs that allow for both real-time streaming of active tasks and on-demand playback of historical tasks from the database.

## 2. System Architecture

The new logging system will be integrated into the `WebUIBackendComponent` and will follow the established pattern of the existing visualization forwarder, but with persistence to a database.

### 2.1. Data Ingestion and Processing Flow

1.  **Internal SAC Flow:** A new, dedicated internal SAC (Solace AI Connector) flow will be instantiated within the `WebUIBackendComponent` upon startup, if task logging is enabled in the configuration.
2.  **Broker Subscription:** This flow will contain a `BrokerInput` component configured to subscribe to the global A2A topic (`[namespace]/a2a/>`). This ensures all A2A messages on the mesh are captured, regardless of their origin or destination.
3.  **Forwarder Component:** A new `TaskLoggerForwarderComponent`, modeled directly on the `VisualizationForwarderComponent`, will receive messages from the `BrokerInput`. Its sole responsibility is to place the raw message data (topic, payload, user properties) onto a new internal, thread-safe `queue.Queue` within the `WebUIBackendComponent`.
4.  **Asynchronous Consumer:** A new asynchronous task, `_task_logger_loop`, will run on the `WebUIBackendComponent`'s event loop. This task will continuously consume messages from the internal queue.
5.  **Service-Layer Processing:** For each message, the `_task_logger_loop` will invoke a new `TaskLoggerService`. This service will contain the business logic to parse the message, determine its relevance, and persist it to the database using the repository pattern. The service will operate statelessly, processing each message as an independent, transactional event.

### 2.2. Relationship to Existing Visualization

-   **Unified Data Source:** The existing `_visualization_message_processor_loop` (for real-time UI updates) and the new `_task_logger_loop` (for database persistence) will both consume raw A2A messages from the same internal queue. This guarantees that the event data sent to the UI for live visualization is structurally identical to the data being stored in the database for historical playback.
-   **Historical Playback:** The concept of replaying historical tasks will be implemented via new API endpoints that query the database, not through the real-time SSE mechanism.

## 3. Data Model Design

The new persistence layer will be built using the existing SQLAlchemy and Alembic infrastructure.

### 3.1. `tasks` Table

This table will store one record for each unique task, serving as the master record for search and retrieval.

| Column                 | Type           | Constraints                  | Description                                                              |
| ---------------------- | -------------- | ---------------------------- | ------------------------------------------------------------------------ |
| `id`                   | `String`       | Primary Key                  | The unique task ID, sourced from the JSON-RPC request ID.                |
| `user_id`              | `String`       | Not Null, Indexed            | The ID of the user who initiated the task.                               |
| `start_time`           | `BigInteger`   | Not Null                     | Epoch milliseconds of the first recorded event for this task.            |
| `end_time`             | `BigInteger`   | Nullable                     | Epoch milliseconds of the final recorded event for this task.            |
| `status`               | `String`       | Nullable                     | The last known terminal state of the task (e.g., 'completed', 'failed'). |
| `initial_request_text` | `Text`         | Nullable, Indexed (Full-text) | A truncated copy of the initial user query for efficient keyword search. |

### 3.2. `task_events` Table

This table will store every individual A2A message as a distinct event, linked to a master task record.

| Column         | Type         | Constraints                | Description                                                              |
| -------------- | ------------ | -------------------------- | ------------------------------------------------------------------------ |
| `id`           | `String`     | Primary Key (e.g., UUID)   | A unique identifier for this specific event log entry.                   |
| `task_id`      | `String`     | FK to `tasks.id`, Indexed  | The task this event belongs to.                                          |
| `created_time` | `BigInteger` | Not Null                   | Epoch milliseconds when the gateway recorded the event.                  |
| `topic`        | `Text`       | Not Null                   | The Solace topic the message was published on.                           |
| `direction`    | `String`     | Not Null                   | The inferred direction (e.g., 'request', 'response', 'status_update').   |
| `payload`      | `JSON`       | Not Null                   | The complete JSON payload of the A2A message.                            |

### 3.3. `feedback` Table

This table will replace the current CSV/log-based feedback storage.

| Column         | Type         | Constraints               | Description                                                              |
| -------------- | ------------ | ------------------------- | ------------------------------------------------------------------------ |
| `id`           | `String`     | Primary Key (e.g., UUID)  | A unique identifier for the feedback entry.                              |
| `session_id`   | `String`     | Not Null                  | The session ID in which feedback was provided.                           |
| `task_id`      | `String`     | Not Null, Indexed         | The ID of the task being rated.                                          |
| `user_id`      | `String`     | Not Null, Indexed         | The ID of the user providing the feedback.                               |
| `rating`       | `String`     | Not Null                  | The rating given (e.g., 'positive', 'negative').                         |
| `comment`      | `Text`       | Nullable                  | Optional free-text comment from the user.                                |
| `created_time` | `BigInteger` | Not Null                  | Epoch milliseconds when the feedback was submitted.                      |

## 4. Component and Service Design

### 4.1. New Components and Services

-   **`TaskLoggerForwarderComponent`**: A new, simple SAC component that forwards messages from a `BrokerInput` to the `WebUIBackendComponent`'s internal queue.
-   **`TaskLoggerService`**: A new service containing the core business logic for processing and persisting task events. It will be responsible for parsing raw messages, identifying the `task_id`, and using the `ITaskRepository` to write to the `tasks` and `task_events` tables.
-   **`ITaskRepository` / `TaskRepository`**: A new repository interface and its SQLAlchemy implementation for database operations on the `tasks` and `task_events` tables. This will follow the exact pattern established by `ISessionRepository` / `SessionRepository`.
-   **`IFeedbackRepository` / `FeedbackRepository`**: A new repository interface and its SQLAlchemy implementation for the `feedback` table, also following the `ISessionRepository` pattern.

### 42. Modified Components and Services

-   **`WebUIBackendComponent`**: Will be modified to:
    -   Initialize the new internal SAC flow for task logging.
    -   Create and manage the internal queue for both logging and visualization.
    -   Run the `_task_logger_loop` asynchronous consumer task.
    -   Instantiate and provide the `TaskLoggerService` and `FeedbackService` to the dependency injection system.
-   **`FeedbackService`**: The existing service will be refactored to use the new `IFeedbackRepository`, allowing it to write to the database when configured to do so.

## 5. API Design

### 5.1. `POST /api/v1/feedback` (Modified)

-   **Behavior:** The endpoint's contract will be modified. The request body will now require a `task_id` instead of a `message_id`. The internal implementation will use the new database-backed `FeedbackService`.

### 5.2. `GET /api/v1/tasks` (New)

-   **Purpose:** To list and search historical tasks.
-   **Authorization:** Requires authentication. Results are filtered by the authenticated user's ID. An administrator with an elevated scope can override this and search all tasks.
-   **Query Parameters:**
    -   `user_id: Optional[str]`: Filter by a specific user ID (admin only).
    -   `start_date: Optional[str]`: ISO 8601 date string for the start of a date range filter.
    -   `end_date: Optional[str]`: ISO 8601 date string for the end of a date range filter.
    -   `search: Optional[str]`: A keyword search string to be matched against the `tasks.initial_request_text` column.
    -   `page: Optional[int] = 1`: For pagination.
    -   `page_size: Optional[int] = 20`: For pagination.
-   **Response:** A paginated JSON object containing a list of task metadata objects, derived from the `tasks` table.

### 5.3. `GET /api/v1/tasks/{task_id}` (New)

-   **Purpose:** To retrieve the complete event history for a single task and return it as a `.stim` file.
-   **Authorization:** Requires authentication. The user must be the owner of the task or have elevated permissions.
-   **Response:** The service will query all associated events from the `task_events` table, construct a YAML document matching the `.stim` file format, and return it with a `Content-Type` of `application/x-yaml`.

## 6. Configuration Design

The following new configuration parameters will be added to the `WebUIBackendApp` schema in `app.py`.

### 6.1. `task_logging` Block

```yaml
task_logging:
  enabled: boolean (default: false)
  log_status_updates: boolean (default: true)
  log_artifact_events: boolean (default: true)
  log_file_parts: boolean (default: true)
  max_file_part_size_bytes: integer (default: 102400) # 100KB
```

### 6.2. `feedback_service` Block

The `feedback_service` configuration block will be removed. The database-backed feedback service will be enabled automatically whenever a `database_url` is configured for the gateway, simplifying the setup. The previous `log` and `csv` types will be removed. The existing `frontend_collect_feedback` flag will be retained to control whether feedback UI elements are displayed to the user.

## 7. Deprecation of `InvocationMonitor`

The introduction of this centralized logging system renders the agent-side `InvocationMonitor` obsolete.

-   The `InvocationMonitor` class in `src/solace_agent_mesh/agent/adk/invocation_monitor.py` will be removed.
-   The instantiation of `InvocationMonitor` in `SamAgentComponent` will be removed.
-   All calls to `invocation_monitor.log_message_event()` in `src/solace_agent_mesh/agent/protocol/event_handlers.py` will be removed.

This change fully decouples the responsibility of conversation logging from the agents and centralizes it in the gateway, fulfilling a primary goal of this feature.
