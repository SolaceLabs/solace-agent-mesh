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


def _make_component(publish=None, namespace="test/ns", gateway_id="webui"):
    """Build a stub gateway component with a callable publish_a2a."""
    component = MagicMock()
    component.publish_a2a = publish or MagicMock()
    component.get_config = MagicMock(return_value=namespace)
    component.gateway_id = gateway_id
    return component


# ---------------------------------------------------------------------------
# PlanResponsePayload model
# ---------------------------------------------------------------------------

class TestPlanResponsePayload:
    """Validate Pydantic model behaviour."""

    def test_accepts_start_action(self):
        p = PlanResponsePayload(planId="p1", agentName="ResearchAgent", action="start")
        assert p.plan_id == "p1"
        assert p.agent_name == "ResearchAgent"
        assert p.action == "start"
        assert p.steps is None

    def test_accepts_cancel_action(self):
        p = PlanResponsePayload(planId="p2", agentName="A", action="cancel")
        assert p.action == "cancel"

    def test_accepts_steps(self):
        p = PlanResponsePayload(planId="p3", agentName="A", action="start", steps=["a", "b"])
        assert p.steps == ["a", "b"]

    def test_rejects_invalid_action(self):
        with pytest.raises(Exception):
            PlanResponsePayload(planId="p4", agentName="A", action="invalid")

    def test_rejects_missing_agent_name(self):
        with pytest.raises(Exception):
            PlanResponsePayload(planId="p5", action="start")


# ---------------------------------------------------------------------------
# POST /research/plan-response
# ---------------------------------------------------------------------------

class TestSubmitPlanResponse:
    """Behavioral tests for the plan-response endpoint."""

    def test_publishes_start_signal_on_correct_topic(self):
        component = _make_component(namespace="acme/sam", gateway_id="webui")

        app = _app_with_user("user-1")

        with patch(PATCH_COMPONENT, component):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/research/plan-response",
                json={
                    "planId": "plan-abc",
                    "agentName": "ResearchAgent",
                    "action": "start",
                    "steps": ["edited step"],
                },
            )

        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["plan_id"] == "plan-abc"

        component.publish_a2a.assert_called_once()
        kwargs = component.publish_a2a.call_args.kwargs
        # Topic must carry namespace + deep_research category + plan_response action
        assert kwargs["topic"] == "acme/sam/sam/events/deep_research/plan_response"
        payload = kwargs["payload"]
        assert payload["event_type"] == "plan_response"
        assert payload["data"]["plan_id"] == "plan-abc"
        assert payload["data"]["agent_name"] == "ResearchAgent"
        assert payload["data"]["user_id"] == "user-1"
        assert payload["data"]["action"] == "start"
        assert payload["data"]["steps"] == ["edited step"]

    def test_publishes_cancel_signal_without_steps(self):
        component = _make_component()
        app = _app_with_user("user-2")

        with patch(PATCH_COMPONENT, component):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/research/plan-response",
                json={"planId": "plan-xyz", "agentName": "A", "action": "cancel"},
            )

        assert resp.status_code == 202
        payload = component.publish_a2a.call_args.kwargs["payload"]
        assert payload["data"]["action"] == "cancel"
        assert payload["data"]["steps"] is None

    def test_returns_503_when_no_component(self):
        app = _app_with_user()

        with patch(PATCH_COMPONENT, None):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/research/plan-response",
                json={"planId": "p1", "agentName": "A", "action": "start"},
            )

        assert resp.status_code == 503

    def test_returns_503_when_publish_unavailable(self):
        component = MagicMock(spec=[])  # no publish_a2a attribute

        app = _app_with_user()

        with patch(PATCH_COMPONENT, component):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/research/plan-response",
                json={"planId": "p1", "agentName": "A", "action": "start"},
            )

        assert resp.status_code == 503

    def test_returns_500_when_publish_fails(self):
        component = _make_component(
            publish=MagicMock(side_effect=RuntimeError("broker down"))
        )
        app = _app_with_user()

        with patch(PATCH_COMPONENT, component):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/research/plan-response",
                json={"planId": "p1", "agentName": "A", "action": "start"},
            )

        assert resp.status_code == 500

    def test_rejects_invalid_action(self):
        app = _app_with_user()

        client = TestClient(app)
        resp = client.post(
            "/api/v1/research/plan-response",
            json={"planId": "p1", "agentName": "A", "action": "pause"},
        )

        assert resp.status_code == 422  # Pydantic validation error
