"""Concurrency tests. No mocks — uses real asyncio and ThreadPoolExecutor."""
import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor

from solace_agent_mesh.common.observability.request_context import (
    RequestContext,
)


async def test_many_concurrent_tasks_no_bleed():
    n = 50
    seen: list[tuple[int, str]] = []

    async def one(i: int):
        with RequestContext.start(f"id-{i}"):
            await asyncio.sleep(0)
            seen.append((i, RequestContext.current()))

    await asyncio.gather(*(one(i) for i in range(n)))
    assert all(rid == f"id-{i}" for i, rid in seen)
    assert RequestContext.current() is None


async def test_run_in_executor_with_copy_context_preserves_id():
    loop = asyncio.get_running_loop()

    def worker():
        return RequestContext.current()

    with RequestContext.start("rid-exec"):
        ctx = contextvars.copy_context()
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = await loop.run_in_executor(pool, ctx.run, worker)
    assert result == "rid-exec"


async def test_run_in_executor_without_copy_context_does_not_preserve():
    """Regression guard: documents that ContextVar is per-context, so a
    future change that drops copy_context() wrapping fails this test."""
    loop = asyncio.get_running_loop()

    def worker():
        return RequestContext.current()

    with RequestContext.start("rid"):
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = await loop.run_in_executor(pool, worker)
    assert result is None
