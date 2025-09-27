# Feature: Unified Task Logging and Visualization

**Version:** 1.0
**Status:** Proposed

## 1. Background

The current system has two distinct mechanisms for observing Agent-to-Agent (A2A) communication: an `InvocationMonitor` for logging and a real-time visualizer. Both have significant limitations.

-   **Invocation Logging:** The current logging mechanism (`InvocationMonitor`) is implemented within a specific agent. This design is brittle, as it only records conversations that are initiated with that particular agent. Tasks that start elsewhere in the mesh are not logged, leading to incomplete system observability.
-   **Visualization:** The current visualization tool provides a real-time stream of A2A events to the browser. While useful for debugging active tasks, it is ephemeral. If a user is not actively watching the stream, the data is lost forever. There is no capability to review past conversations.
-   **Feedback Storage:** User feedback is currently stored in a simple, non-scalable format (CSV or log files), which is separate from other system data and difficult to query or manage.

This fragmented and incomplete approach to observability makes it difficult to debug issues, audit system behavior, or understand the full lifecycle of a task that spans multiple agents.

## 2. Goals and Purpose

The primary goal of this feature is to create a single, robust, and centralized **"Invocation Intelligence"** system within the WebUI Gateway. This system will be responsible for both the persistent recording and the on-demand visualization of all A2A task activity.

The key purposes are:

-   **Decouple Logging from Agents:** Move the responsibility of logging from a single agent to a centralized, passive listener in the gateway.
-   **Ensure Complete Observability:** Capture all A2A protocol messages across the entire mesh, regardless of which agent or gateway handles them.
-   **Provide Persistent Task History:** Replace the ephemeral, real-time-only visualization with a durable, database-backed record of all tasks.
-   **Enhance Diagnostic Capabilities:** Enable users to review, search, and "play back" historical tasks for debugging, auditing, and analysis.
-   **Unify Persistence Strategy:** Consolidate the storage of task logs and user feedback into a single, scalable database, following the application's existing repository pattern.

## 3. Requirements

### R1: Centralized Task Logging Service

-   **R1.1:** A new service shall be created within the WebUI Gateway responsible for logging all A2A task events.
-   **R1.2:** This service must operate as a passive listener on the message broker, independent of any specific gateway's request/response flow.
-   **R1.3:** The service must subscribe to a topic that captures all A2A protocol messages (e.g., `[namespace]/a2a/>`).
-   **R1.4:** The task logging feature must be configurable and disabled by default.

### R2: Database-Backed Persistence

-   **R2.1:** All captured A2A task events shall be stored in a new set of database tables (e.g., `tasks`, `task_events`).
-   **R2.2:** The persistence mechanism for tasks and feedback must follow the established pattern used for session storage, including the use of the repository pattern (Interface -> SQLAlchemy Repository -> Model).
-   **R2.3:** User feedback shall be stored in a new `feedback` table in the same database, replacing the current CSV/log file implementation.
-   **R2.4:** All new database tables must be created and managed via Alembic migrations.
-   **R2.5:** To support efficient searching, the main `tasks` table must contain a denormalized, truncated copy of the initial request text from the first event of each task.

### R3: Configurable Logging Granularity

-   **R3.1:** The system must provide configuration options to selectively enable or disable the logging of different event types (e.g., `TaskStatusUpdate` events, `TaskArtifactUpdate` events).
-   **R3.2:** The system must provide a configuration option to control whether the content of `FilePart` objects is stored.
-   **R3.3:** The system must provide a configuration option to define the maximum size (in bytes) of `FilePart` content to be stored in the database. Content exceeding this limit will be stripped.

### R4: Stateless and Resilient Logging

-   **R4.1:** The logging service shall be stateless. Each message received from the broker will be treated as an independent event to be recorded transactionally. The service will not maintain an in-memory state of "active" tasks.
-   **R4.2:** In the event of database unavailability, it is acceptable for the service to log a warning and discard the event. No in-memory buffering for retries is required.
-   **R4.3:** Malformed or unparseable messages received from the broker should be discarded, and a warning should be logged.

### R5: Historical Task Playback and Export

-   **R5.1:** A new, authorization-protected API endpoint shall be created to list historical tasks from the database. This endpoint must support comprehensive filtering, including:
    -   Filtering by a date range.
    -   Filtering by the user who initiated the task.
    -   A keyword search against the text of the initial request.
-   **R5.2:** A new, authorization-protected API endpoint shall be created to retrieve all recorded events for a specific task ID.
-   **R5.3:** The retrieval endpoint must format the database events into the established `.stim` YAML file format for consumption by the frontend or for download. All data stored in the database for a given task shall be included in the export.

### R6: Authorization

-   **R6.1:** The `userId` associated with a task must be stored with each recorded event to facilitate ownership and authorization checks.
-   **R6.2:** Authenticated users must be able to view the history of their own tasks.
-   **R6.3:** Users with a specific, elevated permission scope must be able to view the task history of all users.

## 4. Decisions Made

The following architectural and terminological decisions have been agreed upon:

-   **Core Terminology:** The central unit of work will be referred to as a **Task**, aligning with the A2A protocol. This name will be used for database tables (`tasks`, `task_events`), services (`TaskLoggerService`), and API endpoints (`/api/v1/tasks`).
-   **Export Format Name:** The human-readable YAML export format will continue to be named a **`.stim` file** to maintain consistency with established team vocabulary.
-   **Naming Convention:** The prefix "a2a" will **not** be used in new class, table, or service names, as the A2A context is implicit within the project's architecture.
-   **Architectural Pattern:** The new logging service will be implemented within the WebUI Gateway. It will follow the existing `VisualizationForwarder` pattern, using a dedicated `BrokerInput` in an internal SAC flow to feed messages to a queue, which is then consumed by the `TaskLoggerService`.
-   **Task Lifecycle Management:** The logger will be a stateless, passive listener. It will not be responsible for determining the "start" or "end" of a task. This logic is deferred to consumers of the logged data (e.g., the UI, an analyst). A separate system component is assumed to be responsible for detecting and reporting stuck tasks via A2A messages, which will be logged like any other event.
-   **Search Performance:** To facilitate efficient keyword searches on historical tasks, a truncated version of the initial request text will be denormalized and stored in the main `tasks` table.
