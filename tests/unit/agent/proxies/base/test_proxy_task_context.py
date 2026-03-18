"""Unit tests for ProxyTaskContext streaming buffer and batching state."""

from solace_agent_mesh.agent.proxies.base.proxy_task_context import ProxyTaskContext


def make_context(threshold: int = 100) -> ProxyTaskContext:
    return ProxyTaskContext(
        task_id="task-123",
        a2a_context={"session_id": "session-abc"},
        _batching_threshold_bytes=threshold,
    )


class TestStreamingBuffer:
    def test_buffer_starts_empty(self):
        ctx = make_context()
        assert ctx.get_streaming_buffer_content() == ""

    def test_append_accumulates_text(self):
        ctx = make_context()
        ctx.append_to_streaming_buffer("Hello")
        ctx.append_to_streaming_buffer(" world")
        assert ctx.get_streaming_buffer_content() == "Hello world"

    def test_clear_empties_buffer(self):
        ctx = make_context()
        ctx.append_to_streaming_buffer("some text")
        ctx.clear_streaming_buffer()
        assert ctx.get_streaming_buffer_content() == ""

    def test_append_after_clear_starts_fresh(self):
        ctx = make_context()
        ctx.append_to_streaming_buffer("first")
        ctx.clear_streaming_buffer()
        ctx.append_to_streaming_buffer("second")
        assert ctx.get_streaming_buffer_content() == "second"

    def test_append_empty_string_is_harmless(self):
        ctx = make_context()
        ctx.append_to_streaming_buffer("before")
        ctx.append_to_streaming_buffer("")
        assert ctx.get_streaming_buffer_content() == "before"


class TestBatchingThreshold:
    def test_default_threshold_is_100(self):
        ctx = ProxyTaskContext(task_id="t", a2a_context={})
        assert ctx.get_batching_threshold() == 100

    def test_custom_threshold_is_stored(self):
        ctx = make_context(threshold=512)
        assert ctx.get_batching_threshold() == 512

    def test_zero_threshold_disables_batching(self):
        ctx = make_context(threshold=0)
        assert ctx.get_batching_threshold() == 0


