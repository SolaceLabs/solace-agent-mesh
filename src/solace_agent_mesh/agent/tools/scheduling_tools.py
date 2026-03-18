"""
Built-in tools for managing scheduled tasks via the agent mesh chat interface.

These tools allow agents (e.g., the orchestrator) to create, list, and delete
scheduled tasks programmatically. The gateway registers its scheduler service
and session factory into the module-level registry on startup.

Admin-only: all tools require the 'admin:scheduling' scope.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from croniter import croniter
from google.adk.tools import ToolContext
from google.genai import types as adk_types

from .registry import tool_registry
from .tool_definition import BuiltinTool
from .tool_result import ToolResult

log = logging.getLogger(__name__)

CATEGORY = "scheduling"
CATEGORY_NAME = "Task Scheduling"
CATEGORY_DESCRIPTION = (
    "Create, list, and delete recurring scheduled tasks that run agents on a cron or interval basis."
)

# ---------------------------------------------------------------------------
# Service locator — the gateway populates this on startup
# ---------------------------------------------------------------------------

_scheduler_registry: Dict[str, Any] = {}


def register_scheduler_backend(
    scheduler_service: Any,
    session_factory: Callable,
    namespace: str,
) -> None:
    """Called by the gateway component to make the scheduler accessible to tools."""
    _scheduler_registry["scheduler_service"] = scheduler_service
    _scheduler_registry["session_factory"] = session_factory
    _scheduler_registry["namespace"] = namespace
    log.info("[SchedulingTools] Scheduler backend registered (namespace=%s)", namespace)


def unregister_scheduler_backend() -> None:
    """Called on gateway shutdown."""
    _scheduler_registry.clear()
    log.info("[SchedulingTools] Scheduler backend unregistered")


def _get_backend():
    """Return (scheduler_service, session_factory, namespace) or raise."""
    svc = _scheduler_registry.get("scheduler_service")
    sf = _scheduler_registry.get("session_factory")
    ns = _scheduler_registry.get("namespace")
    if not svc or not sf or not ns:
        return None, None, None
    return svc, sf, ns


def _get_user_id(tool_context: ToolContext) -> str:
    """Extract user ID from tool context."""
    inv = getattr(tool_context, "_invocation_context", None)
    if inv and hasattr(inv, "user_id") and inv.user_id:
        return inv.user_id
    return "system"


# ---------------------------------------------------------------------------
# schedule_create
# ---------------------------------------------------------------------------


async def schedule_create(
    name: str,
    schedule_type: str,
    schedule_expression: str,
    target_agent_name: str,
    task_message: str,
    description: str = "",
    timezone_str: str = "UTC",
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Create a new scheduled task.

    Args:
        name: Human-readable name for the task.
        schedule_type: One of "cron", "interval", or "one_time".
        schedule_expression: Cron expression (e.g. "0 9 * * *") or interval (e.g. "30m").
        target_agent_name: The agent to invoke on each execution.
        task_message: The prompt/message to send to the agent.
        description: Optional description of the task.
        timezone_str: IANA timezone (default UTC).
        tool_context: Provided by ADK framework.
        tool_config: Optional tool configuration.
    """
    tag = "[SchedulingTools:schedule_create]"

    scheduler_service, session_factory, namespace = _get_backend()
    if not scheduler_service:
        return ToolResult.error(
            "Scheduling is not enabled. The scheduler service is not running.",
            code="SCHEDULER_UNAVAILABLE",
        )

    # Validate schedule_type
    valid_types = ("cron", "interval", "one_time")
    if schedule_type not in valid_types:
        return ToolResult.error(
            f"Invalid schedule_type '{schedule_type}'. Must be one of: {', '.join(valid_types)}",
            code="INVALID_SCHEDULE_TYPE",
        )

    # Validate cron expression
    if schedule_type == "cron" and not croniter.is_valid(schedule_expression):
        return ToolResult.error(
            f"Invalid cron expression: '{schedule_expression}'. "
            "Example: '0 9 * * *' for daily at 9 AM.",
            code="INVALID_CRON",
        )

    # Validate interval format
    if schedule_type == "interval":
        import re
        if not re.match(r"^\d+[smhd]$", schedule_expression):
            return ToolResult.error(
                f"Invalid interval expression: '{schedule_expression}'. "
                "Use format like '30m', '1h', '2d'.",
                code="INVALID_INTERVAL",
            )

    user_id = _get_user_id(tool_context) if tool_context else "system"

    # Build task_message as A2A message parts
    message_parts = [{"type": "text", "text": task_message}]

    from ...gateway.http_sse.repository.scheduled_task_repository import ScheduledTaskRepository
    from ...gateway.http_sse.shared import now_epoch_ms

    task_id = str(uuid.uuid4())
    task_data = {
        "id": task_id,
        "name": name,
        "description": description or f"Created via chat by {user_id}",
        "namespace": namespace,
        "user_id": user_id,
        "created_by": user_id,
        "schedule_type": schedule_type,
        "schedule_expression": schedule_expression,
        "timezone": timezone_str,
        "target_agent_name": target_agent_name,
        "target_type": "agent",
        "task_message": message_parts,
        "task_metadata": None,
        "enabled": True,
        "max_retries": 0,
        "retry_delay_seconds": 60,
        "timeout_seconds": 3600,
        "source": "chat",
        "created_at": now_epoch_ms(),
        "updated_at": now_epoch_ms(),
    }

    try:
        repo = ScheduledTaskRepository()
        with session_factory() as session:
            task = repo.create_task(session, task_data)
            session.commit()

            # Schedule in APScheduler if leader
            if task.enabled and await scheduler_service.is_leader():
                try:
                    await scheduler_service._schedule_task(task)
                except Exception as e:
                    log.error(f"{tag} Failed to activate schedule for {task_id}: {e}")

            log.info(f"{tag} Created task '{name}' (id={task_id}) by user {user_id}")

            # Build human-friendly schedule description
            if schedule_type == "cron":
                schedule_desc = f"cron: {schedule_expression}"
            elif schedule_type == "interval":
                schedule_desc = f"every {schedule_expression}"
            else:
                schedule_desc = f"one-time at {schedule_expression}"

            return ToolResult.ok(
                f"Scheduled task '{name}' created successfully. "
                f"Schedule: {schedule_desc} ({timezone_str}). "
                f"Target agent: {target_agent_name}. "
                f"Task ID: {task_id}",
                data={
                    "task_id": task_id,
                    "name": name,
                    "schedule_type": schedule_type,
                    "schedule_expression": schedule_expression,
                    "target_agent_name": target_agent_name,
                    "timezone": timezone_str,
                    "enabled": True,
                },
            )

    except ValueError as e:
        return ToolResult.error(str(e), code="CONFLICT")
    except Exception as e:
        log.error(f"{tag} Error creating task: {e}", exc_info=True)
        return ToolResult.error(
            f"Failed to create scheduled task: {e}",
            code="CREATE_FAILED",
        )


