"""Tests for the async service component."""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.services.async_service.async_service_component import AsyncServiceComponent
from src.services.async_service.storage_providers.memory_storage_provider import MemoryStorageProvider


class TestAsyncServiceComponent(unittest.TestCase):
    """Test cases for the async service component."""

    def setUp(self):
        """Set up the test environment."""
        self.component = AsyncServiceComponent()
        self.component.storage_provider = MemoryStorageProvider()
        self.component.discard_current_message = MagicMock()

    def test_handle_create_task_group(self):
        """Test handling create task group event."""
        # Create test data
        data = {
            "stimulus_uuid": "test-uuid",
            "session_id": "test-session",
            "gateway_id": "test-gateway",
            "stimulus_state": [],
            "agent_responses": [],
            "async_responses": [
                {
                    "action_name": "test_action",
                    "action_params": {"param1": "value1"},
                    "action_idx": 0,
                    "action_list_id": "test-action-list",
                    "originator": "test-originator",
                    "async_response_id": "test-async-response",
                }
            ],
        }

        # Call the method
        result = self.component.handle_create_task_group(data)

        # Check the result
        self.assertIsNone(result)
        self.component.discard_current_message.assert_called_once()

        # Check that the task group was created
        task_groups = self.component.storage_provider.task_groups
        self.assertEqual(len(task_groups), 1)

        # Get the task group
        task_group_id = list(task_groups.keys())[0]
        task_group = task_groups[task_group_id]

        # Check task group properties
        self.assertEqual(task_group["stimulus_uuid"], "test-uuid")
        self.assertEqual(task_group["session_id"], "test-session")
        self.assertEqual(task_group["gateway_id"], "test-gateway")
        self.assertEqual(len(task_group["task_id_list"]), 1)
        self.assertEqual(task_group["status"], "pending")

        # Check that the task was created
        tasks = self.component.storage_provider.tasks
        self.assertEqual(len(tasks), 1)

        # Get the task
        task_id = task_group["task_id_list"][0]
        task = tasks[task_id]

        # Check task properties
        self.assertEqual(task["task_group_id"], task_group_id)
        self.assertEqual(task["status"], "pending")
        self.assertIsNone(task["user_response"])

    def test_handle_user_response(self):
        """Test handling user response event."""
        # Create a task group and task first
        task_group_id = "test-task-group"
        task_id = "test-task"
        
        self.component.storage_provider.create_task_group(
            task_group_id=task_group_id,
            stimulus_uuid="test-uuid",
            session_id="test-session",
            gateway_id="test-gateway",
            stimulus_state=[],
            agent_responses=[],
            user_responses={},
            task_id_list=[task_id],
            creation_time=datetime.now(),
            status="pending",
        )
        
        self.component.storage_provider.create_task(
            task_id=task_id,
            task_group_id=task_group_id,
            async_response={
                "action_name": "test_action",
                "action_params": {"param1": "value1"},
                "action_idx": 0,
                "action_list_id": "test-action-list",
                "originator": "test-originator",
                "async_response_id": "test-async-response",
            },
            creation_time=datetime.now(),
            timeout_time=datetime.now(),
            status="pending",
            user_response=None,
        )

        # Create test data
        data = {
            "task_id": task_id,
            "user_response": {"decision": "approve", "comment": "Looks good!"},
        }

        # Call the method
        with patch('os.getenv', return_value=''):
            result = self.component.handle_user_response(data)

        # Check the result
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["payload"]["stimulus_uuid"], "test-uuid")
        self.assertEqual(result[0]["payload"]["session_id"], "test-session")
        self.assertEqual(result[0]["payload"]["gateway_id"], "test-gateway")
        
        # Check that the task was updated
        task = self.component.storage_provider.get_task(task_id)
        self.assertEqual(task["status"], "completed")
        self.assertEqual(task["user_response"], {"decision": "approve", "comment": "Looks good!"})
        
        # Check that the task group was updated
        task_group = self.component.storage_provider.get_task_group(task_group_id)
        self.assertEqual(task_group["status"], "completed")
        self.assertEqual(task_group["user_responses"][task_id], {"decision": "approve", "comment": "Looks good!"})


if __name__ == "__main__":
    unittest.main()
