# Implementation Checklist: Event-Driven Feedback Publishing

This checklist provides a terse summary of the implementation steps required for the Event-Driven Feedback Publishing feature.

## Step 1: Update Configuration

-   [x] **1.1:** In `src/solace_agent_mesh/gateway/http_sse/app.py`, add the `feedback_publishing` dictionary schema to `WebUIBackendApp.SPECIFIC_APP_SCHEMA_PARAMS`.
    -   [x] `enabled` (boolean, default `False`)
    -   [x] `topic` (string, default `sam/feedback/v1`)
    -   [x] `include_task_info` (string enum: `none`, `summary`, `stim`, default `none`)
    -   [x] `max_payload_size_bytes` (integer, default `9000000`)
-   [x] **1.2:** In `examples/gateways/webui_example.yaml`, add the `feedback_publishing` block to `app_config` with example values.

## Step 2: Refactor `.stim` File Generation

-   [x] **2.1:** Create a new file `src/solace_agent_mesh/gateway/http_sse/utils/stim_utils.py`.
-   [x] **2.2:** In `stim_utils.py`, define a helper function `create_stim_from_task_data(task: Task, events: list[TaskEvent]) -> dict`.
-   [x] **2.3:** In `src/solace_agent_mesh/gateway/http_sse/routers/tasks.py`, refactor the `get_task_as_stim_file` endpoint to import and use `create_stim_from_task_data`.

## Step 3: Update Dependency Injection

-   [x] **3.1:** In `src/solace_agent_mesh/gateway/http_sse/services/feedback_service.py`, update `FeedbackService.__init__` to accept `component: "WebUIBackendComponent"` and `task_repo: ITaskRepository`.
-   [x] **3.2:** In `src/solace_agent_mesh/gateway/http_sse/dependencies.py`, modify `get_feedback_service` to instantiate `FeedbackService` and inject `get_sac_component` and `get_task_repository` dependencies.
-   [x] **3.3:** In `src/solace_agent_mesh/gateway/http_sse/component.py`, remove the manual instantiation of `self.feedback_service` from `_start_fastapi_server`.
-   [x] **3.4:** In `src/solace_agent_mesh/gateway/http_sse/component.py`, remove the `get_feedback_service` method.

## Step 4: Implement Core Publishing Logic

-   [x] **4.1:** In `src/solace_agent_mesh/gateway/http_sse/services/feedback_service.py`, modify `process_feedback` to be an `async` method.
-   [x] **4.2:** In `process_feedback`, read the `feedback_publishing` config from the injected component.
-   [x] **4.3:** Implement the logic to return early if `enabled` is `False`.
-   [x] **4.4:** Construct the base event payload.
-   [x] **4.5:** Implement the `include_task_info` logic:
    -   [x] **`summary`:** Use the injected `task_repo` to fetch the task summary and add it to the payload.
    -   [x] **`stim`:** Use the `task_repo` and the new `create_stim_from_task_data` helper to generate the stim data.
-   [x] **4.6:** Implement the "Try-Then-Fallback" logic for `stim` payloads:
    -   [x] Serialize the full payload to JSON.
    -   [x] Check size against `max_payload_size_bytes`.
    -   [x] If too large, replace `stim` data with `summary` data and add `truncation_details`.
-   [x] **4.7:** Read the `topic` from config and call `self.component.publish_a2a(topic, payload)` to publish the event.
-   [x] **4.8:** Wrap the publish call in a `try...except` block to handle broker errors gracefully.
