"""Behavioral tests for deep research plan verification functions.

Covers: _generate_research_plan, _is_webui_gateway, _send_plan_verification,
_wait_for_plan_response, _regenerate_queries_from_steps.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from solace_agent_mesh.agent.tools.deep_research_tools import (
    _generate_research_plan,
    _is_webui_gateway,
    _send_plan_verification,
    _wait_for_plan_response,
    _regenerate_queries_from_steps,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_tool_context(
    *,
    canonical_model=None,
    host_component=None,
    a2a_context=None,
):
    """Build a mock ToolContext wired up the way deep_research_tools expects."""
    ctx = MagicMock()
    ctx.state = MagicMock()
    ctx.state.get = MagicMock(return_value=a2a_context)

    inv = MagicMock()
    agent = MagicMock()
    agent.canonical_model = canonical_model

    if host_component is None and canonical_model is not None:
        host_component = MagicMock()
        host_component.get_lite_llm_model = MagicMock(return_value=canonical_model)

    agent.host_component = host_component
    inv.agent = agent
    ctx._invocation_context = inv
    return ctx


def _make_llm_response(text: str):
    """Return a minimal mock that _extract_text_from_llm_response can parse."""
    resp = MagicMock()
    resp.text = text
    resp.parts = None
    resp.content = None
    return resp


def _make_async_llm(response_text: str):
    """Return a mock LLM whose generate_content_async yields one response."""
    model = MagicMock()
    model.model = "test-model"

    async def _gen(*_a, **_kw):
        yield _make_llm_response(response_text)

    model.generate_content_async = MagicMock(side_effect=lambda *a, **k: _gen(*a, **k))
    return model


# ===========================================================================
# _generate_research_plan
# ===========================================================================

@pytest.mark.asyncio
class TestGenerateResearchPlan:
    """Behavioral tests for _generate_research_plan."""

    async def test_returns_steps_from_llm(self):
        """LLM returns valid JSON -> function returns those steps."""
        llm = _make_async_llm('{"steps": ["Gather data", "Analyze results", "Compile report"]}')
        ctx = _make_tool_context(canonical_model=llm)

        steps = await _generate_research_plan(
            "What is quantum computing?",
            ["quantum computing basics", "quantum computing applications"],
            ctx,
        )

        assert steps == ["Gather data", "Analyze results", "Compile report"]

    async def test_truncates_to_six_steps(self):
        """Even if the LLM returns more than 6 steps, only 6 are kept."""
        import json
        many = [f"Step {i}" for i in range(10)]
        llm = _make_async_llm(json.dumps({"steps": many}))
        ctx = _make_tool_context(canonical_model=llm)

        steps = await _generate_research_plan("q", ["q1"], ctx)
        assert len(steps) == 6

    async def test_falls_back_to_queries_on_empty_response(self):
        """Empty LLM response -> original queries returned as fallback."""
        llm = _make_async_llm("")
        ctx = _make_tool_context(canonical_model=llm)

        queries = ["query A", "query B"]
        steps = await _generate_research_plan("q", queries, ctx)
        assert steps == queries

    async def test_falls_back_to_queries_on_invalid_json(self):
        """LLM returns garbage -> original queries returned as fallback."""
        llm = _make_async_llm("this is not json at all")
        ctx = _make_tool_context(canonical_model=llm)

        queries = ["q1", "q2"]
        steps = await _generate_research_plan("q", queries, ctx)
        assert steps == queries

    async def test_falls_back_to_queries_on_exception(self):
        """If LLM call raises, queries are returned as fallback."""
        model = MagicMock()
        model.model = "test"
        model.generate_content_async = MagicMock(side_effect=Exception("boom"))
        ctx = _make_tool_context(canonical_model=model)

        queries = ["fallback1"]
        steps = await _generate_research_plan("q", queries, ctx)
        assert steps == queries

    async def test_uses_sync_fallback_when_no_async(self):
        """When LLM lacks generate_content_async, falls back to generate_content."""
        model = MagicMock(spec=[])  # empty spec -> no generate_content_async
        model.model = "test"
        model.generate_content = MagicMock(
            return_value=_make_llm_response('{"steps": ["sync step"]}')
        )
        ctx = _make_tool_context(canonical_model=model)

        steps = await _generate_research_plan("q", ["q1"], ctx)
        assert steps == ["sync step"]
        model.generate_content.assert_called_once()


# ===========================================================================
# _is_webui_gateway
# ===========================================================================

class TestIsWebuiGateway:
    """Behavioral tests for _is_webui_gateway."""

    def test_always_returns_true(self):
        """Current implementation always returns True."""
        ctx = _make_tool_context()
        assert _is_webui_gateway(ctx) is True


# ===========================================================================
# _send_plan_verification
# ===========================================================================

@pytest.mark.asyncio
class TestSendPlanVerification:
    """Behavioral tests for _send_plan_verification."""

    async def test_publishes_plan_data_signal(self):
        """Happy path: publishes DeepResearchPlanData via host_component."""
        host = MagicMock()
        ctx = _make_tool_context(
            canonical_model=MagicMock(),
            host_component=host,
            a2a_context={"task_id": "t1"},
        )

        await _send_plan_verification(
            plan_id="plan-1",
            title="Test Title",
            research_question="What is AI?",
            steps=["Step 1", "Step 2"],
            research_type="quick",
            max_iterations=3,
            max_runtime_seconds=300,
            sources=["web"],
            tool_context=ctx,
        )

        host.publish_data_signal_from_thread.assert_called_once()
        call_kwargs = host.publish_data_signal_from_thread.call_args[1]
        signal = call_kwargs["signal_data"]
        assert signal.plan_id == "plan-1"
        assert signal.title == "Test Title"
        assert signal.steps == ["Step 1", "Step 2"]
        assert signal.research_type == "quick"

    async def test_no_crash_when_a2a_context_missing(self):
        """Returns silently when a2a_context is absent."""
        ctx = _make_tool_context(canonical_model=MagicMock(), a2a_context=None)
        # Should not raise
        await _send_plan_verification(
            "id", "t", "q", ["s"], "quick", 3, 300, [], ctx
        )

    async def test_no_crash_when_no_invocation_context(self):
        """Returns silently when _invocation_context is None."""
        ctx = MagicMock()
        ctx.state = MagicMock()
        ctx.state.get = MagicMock(return_value={"task_id": "t"})
        ctx._invocation_context = None

        await _send_plan_verification(
            "id", "t", "q", ["s"], "quick", 3, 300, [], ctx
        )

    async def test_no_crash_when_host_component_missing(self):
        """Returns silently when host_component is None."""
        ctx = _make_tool_context(a2a_context={"task_id": "t"})
        ctx._invocation_context.agent.host_component = None

        await _send_plan_verification(
            "id", "t", "q", ["s"], "quick", 3, 300, [], ctx
        )

    async def test_no_crash_on_publish_exception(self):
        """Catches exceptions from publish_data_signal_from_thread."""
        host = MagicMock()
        host.publish_data_signal_from_thread.side_effect = RuntimeError("oops")
        ctx = _make_tool_context(
            canonical_model=MagicMock(),
            host_component=host,
            a2a_context={"task_id": "t"},
        )

        await _send_plan_verification(
            "id", "t", "q", ["s"], "quick", 3, 300, [], ctx
        )


# ===========================================================================
# _wait_for_plan_response
# ===========================================================================

@pytest.mark.asyncio
class TestWaitForPlanResponse:
    """Behavioral tests for _wait_for_plan_response."""

    async def test_returns_cached_response_immediately(self):
        """When cache already has a response, returns it on first poll."""
        cache = MagicMock()
        cache.get_data = MagicMock(return_value={"action": "start", "steps": ["edited"]})

        host = MagicMock()
        host.cache_service = cache

        ctx = _make_tool_context(
            canonical_model=MagicMock(),
            host_component=host,
            a2a_context={"user_id": "user-1"},
        )

        result = await _wait_for_plan_response("plan-1", ["original"], ctx)

        assert result["action"] == "start"
        assert result["steps"] == ["edited"]
        cache.remove_data.assert_called_once_with("deep_research_plan:user-1:plan-1")

    async def test_polls_until_response_appears(self):
        """Simulates multiple poll cycles before the cache returns data."""
        call_count = 0

        def _get_data(key):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                return {"action": "cancel"}
            return None

        cache = MagicMock()
        cache.get_data = MagicMock(side_effect=_get_data)

        host = MagicMock()
        host.cache_service = cache

        ctx = _make_tool_context(
            canonical_model=MagicMock(),
            host_component=host,
            a2a_context={"user_id": "user-1"},
        )

        with patch("solace_agent_mesh.agent.tools.deep_research_tools.asyncio.sleep", new_callable=AsyncMock):
            result = await _wait_for_plan_response("plan-x", ["s1"], ctx)

        assert result["action"] == "cancel"
        assert call_count == 3

    async def test_auto_approves_when_no_cache_service(self):
        """When cache_service is unavailable, auto-approve with original steps."""
        host = MagicMock(spec=[])  # no cache_service attribute
        ctx = _make_tool_context(canonical_model=MagicMock(), host_component=host)

        result = await _wait_for_plan_response("plan-1", ["s1", "s2"], ctx)

        assert result["action"] == "start"
        assert result["steps"] == ["s1", "s2"]

    async def test_auto_approves_when_cache_service_is_none(self):
        """When cache_service exists but is None, auto-approve."""
        host = MagicMock()
        host.cache_service = None
        ctx = _make_tool_context(canonical_model=MagicMock(), host_component=host)

        result = await _wait_for_plan_response("plan-1", ["s1"], ctx)

        assert result["action"] == "start"

    async def test_auto_approves_when_no_host_component(self):
        """When host_component chain is broken, auto-approve."""
        ctx = MagicMock()
        ctx._invocation_context = None

        result = await _wait_for_plan_response("plan-1", ["s1"], ctx)

        assert result["action"] == "start"
        assert result["steps"] == ["s1"]

    async def test_auto_approves_on_exception(self):
        """If an exception occurs during polling, auto-approve."""
        cache = MagicMock()
        cache.get_data = MagicMock(side_effect=RuntimeError("cache down"))

        host = MagicMock()
        host.cache_service = cache

        ctx = _make_tool_context(
            canonical_model=MagicMock(),
            host_component=host,
            a2a_context={"user_id": "user-1"},
        )

        result = await _wait_for_plan_response("plan-1", ["s1"], ctx)

        assert result["action"] == "start"
        assert result["steps"] == ["s1"]


# ===========================================================================
# _regenerate_queries_from_steps
# ===========================================================================

@pytest.mark.asyncio
class TestRegenerateQueriesFromSteps:
    """Behavioral tests for _regenerate_queries_from_steps."""

    async def test_returns_queries_from_llm(self):
        """LLM returns valid JSON -> function returns those queries."""
        llm = _make_async_llm('{"queries": ["search query 1", "search query 2"]}')
        ctx = _make_tool_context(canonical_model=llm)

        queries = await _regenerate_queries_from_steps(
            ["Investigate X", "Analyze Y"], "What is X?", ctx
        )

        assert queries == ["search query 1", "search query 2"]

    async def test_truncates_to_step_count(self):
        """Returned queries are capped to the number of input steps."""
        llm = _make_async_llm('{"queries": ["q1", "q2", "q3", "q4", "q5"]}')
        ctx = _make_tool_context(canonical_model=llm)

        queries = await _regenerate_queries_from_steps(
            ["step1", "step2", "step3"], "q", ctx
        )

        assert len(queries) == 3

    async def test_falls_back_to_steps_on_empty_response(self):
        """Empty LLM response -> original steps returned as fallback."""
        llm = _make_async_llm("")
        ctx = _make_tool_context(canonical_model=llm)

        steps = ["step A", "step B"]
        queries = await _regenerate_queries_from_steps(steps, "q", ctx)
        assert queries == steps

    async def test_falls_back_to_steps_on_invalid_json(self):
        """LLM garbage -> steps used as queries."""
        llm = _make_async_llm("not json")
        ctx = _make_tool_context(canonical_model=llm)

        steps = ["s1"]
        queries = await _regenerate_queries_from_steps(steps, "q", ctx)
        assert queries == steps

    async def test_falls_back_to_steps_on_exception(self):
        """If LLM raises, steps are returned as fallback."""
        model = MagicMock()
        model.model = "test"
        model.generate_content_async = MagicMock(side_effect=Exception("fail"))
        ctx = _make_tool_context(canonical_model=model)

        steps = ["s1", "s2"]
        queries = await _regenerate_queries_from_steps(steps, "q", ctx)
        assert queries == steps

    async def test_uses_sync_fallback_when_no_async(self):
        """When LLM lacks generate_content_async, falls back to generate_content."""
        model = MagicMock(spec=[])
        model.model = "test"
        model.generate_content = MagicMock(
            return_value=_make_llm_response('{"queries": ["sync q"]}')
        )
        ctx = _make_tool_context(canonical_model=model)

        queries = await _regenerate_queries_from_steps(["s1"], "q", ctx)
        assert queries == ["sync q"]
