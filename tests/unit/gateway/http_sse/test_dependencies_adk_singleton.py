"""Tests for get_adk_session_service async singleton initialization."""

import asyncio

import pytest
from unittest.mock import MagicMock, patch


class TestGetAdkSessionServiceSingleton:
    """Verify that concurrent calls only initialize the service once."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_initialize_once(self):
        """Multiple concurrent calls should produce exactly one initialization."""
        import solace_agent_mesh.gateway.http_sse.dependencies as deps

        # Reset singleton to the proper sentinel so the lazy-init path triggers
        deps._adk_session_service = deps._ADK_SESSION_SERVICE_UNSET
        deps._adk_session_service_lock = asyncio.Lock()

        mock_service = MagicMock()
        mock_component = MagicMock()
        # component.get_config("adk_session_service") must return a truthy config
        mock_component.get_config.return_value = {"type": "sql", "database_url": "sqlite:///:memory:"}
        init_call_count = 0

        def mock_create(config, log_identifier="", run_db_migrations=False):
            nonlocal init_call_count
            init_call_count += 1
            return mock_service

        with patch(
            "solace_agent_mesh.agent.adk.services.create_session_service_from_config",
            side_effect=mock_create,
        ):
            # Launch many concurrent calls
            results = await asyncio.gather(
                *[deps.get_adk_session_service(mock_component) for _ in range(20)]
            )

        # All calls should return the same instance
        assert all(r is mock_service for r in results)
        # Initialization should have happened exactly once
        assert init_call_count == 1

        # Clean up
        deps._adk_session_service = deps._ADK_SESSION_SERVICE_UNSET

    @pytest.mark.asyncio
    async def test_returns_cached_service_on_subsequent_calls(self):
        """After initialization, subsequent calls return the cached service without locking."""
        import solace_agent_mesh.gateway.http_sse.dependencies as deps

        mock_service = MagicMock()
        deps._adk_session_service = mock_service

        mock_component = MagicMock()

        result = await deps.get_adk_session_service(mock_component)
        assert result is mock_service

        # Clean up
        deps._adk_session_service = deps._ADK_SESSION_SERVICE_UNSET

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self):
        """When initialization fails, the sentinel stays so the next call retries after cooldown."""
        import solace_agent_mesh.gateway.http_sse.dependencies as deps

        deps._adk_session_service = deps._ADK_SESSION_SERVICE_UNSET
        deps._adk_session_service_lock = asyncio.Lock()
        deps._adk_init_last_failure = 0.0

        mock_component = MagicMock()
        mock_component.get_config.return_value = {"type": "sql", "database_url": "sqlite:///:memory:"}

        mock_service = MagicMock()
        call_count = 0

        def mock_create(config, log_identifier="", run_db_migrations=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("DB temporarily unavailable")
            return mock_service

        with patch(
            "solace_agent_mesh.agent.adk.services.create_session_service_from_config",
            side_effect=mock_create,
        ):
            # First call fails — should return None but not cache it
            result1 = await deps.get_adk_session_service(mock_component)
            assert result1 is None

            # Reset cooldown so the second call retries immediately
            deps._adk_init_last_failure = 0.0

            # Second call should retry and succeed
            result2 = await deps.get_adk_session_service(mock_component)
            assert result2 is mock_service

        assert call_count == 2

        # Clean up
        deps._adk_session_service = deps._ADK_SESSION_SERVICE_UNSET
        deps._adk_init_last_failure = 0.0
