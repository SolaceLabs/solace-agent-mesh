"""Unit tests for context usage and manual compaction endpoints."""

import asyncio
import logging

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestGetModelContextLimit:
    """Tests for _get_model_context_limit pure function."""

    def test_returns_litellm_value_when_available(self):
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _get_model_context_limit,
            )

            mock_info = {"max_input_tokens": 128_000}
            with patch("litellm.get_model_info", return_value=mock_info):
                result = _get_model_context_limit("gpt-4")
                assert result == 128_000

    def test_returns_none_on_exception(self):
        """When LiteLLM raises for both full and bare name, return None."""
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _get_model_context_limit,
            )

            with patch("litellm.get_model_info", side_effect=Exception("unknown model")):
                result = _get_model_context_limit("unknown-model")
                assert result is None

    def test_returns_none_when_litellm_has_no_max_input_tokens(self):
        """When LiteLLM returns info but max_input_tokens is missing, return None."""
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _get_model_context_limit,
            )

            mock_info = {"model_name": "some-model"}  # no max_input_tokens key
            with patch("litellm.get_model_info", return_value=mock_info):
                result = _get_model_context_limit("some-model")
                assert result is None

    def test_strips_provider_prefix_on_fallback(self):
        """When full name fails but bare name succeeds, return the bare name result."""
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _get_model_context_limit,
            )

            def mock_get_model_info(name):
                if name == "custom-provider/gpt-4o":
                    raise Exception("unknown model")
                if name == "gpt-4o":
                    return {"max_input_tokens": 128_000}
                raise Exception("unknown model")

            with patch("litellm.get_model_info", side_effect=mock_get_model_info):
                result = _get_model_context_limit("custom-provider/gpt-4o")
                assert result == 128_000


def _make_mock_db():
    """Create a mock DB session that handles SQLAlchemy query chains for
    ChatTaskModel and TaskModel queries used by the context-usage endpoint."""
    db = MagicMock()
    # Default: no chat_tasks, no completed tasks
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.count.return_value = 0
    query_mock.all.return_value = []
    query_mock.first.return_value = None
    db.query.return_value = query_mock
    return db


def _make_query_chain(all_rows=None, count=0):
    """A stubbed SQLAlchemy query chain.

    `first()` must return None: `_lookup_configured_context_limit` calls it, and
    a bare MagicMock would be truthy, making `row[0]` a MagicMock that Pydantic
    then rejects as `max_input_tokens: int`.
    """
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.count.return_value = count
    q.all.return_value = all_rows or []
    q.first.return_value = None
    return q


def _make_mock_db_with_agents(tasks, events, chat_task_count=0):
    """Like _make_mock_db, but routes TaskEventModel queries separately from
    TaskModel ones, so tests can attribute tasks to different agents."""
    from solace_agent_mesh.gateway.http_sse.repository.models import (
        ChatTaskModel,
        TaskEventModel,
        TaskModel,
    )

    def _dispatch(entity, *_args):
        if entity is ChatTaskModel:
            return _make_query_chain(count=chat_task_count)
        if entity is TaskModel:
            return _make_query_chain(all_rows=tasks)
        if entity is TaskEventModel:
            return _make_query_chain(all_rows=events)
        # ModelConfiguration column lookups fall through to a first() of None.
        return _make_query_chain()

    db = MagicMock()
    db.query.side_effect = _dispatch
    return db


def _make_task(
    task_id, input_tokens=0, output_tokens=0, cached_tokens=0, details=None
):
    task = MagicMock()
    task.id = task_id
    task.total_input_tokens = input_tokens
    task.total_output_tokens = output_tokens
    task.total_cached_input_tokens = cached_tokens
    task.token_usage_details = details
    return task


def _make_request_event(task_id, agent_name):
    event = MagicMock()
    event.task_id = task_id
    event.direction = "request"
    event.payload = {"params": {"message": {"metadata": {"agent_name": agent_name}}}}
    return event


