"""Unit tests for the LogRecord factory. No mocks — uses real Python logging."""
import logging

import pytest

from solace_agent_mesh.common.observability.request_context import (
    LOG_FIELD,
    MISSING_VALUE,
    RequestContext,
)
from solace_agent_mesh.common.observability.request_context_logging import (
    install_log_record_factory,
)


def _record_via_factory():
    """LogRecord constructed via the currently-installed factory."""
    factory = logging.getLogRecordFactory()
    return factory("t", logging.INFO, "x", 1, "m", (), None)


@pytest.fixture(autouse=True)
def _restore_factory():
    """Snapshot/restore the global LogRecord factory so tests don't bleed."""
    original = logging.getLogRecordFactory()
    yield
    logging.setLogRecordFactory(original)


def test_factory_stamps_at_record_creation():
    install_log_record_factory()
    with RequestContext.start("factory-id"):
        r = _record_via_factory()
    assert getattr(r, LOG_FIELD) == "factory-id"


def test_factory_falls_back_when_no_context():
    install_log_record_factory()
    r = _record_via_factory()
    assert getattr(r, LOG_FIELD) == MISSING_VALUE


def test_factory_idempotent_under_repeated_install():
    install_log_record_factory()
    install_log_record_factory()
    install_log_record_factory()
    with RequestContext.start("rid"):
        r = _record_via_factory()
    assert getattr(r, LOG_FIELD) == "rid"


def test_factory_composes_with_existing_custom_factory():
    base = logging.getLogRecordFactory()

    def custom(*a, **kw):
        rec = base(*a, **kw)
        rec.custom_marker = True
        return rec

    logging.setLogRecordFactory(custom)
    install_log_record_factory()
    with RequestContext.start("rid"):
        r = _record_via_factory()
    assert getattr(r, LOG_FIELD) == "rid"
    assert getattr(r, "custom_marker", False) is True
