"""Behavioral tests for TaskContextManager.scan_contexts."""

from solace_agent_mesh.gateway.base.task_context import TaskContextManager


class TestScanContexts:
    def setup_method(self):
        self.mgr = TaskContextManager()
        self.mgr.store_context("task-1", {"channel": "A", "priority": 1})
        self.mgr.store_context("task-2", {"channel": "B", "priority": 2})
        self.mgr.store_context("task-3", {"channel": "A", "priority": 3})

    def test_returns_matching_entries(self):
        results = self.mgr.scan_contexts(lambda tid, ctx: ctx["channel"] == "A")
        assert len(results) == 2
        task_ids = {tid for tid, _ in results}
        assert task_ids == {"task-1", "task-3"}

    def test_returns_empty_when_nothing_matches(self):
        results = self.mgr.scan_contexts(lambda tid, ctx: ctx["channel"] == "Z")
        assert results == []

    def test_returns_all_when_predicate_always_true(self):
        results = self.mgr.scan_contexts(lambda tid, ctx: True)
        assert len(results) == 3

    def test_can_filter_by_task_id(self):
        results = self.mgr.scan_contexts(lambda tid, ctx: tid == "task-2")
        assert len(results) == 1
        assert results[0][0] == "task-2"
        assert results[0][1]["channel"] == "B"

    def test_returned_contexts_are_copies(self):
        results = self.mgr.scan_contexts(lambda tid, ctx: tid == "task-1")
        results[0][1]["channel"] = "MUTATED"
        original = self.mgr.get_context("task-1")
        assert original["channel"] == "A"