async def _call_context_usage(
    db, session_service, model=None, agent_name=None, component=None
):
    """Invoke the endpoint the way the rest of this module does."""
    if component is None:
        component = MagicMock()
        component.model_config = None

    with patch(
        "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
        return_value=component,
    ):
        from solace_agent_mesh.gateway.http_sse.routers.sessions import (
            get_session_context_usage,
        )

        return await get_session_context_usage(
            session_id="test-session-id",
            model=model,
            agent_name=agent_name,
            db=db,
            user={"id": "user-1"},
            session_service=session_service,
            component=component,
        )


class TestGetSessionContextUsage:
    """Tests for the get_session_context_usage endpoint."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def mock_session_service(self):
        return MagicMock()

    @pytest.fixture
    def mock_component(self):
        comp = MagicMock()
        comp.model_config = None
        return comp

    @pytest.mark.asyncio
    async def test_returns_zeros_for_empty_session(
        self, mock_db, mock_session_service, mock_component
    ):
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                get_session_context_usage,
            )

            result = await get_session_context_usage(
                session_id="test-session-id",
                model=None,
                agent_name=None,
                db=mock_db,
                user={"id": "user-1"},
                session_service=mock_session_service,
                component=mock_component,
            )

            assert result.current_context_tokens == 0
            assert result.prompt_tokens == 0
            assert result.completion_tokens == 0
            assert result.total_events == 0
            assert result.has_compaction is False

    @pytest.mark.asyncio
    async def test_returns_404_when_session_not_found(
        self, mock_db, mock_session_service, mock_component
    ):
        from fastapi import HTTPException

        mock_session_service.get_session_details.return_value = None

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                get_session_context_usage,
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_session_context_usage(
                    session_id="test-session-id",
                    model=None,
                    agent_name=None,
                    db=mock_db,
                    user={"id": "user-1"},
                    session_service=mock_session_service,
                    component=mock_component,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_token_data_from_completed_tasks(
        self, mock_db, mock_session_service, mock_component
    ):
        """Token data comes from the gateway's tasks table (LLM-reported totals)."""
        mock_session = MagicMock()
        # Leave agent_id unset so the agent-scoped task filter is a no-op
        # in this unit test (filter behavior is covered separately).
        mock_session.agent_id = None
        mock_session_service.get_session_details.return_value = mock_session

        # Set up mock DB to return completed tasks with token data
        latest_task = MagicMock()
        latest_task.id = "task-latest"
        latest_task.total_input_tokens = 5000
        latest_task.total_output_tokens = 800
        latest_task.total_cached_input_tokens = 200
        latest_task.token_usage_details = None

        older_task = MagicMock()
        older_task.id = "task-older"
        older_task.total_input_tokens = 3000
        older_task.total_output_tokens = 500
        older_task.total_cached_input_tokens = 100
        older_task.token_usage_details = None

        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.count.return_value = 3
        query_mock.all.return_value = [latest_task, older_task]
        mock_db.query.return_value = query_mock

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.routers.sessions._get_model_context_limit",
            return_value=200_000,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                get_session_context_usage,
            )

            result = await get_session_context_usage(
                session_id="test-session-id",
                model="test-model",
                agent_name=None,
                db=mock_db,
                user={"id": "user-1"},
                session_service=mock_session_service,
                component=mock_component,
            )

            # prompt_tokens = cumulative input across ALL completed tasks
            assert result.prompt_tokens == 8000  # 5000 + 3000
            # completion_tokens = cumulative output across all tasks
            assert result.completion_tokens == 1300  # 800 + 500
            # currentContextTokens = latest task's input tokens only
            assert result.current_context_tokens == 5000
            assert result.cached_tokens == 200
            assert result.total_events == 0
            assert result.has_compaction is False
            assert result.total_tasks == 3
            assert result.total_messages == 6


