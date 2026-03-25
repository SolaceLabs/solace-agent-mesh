"""Unit tests for context usage and manual compaction endpoints."""

import asyncio
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
                DEFAULT_CONTEXT_LIMIT,
            )

            with patch(
                "solace_agent_mesh.gateway.http_sse.routers.sessions._get_model_context_limit.__module__",
            ):
                pass

            mock_info = {"max_input_tokens": 128_000}
            with patch("litellm.get_model_info", return_value=mock_info):
                result = _get_model_context_limit("gpt-4")
                assert result == 128_000

    def test_returns_default_on_exception(self):
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _get_model_context_limit,
                DEFAULT_CONTEXT_LIMIT,
            )

            with patch("litellm.get_model_info", side_effect=Exception("unknown model")):
                result = _get_model_context_limit("unknown-model")
                assert result == DEFAULT_CONTEXT_LIMIT


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
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        # Set up mock DB to return completed tasks with token data
        latest_task = MagicMock()
        latest_task.total_input_tokens = 5000
        latest_task.total_output_tokens = 800
        latest_task.total_cached_input_tokens = 200

        older_task = MagicMock()
        older_task.total_input_tokens = 3000
        older_task.total_output_tokens = 500
        older_task.total_cached_input_tokens = 100

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
            assert exc_info.value.detail == "Failed to compact session"

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


class TestContextUsageModelResolution:
    """Tests for model resolution in get_session_context_usage."""

    @pytest.fixture
    def mock_db(self):
        return _make_mock_db()

    @pytest.fixture
    def mock_session_service(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_uses_component_model_config_as_default(
        self, mock_db, mock_session_service
    ):
        """When no model param given, should use component.model_config['model']."""
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        mock_component = MagicMock()
        mock_component.model_config = {"model": "my-custom-model"}

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

        assert result.model == "my-custom-model"

    @pytest.mark.asyncio
    async def test_explicit_model_param_overrides_component_config(
        self, mock_db, mock_session_service
    ):
        """Explicit model query param should take priority over component.model_config."""
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        mock_component = MagicMock()
        mock_component.model_config = {"model": "component-model"}

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
    async def test_falls_back_to_default_model_when_no_config(
        self, mock_db, mock_session_service
    ):
        """Falls back to DEFAULT_MODEL when component has no model_config."""
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        mock_component = MagicMock()
        mock_component.model_config = None  # No model configured

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                get_session_context_usage,
                DEFAULT_MODEL,
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

        assert result.model == DEFAULT_MODEL


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
