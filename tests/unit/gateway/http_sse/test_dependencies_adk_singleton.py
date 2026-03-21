"""Tests for get_adk_session_service async singleton initialization."""

import asyncio

import pytest
from unittest.mock import MagicMock, patch, call


class TestGetAdkSessionServiceSingleton:
    """Verify that concurrent calls only initialize the service once."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_initialize_once(self):
        """Multiple concurrent calls should produce exactly one initialization."""
        import solace_agent_mesh.gateway.http_sse.dependencies as deps

        # Reset singleton state
        deps._adk_session_service = None
        deps._adk_session_service_lock = asyncio.Lock()

        mock_service = MagicMock()
        mock_component = MagicMock()
        init_call_count = 0

        def mock_initialize(component):
            nonlocal init_call_count
            init_call_count += 1
            return mock_service

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.initialize_session_service",
            side_effect=mock_initialize,
        ) if False else patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=mock_component,
        ):
            with patch(
                "solace_agent_mesh.gateway.http_sse.dependencies.initialize_session_service",
                side_effect=mock_initialize,
            ):
                # Launch many concurrent calls
                results = await asyncio.gather(
                    *[deps.get_adk_session_service(mock_component) for _ in range(20)]
                )

        # All calls should return the same instance
        assert all(r is mock_service for r in results)
        # Initialization should have happened exactly once
        assert init_call_count == 1

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
        deps._adk_session_service = None
