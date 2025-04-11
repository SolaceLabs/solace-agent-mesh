"""Test the get_pending_forms functionality in the AsyncServiceComponent."""

import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

from solace_ai_connector.common.message import Message

from src.services.async_service.async_service_component import AsyncServiceComponent
from src.services.async_service.storage_providers.memory_storage_provider import MemoryStorageProvider


class TestAsyncServiceGetPendingForms(unittest.TestCase):
    """Test the get_pending_forms functionality in the AsyncServiceComponent."""

    def setUp(self):
        """Set up the test."""
        # Create a mock environment variable
        os.environ["SOLACE_AGENT_MESH_NAMESPACE"] = "test/"
        
        # Create the component
        self.component = AsyncServiceComponent(storage_provider="memory")
        
        # Create a mock message
        self.message = Message(payload={}, topic="test/topic")
        self.message.set_user_properties({"identity": "test-identity"})
        
        # Create a mock storage provider with test data
        self.storage_provider = MemoryStorageProvider()
        self.component.storage_provider = self.storage_provider
        
        # Set up test data
        self.setup_test_data()
        
    def setup_test_data(self):
        """Set up test data for the tests."""
        # Create a task group
        task_group_id = "test-task-group"
        stimulus_uuid = "test-stimulus"
        session_id = "test-session"
        gateway_id = "test-gateway"
        
        self.storage_provider.create_task_group(
            task_group_id=task_group_id,
            stimulus_uuid=stimulus_uuid,
            session_id=session_id,
            gateway_id=gateway_id,
            stimulus_state=[],
            agent_responses=[],
            user_responses={},
            task_id_list=["task1", "task2", "task3"],
            creation_time=datetime.now(),
            status="pending",
            user_properties={}
        )
        
        # Create tasks with different identities
        # Task 1: Matching identity
        self.storage_provider.create_task(
            task_id="task1",
            task_group_id=task_group_id,
            async_response={
                "response": {
                    "user_form": {
                        "title": "Test Form 1",
                        "fields": [{"name": "field1", "type": "text"}]
                    }
                }
            },
            creation_time=datetime.now(),
            timeout_time=datetime.now(),
            status="pending",
            user_response=None,
            approver_list=[
                {"identity": "test-identity", "interface_properties": {}}
            ]
        )
        
        # Task 2: Non-matching identity
        self.storage_provider.create_task(
            task_id="task2",
            task_group_id=task_group_id,
            async_response={
                "response": {
                    "user_form": {
                        "title": "Test Form 2",
                        "fields": [{"name": "field2", "type": "text"}]
                    }
                }
            },
            creation_time=datetime.now(),
            timeout_time=datetime.now(),
            status="pending",
            user_response=None,
            approver_list=[
                {"identity": "other-identity", "interface_properties": {}}
            ]
        )
        
        # Task 3: Completed task (should not be returned)
        self.storage_provider.create_task(
            task_id="task3",
            task_group_id=task_group_id,
            async_response={
                "response": {
                    "user_form": {
                        "title": "Test Form 3",
                        "fields": [{"name": "field3", "type": "text"}]
                    }
                }
            },
            creation_time=datetime.now(),
            timeout_time=datetime.now(),
            status="completed",
            user_response={"field3": "value3"},
            approver_list=[
                {"identity": "test-identity", "interface_properties": {}}
            ]
        )
    
    def test_get_pending_forms(self):
        """Test the get_pending_forms handler."""
        # Create the request data
        data = {
            "event_type": "get_pending_forms",
            "gateway_id": "test-gateway",
            "identity": "test-identity"
        }
        
        # Call the handler
        result = self.component.handle_get_pending_forms(self.message, data)
        
        # Verify the result
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        
        event = result[0]
        self.assertEqual(event["topic"], "test/solace-agent-mesh/v1/stimulus/async-service/user-response/test-gateway")
        
        pending_forms = event["payload"]["pending_forms"]
        self.assertEqual(len(pending_forms), 1)
        
        form = pending_forms[0]
        self.assertEqual(form["task_id"], "task1")
        self.assertEqual(form["session_id"], "test-session")
        self.assertEqual(form["stimulus_uuid"], "test-stimulus")
        self.assertEqual(form["user_form"]["title"], "Test Form 1")
    
    def test_get_pending_forms_no_match(self):
        """Test the get_pending_forms handler with no matching identity."""
        # Create the request data
        data = {
            "event_type": "get_pending_forms",
            "gateway_id": "test-gateway",
            "identity": "non-existent-identity"
        }
        
        # Call the handler
        result = self.component.handle_get_pending_forms(self.message, data)
        
        # Verify the result
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        
        event = result[0]
        pending_forms = event["payload"]["pending_forms"]
        self.assertEqual(len(pending_forms), 0)
    
    def test_get_pending_forms_missing_gateway_id(self):
        """Test the get_pending_forms handler with missing gateway_id."""
        # Create the request data
        data = {
            "event_type": "get_pending_forms",
            "identity": "test-identity"
        }
        
        # Mock the discard_current_message method
        self.component.discard_current_message = MagicMock()
        
        # Call the handler
        result = self.component.handle_get_pending_forms(self.message, data)
        
        # Verify the result
        self.assertIsNone(result)
        self.component.discard_current_message.assert_called_once()
    
    def test_get_pending_forms_missing_identity(self):
        """Test the get_pending_forms handler with missing identity."""
        # Create the request data
        data = {
            "event_type": "get_pending_forms",
            "gateway_id": "test-gateway"
        }
        
        # Mock the discard_current_message method
        self.component.discard_current_message = MagicMock()
        
        # Call the handler
        result = self.component.handle_get_pending_forms(self.message, data)
        
        # Verify the result
        self.assertIsNone(result)
        self.component.discard_current_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()