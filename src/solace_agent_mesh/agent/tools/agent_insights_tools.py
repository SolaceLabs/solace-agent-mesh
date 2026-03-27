"""
Agent Insights Tools — read-only queries over the existing SAM task/event/feedback
persistence layer to surface agent improvement signals.

These are standard SAM builtin tools registered in the tool registry.
They are exposed via a dedicated autonomous insights agent configured in
preset/agents/agent_insights.yaml.

The agent runs as a feedback-loop daemon: on startup its initializer registers
a repeating SAC timer. Each time the timer fires the agent self-publishes an A2A
request to its own request topic, which triggers the LLM to call the analysis
tools and write a structured report artifact.

Configuration (via tool_config in the YAML):
    database_url        — SQLAlchemy URL for the gateway task DB (required)
    report_interval_s   — seconds between self-triggered analysis runs (default: 86400)
    report_lookback_h   — hours of history each report covers (default: 24)
    report_prompt       — override the prompt sent to the agent on each run
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from google.adk.tools import ToolContext
from google.genai import types as adk_types
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .tool_definition import BuiltinTool
from .tool_result import ToolResult, DataObject, DataDisposition
from .registry import tool_registry

log = logging.getLogger(__name__)

CATEGORY_NAME = "Agent Insights"
CATEGORY_DESCRIPTION = (
    "Autonomous feedback-loop tools that query SAM task history, tool invocations, "
    "and user feedback to produce periodic improvement reports."
)

_SCHEDULER_TIMER_ID = "agent_insights_report_timer"

_DEFAULT_REPORT_PROMPT = (
    "You are running your scheduled agent improvement analysis. "
    "Please:\n"
    "1. Call query_agent_stats to get an overview of task outcomes and token usage.\n"
    "2. Call query_tool_stats to identify any flaky or slow tools.\n"
    "3. Call query_recent_failures to surface failed tasks and negative feedback.\n"
    "4. Based on the data, write a structured improvement report saved as an artifact "
    "named 'insights_report_{date}.md'. The report must include:\n"
    "   - Executive summary (2-3 sentences)\n"
    "   - Key metrics (completion rate, avg latency, negative feedback rate)\n"
    "   - Issues found (flaky tools, patterns in failures, common user requests "
    "     that couldn't be fulfilled)\n"
    "   - Concrete recommendations (e.g. 'Add a calendar tool — 8 users asked about"
    " scheduling in the past 24h', 'Investigate web_request errors — 35% failure rate')\n"
    "   - Next steps\n"
    "Keep it concise and actionable."
)

# ---------------------------------------------------------------------------
# SQLAlchemy helpers
# ---------------------------------------------------------------------------

_engine_cache: Dict[str, Any] = {}


def _get_session(database_url: str):
    if database_url not in _engine_cache:
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        )
        _engine_cache[database_url] = sessionmaker(bind=engine)
    return _engine_cache[database_url]()


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _hours_ago_ms(hours: int) -> int:
    return int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp() * 1000)


def _ms_to_iso(ms: Optional[int]) -> Optional[str]:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _p95(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = max(0, int(len(sorted_vals) * 0.95) - 1)
    return round(sorted_vals[idx])


def _get_db_url(tool_config: Optional[Dict[str, Any]]) -> Optional[str]:
    if not tool_config:
        return None
    return tool_config.get("database_url")


# ---------------------------------------------------------------------------
# Scheduler initializer — called once at agent startup
# ---------------------------------------------------------------------------

def _insights_scheduler_init(component: Any, tool_config: Dict[str, Any]) -> None:
    """
    Registers a repeating SAC timer on the agent component.

    When the timer fires it publishes a synthetic A2A SendMessageRequest back
    to the agent's own request topic so the LLM runs the analysis autonomously.

    This is the same mechanism the agent uses for health-check and card-publish
    timers, so it requires no new infrastructure.
    """
    interval_s = int(tool_config.get("report_interval_s", 86400))
    if interval_s <= 0:
        log.info(
            "[AgentInsights] report_interval_s=%d — autonomous scheduling disabled.",
            interval_s,
        )
        return

    agent_name = component.get_config("agent_name")
    namespace = component.get_config("namespace")
    prompt = tool_config.get("report_prompt", _DEFAULT_REPORT_PROMPT)
    lookback_h = int(tool_config.get("report_lookback_h", 24))

    # Substitute the lookback into the prompt so the LLM uses the right window
    prompt_with_lookback = prompt.replace("{lookback_h}", str(lookback_h))

    def _on_timer(_timer_data: Dict[str, Any]) -> None:
        _self_publish_analysis_request(
            component=component,
            namespace=namespace,
            agent_name=agent_name,
            prompt=prompt_with_lookback,
        )

    interval_ms = interval_s * 1000
    component.add_timer(
        delay_ms=interval_ms,
        timer_id=_SCHEDULER_TIMER_ID,
        interval_ms=interval_ms,
        callback=_on_timer,
    )
    log.info(
        "[AgentInsights] Scheduled autonomous analysis every %ds for agent '%s'.",
        interval_s,
        agent_name,
    )


def _self_publish_analysis_request(
    component: Any,
    namespace: str,
    agent_name: str,
    prompt: str,
) -> None:
    """
    Publishes a minimal A2A SendMessageRequest to the agent's own request topic.
    The agent receives this exactly as if an external caller had sent it.
    """
    from ...common import a2a

    task_id = str(uuid.uuid4())
    request_topic = a2a.get_agent_request_topic(namespace, agent_name)

    # Build a minimal A2A message payload — same shape as the gateway produces
    payload = {
        "jsonrpc": "2.0",
        "id": task_id,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": prompt}],
                "messageId": str(uuid.uuid4()),
                "taskId": task_id,
                "contextId": task_id,
            }
        },
    }

    user_properties = {
        "userId": "agent_insights_daemon",
        "replyTo": f"{namespace}/a2a/v1/insights/daemon/sink/{task_id}",
    }

    log.info(
        "[AgentInsights] Self-publishing scheduled analysis request (task_id=%s) "
        "to topic '%s'.",
        task_id,
        request_topic,
    )

    try:
        component.publish_a2a_message(
            payload=payload,
            topic=request_topic,
            user_properties=user_properties,
        )
    except Exception as exc:
        log.exception(
            "[AgentInsights] Failed to self-publish analysis request: %s", exc
        )


# ---------------------------------------------------------------------------
# Tool 1: query_agent_stats
# ---------------------------------------------------------------------------

async def query_agent_stats(
    lookback_hours: int = 24,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Returns per-user task counts, completion rates, average latency,
    negative-feedback count, and token usage over a lookback window.

    Args:
        lookback_hours: How many hours of history to analyse (default 24).
        tool_context: ADK tool context (injected by framework).
        tool_config: Must contain 'database_url' pointing at the SAM gateway DB.
    """
    log_id = "[AgentInsights:query_agent_stats]"
    db_url = _get_db_url(tool_config)
    if not db_url:
        return ToolResult.error("No database_url configured for agent_insights tools.")

    since_ms = _hours_ago_ms(lookback_hours)

    sql = text("""
        SELECT
            t.user_id,
            COUNT(*)                                          AS total_tasks,
            SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN t.status = 'failed'    THEN 1 ELSE 0 END) AS failed,
            SUM(CASE WHEN t.status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
            ROUND(AVG(CASE WHEN t.end_time IS NOT NULL
                          THEN (t.end_time - t.start_time) ELSE NULL END), 0)
                                                             AS avg_duration_ms,
            SUM(COALESCE(t.total_input_tokens, 0))           AS total_input_tokens,
            SUM(COALESCE(t.total_output_tokens, 0))          AS total_output_tokens,
            (SELECT COUNT(*) FROM feedback f
             WHERE f.task_id = t.id AND f.rating = 'down')   AS negative_feedback
        FROM tasks t
        WHERE t.start_time >= :since_ms
        GROUP BY t.user_id
        ORDER BY total_tasks DESC
    """)

    try:
        session = _get_session(db_url)
        rows = session.execute(sql, {"since_ms": since_ms}).mappings().all()
        session.close()
    except Exception as exc:
        log.exception("%s DB error: %s", log_id, exc)
        return ToolResult.error(f"Database query failed: {exc}")

    stats = [dict(r) for r in rows]
    if not stats:
        return ToolResult.ok(
            f"No tasks found in the last {lookback_hours} hours.",
            data={"lookback_hours": lookback_hours, "agents": []},
        )

    return ToolResult.ok(
        f"Found data for {len(stats)} user(s) over the last {lookback_hours} hours.",
        data={"lookback_hours": lookback_hours, "agents": stats},
        data_objects=[
            DataObject(
                name="agent_stats.json",
                content=json.dumps(stats, indent=2, default=str),
                mime_type="application/json",
                disposition=DataDisposition.ARTIFACT_WITH_PREVIEW,
                description=f"Per-agent stats for last {lookback_hours}h",
            )
        ],
    )


