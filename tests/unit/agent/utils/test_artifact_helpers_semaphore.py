"""Tests for per-event-loop metadata-load semaphore (issue #1591)."""

import asyncio
import gc

import pytest

from solace_agent_mesh.agent.utils.artifact_helpers import (
    _get_metadata_load_semaphore,
    _metadata_load_semaphores,
)


@pytest.mark.asyncio
async def test_returns_semaphore_for_current_loop():
    sem = _get_metadata_load_semaphore()
    assert isinstance(sem, asyncio.Semaphore)


@pytest.mark.asyncio
async def test_same_loop_gets_same_semaphore():
    s1 = _get_metadata_load_semaphore()
    s2 = _get_metadata_load_semaphore()
    assert s1 is s2


def test_different_loops_get_different_semaphores():
    """Two sequential event loops must receive distinct Semaphore instances."""

    async def _acquire():
        return _get_metadata_load_semaphore()

    loop_a = asyncio.new_event_loop()
    try:
        sem_a = loop_a.run_until_complete(_acquire())
    finally:
        loop_a.close()

    loop_b = asyncio.new_event_loop()
    try:
        sem_b = loop_b.run_until_complete(_acquire())
    finally:
        loop_b.close()

    assert sem_a is not sem_b


def test_weak_key_dictionary_cleans_up_after_gc():
    """Entries whose loop has been garbage-collected disappear from the map."""
    gc.collect()
    before = len(_metadata_load_semaphores)

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)

        async def _acquire():
            return _get_metadata_load_semaphore()

        loop.run_until_complete(_acquire())
        assert len(_metadata_load_semaphores) > before
    finally:
        asyncio.set_event_loop(None)
        del loop
        gc.collect()

    assert len(_metadata_load_semaphores) == before