class TestCompactSession:
    """Tests for the compact_session endpoint (message-based compaction)."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_session_service(self):
        return MagicMock()

    @pytest.fixture
    def mock_component(self):
        comp = MagicMock()
        comp.gateway_id = "test-gateway"
        comp._compaction_futures = {}
        comp.sam_events = MagicMock()
        comp.sam_events.publish_session_compact_request = MagicMock(return_value=True)
        return comp

    def _make_resolved_future(self, result_data, loop=None):
        """Create a Future that is already resolved with the given data."""
        if loop is None:
            loop = asyncio.get_event_loop()
        future = loop.create_future()
        future.set_result(result_data)
        return future

    @pytest.mark.asyncio
    async def test_returns_404_when_session_not_found(
        self, mock_db, mock_session_service, mock_component
    ):
        from fastapi import HTTPException

        mock_session_service.get_session_details.return_value = None

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                compact_session,
                CompactSessionRequest,
            )

            with pytest.raises(HTTPException) as exc_info:
                await compact_session(
                    session_id="test-session-id",
                    request=CompactSessionRequest(),
                    agent_name=None,
                    db=mock_db,
                    user={"id": "user-1"},
                    session_service=mock_session_service,
                    component=mock_component,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_when_no_agent(
        self, mock_db, mock_session_service, mock_component
    ):
        from fastapi import HTTPException

        mock_session = MagicMock()
        mock_session.agent_id = None
        mock_session_service.get_session_details.return_value = mock_session

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                compact_session,
                CompactSessionRequest,
            )

            with pytest.raises(HTTPException) as exc_info:
                await compact_session(
                    session_id="test-session-id",
                    request=CompactSessionRequest(),
                    agent_name=None,
                    db=mock_db,
                    user={"id": "user-1"},
                    session_service=mock_session_service,
                    component=mock_component,
                )

            assert exc_info.value.status_code == 400
            assert "agent" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_returns_400_when_agent_reports_not_enough_turns(
        self, mock_db, mock_session_service, mock_component
    ):
        """Agent responds with success=False and 'not enough' error."""
        from fastapi import HTTPException

        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        response_data = {
            "success": False,
            "error_message": "Not enough conversation turns to compact. Need at least 2 user turns.",
        }
        mock_component.register_compaction_future = MagicMock(
            return_value=self._make_resolved_future(response_data)
        )

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                compact_session,
                CompactSessionRequest,
            )

            with pytest.raises(HTTPException) as exc_info:
                await compact_session(
                    session_id="test-session-id",
                    request=CompactSessionRequest(),
                    agent_name=None,
                    db=mock_db,
                    user={"id": "user-1"},
                    session_service=mock_session_service,
                    component=mock_component,
                )

            assert exc_info.value.status_code == 400
            assert "not enough" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_returns_408_on_timeout(
        self, mock_db, mock_session_service, mock_component
    ):
        """When the agent doesn't respond within timeout, return 408."""
        from fastapi import HTTPException

        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        # Create a future that never resolves
        loop = asyncio.get_event_loop()
        never_resolving_future = loop.create_future()
        mock_component.register_compaction_future = MagicMock(
            return_value=never_resolving_future
        )

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.routers.sessions.asyncio.wait_for",
            side_effect=asyncio.TimeoutError(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                compact_session,
                CompactSessionRequest,
            )

            with pytest.raises(HTTPException) as exc_info:
                await compact_session(
                    session_id="test-session-id",
                    request=CompactSessionRequest(),
                    agent_name=None,
                    db=mock_db,
                    user={"id": "user-1"},
                    session_service=mock_session_service,
                    component=mock_component,
                )

            assert exc_info.value.status_code == 408
            assert "timed out" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_does_not_leak_internal_error_details(
        self, mock_db, mock_session_service, mock_component
    ):
        """Verify the 500 response uses a generic message when agent reports failure."""
        from fastapi import HTTPException

        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        response_data = {
            "success": False,
            "error_message": "Compaction failed: secret internal error detail",
        }
        mock_component.register_compaction_future = MagicMock(
            return_value=self._make_resolved_future(response_data)
        )

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                compact_session,
                CompactSessionRequest,
            )

            with pytest.raises(HTTPException) as exc_info:
                await compact_session(
                    session_id="test-session-id",
                    request=CompactSessionRequest(),
                    agent_name=None,
                    db=mock_db,
                    user={"id": "user-1"},
                    session_service=mock_session_service,
                    component=mock_component,
                )

            assert exc_info.value.status_code == 500
            assert "secret" not in exc_info.value.detail
            assert exc_info.value.detail == "Failed to compress session"

    @pytest.mark.asyncio
    async def test_happy_path_compaction(
        self, mock_db, mock_session_service, mock_component
    ):
        """Verify the success path: publish request, receive response, return result."""
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        response_data = {
            "success": True,
            "events_compacted": 2,
            "summary": "Summary of events",
            "remaining_events": 1,
            "remaining_tokens": 500,
        }
        mock_component.register_compaction_future = MagicMock(
            return_value=self._make_resolved_future(response_data)
        )

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                compact_session,
                CompactSessionRequest,
            )

            result = await compact_session(
                session_id="test-session-id",
                request=CompactSessionRequest(),
                agent_name=None,
                db=mock_db,
                user={"id": "user-1"},
                session_service=mock_session_service,
                component=mock_component,
            )

            assert result.events_compacted == 2
            assert result.summary == "Summary of events"
            assert result.remaining_events == 1
            assert result.remaining_tokens == 500

            # Verify the SAM event was published
            mock_component.sam_events.publish_session_compact_request.assert_called_once()
            call_kwargs = mock_component.sam_events.publish_session_compact_request.call_args
            assert call_kwargs.kwargs["session_id"] == "test-session-id"
            assert call_kwargs.kwargs["user_id"] == "user-1"
            assert call_kwargs.kwargs["agent_id"] == "test-agent"

    @pytest.mark.asyncio
    async def test_returns_500_when_publish_fails(
        self, mock_db, mock_session_service, mock_component
    ):
        """When SAM event publish fails, return 500."""
        from fastapi import HTTPException

        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        mock_component.sam_events.publish_session_compact_request.return_value = False
        mock_component.register_compaction_future = MagicMock(
            return_value=self._make_resolved_future({})
        )

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                compact_session,
                CompactSessionRequest,
            )

            with pytest.raises(HTTPException) as exc_info:
                await compact_session(
                    session_id="test-session-id",
                    request=CompactSessionRequest(),
                    agent_name=None,
                    db=mock_db,
                    user={"id": "user-1"},
                    session_service=mock_session_service,
                    component=mock_component,
                )

            assert exc_info.value.status_code == 500
            assert "publish" in exc_info.value.detail.lower()


