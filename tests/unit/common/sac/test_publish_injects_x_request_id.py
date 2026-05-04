"""Tests that publish_a2a_message injects xRequestId into outgoing
user_properties from the active RequestContext, and that its own log
records carry the id.

The component itself is real (a minimal SamComponentBase subclass).
The only mock is the broker boundary — `get_app()` returns a tiny
capture-fake whose `send_message` records what it was called with."""
import logging

import pytest

from solace_agent_mesh.common.observability.request_context import (
    LOG_FIELD,
    RequestContext,
    WIRE_KEY,
)
from solace_agent_mesh.common.observability.request_context_logging import (
    install_log_record_factory,
)
from solace_agent_mesh.common.sac.sam_component_base import SamComponentBase


class _BrokerCaptureApp:
    """Capture-fake at the SAC App boundary. Records everything sent."""

    def __init__(self):
        self.sent: list[dict] = []

    def send_message(self, *, payload, topic, user_properties):
        self.sent.append(
            {"payload": payload, "topic": topic, "user_properties": user_properties}
        )


class _PublishOnlyComponent(SamComponentBase):
    """Real SamComponentBase subclass, constructed via __new__ to avoid the
    full init machinery (irrelevant to publish_a2a_message). Exposes the
    minimum surface the publish helper reads."""

    def __init__(self, broker: _BrokerCaptureApp):
        # Bypass abstract base __init__; set attributes the helper reads.
        self.log_identifier = "[PublishTest]"
        self.max_message_size_bytes = 1_000_000
        self.invocation_monitor = None
        self._broker = broker

    def get_app(self):
        return self._broker

    # Abstract methods — never invoked by these tests.
    async def _handle_message_async(self, message, topic: str) -> None:
        raise NotImplementedError

    def _get_component_id(self) -> str:
        return "publish-test"

    def _get_component_type(self) -> str:
        return "publish-test"

    def _pre_async_cleanup(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _install_factory():
    """The factory is what stamps log records in production — install it
    before each test so caplog receives stamped records."""
    original = logging.getLogRecordFactory()
    install_log_record_factory()
    yield
    logging.setLogRecordFactory(original)


@pytest.fixture
def component():
    return _PublishOnlyComponent(_BrokerCaptureApp())


def test_publish_injects_x_request_id_when_context_active(component):
    with RequestContext.start("publish-rid"):
        component.publish_a2a_message({"k": "v"}, "topic/test")
    sent = component._broker.sent[0]
    assert sent["user_properties"][WIRE_KEY] == "publish-rid"


def test_publish_does_not_inject_when_no_context(component):
    component.publish_a2a_message({"k": "v"}, "topic/test")
    assert WIRE_KEY not in component._broker.sent[0]["user_properties"]


def test_publish_preserves_caller_supplied_id(component):
    with RequestContext.start("ctx-rid"):
        component.publish_a2a_message(
            {"k": "v"},
            "topic/test",
            user_properties={WIRE_KEY: "explicit-rid"},
        )
    assert component._broker.sent[0]["user_properties"][WIRE_KEY] == "explicit-rid"


def test_publish_does_not_mutate_caller_user_properties(component):
    caller_props = {"foo": "bar"}
    with RequestContext.start("rid"):
        component.publish_a2a_message(
            {"k": "v"}, "topic/test", user_properties=caller_props
        )
    # Caller's dict must remain untouched (no xRequestId, no timestamp).
    assert WIRE_KEY not in caller_props
    assert "timestamp" not in caller_props


def test_publish_log_records_carry_x_request_id(component, caplog):
    """Real assertion: log records emitted by publish_a2a_message itself
    must carry x_request_id from the active context."""
    log_name = "solace_agent_mesh.common.sac.sam_component_base"
    with caplog.at_level(logging.DEBUG, logger=log_name):
        with RequestContext.start("logged-rid"):
            component.publish_a2a_message({"k": "v"}, "topic/test")

    relevant = [r for r in caplog.records if r.name == log_name]
    assert relevant, "expected publish_a2a_message to emit at least one log record"
    for r in relevant:
        assert getattr(r, LOG_FIELD) == "logged-rid", (
            f"record {r.message!r} missing or wrong x_request_id"
        )