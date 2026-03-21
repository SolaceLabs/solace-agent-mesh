"""Unit tests for context usage and manual compaction endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestLoadAdkSession:
    """Tests for the _load_adk_session helper."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_session_service(self):
        return MagicMock()

    @pytest.fixture
    def mock_adk_session_service(self):
        svc = MagicMock()
        svc.get_session = AsyncMock()
        return svc

    @pytest.mark.asyncio
    async def test_returns_404_when_session_not_found(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        from fastapi import HTTPException

        mock_session_service.get_session_details.return_value = None

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _load_adk_session,
            )

            with pytest.raises(HTTPException) as exc_info:
                await _load_adk_session(
                    session_id="test-session-id",
                    user_id="user-1",
                    agent_name=None,
                    session_service=mock_session_service,
                    adk_session_service=mock_adk_session_service,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_returns_400_when_no_agent(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        from fastapi import HTTPException

        mock_session = MagicMock()
        mock_session.agent_id = None
        mock_session_service.get_session_details.return_value = mock_session

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _load_adk_session,
            )

            with pytest.raises(HTTPException) as exc_info:
                await _load_adk_session(
                    session_id="test-session-id",
                    user_id="user-1",
                    agent_name=None,
                    session_service=mock_session_service,
                    adk_session_service=mock_adk_session_service,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 400
            assert "agent" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_uses_agent_name_param_over_gateway_agent_id(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        mock_session = MagicMock()
        mock_session.agent_id = "gateway-agent"
        mock_session_service.get_session_details.return_value = mock_session
        mock_adk_session_service.get_session.return_value = MagicMock(user_id="user-1")

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _load_adk_session,
            )

            _, app_name, _ = await _load_adk_session(
                session_id="test-session-id",
                user_id="user-1",
                agent_name="override-agent",
                session_service=mock_session_service,
                adk_session_service=mock_adk_session_service,
                db=mock_db,
            )

            assert app_name == "override-agent"
            mock_adk_session_service.get_session.assert_called_once_with(
                app_name="override-agent",
                user_id="user-1",
                session_id="test-session-id",
            )

    @pytest.mark.asyncio
    async def test_returns_404_when_adk_session_user_id_mismatch(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        """IDOR guard: reject when ADK session belongs to a different user."""
        from fastapi import HTTPException

        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session
        # ADK returns a session owned by a different user
        mock_adk_session_service.get_session.return_value = MagicMock(user_id="other-user")

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _load_adk_session,
            )

            with pytest.raises(HTTPException) as exc_info:
                await _load_adk_session(
                    session_id="test-session-id",
                    user_id="user-1",
                    agent_name="test-agent",
                    session_service=mock_session_service,
                    adk_session_service=mock_adk_session_service,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_falls_back_to_gateway_agent_id(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        mock_session = MagicMock()
        mock_session.agent_id = "gateway-agent"
        mock_session_service.get_session_details.return_value = mock_session
        mock_adk_session_service.get_session.return_value = MagicMock(user_id="user-1")

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _load_adk_session,
            )

            _, app_name, _ = await _load_adk_session(
                session_id="test-session-id",
                user_id="user-1",
                agent_name=None,
                session_service=mock_session_service,
                adk_session_service=mock_adk_session_service,
                db=mock_db,
            )

            assert app_name == "gateway-agent"


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


class TestGetSessionContextUsage:
    """Tests for the get_session_context_usage endpoint."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_session_service(self):
        return MagicMock()

    @pytest.fixture
    def mock_adk_session_service(self):
        svc = MagicMock()
        svc.get_session = AsyncMock()
        return svc

    @pytest.mark.asyncio
    async def test_returns_zeros_for_empty_session(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session
        mock_adk_session_service.get_session.return_value = None

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
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
                adk_session_service=mock_adk_session_service,
            )

            assert result.current_context_tokens == 0
            assert result.prompt_tokens == 0
            assert result.completion_tokens == 0
            assert result.total_events == 0
            assert result.has_compaction is False

    @pytest.mark.asyncio
    async def test_returns_404_when_session_not_found(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        from fastapi import HTTPException

        mock_session_service.get_session_details.return_value = None

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
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
                    adk_session_service=mock_adk_session_service,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_when_no_agent(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        from fastapi import HTTPException

        mock_session = MagicMock()
        mock_session.agent_id = None
        mock_session_service.get_session_details.return_value = mock_session

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
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
                    adk_session_service=mock_adk_session_service,
                )

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_calculates_tokens_with_events(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        # Create mock events with content
        user_event = MagicMock()
        user_event.actions = None
        user_event.content = MagicMock()
        user_event.content.role = "user"

        model_event = MagicMock()
        model_event.actions = None
        model_event.content = MagicMock()
        model_event.content.role = "model"

        adk_session = MagicMock()
        adk_session.events = [user_event, model_event]
        adk_session.user_id = "user-1"
        mock_adk_session_service.get_session.return_value = adk_session

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ), patch(
            "solace_agent_mesh.gateway.http_sse.routers.sessions._get_adk_imports",
            return_value=(lambda content, model: 100, None, None),
        ), patch(
            "solace_agent_mesh.gateway.http_sse.routers.sessions._get_model_context_limit",
            return_value=200_000,
        ), patch(
            "solace_agent_mesh.agent.adk.services._filter_session_by_latest_compaction",
            side_effect=lambda session, **kwargs: session,
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
                adk_session_service=mock_adk_session_service,
            )

            assert result.prompt_tokens == 100
            assert result.completion_tokens == 100
            assert result.current_context_tokens == 200
            assert result.total_events == 2


    @pytest.mark.asyncio
    async def test_compaction_events_excluded_from_token_counts(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        """Compaction events set has_compaction=True but are excluded from token counts."""
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        # Regular user event
        user_event = MagicMock()
        user_event.actions = None
        user_event.content = MagicMock()
        user_event.content.role = "user"

        # Compaction event (should not be counted)
        compaction_event = MagicMock()
        compaction_event.actions = MagicMock()
        compaction_event.actions.compaction = MagicMock()  # truthy
        compaction_event.content = MagicMock()
        compaction_event.content.role = "model"

        # Regular model event
        model_event = MagicMock()
        model_event.actions = None
        model_event.content = MagicMock()
        model_event.content.role = "model"

        adk_session = MagicMock()
        adk_session.events = [user_event, compaction_event, model_event]
        adk_session.user_id = "user-1"
        mock_adk_session_service.get_session.return_value = adk_session

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ), patch(
            "solace_agent_mesh.gateway.http_sse.routers.sessions._get_adk_imports",
            return_value=(lambda content, model: 100, None, None),
        ), patch(
            "solace_agent_mesh.gateway.http_sse.routers.sessions._get_model_context_limit",
            return_value=200_000,
        ), patch(
            "solace_agent_mesh.agent.adk.services._filter_session_by_latest_compaction",
            side_effect=lambda session, **kwargs: session,
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
                adk_session_service=mock_adk_session_service,
            )

            assert result.has_compaction is True
            # Only user_event (100) + model_event (100); compaction_event excluded
            assert result.prompt_tokens == 100
            assert result.completion_tokens == 100
            assert result.current_context_tokens == 200
            assert result.total_events == 3

    @pytest.mark.asyncio
    async def test_returns_zeros_when_adk_session_service_is_none(
        self, mock_db, mock_session_service
    ):
        """When ADK is not configured (adk_session_service=None), return zero tokens."""
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
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
                adk_session_service=None,
            )

            assert result.current_context_tokens == 0
            assert result.prompt_tokens == 0
            assert result.completion_tokens == 0
            assert result.total_events == 0
            assert result.has_compaction is False


class TestCompactSession:
    """Tests for the compact_session endpoint."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_session_service(self):
        return MagicMock()

    @pytest.fixture
    def mock_adk_session_service(self):
        svc = MagicMock()
        svc.get_session = AsyncMock()
        return svc

    @pytest.mark.asyncio
    async def test_returns_404_when_session_not_found(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        from fastapi import HTTPException

        mock_session_service.get_session_details.return_value = None

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
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
                    adk_session_service=mock_adk_session_service,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_when_empty_session(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        from fastapi import HTTPException

        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session
        mock_adk_session_service.get_session.return_value = None

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
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
                    adk_session_service=mock_adk_session_service,
                )

            assert exc_info.value.status_code == 400
            assert "no conversation history" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_returns_400_when_no_agent(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        from fastapi import HTTPException

        mock_session = MagicMock()
        mock_session.agent_id = None
        mock_session_service.get_session_details.return_value = mock_session

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
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
                    adk_session_service=mock_adk_session_service,
                )

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_when_zero_events_compacted(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        from fastapi import HTTPException

        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        adk_session = MagicMock()
        adk_session.events = [MagicMock()]
        adk_session.user_id = "user-1"
        mock_adk_session_service.get_session.return_value = adk_session

        mock_create_compaction = AsyncMock(return_value=(0, ""))
        mock_component = MagicMock()
        mock_component.get_config.return_value = {"model_config": {"model": "test-model"}}

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.routers.sessions._get_adk_imports",
            return_value=(None, None, mock_create_compaction),
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
                    adk_session_service=mock_adk_session_service,
                    component=mock_component,
                )

            assert exc_info.value.status_code == 400
            assert "not enough" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_does_not_leak_internal_error_details(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        """Verify the 500 response uses a generic message, not the raw exception."""
        from fastapi import HTTPException

        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        adk_session = MagicMock()
        adk_session.events = [MagicMock()]
        adk_session.user_id = "user-1"
        mock_adk_session_service.get_session.return_value = adk_session

        mock_create_compaction = AsyncMock(
            side_effect=RuntimeError("secret internal error detail")
        )

        mock_component = MagicMock()
        mock_component.get_config.return_value = {"model_config": {"model": "test-model"}}

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.routers.sessions._get_adk_imports",
            return_value=(None, None, mock_create_compaction),
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
                    adk_session_service=mock_adk_session_service,
                    component=mock_component,
                )

            assert exc_info.value.status_code == 500
            assert "secret" not in exc_info.value.detail
            assert exc_info.value.detail == "Failed to compact session"

    @pytest.mark.asyncio
    async def test_happy_path_compaction(
        self, mock_db, mock_session_service, mock_adk_session_service
    ):
        """Verify the success path: compaction, reload, filtering, response."""
        mock_session = MagicMock()
        mock_session.agent_id = "test-agent"
        mock_session_service.get_session_details.return_value = mock_session

        adk_session = MagicMock()
        adk_session.events = [MagicMock(), MagicMock(), MagicMock()]
        adk_session.user_id = "user-1"
        mock_adk_session_service.get_session.return_value = adk_session

        mock_create_compaction = AsyncMock(return_value=(2, "Summary of events"))

        # Reloaded session after compaction (1 compaction event + 1 remaining)
        reloaded_event = MagicMock()
        reloaded_event.actions = None
        reloaded_session = MagicMock()
        reloaded_session.events = [reloaded_event]
        reloaded_session.user_id = "user-1"

        # get_session returns adk_session first (for load), then reloaded_session (after compact)
        mock_adk_session_service.get_session = AsyncMock(
            side_effect=[adk_session, reloaded_session]
        )

        mock_component = MagicMock()
        mock_component.get_config.return_value = {"model_config": {"model": "test-model"}}

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.routers.sessions._get_adk_imports",
            return_value=(None, lambda events, model: 500, mock_create_compaction),
        ), patch(
            "solace_agent_mesh.agent.adk.services._filter_session_by_latest_compaction",
            side_effect=lambda session, **kwargs: session,
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
                adk_session_service=mock_adk_session_service,
                component=mock_component,
            )

            assert result.events_compacted == 2
            assert result.summary == "Summary of events"
            assert result.remaining_events == 1
            assert result.remaining_tokens == 500
