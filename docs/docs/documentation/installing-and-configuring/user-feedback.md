---
title: User Feedback
sidebar_position: 345
---

User Feedback allows users to provide ratings and comments on AI agent responses through the Web UI. This feature enables quality monitoring, model improvement through evaluation datasets, and user satisfaction tracking. Feedback can be stored in a database for analytics and optionally published to Solace message broker topics for integration with external systems.

## Prerequisites

User Feedback requires session persistence to be enabled. Session persistence ensures that feedback submissions can be reliably stored and associated with specific user interactions and tasks.

To enable session persistence, configure the session service with a database backend in your `shared_config.yaml` file:

```yaml
services:
  session_service:
    type: "sql"
    database_url: "${WEB_UI_GATEWAY_DATABASE_URL, sqlite:///webui-gateway.db}"
    default_behavior: "PERSISTENT"
```

For more information about session service configuration and database setup options, see [Session Service](./configurations.md#session-service).

:::info
If session persistence is not enabled, the system automatically disables the feedback collection feature to prevent data loss. Feedback buttons will not appear in the Web UI when persistence is disabled.
:::

## Enabling User Feedback

To enable feedback collection in the Web UI, set the `frontend_collect_feedback` parameter to `true` in your gateway configuration file:

```yaml
apps:
  - name: webui_example_app
    app_config:
      # Enable feedback collection in the UI
      frontend_collect_feedback: true

      # Session persistence required (see Prerequisites)
      session_service:
        type: "sql"
        database_url: "${WEB_UI_GATEWAY_DATABASE_URL, sqlite:///webui-gateway.db}"
        default_behavior: "PERSISTENT"
```

When enabled, thumbs up and thumbs down buttons appear after completed agent responses in the Web UI. Users can click these buttons to submit feedback, with an optional text comment providing additional context.

## Configuring Feedback Publishing

Feedback can be published to Solace message broker topics for integration with external analytics systems, evaluation pipelines, or monitoring dashboards. This publishing capability is optional and can be configured independently of basic feedback collection.

The following table describes the feedback publishing configuration parameters:

| Parameter | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `enabled` | `boolean` | Enable or disable feedback event publishing. | `false` |
| `topic` | `string` | The topic name for publishing feedback events. Supports environment variable substitution. | `sam/feedback/v1` |
| `include_task_info` | `string` | Controls what task information is included in published events. Options are `none`, `summary`, or `stim`. | `none` |
| `max_payload_size_bytes` | `integer` | Maximum payload size in bytes. If the payload exceeds this limit when using `stim` mode, the system falls back to `summary` mode. | `9000000` |

### Configuration Example

The following example shows how to configure feedback publishing in your gateway configuration file:

```yaml
apps:
  - name: webui_example_app
    app_config:
      frontend_collect_feedback: true

      feedback_publishing:
        enabled: true
        topic: "${NAMESPACE}/sam/feedback/v1"
        include_task_info: "summary"
        max_payload_size_bytes: 9000000
```

### Task Information Modes

The `include_task_info` parameter determines what task details are included with each feedback event:

**`none`** - Only feedback data (task_id, session_id, rating, comment, user_id) is published. Use this mode when you want minimal payload size and don't need task context in the consuming system.

**`summary`** - Includes basic task information such as task_id, user_id, start_time, end_time, status, and initial_request_text. Use this mode for lightweight analytics and monitoring where you need basic task context without full execution details.

**`stim`** - Includes complete task execution history with all events, tool calls, and agent interactions. This mode provides full traceability for debugging and detailed analysis. If the payload exceeds `max_payload_size_bytes`, the system automatically falls back to `summary` mode and logs the fallback decision.

## Using User Feedback

Users submit feedback through the Web UI by clicking thumbs up or thumbs down buttons that appear after completed agent responses. A modal dialog allows users to optionally add text comments explaining their rating. Each task can receive one feedback submission, and buttons are disabled after submission to prevent duplicate feedback.

Feedback is stored in the `feedback` database table with the following information:

- Unique feedback ID
- Associated task ID and session ID
- User ID of the person who submitted the feedback
- Rating type (up or down)
- Optional text comment
- Creation timestamp

The feedback is also stored in the task metadata, allowing quick access to feedback status when retrieving task information through other APIs.

## Retrieving Feedback

You can retrieve feedback programmatically using the `GET /api/v1/feedback` endpoint. This endpoint supports flexible filtering and pagination to help you analyze feedback data.

### Query Parameters

The following table describes the available query parameters:

| Parameter | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `start_date` | `string` | Filter feedback created after this date (ISO 8601 format). | (none) |
| `end_date` | `string` | Filter feedback created before this date (ISO 8601 format). | (none) |
| `task_id` | `string` | Filter by specific task ID. | (none) |
| `session_id` | `string` | Filter by specific session ID. | (none) |
| `rating` | `string` | Filter by rating type (`up` or `down`). | (none) |
| `page` | `integer` | Page number for pagination. | `1` |
| `page_size` | `integer` | Number of results per page. | `20` |
| `query_user_id` | `string` | (Admin only) Query feedback for a specific user. Requires `feedback:read:all` scope. | (none) |

All query parameters are optional and can be combined to create specific filters. Results are returned in descending order by creation time (most recent first).

### Security and Access Control

Regular users can only retrieve their own feedback. Users with the `feedback:read:all` scope can retrieve feedback from any user or all users. When filtering by `task_id`, the system verifies that the user owns the task or has admin permissions before returning results.

### Example API Calls

The following examples demonstrate common feedback retrieval scenarios:

**Get your own feedback from the last week:**
```bash
curl "http://localhost:8000/api/v1/feedback?start_date=2025-10-22T00:00:00&end_date=2025-10-29T23:59:59"
```

**Get all negative feedback for a specific task:**
```bash
curl "http://localhost:8000/api/v1/feedback?task_id=task-abc123&rating=down"
```

**Get feedback from a specific session:**
```bash
curl "http://localhost:8000/api/v1/feedback?session_id=web-session-xyz"
```

**Admin: Get all users' feedback from October:**
```bash
curl "http://localhost:8000/api/v1/feedback?start_date=2025-10-01&end_date=2025-10-31"
```

**Get the first 50 results with pagination:**
```bash
curl "http://localhost:8000/api/v1/feedback?page=1&page_size=50"
```

## Publishing Feedback Events

When feedback publishing is enabled, the system publishes feedback events to the configured Solace topic. The payload structure varies based on the `include_task_info` setting.

### Event Payload Examples

**Mode: `none`**
```json
{
  "feedback": {
    "task_id": "task-abc123",
    "session_id": "web-session-xyz",
    "feedback_type": "up",
    "feedback_text": "Great response!",
    "user_id": "user123"
  }
}
```

**Mode: `summary`**
```json
{
  "feedback": {
    "task_id": "task-abc123",
    "session_id": "web-session-xyz",
    "feedback_type": "up",
    "feedback_text": "Great response!",
    "user_id": "user123"
  },
  "task_summary": {
    "id": "task-abc123",
    "user_id": "user123",
    "start_time": 1730217600000,
    "end_time": 1730217650000,
    "status": "completed",
    "initial_request_text": "Help me analyze this data"
  }
}
```

**Mode: `stim`**
```json
{
  "feedback": {
    "task_id": "task-abc123",
    "session_id": "web-session-xyz",
    "feedback_type": "up",
    "feedback_text": "Great response!",
    "user_id": "user123"
  },
  "task_stim_data": {
    "invocation_details": {
      "log_file_version": "2.0",
      "task_id": "task-abc123",
      "user_id": "user123",
      "start_time": 1730217600000,
      "end_time": 1730217650000,
      "status": "completed",
      "initial_request_text": "Help me analyze this data"
    },
    "invocation_flow": [
      {
        "id": "event-1",
        "created_time": 1730217600000,
        "topic": "namespace/agent/request",
        "direction": "request",
        "payload": { "message": "..." }
      },
      {
        "id": "event-2",
        "created_time": 1730217625000,
        "topic": "namespace/agent/response",
        "direction": "response",
        "payload": { "result": "..." }
      }
    ]
  }
}
```

### Integrating with External Systems

External systems can subscribe to the feedback topic to consume feedback events in real-time. This approach enables integration with various downstream systems such as analytics platforms, evaluation pipelines, and monitoring dashboards.

The topic naming pattern follows the format `{namespace}/sam/feedback/v1`, where `{namespace}` is your configured namespace. You can customize this pattern using the `topic` configuration parameter and environment variable substitution.

:::tip
Use `summary` mode for most analytics and monitoring use cases, as it provides essential task context without the overhead of full execution traces. Reserve `stim` mode for detailed debugging and analysis scenarios where complete execution history is required.
:::

## Data Retention

Feedback records are subject to the data retention policies configured in your gateway. The data retention service automatically cleans up old feedback records based on the configured retention period, preventing unbounded database growth.

To configure data retention for feedback, set the `feedback_retention_days` parameter in your gateway configuration:

```yaml
apps:
  - name: webui_example_app
    app_config:
      data_retention:
        enabled: true
        feedback_retention_days: 90
        cleanup_interval_hours: 24
        batch_size: 1000
```

For detailed information about data retention configuration and cleanup policies, see the [Data Retention documentation](./configurations.md).
