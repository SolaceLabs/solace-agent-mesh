# Detailed Design: Event-Driven Feedback Publishing

**Version:** 1.0
**Status:** Proposed
**Related Feature:** [Feature: Event-Driven Feedback Publishing](../features/002-event-driven-feedback-publishing.md)

## 1. Introduction

This document provides the detailed technical design for implementing the Event-Driven Feedback Publishing feature. The goal is to publish user feedback submitted via the WebUI to a configurable Solace topic, optionally enriching the event with contextual task information. This design decouples feedback generation from its consumption, enabling real-time observability and integration with external systems.

## 2. System Architecture and Component Interaction

The feature will be integrated into the existing WebUI Gateway architecture, leveraging existing components and patterns to minimize complexity and ensure consistency.

-   **`WebUIBackendApp` (`src/solace_agent_mesh/gateway/http_sse/app.py`):**
    -   The application's Pydantic schema (`SPECIFIC_APP_SCHEMA_PARAMS`) will be extended to include a new `feedback_publishing` configuration block.
    -   This will provide centralized validation for the new settings (`enabled`, `topic`, `include_task_info`, `max_payload_size_bytes`).

-   **`WebUIBackendComponent` (`src/solace_agent_mesh/gateway/http_sse/component.py`):**
    -   This component will continue to serve as the central hub.
    -   It will hold the parsed `feedback_publishing` configuration.
    -   Its existing `publish_a2a` method will be used by the `FeedbackService` to send the final event to the Solace broker, ensuring reuse of the existing broker connection.

-   **`FeedbackService` (`src/solace_agent_mesh/gateway/http_sse/services/feedback_service.py`):**
    -   This service will contain the core business logic for the feature.
    -   Its `process_feedback` method will be enhanced to orchestrate the creation and publishing of the feedback event.
    -   It will be responsible for reading the configuration, fetching task data, constructing the payload, handling payload size limits, and calling the component's publish method.

-   **`TaskRepository` (`src/solace_agent_mesh/gateway/http_sse/repository/task_repository.py`):**
    -   This repository will be used by the `FeedbackService` to fetch task-related data from the database.
    -   The `find_by_id` method will be used to retrieve the task summary.
    -   The `find_by_id_with_events` method will be used to retrieve the full task history required for the `stim` option.

-   **`dependencies.py` (`src/solace_agent_mesh/gateway/http_sse/dependencies.py`):**
    -   The `get_feedback_service` dependency injector will be updated.
    -   It will be responsible for injecting instances of the `WebUIBackendComponent` and `TaskRepository` into the `FeedbackService` upon its creation, making the necessary methods and data access available.

-   **`routers/tasks.py` (`src/solace_agent_mesh/gateway/http_sse/routers/tasks.py`):**
    -   The logic for formatting a task and its events into the `.stim` file structure will be refactored out of the `/tasks/{task_id}` endpoint into a reusable helper function.

## 3. Configuration Design

All configuration for this feature will be consolidated under a new `feedback_publishing` dictionary within the `app_config` block of `webui_example.yaml`.

### 3.1. YAML Configuration (`webui_example.yaml`)

```yaml
# In app_config:
feedback_publishing:
  enabled: true
  topic: "${NAMESPACE}/sam/feedback/v1"
  include_task_info: "stim" # Options: "none", "summary", "stim"
  max_payload_size_bytes: 9000000 # 9MB default, safety margin below 10MB broker limit
```

### 3.2. Schema Validation (`app.py`)

The `SPECIFIC_APP_SCHEMA_PARAMS` list in `WebUIBackendApp` will be updated with a new dictionary entry for `feedback_publishing` to ensure type-safe configuration loading and validation at startup.

```python
# In WebUIBackendApp.SPECIFIC_APP_SCHEMA_PARAMS
{
    "name": "feedback_publishing",
    "required": False,
    "type": "dict",
    "description": "Configuration for publishing user feedback to the message broker.",
    "dict_schema": {
        "enabled": {
            "type": "boolean", "required": False, "default": False,
            "description": "Enable/disable feedback publishing."
        },
        "topic": {
            "type": "string", "required": False, "default": "sam/feedback/v1",
            "description": "The Solace topic to publish feedback events to."
        },
        "include_task_info": {
            "type": "string", "required": False, "default": "none",
            "enum": ["none", "summary", "stim"],
            "description": "Level of task detail to include in the feedback event."
        },
        "max_payload_size_bytes": {
            "type": "integer", "required": False, "default": 9000000,
            "description": "Max payload size in bytes before 'stim' falls back to 'summary'."
        }
    }
}
```

## 4. Data Models and Payloads

The event published to the configured Solace topic will be a JSON object. The structure will vary based on the `include_task_info` configuration.

### 4.1. Base Payload Structure

All events will contain a `feedback` object.

