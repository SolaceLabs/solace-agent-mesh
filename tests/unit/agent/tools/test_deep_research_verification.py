"""Behavioral tests for deep research plan verification functions.

Covers: _generate_research_plan, _is_interactive_plan_client,
_send_plan_verification, _wait_for_plan_response, _regenerate_queries_from_steps.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from solace_agent_mesh.agent.tools.deep_research_tools import (
    _generate_research_plan,
    _is_interactive_plan_client,
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
# _is_interactive_plan_client
# ===========================================================================

class TestIsInteractivePlanClient:
    """Behavioral tests for _is_interactive_plan_client."""

    def test_capability_flag_accepts(self):
        """Gateway advertises the capability -> verification allowed."""
        ctx = _make_tool_context(a2a_context={
            "client_id": "any-gateway-id",
            "gateway_capabilities": {"interactive_plan_verification": True},
        })
        assert _is_interactive_plan_client(ctx, None) is True

    def test_capability_flag_false_rejects(self):
        """Gateway explicitly says no -> verification skipped."""
        ctx = _make_tool_context(a2a_context={
            "client_id": "any-gateway-id",
            "gateway_capabilities": {"interactive_plan_verification": False},
        })
        assert _is_interactive_plan_client(ctx, None) is False

    def test_no_capability_no_legacy_config_rejects(self):
        """No capability flag and no legacy allowlist -> default deny (auto-approve path)."""
        ctx = _make_tool_context(a2a_context={"client_id": "http_sse_gateway"})
        assert _is_interactive_plan_client(ctx, None) is False

    def test_legacy_allowlist_still_works(self):
        """Back-compat: capability missing but operator set the legacy allowlist."""
        ctx = _make_tool_context(a2a_context={"client_id": "my_custom_webui"})
        cfg = {"interactive_plan_verification_clients": ["my_custom_webui"]}
        assert _is_interactive_plan_client(ctx, cfg) is True

    def test_legacy_allowlist_rejects_unlisted_client(self):
        ctx = _make_tool_context(a2a_context={"client_id": "http_sse_gateway"})
        cfg = {"interactive_plan_verification_clients": ["my_custom_webui"]}
        assert _is_interactive_plan_client(ctx, cfg) is False

    def test_legacy_wildcard_accepts_any_client(self):
        ctx = _make_tool_context(a2a_context={"client_id": "slack_gateway_abc"})
        cfg = {"interactive_plan_verification_clients": ["*"]}
        assert _is_interactive_plan_client(ctx, cfg) is True

    def test_capability_flag_wins_over_legacy_allowlist(self):
        """Capability flag is checked first; legacy fallback only runs when it's absent."""
        ctx = _make_tool_context(a2a_context={
            "client_id": "not-on-list",
            "gateway_capabilities": {"interactive_plan_verification": True},
        })
        cfg = {"interactive_plan_verification_clients": ["only-this-one"]}
        assert _is_interactive_plan_client(ctx, cfg) is True

    def test_missing_a2a_context_rejects(self):
        """Without a2a_context we can't tell - default to non-interactive."""
        ctx = _make_tool_context(a2a_context=None)
        assert _is_interactive_plan_client(ctx, None) is False

    def test_missing_client_id_rejects(self):
        ctx = _make_tool_context(a2a_context={"user_id": "u1"})
        assert _is_interactive_plan_client(ctx, None) is False

    def test_malformed_capabilities_falls_through(self):
        """A non-dict capabilities value is ignored, not crashed on."""
        ctx = _make_tool_context(a2a_context={
            "client_id": "x",
            "gateway_capabilities": "not-a-dict",
        })
        assert _is_interactive_plan_client(ctx, None) is False


# ===========================================================================
# _send_plan_verification
# ===========================================================================

