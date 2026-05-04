"""Unit tests for RequestContext. No mocks — pure ContextVar/regex code."""
import asyncio

import pytest

from solace_agent_mesh.common.observability.request_context import (
    HEADER_NAME,
    LOG_FIELD,
    WIRE_KEY,
    RequestContext,
    append_x_request_id,
)


def test_constants_match_spec():
    assert HEADER_NAME == "X-Request-ID"
    assert WIRE_KEY == "xRequestId"
    assert LOG_FIELD == "x_request_id"


def test_current_returns_none_outside_context():
    assert RequestContext.current() is None


def test_start_generates_id_when_none_provided():
    with RequestContext.start() as rc:
        assert rc.x_request_id
        assert RequestContext.current() == rc.x_request_id


def test_start_uses_provided_valid_id():
    with RequestContext.start("abc-123") as rc:
        assert rc.x_request_id == "abc-123"
        assert RequestContext.current() == "abc-123"


@pytest.mark.parametrize(
    "bad", ["bad\nvalue", "with space", "x" * 200, "", "\x00bad"]
)
def test_start_rejects_invalid_and_generates_fresh(bad):
    with RequestContext.start(bad) as rc:
        assert rc.x_request_id != bad
        assert "\n" not in rc.x_request_id
        assert " " not in rc.x_request_id
        assert len(rc.x_request_id) <= 128


def test_from_user_properties_enters_when_valid_id_present():
    with RequestContext.from_user_properties({"xRequestId": "u-1"}):
        assert RequestContext.current() == "u-1"


def test_from_user_properties_is_nullcontext_when_id_missing():
    """No fresh id is generated — internal/discovery traffic legitimately
    lacks an upstream id and should leave context untouched."""
    assert RequestContext.current() is None
    with RequestContext.from_user_properties({}):
        assert RequestContext.current() is None
    assert RequestContext.current() is None


def test_from_user_properties_is_nullcontext_when_dict_is_none():
    with RequestContext.from_user_properties(None):
        assert RequestContext.current() is None


def test_from_user_properties_is_nullcontext_when_id_invalid():
    """Malformed inbound ids (control chars, oversize, wrong type) are
    rejected and do not leak into our log stream."""
    for bad in ["bad\nvalue", "with space", "x" * 200, "", 12345, None]:
        with RequestContext.from_user_properties({"xRequestId": bad}):
            assert RequestContext.current() is None, f"failed for {bad!r}"


def test_from_user_properties_does_not_overwrite_outer_context():
    """If a context is already active (rare but possible), an inbound
    message lacking an id does NOT clobber the outer id."""
    with RequestContext.start("outer"):
        with RequestContext.from_user_properties({}):
            assert RequestContext.current() == "outer"
        assert RequestContext.current() == "outer"


def test_exit_resets_to_none():
    with RequestContext.start("temp"):
        assert RequestContext.current() == "temp"
    assert RequestContext.current() is None


def test_exit_resets_on_exception():
    with pytest.raises(RuntimeError):
        with RequestContext.start("temp"):
            assert RequestContext.current() == "temp"
            raise RuntimeError("boom")
    assert RequestContext.current() is None


def test_append_x_request_id_appends_when_context_active():
    with RequestContext.start("rid-1"):
        out = append_x_request_id("Sorry, something broke.")
    assert out == "Sorry, something broke.\nx-request-id: rid-1"


def test_append_x_request_id_returns_unchanged_when_no_context():
    assert append_x_request_id("Sorry, something broke.") == "Sorry, something broke."


def test_nested_contexts_restore_outer_on_exit():
    with RequestContext.start("outer"):
        assert RequestContext.current() == "outer"
        with RequestContext.start("inner"):
            assert RequestContext.current() == "inner"
        assert RequestContext.current() == "outer"
    assert RequestContext.current() is None


async def test_concurrent_asyncio_tasks_isolated():
    """Two coroutines on the same event loop must see their own id."""
    seen_a: list[str] = []
    seen_b: list[str] = []
    started_a = asyncio.Event()
    started_b = asyncio.Event()

    async def task_a():
        with RequestContext.start("id-A"):
            started_a.set()
            await started_b.wait()
            seen_a.append(RequestContext.current())

    async def task_b():
        with RequestContext.start("id-B"):
            started_b.set()
            await started_a.wait()
            seen_b.append(RequestContext.current())

    await asyncio.gather(task_a(), task_b())
    assert seen_a == ["id-A"]
    assert seen_b == ["id-B"]
    assert RequestContext.current() is None