class TestCompactSessionPersistence:
    """Tests that happy-path compaction persists the synthetic TaskModel
    row and the compaction_notification chat task that the indicator relies on
    after refresh."""

    @pytest.fixture
    def mock_session_service(self):
        return MagicMock()

    @pytest.fixture
    def mock_component(self):
        comp = MagicMock()
        comp.gateway_id = "test-gateway"
        comp._compaction_futures = {}
        comp.sam_events = MagicMock()
        comp.sam_events.publish_session_compact_request = MagicMock(return_value=True)
        return comp

    def _make_resolved_future(self, result_data):
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        future.set_result(result_data)
        return future

    @pytest.mark.asyncio
    async def test_persists_synthetic_cost_task_and_notification(
        self, mock_session_service, mock_component
    ):
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        response_data = {
            "success": True,
            "events_compacted": 3,
            "summary": "Prior turns condensed.",
            "remaining_events": 1,
            "remaining_tokens": 1234,
            "compaction_prompt_tokens": 500,
            "compaction_completion_tokens": 60,
        }
        mock_component.register_compaction_future = MagicMock(
            return_value=self._make_resolved_future(response_data)
        )

        # Mock DB: query for latest TaskModel returns a row whose start_time
        # is in the past so the synthetic row uses wall-clock time instead.
        latest = MagicMock()
        latest.start_time = 1000  # far older than now()
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.first.return_value = latest
        mock_db = MagicMock()
        mock_db.query.return_value = query_mock

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                compact_session,
                CompactSessionRequest,
            )

            result = await compact_session(
                session_id="sess-1",
                request=CompactSessionRequest(),
                agent_name=None,
                db=mock_db,
                user={"id": "user-1"},
                session_service=mock_session_service,
                component=mock_component,
            )

        # Synthetic compaction-cost TaskModel was added + committed
        assert mock_db.add.call_count == 1
        added = mock_db.add.call_args.args[0]
        assert added.id.startswith("compaction-cost-")
        assert added.session_id == "sess-1"
        assert added.user_id == "user-1"
        assert added.total_input_tokens == 500
        assert added.total_output_tokens == 60
        assert added.token_usage_details == {
            "post_compaction_remaining_tokens": 1234
        }
        # Synthetic start_time must be strictly greater than the latest row
        # AND at least current wall-clock ms so the context-usage reader
        # (order_by desc(start_time)) picks it up as the most recent row.
        assert added.start_time > latest.start_time
        mock_db.commit.assert_called()

        # compaction_notification chat task was persisted
        mock_session_service.save_task.assert_called_once()
        save_kwargs = mock_session_service.save_task.call_args.kwargs
        assert save_kwargs["session_id"] == "sess-1"
        assert save_kwargs["task_id"].startswith("manual-compaction-")
        bubbles_json = save_kwargs["message_bubbles"]
        import json as _json
        bubbles = _json.loads(bubbles_json)
        assert bubbles[0]["parts"][0]["data"]["type"] == "compaction_notification"
        assert bubbles[0]["parts"][0]["data"]["summary"] == "Prior turns condensed."

        assert result.summary == "Prior turns condensed."


