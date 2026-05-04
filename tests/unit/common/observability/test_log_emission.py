"""Acceptance test: real component code emitting real log lines must
carry the x-request-id from the active context.

The mechanism in production: `install_log_record_factory()` stamps every
LogRecord at construction time, regardless of logger or handler. These
tests exercise that path with caplog (real LogRecord capture) and with
a real dictConfig wired to a real StreamHandler + JsonFormatter."""
import asyncio
import io
import json
import logging
import logging.config

import pytest

from solace_agent_mesh.common.observability.request_context import (
    LOG_FIELD,
    RequestContext,
)
from solace_agent_mesh.common.observability.request_context_logging import (
    install_log_record_factory,
)


@pytest.fixture(autouse=True)
def _restore_factory():
    original = logging.getLogRecordFactory()
    yield
    logging.setLogRecordFactory(original)


def test_log_record_carries_x_request_id_when_emitted_inside_context(caplog):
    install_log_record_factory()
    log = logging.getLogger("test.emission.basic")

    with caplog.at_level(logging.INFO, logger="test.emission.basic"):
        with RequestContext.start("emit-id"):
            log.info("hello")

    matching = [r for r in caplog.records if r.message == "hello"]
    assert matching, "expected the log line to be captured"
    assert getattr(matching[0], LOG_FIELD) == "emit-id"


def test_log_record_outside_context_has_fallback(caplog):
    install_log_record_factory()
    log = logging.getLogger("test.emission.fallback")

    with caplog.at_level(logging.INFO, logger="test.emission.fallback"):
        log.info("no-context")

    matching = [r for r in caplog.records if r.message == "no-context"]
    assert matching
    assert getattr(matching[0], LOG_FIELD) == "-"


async def test_concurrent_log_emissions_carry_correct_ids(caplog):
    install_log_record_factory()
    log = logging.getLogger("test.emission.concurrency")

    async def one(i: int):
        with RequestContext.start(f"id-{i}"):
            log.info(f"msg-{i}")
            await asyncio.sleep(0)

    with caplog.at_level(logging.INFO, logger="test.emission.concurrency"):
        await asyncio.gather(*(one(i) for i in range(10)))

    by_msg = {r.message: getattr(r, LOG_FIELD) for r in caplog.records}
    for i in range(10):
        assert by_msg[f"msg-{i}"] == f"id-{i}"


def test_json_formatter_emits_x_request_id_field():
    """End-to-end: real dictConfig with JsonFormatter on a real
    StreamHandler. The factory stamps every record at construction;
    no filter wiring needed in the config."""
    install_log_record_factory()
    buffer = io.StringIO()

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.json.JsonFormatter",
                "format": "%(levelname)s %(name)s %(x_request_id)s %(message)s",
            },
        },
        "handlers": {
            "stream": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": buffer,
            },
        },
        "loggers": {
            "test.emission.json": {
                "level": "INFO",
                "handlers": ["stream"],
                "propagate": False,
            },
        },
    }
    logging.config.dictConfig(config)
    log = logging.getLogger("test.emission.json")

    with RequestContext.start("json-id"):
        log.info("payload")

    line = buffer.getvalue().strip()
    parsed = json.loads(line)
    assert parsed["x_request_id"] == "json-id"
    assert parsed["message"] == "payload"