```json
{
  "feedback": {
    "task_id": "...",
    "session_id": "...",
    "feedback_type": "up",
    "feedback_text": "Very helpful!",
    "user_id": "user@example.com"
  }
  // ... additional context-dependent fields
}
```

### 4.2. Payload with `include_task_info: "summary"`

A `task_summary` object will be added, containing the `Task` entity as retrieved from the database.

```json
{
  "feedback": { ... },
  "task_summary": {
    "id": "...",
    "user_id": "...",
    "start_time": 1678886400000,
    "end_time": 1678886410000,
    "status": "completed",
    "initial_request_text": "What is the capital of France?"
  }
}
```

### 4.3. Payload with `include_task_info: "stim"`

A `task_stim_data` object will be added, containing the full `.stim` file structure.

```json
{
  "feedback": { ... },
  "task_stim_data": {
    "invocation_details": {
      "log_file_version": "2.0",
      "task_id": "...",
      "user_id": "...",
      "start_time": 1678886400000,
      "end_time": 1678886410000,
      "status": "completed",
      "initial_request_text": "..."
    },
    "invocation_flow": [
      { "id": "...", "task_id": "...", "topic": "...", ... },
      { "id": "...", "task_id": "...", "topic": "...", ... }
    ]
  }
}
```

### 4.4. Payload with Truncation Fallback

If the `stim` payload exceeds `max_payload_size_bytes`, it will be replaced by `task_summary`, and a `truncation_details` object will be added.

```json
{
  "feedback": { ... },
  "task_summary": { ... },
  "truncation_details": {
    "strategy": "fallback_to_summary",
    "reason": "payload_too_large"
  }
}
```

## 5. Detailed Logic Flow (`FeedbackService`)

The `process_feedback` method will execute the following logic:

1.  **Check if Enabled:** Read the `feedback_publishing.enabled` flag from the component's configuration. If `false`, exit early.
2.  **Construct Base Payload:** Create the main dictionary and populate the `feedback` object using data from the incoming `FeedbackPayload` and the `user_id`.
3.  **Fetch Task Context Config:** Read the `include_task_info` value from the configuration.
4.  **Handle `summary`:**
    -   If `include_task_info` is `"summary"`, use the injected `TaskRepository` to call `find_by_id(task_id)`.
    -   If a task is found, add its `model_dump()` to the payload under the `task_summary` key.
5.  **Handle `stim`:**
    -   If `include_task_info` is `"stim"`, proceed with the "Try-Then-Fallback" logic:
        a.  Use the `TaskRepository` to call `find_by_id_with_events(task_id)`.
        b.  If data is found, pass it to the refactored `.stim` helper function to generate the `task_stim_data` dictionary.
        c.  Add this dictionary to the main payload.
        d.  Serialize the entire payload to a JSON string and get its byte length.
        e.  Read `max_payload_size_bytes` from the configuration.
        f.  **If size > limit:**
            i.  Remove the `task_stim_data` key from the payload.
            ii. Use the `TaskRepository` to fetch the `summary` data (if not already fetched).
            iii. Add the summary to the payload under the `task_summary` key.
            iv. Add the `truncation_details` object to the payload.
            v.  Log a warning about the fallback.
6.  **Publish Event:**
    -   Read the destination `topic` from the configuration.
    -   Call `component.publish_a2a(topic, payload)`.
    -   Wrap the publish call in a `try...except` block to log warnings if the broker is unavailable, but do not raise an exception to the client.

## 6. Refactoring `.stim` Generation

The logic for generating the `.stim` file format, currently located inside the `get_task_as_stim_file` endpoint in `src/solace_agent_mesh/gateway/http_sse/routers/tasks.py`, will be extracted.

-   A new helper function, e.g., `create_stim_from_task_data(task: Task, events: list[TaskEvent]) -> dict`, will be created.
-   This function will be placed in a suitable shared location, such as a new `utils` module within the `http_sse` package or as a static method on the `TaskRepository`.
-   Both the `tasks.py` router and the `FeedbackService` will call this new, single-source-of-truth function.

## 7. Dependency Injection

To facilitate the new logic, dependency injection will be updated:

-   The `FeedbackService.__init__` method will be modified to accept `component: WebUIBackendComponent` and `task_repo: ITaskRepository`.
-   The `get_feedback_service` function in `src/solace_agent_mesh/gateway/http_sse/dependencies.py` will be updated to fetch these dependencies (using `get_sac_component` and `get_task_repository`) and inject them when creating the `FeedbackService` instance.

## 8. Error Handling

-   **Broker Unavailability:** If the call to `component.publish_a2a` fails (e.g., due to a disconnected broker), the exception will be caught, a warning will be logged, and the method will complete successfully from the client's perspective. The feedback event will be dropped.
-   **Payload Size:** Oversized payloads for the `stim` option are handled gracefully by the "fallback to summary" mechanism, ensuring a useful event is always published.
-   **Database Unavailability:** If the `TaskRepository` fails to fetch task data, an error will be logged, and the feedback event will be published without the additional context.