class TestContextUsageModelResolution:
    """Tests for model resolution in get_session_context_usage."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def mock_session_service(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_ignores_component_model_config(
        self, mock_db, mock_session_service
    ):
        """The gateway's own `model:` config must never leak into the response.

        `component` here is the WebUI gateway, not the agent, so its model bears
        no relationship to the model the agent runs.
        """
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        mock_component = MagicMock()
        mock_component.model_config = {"model": "gateway-model"}

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                get_session_context_usage,
            )

            result = await get_session_context_usage(
                session_id="test-session-id",
                model=None,
                agent_name=None,
                db=mock_db,
                user={"id": "user-1"},
                session_service=mock_session_service,
                component=mock_component,
            )

        assert result.model is None
        assert result.max_input_tokens is None

    @pytest.mark.asyncio
    async def test_explicit_model_param_wins(self, mock_db, mock_session_service):
        """An explicit ?model= query param overrides everything else."""
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        mock_component = MagicMock()
        mock_component.model_config = {"model": "gateway-model"}

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                get_session_context_usage,
            )

            result = await get_session_context_usage(
                session_id="test-session-id",
                model="explicit-model",
                agent_name=None,
                db=mock_db,
                user={"id": "user-1"},
                session_service=mock_session_service,
                component=mock_component,
            )

        assert result.model == "explicit-model"

    @pytest.mark.asyncio
    async def test_returns_null_model_when_no_completed_tasks(
        self, mock_db, mock_session_service
    ):
        """With nothing to attribute a model to, report null rather than inventing one.

        The client hides the indicator on a null limit, which beats showing a
        real denominator for a model the agent never ran.
        """
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        mock_component = MagicMock()
        mock_component.model_config = None

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                get_session_context_usage,
            )

            result = await get_session_context_usage(
                session_id="test-session-id",
                model=None,
                agent_name=None,
                db=mock_db,
                user={"id": "user-1"},
                session_service=mock_session_service,
                component=mock_component,
            )

        assert result.model is None
        assert result.max_input_tokens is None
        assert result.usage_percentage == 0.0

    @pytest.mark.asyncio
    async def test_model_from_latest_task_by_model(self, mock_session_service):
        """The model comes from the agent's latest completed task."""
        mock_session = MagicMock()
        mock_session.agent_id = None
        mock_session_service.get_session_details.return_value = mock_session

        task = _make_task(
            "task-1",
            input_tokens=1000,
            details={
                "by_model": {
                    "openai/gpt-4o": {"input_tokens": 1000, "max_input_tokens": 128_000}
                }
            },
        )
        db = _make_mock_db_with_agents(tasks=[task], events=[])

        result = await _call_context_usage(db, mock_session_service)

        assert result.model == "openai/gpt-4o"
        # Resolved via the agent-stamped max_input_tokens, not the LiteLLM registry.
        assert result.max_input_tokens == 128_000

    @pytest.mark.asyncio
    async def test_dominant_model_wins_when_multiple(self, mock_session_service):
        """When a task used several models, the one with most input tokens wins."""
        mock_session = MagicMock()
        mock_session.agent_id = None
        mock_session_service.get_session_details.return_value = mock_session

        task = _make_task(
            "task-1",
            input_tokens=1000,
            details={
                "by_model": {
                    "minor-model": {"input_tokens": 100},
                    "dominant-model": {"input_tokens": 900, "max_input_tokens": 64_000},
                }
            },
        )
        db = _make_mock_db_with_agents(tasks=[task], events=[])

        result = await _call_context_usage(db, mock_session_service)

        assert result.model == "dominant-model"

    @pytest.mark.asyncio
    async def test_null_model_when_by_model_empty(self, mock_session_service, caplog):
        """A provider that omits usage metadata leaves by_model empty.

        The token totals still come through; only the model is unknown. This is
        the case the issue reports as failing silently, so it must also warn.
        """
        mock_session = MagicMock()
        mock_session.agent_id = None
        mock_session_service.get_session_details.return_value = mock_session

        task = _make_task("task-1", input_tokens=5000, output_tokens=700, details={})
        db = _make_mock_db_with_agents(tasks=[task], events=[])

        with caplog.at_level(
            logging.WARNING,
            logger="solace_agent_mesh.gateway.http_sse.routers.sessions",
        ):
            result = await _call_context_usage(db, mock_session_service)

        assert result.model is None
        assert result.max_input_tokens is None
        assert result.usage_percentage == 0.0
        # Token math must survive an unresolvable model.
        assert result.prompt_tokens == 5000
        assert result.completion_tokens == 700
        assert "no model could be attributed" in caplog.text

    @pytest.mark.asyncio
    async def test_by_model_ignores_non_dict_entries(self, mock_session_service):
        """Malformed by_model entries are skipped rather than crashing."""
        mock_session = MagicMock()
        mock_session.agent_id = None
        mock_session_service.get_session_details.return_value = mock_session

        task = _make_task(
            "task-1",
            input_tokens=1000,
            details={
                "by_model": {
                    "good-model": {"input_tokens": 10, "max_input_tokens": 50_000},
                    "bad-model": "oops",
                }
            },
        )
        db = _make_mock_db_with_agents(tasks=[task], events=[])

        result = await _call_context_usage(db, mock_session_service)

        assert result.model == "good-model"


