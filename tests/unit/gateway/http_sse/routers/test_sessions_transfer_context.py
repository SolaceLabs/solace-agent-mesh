"""Unit tests for POST /sessions/{session_id}/transfer-context endpoint and helpers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestResolveAgentDisplayName:
    """Tests for _resolve_agent_display_name helper."""

    def _make_registry(self, agent_card=None):
        registry = MagicMock()
        registry.get_agent.return_value = agent_card
        return registry

    def _make_card_with_display_name(self, display_name):
        ext = MagicMock()
        ext.uri = "https://solace.com/a2a/extensions/display-name"
        ext.params = {"display_name": display_name}
        card = MagicMock()
        card.capabilities.extensions = [ext]
        return card

    def test_returns_display_name_from_extension(self):
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _resolve_agent_display_name,
            )

        card = self._make_card_with_display_name("My Agent")
        registry = self._make_registry(card)
        assert _resolve_agent_display_name(registry, "my-agent") == "My Agent"

    def test_falls_back_to_agent_name_when_no_extension(self):
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _resolve_agent_display_name,
            )

        card = MagicMock()
        card.capabilities.extensions = []
        registry = self._make_registry(card)
        assert _resolve_agent_display_name(registry, "my-agent") == "my-agent"

    def test_falls_back_when_agent_not_found(self):
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _resolve_agent_display_name,
            )

        registry = self._make_registry(None)
        assert _resolve_agent_display_name(registry, "missing-agent") == "missing-agent"

    def test_handles_no_capabilities(self):
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                _resolve_agent_display_name,
            )

        card = MagicMock()
        card.capabilities = None
        registry = self._make_registry(card)
        assert _resolve_agent_display_name(registry, "my-agent") == "my-agent"


def _mock_session_service_with_ownership(owns_session=True):
    """Create a mock session service that simulates ownership check."""
    service = MagicMock()
    service.get_session_details.return_value = MagicMock() if owns_session else None
    return service


class TestTransferContextEndpoint:
    """Tests for POST /sessions/{session_id}/transfer-context."""

    @pytest.fixture
    def mock_agent_registry(self):
        registry = MagicMock()
        registry.__contains__ = MagicMock(return_value=True)
        registry.get_agent.return_value = MagicMock(capabilities=None)
        return registry

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_session_service(self):
        return _mock_session_service_with_ownership(owns_session=True)

    @pytest.mark.asyncio
    async def test_same_source_and_target_returns_early(self, mock_agent_registry, mock_db, mock_session_service):
        from fastapi import HTTPException

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                transfer_context,
                TransferContextRequest,
            )

        request_body = TransferContextRequest(
            source_agent_name="agent-a",
            target_agent_name="agent-a",
        )

        result = await transfer_context(
            session_id="sess-1",
            request_body=request_body,
            user={"id": "user1"},
            db=mock_db,
            session_service=mock_session_service,
            adk_session_service=MagicMock(),
            agent_registry=mock_agent_registry,
        )

        assert result.context_transferred is False
        assert "same" in result.message.lower()

    @pytest.mark.asyncio
    async def test_unregistered_source_agent_returns_422(self, mock_agent_registry, mock_db, mock_session_service):
        from fastapi import HTTPException

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                transfer_context,
                TransferContextRequest,
            )

        # Source not in registry, target is
        mock_agent_registry.__contains__ = MagicMock(
            side_effect=lambda name: name != "bad-agent"
        )

        request_body = TransferContextRequest(
            source_agent_name="bad-agent",
            target_agent_name="agent-b",
        )

        with pytest.raises(HTTPException) as exc_info:
            await transfer_context(
                session_id="sess-1",
                request_body=request_body,
                user={"id": "user1"},
                db=mock_db,
                session_service=mock_session_service,
                adk_session_service=MagicMock(),
                agent_registry=mock_agent_registry,
            )

        assert exc_info.value.status_code == 422
        assert "not registered" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_unregistered_target_agent_returns_422(self, mock_agent_registry, mock_db, mock_session_service):
        from fastapi import HTTPException

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                transfer_context,
                TransferContextRequest,
            )

        # Source is in registry, target is not
        mock_agent_registry.__contains__ = MagicMock(
            side_effect=lambda name: name != "bad-target"
        )

        request_body = TransferContextRequest(
            source_agent_name="agent-a",
            target_agent_name="bad-target",
        )

        with pytest.raises(HTTPException) as exc_info:
            await transfer_context(
                session_id="sess-1",
                request_body=request_body,
                user={"id": "user1"},
                db=mock_db,
                session_service=mock_session_service,
                adk_session_service=MagicMock(),
                agent_registry=mock_agent_registry,
            )

        assert exc_info.value.status_code == 422
        assert "not registered" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_missing_adk_service_returns_unavailable(self, mock_agent_registry, mock_db, mock_session_service):
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                transfer_context,
                TransferContextRequest,
            )

        request_body = TransferContextRequest(
            source_agent_name="agent-a",
            target_agent_name="agent-b",
        )

        result = await transfer_context(
            session_id="sess-1",
            request_body=request_body,
            user={"id": "user1"},
            db=mock_db,
            session_service=mock_session_service,
            adk_session_service=None,
            agent_registry=mock_agent_registry,
        )

        assert result.context_transferred is False
        assert "unavailable" in result.message.lower()

    @pytest.mark.asyncio
    async def test_invalid_session_id_returns_400(self, mock_agent_registry, mock_db, mock_session_service):
        from fastapi import HTTPException

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                transfer_context,
                TransferContextRequest,
            )

        request_body = TransferContextRequest(
            source_agent_name="agent-a",
            target_agent_name="agent-b",
        )

        for bad_id in ["", "null", "undefined", "   "]:
            with pytest.raises(HTTPException) as exc_info:
                await transfer_context(
                    session_id=bad_id,
                    request_body=request_body,
                    user={"id": "user1"},
                    db=mock_db,
                    session_service=mock_session_service,
                    adk_session_service=MagicMock(),
                    agent_registry=mock_agent_registry,
                )

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_transfer_success_returns_true(self, mock_agent_registry, mock_db, mock_session_service):
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                transfer_context,
                TransferContextRequest,
            )

        request_body = TransferContextRequest(
            source_agent_name="agent-a",
            target_agent_name="agent-b",
        )

        with patch(
            "solace_agent_mesh.agent.adk.services.transfer_session_context",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await transfer_context(
                session_id="sess-1",
                request_body=request_body,
                user={"id": "user1"},
                db=mock_db,
                session_service=mock_session_service,
                adk_session_service=MagicMock(),
                agent_registry=mock_agent_registry,
            )

        assert result.context_transferred is True

    @pytest.mark.asyncio
    async def test_transfer_failure_returns_false(self, mock_agent_registry, mock_db, mock_session_service):
        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                transfer_context,
                TransferContextRequest,
            )

        request_body = TransferContextRequest(
            source_agent_name="agent-a",
            target_agent_name="agent-b",
        )

        with patch(
            "solace_agent_mesh.agent.adk.services.transfer_session_context",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await transfer_context(
                session_id="sess-1",
                request_body=request_body,
                user={"id": "user1"},
                db=mock_db,
                session_service=mock_session_service,
                adk_session_service=MagicMock(),
                agent_registry=mock_agent_registry,
            )

        assert result.context_transferred is False
        assert "no conversation context" in result.message.lower()

    @pytest.mark.asyncio
    async def test_session_not_owned_returns_404(self, mock_agent_registry, mock_db):
        """Issue #10: session ownership check returns 404."""
        from fastapi import HTTPException

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                transfer_context,
                TransferContextRequest,
            )

        not_owned_service = _mock_session_service_with_ownership(owns_session=False)

        request_body = TransferContextRequest(
            source_agent_name="agent-a",
            target_agent_name="agent-b",
        )

        with pytest.raises(HTTPException) as exc_info:
            await transfer_context(
                session_id="sess-1",
                request_body=request_body,
                user={"id": "user1"},
                db=mock_db,
                session_service=not_owned_service,
                adk_session_service=MagicMock(),
                agent_registry=mock_agent_registry,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_500(self, mock_agent_registry, mock_db, mock_session_service):
        """Issue #10: RuntimeError from transfer_session_context returns 500."""
        from fastapi import HTTPException

        with patch(
            "solace_agent_mesh.gateway.http_sse.dependencies.get_sac_component",
            return_value=MagicMock(),
        ):
            from solace_agent_mesh.gateway.http_sse.routers.sessions import (
                transfer_context,
                TransferContextRequest,
            )

        request_body = TransferContextRequest(
            source_agent_name="agent-a",
            target_agent_name="agent-b",
        )

        with patch(
            "solace_agent_mesh.agent.adk.services.transfer_session_context",
            new_callable=AsyncMock,
            side_effect=RuntimeError("unexpected failure"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await transfer_context(
                    session_id="sess-1",
                    request_body=request_body,
                    user={"id": "user1"},
                    db=mock_db,
                    session_service=mock_session_service,
                    adk_session_service=MagicMock(),
                    agent_registry=mock_agent_registry,
                )

        assert exc_info.value.status_code == 500
