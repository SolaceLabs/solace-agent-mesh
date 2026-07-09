"""
Unit tests for src/solace_agent_mesh/agent/tools/agent_insights_tools.py

Tests are self-contained: they spin up an in-memory SQLite database,
populate it with synthetic task/feedback/event rows, and assert on the
ToolResult objects returned by each tool function.

No Solace broker, no ADK agent, no LLM is required.
"""

import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Helpers: build an in-memory DB matching the gateway schema (minimal subset)
# ---------------------------------------------------------------------------

DDL = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    parent_task_id TEXT,
    start_time INTEGER NOT NULL,
    end_time INTEGER,
    status TEXT,
    initial_request_text TEXT,
    total_input_tokens INTEGER,
    total_output_tokens INTEGER,
    total_cached_input_tokens INTEGER,
    token_usage_details TEXT,
    execution_mode TEXT DEFAULT 'foreground',
    last_activity_time INTEGER,
    background_execution_enabled INTEGER DEFAULT 0,
    max_execution_time_ms INTEGER,
    session_id TEXT,
    events_buffered INTEGER DEFAULT 0,
    events_consumed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS task_events (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT,
    created_time INTEGER NOT NULL,
    topic TEXT NOT NULL,
    direction TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    rating TEXT NOT NULL,
    comment TEXT,
    created_time INTEGER NOT NULL
);
"""


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _ms(hours_ago: float = 0) -> int:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return int(dt.timestamp() * 1000)


def make_db() -> str:
    """Create an in-memory SQLite DB, populate with fixtures, return its URL."""
    # Use a file-based SQLite so we can share across connections within the test
    db_path = f"/tmp/test_insights_{uuid.uuid4().hex}.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        for stmt in DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()
    return url


def insert_task(
    url: str,
    task_id: str,
    user_id: str = "user_a",
    status: str = "completed",
    start_time: int = None,
    end_time: int = None,
    initial_request_text: str = "help me",
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> None:
    engine = create_engine(url, connect_args={"check_same_thread": False})
    now = _now_ms()
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO tasks (id, user_id, status, start_time, end_time, "
                "initial_request_text, total_input_tokens, total_output_tokens) "
                "VALUES (:id, :uid, :status, :st, :et, :req, :it, :ot)"
            ),
            {
                "id": task_id,
                "uid": user_id,
                "status": status,
                "st": start_time or now,
                "et": end_time or (now + 2000),
                "req": initial_request_text,
                "it": input_tokens,
                "ot": output_tokens,
            },
        )
        conn.commit()


def insert_feedback(
    url: str,
    task_id: str,
    rating: str = "down",
    comment: str = None,
    user_id: str = "user_a",
) -> None:
    engine = create_engine(url, connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO feedback (id, session_id, task_id, user_id, rating, comment, created_time) "
                "VALUES (:id, :sid, :tid, :uid, :rating, :comment, :ct)"
            ),
            {
                "id": str(uuid.uuid4()),
                "sid": "sess-1",
                "tid": task_id,
                "uid": user_id,
                "rating": rating,
                "comment": comment,
                "ct": _now_ms(),
            },
        )
        conn.commit()


def insert_tool_events(
    url: str,
    task_id: str,
    tool_name: str,
    is_error: bool = False,
    start_ts: int = None,
    result_ts_offset_ms: int = 500,
) -> None:
    """Insert a start + result pair for a tool call."""
    engine = create_engine(url, connect_args={"check_same_thread": False})
    now = _now_ms()
    fid = str(uuid.uuid4())
    start_ts = start_ts or now

    start_signal = {
        "type": "tool_invocation_start",
        "tool_name": tool_name,
        "tool_args": {},
        "function_call_id": fid,
    }
    result_signal = {
        "type": "tool_result",
        "tool_name": tool_name,
        "function_call_id": fid,
        "result_data": {"status": "error", "message": "boom"} if is_error else {"status": "success"},
    }

    def make_payload(signal: Dict[str, Any]) -> str:
        # Mimic the A2A envelope structure TaskLoggerService stores
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "tasks/sendSubscribe",
                "params": {
                    "message": {
                        "parts": [{"kind": "data", "data": signal}]
                    }
                },
            }
        )

    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO task_events (id, task_id, user_id, created_time, topic, direction, payload) "
                "VALUES (:id, :tid, :uid, :ct, :topic, :dir, :payload)"
            ),
            {
                "id": str(uuid.uuid4()),
                "tid": task_id,
                "uid": "user_a",
                "ct": start_ts,
                "topic": f"test/a2a/v1/agent/request/TestAgent",
                "dir": "outbound",
                "payload": make_payload(start_signal),
            },
        )
        conn.execute(
            text(
                "INSERT INTO task_events (id, task_id, user_id, created_time, topic, direction, payload) "
                "VALUES (:id, :tid, :uid, :ct, :topic, :dir, :payload)"
            ),
            {
                "id": str(uuid.uuid4()),
                "tid": task_id,
                "uid": "user_a",
                "ct": start_ts + result_ts_offset_ms,
                "topic": f"test/a2a/v1/gateway/status/gw/t1",
                "dir": "inbound",
                "payload": make_payload(result_signal),
            },
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_url():
    return make_db()


@pytest.fixture()
def tool_cfg(db_url):
    return {"database_url": db_url}


def _mock_ctx():
    ctx = MagicMock()
    ctx._invocation_context = MagicMock()
    return ctx


# ---------------------------------------------------------------------------
# Tests: query_agent_stats
# ---------------------------------------------------------------------------

class TestQueryAgentStats:
    @pytest.mark.asyncio
    async def test_no_database_url(self):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_agent_stats

        result = await query_agent_stats(tool_context=_mock_ctx(), tool_config={})
        assert result.status == "error"
        assert "database_url" in result.message

    @pytest.mark.asyncio
    async def test_empty_db(self, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_agent_stats

        result = await query_agent_stats(lookback_hours=24, tool_context=_mock_ctx(), tool_config=tool_cfg)
        assert result.status == "success"
        assert "No tasks" in result.message

    @pytest.mark.asyncio
    async def test_returns_stats_for_recent_tasks(self, db_url, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_agent_stats

        insert_task(db_url, "t1", status="completed", start_time=_ms(1), end_time=_ms(1) + 3000)
        insert_task(db_url, "t2", status="failed",    start_time=_ms(1), end_time=_ms(1) + 1000)
        insert_task(db_url, "t3", status="completed", start_time=_ms(1), end_time=_ms(1) + 5000)

        result = await query_agent_stats(lookback_hours=24, tool_context=_mock_ctx(), tool_config=tool_cfg)

        assert result.status == "success"
        assert result.data is not None
        agents = result.data["agents"]
        assert len(agents) >= 1
        row = agents[0]
        assert row["total_tasks"] == 3
        assert row["completed"] == 2
        assert row["failed"] == 1

    @pytest.mark.asyncio
    async def test_excludes_tasks_outside_window(self, db_url, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_agent_stats

        insert_task(db_url, "old", status="completed", start_time=_ms(48))  # 48h ago
        insert_task(db_url, "recent", status="completed", start_time=_ms(1))

        result = await query_agent_stats(lookback_hours=24, tool_context=_mock_ctx(), tool_config=tool_cfg)

        assert result.status == "success"
        agents = result.data["agents"]
        # Only the recent task should be in scope
        total = sum(a["total_tasks"] for a in agents)
        assert total == 1

    @pytest.mark.asyncio
    async def test_artifact_produced(self, db_url, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_agent_stats

        insert_task(db_url, "t1", start_time=_ms(1))
        result = await query_agent_stats(lookback_hours=24, tool_context=_mock_ctx(), tool_config=tool_cfg)

        assert result.status == "success"
        assert len(result.data_objects) == 1
        assert result.data_objects[0].name == "agent_stats.json"


# ---------------------------------------------------------------------------
# Tests: query_tool_stats
# ---------------------------------------------------------------------------

class TestQueryToolStats:
    @pytest.mark.asyncio
    async def test_no_database_url(self):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_tool_stats

        result = await query_tool_stats(tool_context=_mock_ctx(), tool_config={})
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_empty_db(self, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_tool_stats

        result = await query_tool_stats(lookback_hours=24, tool_context=_mock_ctx(), tool_config=tool_cfg)
        assert result.status == "success"
        assert "No tool invocation" in result.message

    @pytest.mark.asyncio
    async def test_detects_flaky_tool(self, db_url, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_tool_stats

        task_ids = [str(uuid.uuid4()) for _ in range(5)]
        for i, tid in enumerate(task_ids):
            insert_task(db_url, tid, start_time=_ms(1))
            # 3 out of 5 calls error → 60% error rate → should be flagged as flaky
            insert_tool_events(db_url, tid, "flaky_tool", is_error=(i < 3))

        result = await query_tool_stats(
            lookback_hours=24, min_calls=3, tool_context=_mock_ctx(), tool_config=tool_cfg
        )
        assert result.status == "success"
        assert "flaky_tool" in result.message.lower() or result.data["flaky_count"] >= 1
        assert len(result.data_objects) == 1
        stats = json.loads(result.data_objects[0].content)
        flaky_tool_row = next((s for s in stats if s["tool_name"] == "flaky_tool"), None)
        assert flaky_tool_row is not None
        assert flaky_tool_row["error_rate"] >= 0.5

    @pytest.mark.asyncio
    async def test_min_calls_filter(self, db_url, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_tool_stats

        # Only 2 calls — below the min_calls=3 threshold
        for i in range(2):
            tid = str(uuid.uuid4())
            insert_task(db_url, tid, start_time=_ms(1))
            insert_tool_events(db_url, tid, "rare_tool", is_error=True)

        result = await query_tool_stats(
            lookback_hours=24, min_calls=3, tool_context=_mock_ctx(), tool_config=tool_cfg
        )
        # rare_tool should be excluded
        if result.data_objects:
            stats = json.loads(result.data_objects[0].content)
            assert not any(s["tool_name"] == "rare_tool" for s in stats)

    @pytest.mark.asyncio
    async def test_latency_computed(self, db_url, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_tool_stats

        for _ in range(3):
            tid = str(uuid.uuid4())
            insert_task(db_url, tid, start_time=_ms(1))
            # 8 000 ms result_ts_offset → p95 should be ≥ 5 000 ms
            insert_tool_events(db_url, tid, "slow_tool", is_error=False, result_ts_offset_ms=8000)

        result = await query_tool_stats(
            lookback_hours=24, min_calls=3, tool_context=_mock_ctx(), tool_config=tool_cfg
        )
        assert result.status == "success"
        if result.data_objects:
            stats = json.loads(result.data_objects[0].content)
            slow = next((s for s in stats if s["tool_name"] == "slow_tool"), None)
            if slow:
                assert slow["p95_duration_ms"] >= 5000


# ---------------------------------------------------------------------------
# Tests: query_recent_failures
# ---------------------------------------------------------------------------

class TestQueryRecentFailures:
    @pytest.mark.asyncio
    async def test_no_database_url(self):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_recent_failures

        result = await query_recent_failures(tool_context=_mock_ctx(), tool_config={})
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_empty_db(self, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_recent_failures

        result = await query_recent_failures(lookback_hours=24, tool_context=_mock_ctx(), tool_config=tool_cfg)
        assert result.status == "success"
        assert "No" in result.message

    @pytest.mark.asyncio
    async def test_surfaces_failed_tasks(self, db_url, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_recent_failures

        insert_task(db_url, "f1", status="failed",    start_time=_ms(1), initial_request_text="book a flight")
        insert_task(db_url, "f2", status="cancelled", start_time=_ms(1), initial_request_text="set a reminder")
        insert_task(db_url, "ok", status="completed", start_time=_ms(1))

        result = await query_recent_failures(lookback_hours=24, tool_context=_mock_ctx(), tool_config=tool_cfg)
        assert result.status == "success"
        assert result.data["hard_failures"] == 2
        assert result.data["total"] == 2

    @pytest.mark.asyncio
    async def test_surfaces_negative_feedback(self, db_url, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_recent_failures

        insert_task(db_url, "ok1", status="completed", start_time=_ms(1), initial_request_text="summarise this doc")
        insert_feedback(db_url, "ok1", rating="down", comment="totally wrong answer")

        result = await query_recent_failures(
            lookback_hours=24, include_negative_feedback=True, tool_context=_mock_ctx(), tool_config=tool_cfg
        )
        assert result.status == "success"
        assert result.data["negative_feedback"] >= 1

    @pytest.mark.asyncio
    async def test_excludes_old_tasks(self, db_url, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_recent_failures

        insert_task(db_url, "old_fail", status="failed", start_time=_ms(72))  # 3 days ago
        insert_task(db_url, "new_fail", status="failed", start_time=_ms(1))

        result = await query_recent_failures(lookback_hours=24, tool_context=_mock_ctx(), tool_config=tool_cfg)
        assert result.data["hard_failures"] == 1

    @pytest.mark.asyncio
    async def test_artifact_produced(self, db_url, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_recent_failures

        insert_task(db_url, "f1", status="failed", start_time=_ms(1))
        result = await query_recent_failures(lookback_hours=24, tool_context=_mock_ctx(), tool_config=tool_cfg)
        assert result.status == "success"
        assert len(result.data_objects) == 1
        assert result.data_objects[0].name == "recent_failures.json"
        payload = json.loads(result.data_objects[0].content)
        assert any(item["task_id"] == "f1" for item in payload)

    @pytest.mark.asyncio
    async def test_limit_respected(self, db_url, tool_cfg):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import query_recent_failures

        for i in range(10):
            insert_task(db_url, f"fail_{i}", status="failed", start_time=_ms(1))

        result = await query_recent_failures(
            lookback_hours=24, limit=3, tool_context=_mock_ctx(), tool_config=tool_cfg
        )
        assert result.status == "success"
        payload = json.loads(result.data_objects[0].content)
        assert len(payload) <= 3


# ---------------------------------------------------------------------------
# Tests: internal helpers
# ---------------------------------------------------------------------------

class TestInternalHelpers:
    def test_extract_signals_nested(self):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import _extract_signals

        payload = {
            "params": {
                "message": {
                    "parts": [
                        {"kind": "data", "data": {"type": "tool_invocation_start", "tool_name": "foo", "tool_args": {}, "function_call_id": "id1"}},
                        {"kind": "data", "data": {"type": "tool_result", "tool_name": "foo", "result_data": {}, "function_call_id": "id1"}},
                    ]
                }
            }
        }
        signals = _extract_signals(payload)
        assert len(signals) == 2
        assert signals[0]["type"] == "tool_invocation_start"
        assert signals[1]["type"] == "tool_result"

    def test_extract_signals_string_payload(self):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import _extract_signals

        signals = _extract_signals("not a dict")
        assert signals == []

    def test_is_error_result_dict_status(self):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import _is_error_result

        assert _is_error_result({"status": "error"}) is True
        assert _is_error_result({"status": "success"}) is False

    def test_is_error_result_string_heuristic(self):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import _is_error_result

        assert _is_error_result("Traceback (most recent call last): ...") is True
        assert _is_error_result("Result: 42") is False

    def test_p95_single_value(self):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import _p95

        assert _p95([1000]) == 1000

    def test_p95_empty(self):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import _p95

        assert _p95([]) == 0.0

    def test_p95_sorted(self):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import _p95

        values = list(range(1, 101))  # 1..100
        # p95 of 100 values → index 94 (0-based) → value 95
        assert _p95(values) == 95


# ---------------------------------------------------------------------------
# Tests: tool registration
# ---------------------------------------------------------------------------

class TestToolRegistration:
    def test_tools_registered_in_registry(self):
        from src.solace_agent_mesh.agent.tools.registry import tool_registry
        import src.solace_agent_mesh.agent.tools.agent_insights_tools  # noqa: F401 ensure module loaded

        assert tool_registry.get_tool_by_name("query_agent_stats") is not None
        assert tool_registry.get_tool_by_name("query_tool_stats") is not None
        assert tool_registry.get_tool_by_name("query_recent_failures") is not None

    def test_tools_have_correct_category(self):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import (
            query_agent_stats_tool,
            query_tool_stats_tool,
            query_recent_failures_tool,
        )

        for tool in (query_agent_stats_tool, query_tool_stats_tool, query_recent_failures_tool):
            assert tool.category == "agent_insights"

    def test_query_agent_stats_has_initializer(self):
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import (
            query_agent_stats_tool,
            _insights_scheduler_init,
        )
        assert query_agent_stats_tool.initializer is _insights_scheduler_init


# ---------------------------------------------------------------------------
# Tests: scheduler initializer
# ---------------------------------------------------------------------------

class TestSchedulerInit:
    def test_registers_timer_on_component(self):
        """Initializer should call component.add_timer with the configured interval."""
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import _insights_scheduler_init

        mock_component = MagicMock()
        mock_component.get_config.side_effect = lambda key: {
            "agent_name": "AgentInsights",
            "namespace": "test/dev",
        }.get(key)

        _insights_scheduler_init(mock_component, {"database_url": "sqlite:///:memory:", "report_interval_s": 3600})

        mock_component.add_timer.assert_called_once()
        call_kwargs = mock_component.add_timer.call_args
        args = call_kwargs[1] if call_kwargs[1] else {}
        # interval_ms should equal report_interval_s * 1000
        assert args.get("interval_ms") == 3600 * 1000
        assert args.get("delay_ms") == 3600 * 1000

    def test_no_timer_when_interval_zero(self):
        """Setting report_interval_s=0 should disable scheduling entirely."""
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import _insights_scheduler_init

        mock_component = MagicMock()
        mock_component.get_config.side_effect = lambda key: {
            "agent_name": "AgentInsights",
            "namespace": "test/dev",
        }.get(key)

        _insights_scheduler_init(mock_component, {"database_url": "sqlite:///:memory:", "report_interval_s": 0})

        mock_component.add_timer.assert_not_called()

    def test_self_publish_called_on_timer_fire(self):
        """When the registered timer callback fires it should publish an A2A message."""
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import _insights_scheduler_init

        mock_component = MagicMock()
        mock_component.get_config.side_effect = lambda key: {
            "agent_name": "AgentInsights",
            "namespace": "test/dev",
        }.get(key)

        captured_callback = {}

        def capture_add_timer(**kwargs):
            captured_callback["fn"] = kwargs.get("callback")

        mock_component.add_timer.side_effect = capture_add_timer

        _insights_scheduler_init(mock_component, {"database_url": "sqlite:///:memory:", "report_interval_s": 60})

        # Simulate the timer firing
        assert "fn" in captured_callback, "No callback was registered"
        captured_callback["fn"]({})

        # The callback should have tried to publish a message
        mock_component.publish_a2a_message.assert_called_once()
        call_kwargs = mock_component.publish_a2a_message.call_args[1]
        assert "payload" in call_kwargs
        assert "topic" in call_kwargs
        # Topic should contain the agent name
        assert "AgentInsights" in call_kwargs["topic"]

    def test_self_publish_payload_is_valid_a2a(self):
        """The self-published payload should be a valid A2A SendMessageRequest shape."""
        from src.solace_agent_mesh.agent.tools.agent_insights_tools import _self_publish_analysis_request

        mock_component = MagicMock()

        _self_publish_analysis_request(
            component=mock_component,
            namespace="myorg/dev",
            agent_name="AgentInsights",
            prompt="run analysis",
        )

        mock_component.publish_a2a_message.assert_called_once()
        payload = mock_component.publish_a2a_message.call_args[1]["payload"]

        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "message/send"
        assert "params" in payload
        msg = payload["params"]["message"]
        assert msg["role"] == "user"
        assert any(p.get("text") == "run analysis" for p in msg["parts"])