class TestContextUsageAgentScoping:
    """Tests for scoping context usage to the caller-supplied agent_name."""

    @pytest.fixture
    def mock_session_service(self):
        service = MagicMock()
        session = MagicMock()
        session.agent_id = None
        service.get_session_details.return_value = session
        return service

    @staticmethod
    def _two_agent_db(chat_task_count=0):
        """Newest-first: agent-a ran most recently, agent-b before it."""
        task_a = _make_task(
            "task-a",
            input_tokens=5000,
            details={
                "by_model": {
                    "openai/gpt-4o": {"input_tokens": 5000, "max_input_tokens": 128_000}
                }
            },
        )
        task_b = _make_task(
            "task-b",
            input_tokens=300,
            details={
                "by_model": {
                    "anthropic/claude-x": {
                        "input_tokens": 300,
                        "max_input_tokens": 100_000,
                    }
                }
            },
        )
        events = [
            _make_request_event("task-a", "agent-a"),
            _make_request_event("task-b", "agent-b"),
        ]
        return _make_mock_db_with_agents(
            tasks=[task_a, task_b], events=events, chat_task_count=chat_task_count
        )

    @pytest.mark.asyncio
    async def test_agent_name_scopes_model_and_tokens(self, mock_session_service):
        """agent_name selects the agent, and model and tokens agree with each other.

        Reporting agent A's tokens beside agent B's model would be worse than
        either being wrong on its own.
        """
        db = self._two_agent_db()

        result = await _call_context_usage(
            db, mock_session_service, agent_name="agent-b"
        )

        assert result.model == "anthropic/claude-x"
        assert result.max_input_tokens == 100_000
        assert result.prompt_tokens == 300
        assert result.current_context_tokens == 300

    @pytest.mark.asyncio
    async def test_agent_name_with_no_matching_tasks_returns_empty(
        self, mock_session_service
    ):
        """A newly-selected agent has no context in this session yet."""
        task_a = _make_task(
            "task-a",
            input_tokens=5000,
            details={"by_model": {"openai/gpt-4o": {"input_tokens": 5000}}},
        )
        db = _make_mock_db_with_agents(
            tasks=[task_a], events=[_make_request_event("task-a", "agent-a")]
        )

        result = await _call_context_usage(
            db, mock_session_service, agent_name="agent-b"
        )

        assert result.model is None
        assert result.max_input_tokens is None
        assert result.current_context_tokens == 0
        assert result.prompt_tokens == 0

    @pytest.mark.asyncio
    async def test_compaction_cost_row_alone_does_not_leak_into_other_agent(
        self, mock_session_service
    ):
        """Compaction-cost rows survive agent filtering but are not an agent's context.

        Regression test: a session compacted under agent A must not report A's
        post-compaction remaining tokens as newly-selected agent B's context.
        """
        compaction_row = _make_task(
            "compaction-cost-1",
            input_tokens=1000,
            details={"post_compaction_remaining_tokens": 42_000},
        )
        task_a = _make_task(
            "task-a",
            input_tokens=5000,
            details={"by_model": {"openai/gpt-4o": {"input_tokens": 5000}}},
        )
        db = _make_mock_db_with_agents(
            tasks=[compaction_row, task_a],
            events=[_make_request_event("task-a", "agent-a")],
        )

        result = await _call_context_usage(
            db, mock_session_service, agent_name="agent-b"
        )

        assert result.current_context_tokens == 0
        assert result.model is None

    @pytest.mark.asyncio
    async def test_omitting_agent_name_falls_back_to_latest_task_agent(
        self, mock_session_service
    ):
        """Callers that don't send agent_name keep the previous behaviour."""
        db = self._two_agent_db()

        result = await _call_context_usage(db, mock_session_service, agent_name=None)

        assert result.model == "openai/gpt-4o"
        assert result.prompt_tokens == 5000

    @pytest.mark.asyncio
    async def test_totals_remain_session_wide(self, mock_session_service):
        """totalTasks/totalMessages stay session-wide, deliberately.

        The client polls after each response until totalTasks increases; making
        these agent-scoped would stall that loop on an agent's first message.
        """
        db = self._two_agent_db(chat_task_count=4)

        result = await _call_context_usage(
            db, mock_session_service, agent_name="agent-unknown"
        )

        assert result.total_tasks == 4
        assert result.total_messages == 8