# ---------------------------------------------------------------------------
# Tool 2: query_tool_stats
# ---------------------------------------------------------------------------

async def query_tool_stats(
    lookback_hours: int = 24,
    min_calls: int = 3,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Analyses tool invocation signals stored in task_events to surface:
    - tools with the highest error rates (flaky tools, flagged at ≥20%)
    - tools with the highest p95 latency (flagged at ≥5 s)

    Args:
        lookback_hours: Hours of history to analyse (default 24).
        min_calls: Minimum call count required to include a tool (default 3).
        tool_context: ADK tool context.
        tool_config: Must contain 'database_url'.
    """
    log_id = "[AgentInsights:query_tool_stats]"
    db_url = _get_db_url(tool_config)
    if not db_url:
        return ToolResult.error("No database_url configured for agent_insights tools.")

    since_ms = _hours_ago_ms(lookback_hours)

    sql = text("""
        SELECT te.task_id, te.created_time, te.payload
        FROM task_events te
        JOIN tasks t ON t.id = te.task_id
        WHERE t.start_time >= :since_ms
          AND (
                (te.payload LIKE '%tool_invocation_start%')
             OR (te.payload LIKE '%tool_result%')
          )
    """)

    try:
        session = _get_session(db_url)
        rows = session.execute(sql, {"since_ms": since_ms}).mappings().all()
        session.close()
    except Exception as exc:
        log.exception("%s DB error: %s", log_id, exc)
        return ToolResult.error(f"Database query failed: {exc}")

    starts: Dict[str, Dict] = {}
    results: Dict[str, List[Dict]] = {}

    for row in rows:
        payload = row["payload"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                continue

        for sig in _extract_signals(payload):
            sig_type = sig.get("type")
            if sig_type == "tool_invocation_start":
                fid = sig.get("function_call_id", "")
                starts[fid] = {
                    "tool_name": sig.get("tool_name", "unknown"),
                    "ts": row["created_time"],
                }
            elif sig_type == "tool_result":
                tool_name = sig.get("tool_name", "unknown")
                fid = sig.get("function_call_id", "")
                start_info = starts.get(fid, {})
                start_ts = start_info.get("ts")
                duration_ms = (row["created_time"] - start_ts) if start_ts else None
                is_error = _is_error_result(sig.get("result_data"))
                results.setdefault(tool_name, []).append(
                    {"duration_ms": duration_ms, "is_error": is_error}
                )

    if not results:
        return ToolResult.ok(
            f"No tool invocation data found in the last {lookback_hours} hours.",
            data={"lookback_hours": lookback_hours, "tools": []},
        )

    tool_stats = []
    for tool_name, calls in results.items():
        if len(calls) < min_calls:
            continue
        errors = sum(1 for c in calls if c["is_error"])
        durations = [c["duration_ms"] for c in calls if c["duration_ms"] is not None]
        tool_stats.append(
            {
                "tool_name": tool_name,
                "call_count": len(calls),
                "error_count": errors,
                "error_rate": round(errors / len(calls), 3),
                "avg_duration_ms": round(sum(durations) / len(durations)) if durations else None,
                "p95_duration_ms": _p95(durations) if durations else None,
            }
        )

    tool_stats.sort(key=lambda x: x["error_rate"], reverse=True)

    flaky = [t for t in tool_stats if t["error_rate"] >= 0.20]
    slow = sorted(
        [t for t in tool_stats if t.get("p95_duration_ms") and t["p95_duration_ms"] >= 5000],
        key=lambda x: x["p95_duration_ms"],
        reverse=True,
    )

    insight_lines = []
    if flaky:
        insight_lines.append(
            "Flaky tools (≥20% error rate): "
            + ", ".join(f"{t['tool_name']} ({t['error_rate']*100:.0f}%)" for t in flaky)
        )
    if slow:
        insight_lines.append(
            "Slow tools (p95 ≥5 s): "
            + ", ".join(f"{t['tool_name']} ({t['p95_duration_ms']}ms p95)" for t in slow)
        )
    if not insight_lines:
        insight_lines.append("All tools within normal error-rate and latency thresholds.")

    return ToolResult.ok(
        " | ".join(insight_lines),
        data={
            "lookback_hours": lookback_hours,
            "tool_count": len(tool_stats),
            "flaky_count": len(flaky),
            "slow_count": len(slow),
        },
        data_objects=[
            DataObject(
                name="tool_stats.json",
                content=json.dumps(tool_stats, indent=2, default=str),
                mime_type="application/json",
                disposition=DataDisposition.ARTIFACT_WITH_PREVIEW,
                description=f"Per-tool stats for last {lookback_hours}h",
            )
        ],
    )


# ---------------------------------------------------------------------------
# Tool 3: query_recent_failures
# ---------------------------------------------------------------------------

async def query_recent_failures(
    lookback_hours: int = 24,
    limit: int = 20,
    include_negative_feedback: bool = True,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Returns tasks that failed, were cancelled, or received negative user feedback,
    along with the user's original request text.

    Args:
        lookback_hours: Hours of history (default 24).
        limit: Max tasks to return (default 20).
        include_negative_feedback: Also surface completed tasks with 'down' feedback.
        tool_context: ADK tool context.
        tool_config: Must contain 'database_url'.
    """
    log_id = "[AgentInsights:query_recent_failures]"
    db_url = _get_db_url(tool_config)
    if not db_url:
        return ToolResult.error("No database_url configured for agent_insights tools.")

    since_ms = _hours_ago_ms(lookback_hours)

    if include_negative_feedback:
        sql = text("""
            SELECT DISTINCT
                t.id, t.user_id, t.status,
                t.start_time, t.end_time,
                t.initial_request_text,
                f.rating AS feedback_rating,
                f.comment AS feedback_comment
            FROM tasks t
            LEFT JOIN feedback f ON f.task_id = t.id
            WHERE t.start_time >= :since_ms
              AND (t.status IN ('failed', 'cancelled') OR f.rating = 'down')
            ORDER BY t.start_time DESC
            LIMIT :limit
        """)
    else:
        sql = text("""
            SELECT
                t.id, t.user_id, t.status,
                t.start_time, t.end_time,
                t.initial_request_text,
                NULL AS feedback_rating,
                NULL AS feedback_comment
            FROM tasks t
            WHERE t.start_time >= :since_ms
              AND t.status IN ('failed', 'cancelled')
            ORDER BY t.start_time DESC
            LIMIT :limit
        """)

    try:
        session = _get_session(db_url)
        rows = session.execute(sql, {"since_ms": since_ms, "limit": limit}).mappings().all()
        session.close()
    except Exception as exc:
        log.exception("%s DB error: %s", log_id, exc)
        return ToolResult.error(f"Database query failed: {exc}")

    failures = [
        {
            "task_id": row["id"],
            "user_id": row["user_id"],
            "status": row["status"],
            "duration_ms": (row["end_time"] - row["start_time"]) if row["end_time"] else None,
            "request": row["initial_request_text"],
            "feedback_rating": row["feedback_rating"],
            "feedback_comment": row["feedback_comment"],
            "started_at": _ms_to_iso(row["start_time"]),
        }
        for row in rows
    ]

    if not failures:
        return ToolResult.ok(
            f"No failed/cancelled tasks or negatively-rated interactions in the last {lookback_hours} hours.",
            data={"lookback_hours": lookback_hours, "failures": []},
        )

    neg_feedback = sum(1 for f in failures if f["feedback_rating"] == "down")
    hard_failures = sum(1 for f in failures if f["status"] in ("failed", "cancelled"))

    return ToolResult.ok(
        f"Found {len(failures)} problematic interactions in the last {lookback_hours} hours: "
        f"{hard_failures} failed/cancelled, {neg_feedback} with negative feedback.",
        data={
            "lookback_hours": lookback_hours,
            "total": len(failures),
            "hard_failures": hard_failures,
            "negative_feedback": neg_feedback,
        },
        data_objects=[
            DataObject(
                name="recent_failures.json",
                content=json.dumps(failures, indent=2, default=str),
                mime_type="application/json",
                disposition=DataDisposition.ARTIFACT_WITH_PREVIEW,
                description=f"Failed/cancelled/down-rated tasks in last {lookback_hours}h",
            )
        ],
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_signals(payload: Any) -> List[Dict]:
    """Recursively walk an A2A payload dict to collect signal data parts."""
    signals: List[Dict] = []
    _walk(payload, signals)
    return signals


def _walk(obj: Any, acc: List[Dict]) -> None:
    if isinstance(obj, dict):
        if "type" in obj and obj["type"] in (
            "tool_invocation_start",
            "tool_result",
            "llm_invocation",
            "llm_response",
        ):
            acc.append(obj)
        for v in obj.values():
            _walk(v, acc)
    elif isinstance(obj, list):
        for item in obj:
            _walk(item, acc)


def _is_error_result(result_data: Any) -> bool:
    if result_data is None:
        return False
    if isinstance(result_data, dict):
        if result_data.get("status") == "error":
            return True
        if result_data.get("error_code"):
            return True
    if isinstance(result_data, str):
        lower = result_data.lower()
        return any(kw in lower for kw in ("error", "failed", "exception", "traceback"))
    return False


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

query_agent_stats_tool = BuiltinTool(
    name="query_agent_stats",
    implementation=query_agent_stats,
    description=(
        "Returns per-agent task counts, completion rates, average latency, "
        "token usage, and negative-feedback rate for a configurable lookback window. "
        "Use this to get a high-level health overview of all agents."
    ),
    category="agent_insights",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    initializer=_insights_scheduler_init,
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "lookback_hours": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="Hours of history to analyse (default 24).",
            ),
        },
        required=[],
    ),
    examples=[
        {"input": {"lookback_hours": 48}, "output": "Stats for 3 agents over the last 48 hours."}
    ],
)

