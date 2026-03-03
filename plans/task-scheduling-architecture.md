# Task Scheduling Architecture — `amir/task-scheduling`

> **Purpose:** This document describes the architecture implemented in the `amir/task-scheduling` branch of the `sam` repository. It is intended to help someone write a feature description for this work.

---

## Overview

This branch adds a **cron-like task scheduling system** to the SAM (Solace Agent Mesh) HTTP/SSE gateway. It allows users and administrators to define recurring or one-time tasks that are automatically dispatched to AI agents in the mesh on a schedule — without any human interaction at execution time.

Key capabilities:
- **Three schedule types:** cron expressions, fixed intervals, and one-time execution
- **Distributed-safe:** database-backed leader election ensures only one scheduler instance fires tasks across multiple gateway replicas
- **Kubernetes-native option:** tasks can be backed by real K8s CronJobs/Jobs for horizontal scaling
- **AI-assisted task creation:** a conversational LLM assistant helps users build task configurations in natural language
- **Multi-channel notifications:** SSE, webhooks (Slack/Teams/generic), and Solace broker topics
- **Full REST API + execution history**

---

## System Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        HTTP/SSE Gateway (FastAPI)                        │
│                                                                          │
│  ┌──────────────────────┐    ┌──────────────────────────────────────┐   │
│  │  REST API Router      │    │  WebUIBackendComponent               │   │
│  │  /api/v1/scheduled-  │    │  (SAC Component)                     │   │
│  │  tasks/*             │    │                                      │   │
│  │                      │    │  ┌────────────────────────────────┐  │   │
│  │  CRUD + enable/      │    │  │  SchedulerService              │  │   │
│  │  disable + history   │    │  │  (core orchestrator)           │  │   │
│  │  + status            │    │  │                                │  │   │
│  │                      │    │  │  ┌──────────────────────────┐  │  │   │
│  │  TaskBuilderAssistant│    │  │  │  LeaderElection          │  │  │   │
│  │  (LLM chat UI)       │    │  │  │  (DB-based lock)         │  │  │   │
│  └──────────────────────┘    │  │  └──────────────────────────┘  │  │   │
│                              │  │  ┌──────────────────────────┐  │  │   │
│                              │  │  │  APScheduler             │  │  │   │
│                              │  │  │  (AsyncIOScheduler)      │  │  │   │
│                              │  │  └──────────────────────────┘  │  │   │
│                              │  │  ┌──────────────────────────┐  │  │   │
│                              │  │  │  ResultHandler OR        │  │  │   │
│                              │  │  │  StatelessResultCollector│  │  │   │
│                              │  │  └──────────────────────────┘  │  │   │
│                              │  │  ┌──────────────────────────┐  │  │   │
│                              │  │  │  NotificationService     │  │  │   │
│                              │  │  └──────────────────────────┘  │  │   │
│                              │  │  ┌──────────────────────────┐  │  │   │
│                              │  │  │  K8SCronJobManager       │  │  │   │
│                              │  │  │  (optional)              │  │  │   │
│                              │  │  └──────────────────────────┘  │  │   │
│                              │  └────────────────────────────────┘  │   │
│                              └──────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
         │                                        │
         │ A2A Protocol (Solace Broker)            │ A2A Response
         ▼                                        ▲
┌─────────────────────┐              ┌────────────────────────────────────┐
│  Target AI Agent    │──────────────│  SchedulerResultForwarderComponent │
│  (any SAM agent)    │              │  (SAC Component, broker subscriber) │
└─────────────────────┘              └────────────────────────────────────┘
```

---

## Database Schema

Three new tables are introduced via Alembic migration [`20251117_create_scheduled_tasks_tables.py`](src/solace_agent_mesh/gateway/http_sse/alembic/versions/20251117_create_scheduled_tasks_tables.py):

### `scheduled_tasks`
Stores task definitions. Key columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | String (UUID) | Primary key |
| `name` | String | Human-readable name |
| `namespace` | String | A2A namespace (multi-tenancy) |
| `user_id` | String (nullable) | NULL = namespace-level task; set = user-owned |
| `schedule_type` | Enum | `cron`, `interval`, or `one_time` |
| `schedule_expression` | String | Cron expr, interval string (e.g. `30m`), or ISO 8601 datetime |
| `timezone` | String | Timezone for schedule evaluation |
| `target_agent_name` | String | Which SAM agent receives the task |
| `task_message` | JSON | A2A message parts (text/file) to send |
| `task_metadata` | JSON | Additional A2A metadata |
| `enabled` | Boolean | Whether the task is active |
| `max_retries` | Integer | Retry attempts on failure |
| `retry_delay_seconds` | Integer | Delay between retries |
| `timeout_seconds` | Integer | Max execution time (default 3600s) |
| `notification_config` | JSON | Notification channel configuration |
| `next_run_at` | BigInteger (epoch ms) | Next scheduled execution time |
| `last_run_at` | BigInteger (epoch ms) | Last execution time |
| `deleted_at` | BigInteger (epoch ms) | Soft-delete timestamp |

### `scheduled_task_executions`
One record per execution attempt:

| Column | Type | Purpose |
|---|---|---|
| `id` | String (UUID) | Primary key |
| `scheduled_task_id` | FK → `scheduled_tasks` | Parent task |
| `status` | Enum | `pending`, `running`, `completed`, `failed`, `timeout`, `cancelled`, `skipped` |
| `a2a_task_id` | String | The A2A task ID used when submitting to the agent |
| `scheduled_for` | BigInteger (epoch ms) | When this execution was triggered |
| `started_at` / `completed_at` | BigInteger (epoch ms) | Timing |
| `result_summary` | JSON | Agent response text, messages, metadata |
| `artifacts` | JSON | List of artifact URIs produced |
| `error_message` | Text | Error details on failure |
| `retry_count` | Integer | Which retry attempt this was |
| `notifications_sent` | JSON | Delivery status per channel |

### `scheduler_locks`
Single-row table for distributed leader election:

| Column | Purpose |
|---|---|
| `leader_id` | Instance ID of the current leader |
| `leader_namespace` | Namespace the leader operates in |
| `acquired_at` | When leadership was acquired |
| `expires_at` | Lease expiry (renewed by heartbeat) |
| `heartbeat_at` | Last heartbeat timestamp |

---

## Core Service: `SchedulerService`

**File:** [`services/scheduler/scheduler_service.py`](src/solace_agent_mesh/gateway/http_sse/services/scheduler/scheduler_service.py)

This is the central orchestrator. It is instantiated inside the [`WebUIBackendComponent`](src/solace_agent_mesh/gateway/http_sse/component.py) when `scheduler_service.enabled: true` is set in the gateway config.

### Startup Sequence

```
SchedulerService.start()
  ├── LeaderElection.start()          # begins DB-based election loop
  ├── AsyncIOScheduler.start()        # APScheduler starts
  ├── asyncio.create_task(_monitor_leadership())   # watches for leader changes
  └── asyncio.create_task(_stale_cleanup_loop())   # periodic stale execution cleanup
```

### Leadership Monitoring

Every 5 seconds, `_monitor_leadership()` checks `LeaderElection.is_leader()`:
- **On becoming leader:** calls `_load_scheduled_tasks()` — queries all enabled tasks from DB and registers them with APScheduler
- **On losing leadership:** calls `_unload_all_tasks()` — removes all jobs from APScheduler

This ensures only one gateway instance fires tasks at any time.

### Task Execution Flow

```
APScheduler fires → _execute_scheduled_task(task_id)
  ├── Check max_concurrent_executions limit (default: 10)
  │     └── If exceeded: create SKIPPED execution record, return
  ├── Load task from DB, create PENDING execution record
  ├── asyncio.create_task(_submit_task_to_agent_mesh(task_id, execution_id))
  ├── asyncio.wait_for(execution_task, timeout=timeout_seconds)
  │     ├── On success: check execution status, send success notification
  │     └── On TimeoutError: mark execution as TIMEOUT, send failure notification
  └── Retry logic: if failed and retry_count < max_retries → sleep → recurse
```

### A2A Message Construction

When submitting to the agent mesh, the scheduler:
1. Creates A2A message parts from `task_message` JSON (text or file parts)
2. Sets `sessionBehavior: "RUN_BASED"` — prevents session history accumulation
3. Sets `returnArtifacts: true` — requests artifact listing in the final response
4. Uses a deterministic session ID: `scheduler_{task_id}`
5. Publishes to the agent's request topic via the Solace broker
6. Sets `replyTo` to `{namespace}a2a/v1/scheduler/response/{instance_id}`

---

## Leader Election: `LeaderElection`

**File:** [`services/scheduler/leader_election.py`](src/solace_agent_mesh/gateway/http_sse/services/scheduler/leader_election.py)

Uses a **database-based distributed lock** (the `scheduler_locks` table) with a heartbeat mechanism:

```
_election_loop() runs continuously:
  ├── _try_acquire_leadership()
  │     ├── SELECT FOR UPDATE SKIP LOCKED on scheduler_locks
  │     ├── If no row: INSERT new lock → become leader
  │     ├── If row expired (expires_at < now): take over → become leader
  │     ├── If row owned by self: renew lease → remain leader
  │     └── If row owned by other: return False
  └── If leader: _maintain_leadership()
        └── _send_heartbeat() every heartbeat_interval_seconds (default: 30s)
              └── Updates expires_at = now + lease_duration (default: 60s)
```

If a gateway instance crashes, its lease expires after 60 seconds and another instance takes over.

---

## Schedule Trigger Types

Implemented in [`SchedulerService._create_trigger()`](src/solace_agent_mesh/gateway/http_sse/services/scheduler/scheduler_service.py:531):

| `schedule_type` | `schedule_expression` example | APScheduler trigger |
|---|---|---|
| `cron` | `0 9 * * 1-5` | `CronTrigger.from_crontab()` with timezone |
| `interval` | `30m`, `1h`, `2d`, `45s` | `IntervalTrigger(seconds=N)` |
| `one_time` | `2025-12-25T09:00:00` | `DateTrigger(run_date=...)` |

Cron expressions are validated with `croniter.is_valid()` before scheduling.

---

## Result Handling

Two implementations exist, selected by config:

### `ResultHandler` (default, single-instance)

**File:** [`services/scheduler/result_handler.py`](src/solace_agent_mesh/gateway/http_sse/services/scheduler/result_handler.py)

- Maintains an **in-memory dict** `pending_executions: {a2a_task_id → execution_id}`
- When an A2A response arrives on the scheduler response topic, looks up the execution by `a2a_task_id`
- Extracts agent response text, file parts, and artifacts from the A2A `Task` result
- Updates the `scheduled_task_executions` record with status, result summary, and artifact URIs

### `StatelessResultCollector` (K8s / multi-replica mode)

**File:** [`services/scheduler/stateless_result_collector.py`](src/solace_agent_mesh/gateway/http_sse/services/scheduler/stateless_result_collector.py)

- **No in-memory state** — queries the DB by `a2a_task_id` to find the pending execution
- Safe for horizontal scaling: any replica can process any response
- Enabled via `scheduler_service.use_stateless_collector: true`

### Response Routing

The [`SchedulerResultForwarderComponent`](src/solace_agent_mesh/gateway/http_sse/components/scheduler_result_forwarder.py) is a SAC (Solace AI Connector) component that:
1. Subscribes to `{namespace}a2a/v1/scheduler/response/{instance_id}` on the Solace broker
2. Puts received messages into a Python queue
3. The `WebUIBackendComponent` drains this queue and calls `scheduler_service.result_handler.handle_response()`

---

## Kubernetes Mode: `K8SCronJobManager`

**File:** [`services/scheduler/k8s_manager.py`](src/solace_agent_mesh/gateway/http_sse/services/scheduler/k8s_manager.py)

When `scheduler_service.k8s_enabled: true`, the scheduler syncs tasks to native Kubernetes resources:

| Task type | K8s resource | Notes |
|---|---|---|
| `cron` | `CronJob` | `concurrencyPolicy: Forbid` prevents overlapping runs |
| `interval` | `CronJob` | Interval converted to nearest cron expression |
| `one_time` | `Job` | `ttlSecondsAfterFinished: 3600` for auto-cleanup |

Each CronJob/Job runs a **task executor container** (`executor_image`) with environment variables injected from K8s Secrets:
- `DATABASE_URL` — from `database_url_secret`
- `BROKER_URL`, `BROKER_USERNAME`, `BROKER_PASSWORD`, `BROKER_VPN` — from `broker_config_secret`
- `TASK_ID`, `NAMESPACE` — passed directly

CronJobs are labeled with `managed-by: sam-scheduler` and annotated with task metadata for traceability.

---

## Notification Service

**File:** [`services/scheduler/notification_service.py`](src/solace_agent_mesh/gateway/http_sse/services/scheduler/notification_service.py)

After each execution completes (success or failure), notifications are sent based on `notification_config` on the task:

```yaml
notification_config:
  on_success: true
  on_failure: true
  include_artifacts: true
  channels:
    - type: sse
      config: {}
    - type: webhook
      config:
        url: https://hooks.slack.com/...
        webhook_type: slack   # or "teams" or "generic"
    - type: broker_topic
      config:
        topic: myapp/scheduler/results
        include_full_result: false
    - type: email
      config: {}   # placeholder, not yet implemented
```

Notification delivery status is recorded in `notifications_sent` on the execution record.

---

## AI-Assisted Task Builder

**File:** [`services/task_builder_assistant.py`](src/solace_agent_mesh/gateway/http_sse/services/task_builder_assistant.py)

A conversational LLM assistant that helps users create scheduled tasks through natural language. Exposed via:

- `POST /api/v1/scheduled-tasks/builder/chat` — process a user message, return task config updates
- `GET /api/v1/scheduled-tasks/builder/greeting` — get initial greeting

The assistant:
1. Maintains conversation history
2. Injects current task configuration and available agents into each LLM call
3. Returns structured JSON with `task_updates` (partial task config) and `ready_to_save` flag
4. Helps convert natural language schedules to cron expressions

Example interaction:
> User: "Generate a daily report at 9 AM"
> Assistant: Returns `schedule_type: cron`, `schedule_expression: 0 9 * * *`, asks for report details

---

## REST API

**File:** [`routers/scheduled_tasks.py`](src/solace_agent_mesh/gateway/http_sse/routers/scheduled_tasks.py)

Mounted at `/api/v1/scheduled-tasks` when `scheduler_service.enabled: true`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/` | Create a new scheduled task |
| `GET` | `/` | List tasks (paginated, with namespace/user filtering) |
| `GET` | `/{task_id}` | Get task details |
| `PATCH` | `/{task_id}` | Update task (auto-reschedules if schedule changed) |
| `DELETE` | `/{task_id}` | Soft-delete task (unschedules immediately) |
| `POST` | `/{task_id}/enable` | Enable and schedule task |
| `POST` | `/{task_id}/disable` | Disable and unschedule task |
| `GET` | `/{task_id}/executions` | Execution history (paginated) |
| `GET` | `/executions/recent` | Recent executions across all tasks |
| `GET` | `/scheduler/status` | Scheduler instance status |
| `POST` | `/builder/chat` | AI task builder chat |
| `GET` | `/builder/greeting` | AI task builder greeting |

All endpoints require authentication (`get_current_user`). Access control: users can only see/modify their own tasks or namespace-level tasks (where `user_id IS NULL`).

---

## YAML Task Loader

**File:** [`services/scheduler/yaml_loader.py`](src/solace_agent_mesh/gateway/http_sse/services/scheduler/yaml_loader.py)

Allows defining scheduled tasks in YAML files for GitOps-style management:

```yaml
scheduled_tasks:
  - name: Daily Report
    schedule_type: cron
    schedule_expression: "0 9 * * *"
    timezone: America/Toronto
    target_agent_name: OrchestratorAgent
    task_message:
      - type: text
        text: "Generate the daily activity report"
    max_retries: 2
    timeout_seconds: 1800
    notification_config:
      on_success: true
      channels:
        - type: webhook
          config:
            url: https://hooks.slack.com/...
            webhook_type: slack
```

`YamlTaskLoader.load_from_file()` or `load_from_directory()` creates or updates tasks by name (upsert semantics). YAML-defined tasks are namespace-level (`user_id = NULL`).

---

## Configuration

The scheduler is enabled in the gateway YAML config:

```yaml
scheduler_service:
  enabled: true
  instance_id: "my-gateway-1"          # optional, auto-generated if omitted
  default_timeout_seconds: 3600
  max_concurrent_executions: 10
  stale_execution_timeout_seconds: 7200
  stale_cleanup_interval_seconds: 3600
  
  # For K8s horizontal scaling
  use_stateless_collector: false
  k8s_enabled: false
  k8s:
    namespace: default
    executor_image: my-registry/sam-scheduler-executor:latest
    database_url_secret: sam-scheduler-db
    broker_config_secret: sam-scheduler-broker
  
  leader_election:
    heartbeat_interval_seconds: 30
    lease_duration_seconds: 60
```

The scheduler requires `session_service.type: sql` (PostgreSQL or SQLite) to be configured on the gateway.

---

## Key Design Decisions

1. **Database-backed leader election** (not ZooKeeper/etcd/Redis) — keeps the dependency footprint minimal; the existing gateway database is reused.

2. **APScheduler as the in-process scheduler** — well-tested Python library with native asyncio support, cron/interval/date triggers, and `max_instances=1` per job to prevent concurrent runs.

3. **`RUN_BASED` session behavior** — scheduled tasks use a special session mode that prevents the agent from accumulating conversation history, keeping each execution independent.

4. **Soft deletes** — tasks are never hard-deleted; `deleted_at` is set instead, preserving execution history.

5. **Two result handler modes** — `ResultHandler` (in-memory, simpler) for single-instance deployments; `StatelessResultCollector` (DB-only) for K8s multi-replica deployments.

6. **Graceful leadership transfer** — when a gateway instance shuts down, it sets `expires_at = now` to immediately release the lock, allowing another instance to take over without waiting for lease expiry.

---

## File Map

```
src/solace_agent_mesh/gateway/http_sse/
├── alembic/versions/
│   └── 20251117_create_scheduled_tasks_tables.py   # DB migration
├── components/
│   └── scheduler_result_forwarder.py               # SAC component: broker → queue
├── repository/
│   ├── models/
│   │   └── scheduled_task_model.py                 # SQLAlchemy models + enums
│   └── scheduled_task_repository.py                # DB access layer
├── routers/
│   └── scheduled_tasks.py                          # REST API endpoints
├── services/
│   ├── task_builder_assistant.py                   # LLM-assisted task creation
│   └── scheduler/
│       ├── __init__.py
│       ├── scheduler_service.py                    # Core orchestrator
│       ├── leader_election.py                      # Distributed lock / heartbeat
│       ├── result_handler.py                       # In-memory result tracking
│       ├── stateless_result_collector.py           # DB-only result tracking (K8s)
│       ├── notification_service.py                 # Multi-channel notifications
│       ├── k8s_manager.py                          # K8s CronJob/Job management
│       └── yaml_loader.py                          # YAML task import
└── main.py                                         # Router registration (conditional)
```