class TestCreateSessionServiceFromConfig:
    """Tests for create_session_service_from_config in services.py."""

    def test_memory_type_returns_in_memory_service(self):
        from solace_agent_mesh.agent.adk.services import create_session_service_from_config
        from google.adk.sessions import InMemorySessionService

        svc = create_session_service_from_config({"type": "memory"})
        assert isinstance(svc, InMemorySessionService)

    def test_defaults_to_memory_when_no_type(self):
        from solace_agent_mesh.agent.adk.services import create_session_service_from_config
        from google.adk.sessions import InMemorySessionService

        svc = create_session_service_from_config({})
        assert isinstance(svc, InMemorySessionService)

    def test_sql_type_raises_without_database_url(self):
        from solace_agent_mesh.agent.adk.services import create_session_service_from_config

        with pytest.raises(ValueError, match="database_url"):
            create_session_service_from_config({"type": "sql"})

    def test_unsupported_type_raises(self):
        from solace_agent_mesh.agent.adk.services import create_session_service_from_config

        with pytest.raises(ValueError, match="Unsupported"):
            create_session_service_from_config({"type": "unknown_backend"})

    def test_none_config_defaults_to_memory(self):
        from solace_agent_mesh.agent.adk.services import create_session_service_from_config
        from google.adk.sessions import InMemorySessionService

        svc = create_session_service_from_config(None)
        assert isinstance(svc, InMemorySessionService)
