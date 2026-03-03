# Feature Description: Scheduled Task Execution for SAM

## Summary

SAM (Solace Agent Mesh) gains the ability to run AI agent tasks automatically on a schedule — without any user interaction at execution time. Users can define recurring or one-time tasks that are dispatched to any agent in the mesh using cron expressions, fixed intervals, or a specific date/time. Results, artifacts, and notifications are captured and surfaced through the existing SAM UI and APIs.

---

## Problem Statement

Today, every SAM interaction requires a human to initiate it. There is no way to automate recurring workflows such as:

- Generating a daily summary report at 9 AM
- Running a health check every 30 minutes
- Sending a weekly digest to a Slack channel every Monday
- Triggering a one-time data migration at a specific date and time

Users who want to automate these workflows must rely on external schedulers (cron jobs, CI pipelines, custom scripts) that call SAM's API — adding operational overhead and coupling external systems to SAM's internals.

---

## Feature Description

### What It Does

This feature introduces a **built-in task scheduler** in the SAM gateway. Users and administrators can define **scheduled tasks** — each specifying:

- **What to do:** a message (prompt) to send to a specific AI agent
- **When to do it:** a cron expression, a fixed interval, or a one-time datetime
- **What to do with the result:** optional (future enhancement) notifications via Slack, Teams, webhooks, or Solace broker topics

The scheduler runs inside the gateway process, handles distributed coordination automatically when multiple gateway instances are deployed, and stores all execution history in the database. NOTE: This might need to move out of the gateway.

---

### Schedule Types

| Type | Expression Format | Example |
|---|---|---|
| **Cron** | Standard 5-field cron | `0 9 * * 1-5` (weekdays at 9 AM) |
| **Interval** | Duration with unit suffix | `30m`, `1h`, `2d`, `45s` |
| **One-time** | ISO 8601 datetime | `2025-12-31T23:59:00` |

---

### Key Capabilities

#### 1. Task Definition
Each scheduled task specifies:
- **Name and description** — human-readable label
- **Target agent** — which SAM agent receives the task (e.g. `OrchestratorAgent`, `ResearchAgent`)
- **Task message** — the prompt/instruction sent to the agent (text or file parts)
- **Schedule** — when and how often to run
- **Timezone** — schedule is evaluated in the specified timezone
- **Retry policy** — configurable retry count and delay on failure
- **Timeout** — maximum execution time before the task is cancelled (default: 1 hour)
- **Notifications** — where to send results when execution completes

#### 2. Execution Tracking
Every time a scheduled task fires, an **execution record** is created and updated in real time:
- Status: `pending → running → completed / failed / timeout / skipped`
- Agent response text and any artifacts produced
- Timing: scheduled time, start time, completion time
- Error details on failure
- Notification delivery status

#### 3. Distributed Safety
When multiple gateway instances are running (e.g. in Kubernetes), the scheduler uses a **database-backed leader election** mechanism to ensure exactly one instance fires each task. If the active instance crashes, another takes over within 60 seconds.

#### 4. Notifications
After each execution, results can be delivered to:
- **Slack** — formatted message with task name, status, and execution ID
- **Microsoft Teams** — MessageCard format
- **Generic webhook** — raw JSON payload via HTTP POST
- **Solace broker topic** — publish result summary to any topic for downstream consumers
- **SSE (WebUI)** — real-time notification to the user's active browser session

Notifications can be configured to fire on success, failure, or both. Artifacts produced by the agent can optionally be included.

#### 5. AI-Assisted Task Creation
A conversational LLM assistant helps users create scheduled tasks through natural language. Users describe what they want in plain English, and the assistant:
- Suggests appropriate schedule types and cron expressions
- Identifies the right target agent from the available list
- Builds the task message based on the user's description
- Confirms the configuration before saving

Example:
> "I need a task that generates a daily sales report every morning"
> → Assistant suggests `0 9 * * *`, asks for report details, proposes `OrchestratorAgent`

#### 6. YAML-Based Task Management
Administrators can define scheduled tasks in YAML files for version-controlled, GitOps-style management. Tasks defined in YAML are namespace-level (shared across all users) and are upserted on load.

```yaml
scheduled_tasks:
  - name: Daily Sales Report
    schedule_type: cron
    schedule_expression: "0 9 * * 1-5"
    timezone: America/Toronto
    target_agent_name: OrchestratorAgent
    task_message:
      - type: text
        text: "Generate the daily sales report for yesterday"
    max_retries: 2
    timeout_seconds: 1800
    notification_config:
      on_success: true
      on_failure: true
      channels:
        - type: webhook
          config:
            url: https://hooks.slack.com/services/...
            webhook_type: slack
```

#### 7. Kubernetes-Native Mode (Optional)
For large-scale deployments, the scheduler can delegate task execution to native **Kubernetes CronJobs and Jobs** instead of running tasks in-process. This enables true horizontal scaling where each task execution runs in its own isolated pod.

---

### REST API

A new set of API endpoints is available under `/api/v1/scheduled-tasks/`:

| Operation | Endpoint |
|---|---|
| Create task | `POST /scheduled-tasks/` |
| List tasks | `GET /scheduled-tasks/` |
| Get task | `GET /scheduled-tasks/{id}` |
| Update task | `PATCH /scheduled-tasks/{id}` |
| Delete task | `DELETE /scheduled-tasks/{id}` |
| Enable task | `POST /scheduled-tasks/{id}/enable` |
| Disable task | `POST /scheduled-tasks/{id}/disable` |
| Execution history | `GET /scheduled-tasks/{id}/executions` |
| Recent executions | `GET /scheduled-tasks/executions/recent` |
| Scheduler status | `GET /scheduled-tasks/scheduler/status` |
| AI builder chat | `POST /scheduled-tasks/builder/chat` |

---

### Multi-Tenancy

- **User-level tasks** — owned by a specific user; only that user can view/modify them
- **Namespace-level tasks** — shared across all users in the namespace (typically created via YAML or by admins); visible to all users but not modifiable by regular users

---

## Configuration

The scheduler is opt-in and requires SQL persistence to be enabled on the gateway:

```yaml
# In gateway config
scheduler_service:
  enabled: true
```

Additional options control concurrency limits, timeouts, retry behavior, leader election parameters, and Kubernetes integration.

---

## User Stories

- **As a business analyst**, I want to schedule a weekly report to be generated every Monday morning and delivered to our Slack channel, so I don't have to remember to run it manually.

- **As a DevOps engineer**, I want to set up a health check that runs every 15 minutes and alerts our Teams channel if any issues are detected, so we catch problems before users do.

- **As an administrator**, I want to define shared scheduled tasks in a YAML file checked into our repository, so task definitions are version-controlled and auditable.

- **As a developer**, I want to trigger a one-time data migration task at a specific date and time, and receive a notification when it completes with the results.

- **As a power user**, I want to describe what I want to automate in plain English and have the system help me configure the schedule and agent, without needing to know cron syntax.

---

## Out of Scope (This Release)

- Email notifications (infrastructure placeholder exists, not yet implemented)
- UI for viewing/managing scheduled tasks (API-only in this release)
- Task dependencies or chaining (task A triggers task B on completion)
- Per-execution resource quotas
