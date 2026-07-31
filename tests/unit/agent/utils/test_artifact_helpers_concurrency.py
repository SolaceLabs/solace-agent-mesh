"""Concurrency regression tests for artifact metadata listing."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, patch

import pytest
from google.adk.artifacts import BaseArtifactService

from solace_agent_mesh.agent.utils.artifact_helpers import (
    _METADATA_LOAD_LIMIT,
    get_artifact_info_list,
    get_artifact_info_list_fast,
)


@pytest.mark.parametrize(
    "list_function", [get_artifact_info_list, get_artifact_info_list_fast]
)
def test_metadata_load_limit_is_loop_local_under_contention(list_function):
    """Both listing paths enforce an independent limit on each event loop."""
    release_loads = threading.Event()
    loops_ready = [threading.Event(), threading.Event()]
    loop_state = threading.local()
    states = [
        {"entered": 0, "active": 0, "max_active": 0},
        {"entered": 0, "active": 0, "max_active": 0},
    ]

    async def blocked_load(**_kwargs):
        state = loop_state.current
        state["entered"] += 1
        state["active"] += 1
        state["max_active"] = max(state["max_active"], state["active"])
        try:
            await state["gate"].wait()
        finally:
            state["active"] -= 1
        return {
            "metadata": {"mime_type": "text/plain", "size_bytes": 1},
            "version": 1,
        }

    async def run_on_loop(index):
        state = states[index]
        loop_state.current = state
        state["gate"] = asyncio.Event()

        service = AsyncMock(spec=BaseArtifactService)
        service.list_versions = AsyncMock(return_value=[1])
        if list_function is get_artifact_info_list_fast:
            service.list_artifact_keys = AsyncMock(
                return_value=[
                    f"artifact-{number}.txt"
                    for number in range(_METADATA_LOAD_LIMIT + 1)
                ]
            )
            listing = asyncio.create_task(
                list_function(
                    artifact_service=service,
                    app_name="app",
                    user_id="user",
                    session_id=f"session-{index}",
                )
            )
        else:
            service.list_artifact_keys = AsyncMock(return_value=["artifact.txt"])

            async def list_all_sessions():
                nested_results = await asyncio.gather(
                    *(
                        list_function(
                            artifact_service=service,
                            app_name="app",
                            user_id="user",
                            session_id=f"session-{index}-{number}",
                        )
                        for number in range(_METADATA_LOAD_LIMIT + 1)
                    )
                )
                return [item for result in nested_results for item in result]

            listing = asyncio.create_task(list_all_sessions())

        async def wait_for_contention():
            while state["entered"] < _METADATA_LOAD_LIMIT and not listing.done():
                await asyncio.sleep(0)

        await asyncio.wait_for(wait_for_contention(), timeout=5)
        await asyncio.sleep(0)
        loops_ready[index].set()

        await asyncio.to_thread(release_loads.wait)
        state["gate"].set()
        return await listing

    with (
        patch(
            "solace_agent_mesh.agent.utils.artifact_helpers.load_artifact_content_or_metadata",
            new=blocked_load,
        ),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        futures = []
        try:
            futures.append(executor.submit(asyncio.run, run_on_loop(0)))
            assert loops_ready[0].wait(10)

            futures.append(executor.submit(asyncio.run, run_on_loop(1)))
            assert loops_ready[1].wait(10)
        finally:
            release_loads.set()

        results = [future.result(timeout=10) for future in futures]

    for state, result in zip(states, results, strict=True):
        assert state["entered"] == _METADATA_LOAD_LIMIT + 1
        assert state["max_active"] == _METADATA_LOAD_LIMIT
        assert len(result) == _METADATA_LOAD_LIMIT + 1
        assert all(
            not info.description.startswith("Error loading details") for info in result
        )
