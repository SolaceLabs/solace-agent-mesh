"""Behavioral tests for the research plan-response router."""

import pytest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from solace_agent_mesh.gateway.http_sse.routers.research import router, PlanResponsePayload

# The endpoint imports sac_component_instance locally from ..dependencies,
# so we patch it on the dependencies module where it lives.
PATCH_COMPONENT = "solace_agent_mesh.gateway.http_sse.dependencies.sac_component_instance"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _app_with_user(user_id="user-1"):
    """Create a FastAPI app with the router and a mocked user dependency."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    from solace_agent_mesh.gateway.http_sse.routers.research import get_user_id
    app.dependency_overrides[get_user_id] = lambda: user_id
    return app


# ---------------------------------------------------------------------------
# PlanResponsePayload model
# ---------------------------------------------------------------------------

class TestPlanResponsePayload:
    """Validate Pydantic model behaviour."""

    def test_accepts_start_action(self):
        p = PlanResponsePayload(planId="p1", action="start")
        assert p.plan_id == "p1"
        assert p.action == "start"
        assert p.steps is None

    def test_accepts_cancel_action(self):
        p = PlanResponsePayload(planId="p2", action="cancel")
        assert p.action == "cancel"

    def test_accepts_steps(self):
        p = PlanResponsePayload(planId="p3", action="start", steps=["a", "b"])
        assert p.steps == ["a", "b"]

    def test_rejects_invalid_action(self):
        with pytest.raises(Exception):
            PlanResponsePayload(planId="p4", action="invalid")


# ---------------------------------------------------------------------------
# POST /research/plan-response
# ---------------------------------------------------------------------------

class TestSubmitPlanResponse:
    """Behavioral tests for the plan-response endpoint."""

    def test_stores_start_response_in_cache(self):
        cache = MagicMock()
        component = MagicMock()
        component.cache_service = cache

        app = _app_with_user("user-1")

        with patch(PATCH_COMPONENT, component):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/research/plan-response",
                json={"planId": "plan-abc", "action": "start", "steps": ["edited step"]},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["plan_id"] == "plan-abc"
        assert body["action"] == "start"

        cache.add_data.assert_called_once()
        call_kwargs = cache.add_data.call_args[1]
        assert call_kwargs["key"] == "deep_research_plan:user-1:plan-abc"
        assert call_kwargs["value"]["action"] == "start"
        assert call_kwargs["value"]["steps"] == ["edited step"]
        assert call_kwargs["expiry"] == 120

    def test_stores_cancel_response_in_cache(self):
        cache = MagicMock()
        component = MagicMock()
        component.cache_service = cache

        app = _app_with_user("user-2")

        with patch(PATCH_COMPONENT, component):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/research/plan-response",
                json={"planId": "plan-xyz", "action": "cancel"},
            )

        assert resp.status_code == 200
        assert resp.json()["action"] == "cancel"

        stored = cache.add_data.call_args[1]["value"]
        assert stored["action"] == "cancel"
        assert stored["steps"] is None

    def test_returns_503_when_no_component(self):
        app = _app_with_user()

        with patch(PATCH_COMPONENT, None):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/research/plan-response",
                json={"planId": "p1", "action": "start"},
            )

        assert resp.status_code == 503

    def test_returns_503_when_no_cache_service(self):
        component = MagicMock(spec=[])  # no cache_service attribute

        app = _app_with_user()

        with patch(PATCH_COMPONENT, component):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/research/plan-response",
                json={"planId": "p1", "action": "start"},
            )

        assert resp.status_code == 503

    def test_returns_500_when_cache_write_fails(self):
        cache = MagicMock()
        cache.add_data.side_effect = RuntimeError("redis down")
        component = MagicMock()
        component.cache_service = cache

        app = _app_with_user()

        with patch(PATCH_COMPONENT, component):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/research/plan-response",
                json={"planId": "p1", "action": "start"},
            )

        assert resp.status_code == 500

    def test_rejects_invalid_action(self):
        app = _app_with_user()

        client = TestClient(app)
        resp = client.post(
            "/api/v1/research/plan-response",
            json={"planId": "p1", "action": "pause"},
        )

        assert resp.status_code == 422  # Pydantic validation error
