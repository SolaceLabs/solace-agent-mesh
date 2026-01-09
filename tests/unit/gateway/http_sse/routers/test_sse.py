"""
Unit tests for SSE router helper functions and filtering logic.

Tests cover:
1. Background task artifact filtering during event replay
2. Event type determination from payload structure
"""

import pytest
from unittest.mock import Mock


class MockEvent:
    """Mock event object for testing."""
    
    def __init__(self, direction: str, payload: dict, created_time: int = 0):
        self.direction = direction
        self.payload = payload
        self.created_time = created_time


def filter_background_task_events(missed_events: list, is_background_task: bool) -> list:
    """
    Replicates the filtering logic from sse.py for testing.
    
    For background tasks, filter out intermediate artifact-update events
    to prevent duplicate artifacts in chat. Only keep the final task response
    which contains the complete artifact list.
    """
    if not is_background_task:
        return missed_events
    
    # Find if there's a final task response
    has_final_response = any(
        e.direction == "response" and
        "result" in e.payload and
        e.payload.get("result", {}).get("kind") == "task"
        for e in missed_events
    )
    
    if has_final_response:
        # Filter out artifact-update events since the final response contains all artifacts
        filtered_events = []
        for e in missed_events:
            if e.direction == "response" and "result" in e.payload:
                result = e.payload.get("result", {})
                if result.get("kind") == "artifact-update":
                    continue
            filtered_events.append(e)
        return filtered_events
    
    return missed_events


def determine_event_type(event: MockEvent) -> str:
    """
    Replicates the event type determination logic from sse.py for testing.
    """
    event_type = "status_update"  # Default
    
    # Determine event type from the payload structure
    if event.direction == "response":
        # Check if it's a final response (Task object) or status update
        if "result" in event.payload:
            result = event.payload.get("result", {})
            if result.get("kind") == "task":
                event_type = "final_response"
            elif result.get("kind") == "status-update":
                event_type = "status_update"
            elif result.get("kind") == "artifact-update":
                event_type = "artifact_update"
    
    return event_type


class TestBackgroundTaskArtifactFiltering:
    """Tests for background task artifact filtering during event replay."""
    
    def test_non_background_task_no_filtering(self):
        """Test that non-background tasks don't filter any events."""
        events = [
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "file1.txt"}}}),
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "file2.txt"}}}),
            MockEvent("response", {"result": {"kind": "task", "status": {"state": "completed"}}}),
        ]
        
        result = filter_background_task_events(events, is_background_task=False)
        
        assert len(result) == 3
        assert result == events
    
    def test_background_task_filters_artifact_updates_when_final_response_exists(self):
        """Test that background tasks filter out artifact-update events when final response exists."""
        events = [
            MockEvent("response", {"result": {"kind": "status-update", "status": {"state": "working"}}}),
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "file1.txt"}}}),
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "file2.txt"}}}),
            MockEvent("response", {"result": {"kind": "task", "status": {"state": "completed"}}}),
        ]
        
        result = filter_background_task_events(events, is_background_task=True)
        
        # Should filter out the 2 artifact-update events
        assert len(result) == 2
        
        # Verify remaining events are status-update and task
        kinds = [e.payload.get("result", {}).get("kind") for e in result]
        assert "artifact-update" not in kinds
        assert "status-update" in kinds
        assert "task" in kinds
    
    def test_background_task_keeps_all_events_when_no_final_response(self):
        """Test that background tasks keep all events when no final response exists."""
        events = [
            MockEvent("response", {"result": {"kind": "status-update", "status": {"state": "working"}}}),
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "file1.txt"}}}),
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "file2.txt"}}}),
        ]
        
        result = filter_background_task_events(events, is_background_task=True)
        
        # Should keep all events since there's no final task response
        assert len(result) == 3
        assert result == events
    
    def test_background_task_handles_empty_events(self):
        """Test that background task filtering handles empty event list."""
        events = []
        
        result = filter_background_task_events(events, is_background_task=True)
        
        assert len(result) == 0
        assert result == []
    
    def test_background_task_preserves_non_response_events(self):
        """Test that non-response events are preserved during filtering."""
        events = [
            MockEvent("request", {"method": "message/send", "params": {}}),
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "file1.txt"}}}),
            MockEvent("response", {"result": {"kind": "task", "status": {"state": "completed"}}}),
        ]
        
        result = filter_background_task_events(events, is_background_task=True)
        
        # Should keep request and task, filter out artifact-update
        assert len(result) == 2
        assert result[0].direction == "request"
        assert result[1].payload.get("result", {}).get("kind") == "task"
    
    def test_background_task_handles_events_without_result(self):
        """Test that events without 'result' field are preserved."""
        events = [
            MockEvent("response", {"error": {"code": -32000, "message": "Error"}}),
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "file1.txt"}}}),
            MockEvent("response", {"result": {"kind": "task", "status": {"state": "completed"}}}),
        ]
        
        result = filter_background_task_events(events, is_background_task=True)
        
        # Should keep error response and task, filter out artifact-update
        assert len(result) == 2
        assert "error" in result[0].payload
        assert result[1].payload.get("result", {}).get("kind") == "task"
    
    def test_background_task_filters_multiple_artifact_updates(self):
        """Test filtering with many artifact-update events."""
        events = [
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": f"file{i}.txt"}}})
            for i in range(10)
        ]
        events.append(MockEvent("response", {"result": {"kind": "task", "status": {"state": "completed"}}}))
        
        result = filter_background_task_events(events, is_background_task=True)
        
        # Should only have the final task response
        assert len(result) == 1
        assert result[0].payload.get("result", {}).get("kind") == "task"