query_tool_stats_tool = BuiltinTool(
    name="query_tool_stats",
    implementation=query_tool_stats,
    description=(
        "Analyses tool invocation signals in the event log to surface flaky tools "
        "(high error rate) and slow tools (high p95 latency). "
        "Use this to identify specific tools that need attention."
    ),
    category="agent_insights",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "lookback_hours": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="Hours of history to analyse (default 24).",
            ),
            "min_calls": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="Minimum call count to include a tool (default 3).",
            ),
        },
        required=[],
    ),
    examples=[
        {
            "input": {"lookback_hours": 24, "min_calls": 5},
            "output": "Flaky tools: web_request (35% errors). Slow tools: sql_query (8200ms p95).",
        }
    ],
)

query_recent_failures_tool = BuiltinTool(
    name="query_recent_failures",
    implementation=query_recent_failures,
    description=(
        "Returns tasks that failed, were cancelled, or received negative user feedback, "
        "with the original user request text. "
        "Use this to identify patterns such as apology loops, missing capabilities, "
        "or high-friction interactions, and suggest concrete improvements."
    ),
    category="agent_insights",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "lookback_hours": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="Hours of history to analyse (default 24).",
            ),
            "limit": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="Maximum number of tasks to return (default 20).",
            ),
            "include_negative_feedback": adk_types.Schema(
                type=adk_types.Type.BOOLEAN,
                description=(
                    "Also include completed tasks that received a thumbs-down "
                    "rating from the user (default true)."
                ),
            ),
        },
        required=[],
    ),
    examples=[
        {
            "input": {"lookback_hours": 24, "limit": 10},
            "output": "Found 4 failures: 2 tasks failed, 2 with negative feedback.",
        }
    ],
)

tool_registry.register(query_agent_stats_tool)
tool_registry.register(query_tool_stats_tool)
tool_registry.register(query_recent_failures_tool)
