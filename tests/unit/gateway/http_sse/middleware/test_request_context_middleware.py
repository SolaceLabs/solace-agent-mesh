"""RequestContextMiddleware tests. No mocks — real FastAPI app, real
TestClient, real Python logging."""
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from solace_agent_mesh.common.observability.request_context import (
    HEADER_NAME,
    LOG_FIELD,
    RequestContext,
)
from solace_agent_mesh.common.observability.request_context_logging import (
    install_log_record_factory,
)
from solace_agent_mesh.gateway.http_sse.middleware.request_context import (
    RequestContextMiddleware,
)


@pytest.fixture(autouse=True)
def _factory_installed():
    install_log_record_factory()


@pytest.fixture
def app():
    a = FastAPI()
    a.add_middleware(RequestContextMiddleware)

    @a.get("/echo")
    async def echo():
        return {"x_request_id": RequestContext.current()}

    @a.get("/log")
    async def log_endpoint():
        logging.getLogger("test.middleware.request").info("inside-handler")
        return {"ok": True}

    return a


def test_response_carries_generated_id_when_inbound_absent(app):
    r = TestClient(app).get("/echo")
    assert r.status_code == 200
    assert r.headers[HEADER_NAME]
    assert r.json()["x_request_id"] == r.headers[HEADER_NAME]


def test_inbound_valid_header_is_echoed(app):
    r = TestClient(app).get("/echo", headers={HEADER_NAME: "client-rid"})
    assert r.headers[HEADER_NAME] == "client-rid"
    assert r.json()["x_request_id"] == "client-rid"


def test_inbound_invalid_header_is_replaced(app):
    r = TestClient(app).get("/echo", headers={HEADER_NAME: "bad\nvalue"})
    assert r.headers[HEADER_NAME] != "bad\nvalue"
    assert "\n" not in r.headers[HEADER_NAME]


def test_context_cleared_after_response(app):
    TestClient(app).get("/echo")
    assert RequestContext.current() is None


def test_handler_log_records_carry_x_request_id(app, caplog):
    with caplog.at_level(logging.INFO, logger="test.middleware.request"):
        TestClient(app).get("/log", headers={HEADER_NAME: "log-rid"})
    matching = [r for r in caplog.records if r.message == "inside-handler"]
    assert matching
    assert getattr(matching[0], LOG_FIELD) == "log-rid"