"""Unit tests for source query parameter validation in GET /sessions endpoint."""

import pytest
from unittest.mock import MagicMock

from solace_agent_mesh.shared.api.pagination import Meta, PaginationMeta


class TestGetAllSessionsSourceFilter:
    """Tests for source parameter validation in get_all_sessions."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_session_service(self):
        """Create a mock SessionService that returns a valid paginated response."""
        service = MagicMock()
        paginated = MagicMock()
        paginated.data = []
        paginated.meta = Meta(
            pagination=PaginationMeta(
                page_number=1, count=0, page_size=20, next_page=None, total_pages=0
            )
        )
        service.get_user_sessions.return_value = paginated
        return service

    @pytest.fixture
    def mock_user(self):
        """Create a mock user dict."""
        return {"id": "test-user-id"}

    @pytest.mark.asyncio
    async def test_invalid_source_returns_400(
        self, mock_db, mock_session_service, mock_user
    ):
        """Test that an invalid source value raises HTTP 400."""
        from fastapi import HTTPException

        from solace_agent_mesh.gateway.http_sse.routers.sessions import (
            get_all_sessions,
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_all_sessions(
                project_id=None,
                source="bogus",
                page_number=1,
                page_size=20,
                db=mock_db,
                user=mock_user,
                session_service=mock_session_service,
                user_config={},
                config_resolver=MagicMock(),
            )

        assert exc_info.value.status_code == 400
        assert "Invalid source filter" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_source_chat_passes_validation(
        self, mock_db, mock_session_service, mock_user
    ):
        """Test that source='chat' does not raise a 400 error."""
        from solace_agent_mesh.gateway.http_sse.routers.sessions import (
            get_all_sessions,
        )

        result = await get_all_sessions(
            project_id=None,
            source="chat",
            page_number=1,
            page_size=20,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service,
            user_config={},
            config_resolver=MagicMock(),
        )

        assert result is not None
        mock_session_service.get_user_sessions.assert_called_once()

    @pytest.mark.asyncio
    async def test_valid_source_scheduler_passes_validation(
        self, mock_db, mock_session_service, mock_user
    ):
        """Test that source='scheduler' does not raise a 400 error."""
        from solace_agent_mesh.gateway.http_sse.routers.sessions import (
            get_all_sessions,
        )

        mock_config_resolver = MagicMock()
        mock_config_resolver.validate_operation_config.return_value = {"valid": True}

        result = await get_all_sessions(
            project_id=None,
            source="scheduler",
            page_number=1,
            page_size=20,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service,
            user_config={},
            config_resolver=mock_config_resolver,
        )

        assert result is not None
        mock_session_service.get_user_sessions.assert_called_once()

    @pytest.mark.asyncio
    async def test_source_none_passes_validation(
        self, mock_db, mock_session_service, mock_user
    ):
        """Test that source=None (omitted) does not raise a 400 error."""
        from solace_agent_mesh.gateway.http_sse.routers.sessions import (
            get_all_sessions,
        )

        result = await get_all_sessions(
            project_id=None,
            source=None,
            page_number=1,
            page_size=20,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service,
            user_config={},
            config_resolver=MagicMock(),
        )

        assert result is not None
        mock_session_service.get_user_sessions.assert_called_once()


class TestSessionsAgentFilter:
    """The embedded surface scopes sessions to one agent via the `agent_id` query param.

    These verify the param threads from the router into the service (the repo-level
    filter is covered in test_session_repository.py). The FE sends snake_case
    `agent_id`; these lock the router->service forwarding so that contract can't drift
    silently.
    """

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        return {"id": "test-user-id"}

    @pytest.fixture
    def mock_session_service(self):
        service = MagicMock()
        paginated = MagicMock()
        paginated.data = []
        paginated.meta = Meta(
            pagination=PaginationMeta(
                page_number=1, count=0, page_size=20, next_page=None, total_pages=0
            )
        )
        service.get_user_sessions.return_value = paginated
        service.search_sessions.return_value = paginated
        return service

    @pytest.mark.asyncio
    async def test_get_all_sessions_forwards_agent_id(
        self, mock_db, mock_session_service, mock_user
    ):
        from solace_agent_mesh.gateway.http_sse.routers.sessions import get_all_sessions

        await get_all_sessions(
            project_id=None,
            source=None,
            agent_id="WeatherAgent",
            page_number=1,
            page_size=20,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service,
            user_config={},
            config_resolver=MagicMock(),
        )

        mock_session_service.get_user_sessions.assert_called_once()
        assert mock_session_service.get_user_sessions.call_args.kwargs["agent_id"] == "WeatherAgent"

    @pytest.mark.asyncio
    async def test_get_all_sessions_agent_id_none_forwarded(
        self, mock_db, mock_session_service, mock_user
    ):
        from solace_agent_mesh.gateway.http_sse.routers.sessions import get_all_sessions

        await get_all_sessions(
            project_id=None,
            source=None,
            agent_id=None,
            page_number=1,
            page_size=20,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service,
            user_config={},
            config_resolver=MagicMock(),
        )

        assert mock_session_service.get_user_sessions.call_args.kwargs["agent_id"] is None

    @pytest.mark.asyncio
    async def test_search_sessions_forwards_agent_id(
        self, mock_db, mock_session_service, mock_user
    ):
        from solace_agent_mesh.gateway.http_sse.routers.sessions import search_sessions

        await search_sessions(
            query="report",
            project_id=None,
            agent_id="WeatherAgent",
            page_number=1,
            page_size=20,
            db=mock_db,
            user=mock_user,
            session_service=mock_session_service,
        )

        mock_session_service.search_sessions.assert_called_once()
        assert mock_session_service.search_sessions.call_args.kwargs["agent_id"] == "WeatherAgent"