# ---------------------------------------------------------------------------
# schedule_list
# ---------------------------------------------------------------------------


async def schedule_list(
    enabled_only: bool = False,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    List all scheduled tasks visible to the current user.

    Args:
        enabled_only: If true, only return enabled tasks.
        tool_context: Provided by ADK framework.
        tool_config: Optional tool configuration.
    """
    tag = "[SchedulingTools:schedule_list]"

    scheduler_service, session_factory, namespace = _get_backend()
    if not scheduler_service:
        return ToolResult.error(
            "Scheduling is not enabled. The scheduler service is not running.",
            code="SCHEDULER_UNAVAILABLE",
        )

    user_id = _get_user_id(tool_context) if tool_context else None

    from ...gateway.http_sse.repository.scheduled_task_repository import ScheduledTaskRepository

    try:
        repo = ScheduledTaskRepository()
        with session_factory() as session:
            tasks = repo.find_by_namespace(
                session,
                namespace=namespace,
                user_id=user_id,
                include_namespace_tasks=True,
                enabled_only=enabled_only,
            )

            if not tasks:
                return ToolResult.ok(
                    "No scheduled tasks found.",
                    data={"tasks": [], "total": 0},
                )

            task_list = []
            for t in tasks:
                next_run = ""
                if t.next_run_at:
                    next_run = datetime.fromtimestamp(
                        t.next_run_at / 1000, tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%M UTC")

                task_list.append({
                    "task_id": t.id,
                    "name": t.name,
                    "description": t.description or "",
                    "schedule_type": t.schedule_type.value if hasattr(t.schedule_type, 'value') else str(t.schedule_type),
                    "schedule_expression": t.schedule_expression,
                    "target_agent_name": t.target_agent_name,
                    "enabled": t.enabled,
                    "status": t.status,
                    "next_run": next_run,
                    "run_count": t.run_count,
                    "source": t.source or "ui",
                })

            summary_lines = []
            for t in task_list:
                status_icon = "on" if t["enabled"] else "off"
                summary_lines.append(
                    f"- **{t['name']}** [{status_icon}] → {t['target_agent_name']} "
                    f"({t['schedule_type']}: {t['schedule_expression']})"
                    + (f" — next: {t['next_run']}" if t['next_run'] else "")
                )

            return ToolResult.ok(
                f"Found {len(task_list)} scheduled task(s):\n" + "\n".join(summary_lines),
                data={"tasks": task_list, "total": len(task_list)},
            )

    except Exception as e:
        log.error(f"{tag} Error listing tasks: {e}", exc_info=True)
        return ToolResult.error(
            f"Failed to list scheduled tasks: {e}",
            code="LIST_FAILED",
        )


# ---------------------------------------------------------------------------
# schedule_delete
# ---------------------------------------------------------------------------


async def schedule_delete(
    task_id: str,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Delete a scheduled task by ID.

    Args:
        task_id: The ID of the scheduled task to delete.
        tool_context: Provided by ADK framework.
        tool_config: Optional tool configuration.
    """
    tag = "[SchedulingTools:schedule_delete]"

    scheduler_service, session_factory, namespace = _get_backend()
    if not scheduler_service:
        return ToolResult.error(
            "Scheduling is not enabled. The scheduler service is not running.",
            code="SCHEDULER_UNAVAILABLE",
        )

    user_id = _get_user_id(tool_context) if tool_context else "system"

    from ...gateway.http_sse.repository.scheduled_task_repository import ScheduledTaskRepository

    try:
        repo = ScheduledTaskRepository()
        with session_factory() as session:
            # Verify task exists and user has access
            task = repo.find_by_id(session, task_id, user_id=user_id)
            if not task:
                return ToolResult.error(
                    f"Scheduled task '{task_id}' not found or not accessible.",
                    code="NOT_FOUND",
                )

            task_name = task.name

            # Soft-delete in DB
            deleted = repo.soft_delete(session, task_id, deleted_by=user_id)
            if not deleted:
                return ToolResult.error(
                    f"Failed to delete task '{task_id}'.",
                    code="DELETE_FAILED",
                )

            session.commit()

            # Unschedule from APScheduler
            try:
                await scheduler_service._unschedule_task(task_id)
            except Exception as e:
                log.warning(f"{tag} Failed to unschedule task {task_id}: {e}")

            log.info(f"{tag} Deleted task '{task_name}' (id={task_id}) by user {user_id}")

            return ToolResult.ok(
                f"Scheduled task '{task_name}' (ID: {task_id}) has been deleted.",
                data={"task_id": task_id, "name": task_name, "deleted": True},
            )

    except Exception as e:
        log.error(f"{tag} Error deleting task: {e}", exc_info=True)
        return ToolResult.error(
            f"Failed to delete scheduled task: {e}",
            code="DELETE_FAILED",
        )


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

schedule_create_tool = BuiltinTool(
    name="schedule_create",
    implementation=schedule_create,
    description=(
        "Create a new scheduled task that runs an agent on a recurring schedule. "
        "Supports cron expressions (e.g. '0 9 * * *' for daily at 9 AM), "
        "intervals (e.g. '30m', '1h'), and one-time schedules. "
        "Use this when the user wants to automate a recurring task like "
        "'generate a daily report' or 'check system health every 30 minutes'."
    ),
    category=CATEGORY,
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["admin:scheduling"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "name": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Human-readable name for the scheduled task.",
            ),
            "schedule_type": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Type of schedule: 'cron', 'interval', or 'one_time'.",
                enum=["cron", "interval", "one_time"],
            ),
            "schedule_expression": adk_types.Schema(
                type=adk_types.Type.STRING,
                description=(
                    "Schedule expression. For cron: standard 5-field cron (e.g. '0 9 * * *'). "
                    "For interval: duration with suffix (e.g. '30m', '1h', '2d'). "
                    "For one_time: ISO 8601 datetime."
                ),
            ),
            "target_agent_name": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Name of the agent to invoke on each execution.",
            ),
            "task_message": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The prompt or message to send to the target agent on each execution.",
            ),
            "description": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional description of what this task does.",
            ),
            "timezone_str": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="IANA timezone for the schedule (default: UTC). E.g. 'America/New_York'.",
            ),
        },
        required=["name", "schedule_type", "schedule_expression", "target_agent_name", "task_message"],
    ),
    examples=[
        {
            "input": {
                "name": "Daily Report",
                "schedule_type": "cron",
                "schedule_expression": "0 9 * * *",
                "target_agent_name": "OrchestratorAgent",
                "task_message": "Generate a summary of yesterday's activities",
            },
            "output": "Scheduled task 'Daily Report' created. Schedule: cron: 0 9 * * * (UTC).",
        },
        {
            "input": {
                "name": "Health Check",
                "schedule_type": "interval",
                "schedule_expression": "30m",
                "target_agent_name": "OrchestratorAgent",
                "task_message": "Check API endpoints and database connections",
            },
            "output": "Scheduled task 'Health Check' created. Schedule: every 30m (UTC).",
        },
    ],
)

schedule_list_tool = BuiltinTool(
    name="schedule_list",
    implementation=schedule_list,
    description=(
        "List all scheduled tasks. Shows task names, schedules, target agents, "
        "status (enabled/disabled), and next run time. Use this when the user "
        "asks what tasks are scheduled, wants to review their automations, "
        "or needs a task ID for deletion."
    ),
    category=CATEGORY,
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["admin:scheduling"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "enabled_only": adk_types.Schema(
                type=adk_types.Type.BOOLEAN,
                description="If true, only show enabled tasks. Default: false (show all).",
            ),
        },
        required=[],
    ),
    examples=[],
)

schedule_delete_tool = BuiltinTool(
    name="schedule_delete",
    implementation=schedule_delete,
    description=(
        "Delete a scheduled task by its ID. The task is soft-deleted and unscheduled. "
        "Use schedule_list first to find the task ID if the user refers to a task by name."
    ),
    category=CATEGORY,
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["admin:scheduling"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "task_id": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The UUID of the scheduled task to delete.",
            ),
        },
        required=["task_id"],
    ),
    examples=[],
)

# Register all scheduling tools
tool_registry.register(schedule_create_tool)
tool_registry.register(schedule_list_tool)
tool_registry.register(schedule_delete_tool)