@pytest.mark.asyncio
class TestSendPlanVerification:
    """Behavioral tests for _send_plan_verification."""

    async def test_publishes_plan_data_signal(self):
        """Happy path: publishes DeepResearchPlanData via host_component."""
        host = MagicMock()
        host.agent_name = "ResearchAgent"
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
        host.agent_name = "ResearchAgent"
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
    """Behavioral tests for _wait_for_plan_response (Future-based)."""

    async def test_resolves_with_registered_response(self):
        """Tool registers a waiter; resolving the future returns the response."""
        host = MagicMock()
        registered = {}

        def _register(plan_id, user_id, future, loop):
            registered["plan_id"] = plan_id
            registered["user_id"] = user_id
            registered["future"] = future
            registered["loop"] = loop

        host.register_deep_research_plan_waiter = MagicMock(side_effect=_register)
        host.drop_deep_research_plan_waiter = MagicMock()

        ctx = _make_tool_context(
            canonical_model=MagicMock(),
            host_component=host,
            a2a_context={"user_id": "user-1"},
        )

        async def _resolver():
            # Give the tool a tick to register before we complete the future.
            await asyncio.sleep(0)
            registered["future"].set_result({"action": "start", "steps": ["edited"]})

        result, _ = await asyncio.gather(
            _wait_for_plan_response("plan-1", ["original"], ctx),
            _resolver(),
        )

        assert result == {"action": "start", "steps": ["edited"]}
        assert registered["plan_id"] == "plan-1"
        assert registered["user_id"] == "user-1"

    async def test_timeout_drops_waiter_and_publishes_stale_signal(self):
        """On timeout, waiter is dropped and a timed_out signal is published."""
        host = MagicMock()
        host.register_deep_research_plan_waiter = MagicMock()
        host.drop_deep_research_plan_waiter = MagicMock()
        host.publish_data_signal_from_thread = MagicMock(return_value=True)

        ctx = _make_tool_context(
            canonical_model=MagicMock(),
            host_component=host,
            a2a_context={"user_id": "user-1"},
        )

        with patch(
            "solace_agent_mesh.agent.tools.deep_research_tools._PLAN_RESPONSE_TIMEOUT_SECONDS",
            0,
        ):
            result = await _wait_for_plan_response("plan-1", ["s1"], ctx)

        assert result["action"] == "cancel"
        assert result["reason"] == "timeout"
        host.drop_deep_research_plan_waiter.assert_called_once_with("plan-1")
        host.publish_data_signal_from_thread.assert_called_once()

    async def test_auto_approves_when_host_lacks_registry_api(self):
        """A host_component without register_deep_research_plan_waiter auto-approves."""
        host = MagicMock(spec=[])  # no registry methods at all
        ctx = _make_tool_context(canonical_model=MagicMock(), host_component=host)

        result = await _wait_for_plan_response("plan-1", ["s1", "s2"], ctx)

        assert result["action"] == "start"
        assert result["steps"] == ["s1", "s2"]

    async def test_auto_approves_when_no_host_component(self):
        """When host_component chain is broken, auto-approve."""
        ctx = MagicMock()
        ctx._invocation_context = None

        result = await _wait_for_plan_response("plan-1", ["s1"], ctx)

        assert result["action"] == "start"
        assert result["steps"] == ["s1"]

    async def test_auto_approves_when_no_user_id(self):
        """Missing user_id on a2a_context short-circuits to auto-approve."""
        host = MagicMock()
        host.register_deep_research_plan_waiter = MagicMock()
        ctx = _make_tool_context(
            canonical_model=MagicMock(),
            host_component=host,
            a2a_context={},  # no user_id
        )

        result = await _wait_for_plan_response("plan-1", ["s1"], ctx)

        assert result["action"] == "start"
        assert result["steps"] == ["s1"]
        host.register_deep_research_plan_waiter.assert_not_called()

    async def test_auto_approves_when_register_raises(self):
        """If the waiter registration raises, auto-approve defensively."""
        host = MagicMock()
        host.register_deep_research_plan_waiter = MagicMock(
            side_effect=RuntimeError("registry down")
        )

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