class TestEventTypeDetermination:
    """Tests for event type determination from payload structure."""
    
    def test_final_response_event_type(self):
        """Test that task kind results in final_response event type."""
        event = MockEvent("response", {"result": {"kind": "task", "status": {"state": "completed"}}})
        
        result = determine_event_type(event)
        
        assert result == "final_response"
    
    def test_status_update_event_type(self):
        """Test that status-update kind results in status_update event type."""
        event = MockEvent("response", {"result": {"kind": "status-update", "status": {"state": "working"}}})
        
        result = determine_event_type(event)
        
        assert result == "status_update"
    
    def test_artifact_update_event_type(self):
        """Test that artifact-update kind results in artifact_update event type."""
        event = MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "file.txt"}}})
        
        result = determine_event_type(event)
        
        assert result == "artifact_update"
    
    def test_default_event_type_for_unknown_kind(self):
        """Test that unknown kind defaults to status_update."""
        event = MockEvent("response", {"result": {"kind": "unknown-kind"}})
        
        result = determine_event_type(event)
        
        assert result == "status_update"
    
    def test_default_event_type_for_non_response(self):
        """Test that non-response events default to status_update."""
        event = MockEvent("request", {"method": "message/send"})
        
        result = determine_event_type(event)
        
        assert result == "status_update"
    
    def test_default_event_type_for_response_without_result(self):
        """Test that response without result defaults to status_update."""
        event = MockEvent("response", {"error": {"code": -32000}})
        
        result = determine_event_type(event)
        
        assert result == "status_update"
    
    def test_default_event_type_for_empty_result(self):
        """Test that response with empty result defaults to status_update."""
        event = MockEvent("response", {"result": {}})
        
        result = determine_event_type(event)
        
        assert result == "status_update"


class TestBackgroundTaskReplayScenarios:
    """Integration-style tests for realistic background task replay scenarios."""
    
    def test_complete_background_task_replay_scenario(self):
        """Test a complete background task replay scenario with mixed events."""
        # Simulate a background task that:
        # 1. Starts with a status update
        # 2. Creates multiple artifacts
        # 3. Completes with a final task response
        events = [
            MockEvent("response", {"result": {"kind": "status-update", "status": {"state": "working", "message": "Starting research..."}}}, created_time=1000),
            MockEvent("response", {"result": {"kind": "status-update", "status": {"state": "working", "message": "Analyzing data..."}}}, created_time=2000),
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "research_notes.md"}}}, created_time=3000),
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "data_analysis.csv"}}}, created_time=4000),
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "final_report.pdf"}}}, created_time=5000),
            MockEvent("response", {"result": {"kind": "task", "status": {"state": "completed"}, "artifacts": [
                {"name": "research_notes.md"},
                {"name": "data_analysis.csv"},
                {"name": "final_report.pdf"}
            ]}}, created_time=6000),
        ]
        
        result = filter_background_task_events(events, is_background_task=True)
        
        # Should have 3 events: 2 status updates + 1 final task
        assert len(result) == 3
        
        # Verify event types
        kinds = [e.payload.get("result", {}).get("kind") for e in result]
        assert kinds.count("status-update") == 2
        assert kinds.count("task") == 1
        assert "artifact-update" not in kinds
    
    def test_incomplete_background_task_replay_scenario(self):
        """Test replay of an incomplete background task (no final response yet)."""
        # Simulate a background task that is still in progress
        events = [
            MockEvent("response", {"result": {"kind": "status-update", "status": {"state": "working", "message": "Starting..."}}}, created_time=1000),
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "partial_results.txt"}}}, created_time=2000),
            MockEvent("response", {"result": {"kind": "status-update", "status": {"state": "working", "message": "Still processing..."}}}, created_time=3000),
        ]
        
        result = filter_background_task_events(events, is_background_task=True)
        
        # Should keep all events since task is not complete
        assert len(result) == 3
        assert result == events
    
    def test_foreground_task_replay_scenario(self):
        """Test that foreground tasks don't filter anything."""
        events = [
            MockEvent("response", {"result": {"kind": "status-update", "status": {"state": "working"}}}),
            MockEvent("response", {"result": {"kind": "artifact-update", "artifact": {"name": "file.txt"}}}),
            MockEvent("response", {"result": {"kind": "task", "status": {"state": "completed"}}}),
        ]
        
        result = filter_background_task_events(events, is_background_task=False)
        
        # Should keep all events for foreground tasks
        assert len(result) == 3
        assert result == events
