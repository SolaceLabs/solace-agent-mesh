"""Tests for the action manager form preservation."""

import unittest
from datetime import datetime
from src.orchestrator.action_manager import ActionRequestList


class TestActionManagerFormPreservation(unittest.TestCase):
    """Test cases for the action manager form preservation."""

    def test_add_response_preserves_user_form(self):
        """Test that add_response preserves the user_form field."""
        # Create an action request list
        action_list_id = "test-action-list-id"
        actions = [
            {
                "action_idx": 0,
                "action_name": "test_action",
                "agent_name": "test_agent",
                "action_params": {"param1": "value1"},
            }
        ]
        user_properties = {"user_id": "test-user"}
        
        action_request_list = ActionRequestList(action_list_id, actions, user_properties)
        
        # Create an action response with a user_form
        action_response_obj = {
            "action_idx": 0,
            "action_name": "test_action",
            "action_list_id": action_list_id,
            "action_params": {"param1": "value1"},
            "originator": "orchestrator",
            "is_async": True,
            "user_form": {
                "schema": {
                    "title": "Test Form",
                    "description": "A test form",
                    "properties": {
                        "name": {"type": "string", "title": "Name"},
                        "email": {"type": "string", "title": "Email"},
                    },
                    "required": ["name", "email"],
                },
                "formData": {
                    "name": "John Doe",
                    "email": "john@example.com",
                },
            },
        }
        
        # Create response_text_and_files
        response_text_and_files = {
            "text": "Please fill out the form",
            "files": [],
        }
        
        # Add the response to the action request list
        action_request_list.add_response(action_response_obj, response_text_and_files)
        
        # Get the action from the action request list
        action = action_request_list.actions[0]
        
        # Verify that the response has the text
        self.assertEqual(action["response"]["text"], "Please fill out the form")
        
        # Verify that the response has the files (which might be empty or not present)
        self.assertEqual(action["response"].get("files", []), [])
        
        # Verify that the response has the user_form
        self.assertIn("user_form", action["response"])
        self.assertEqual(action["response"]["user_form"]["schema"]["title"], "Test Form")
        self.assertEqual(action["response"]["user_form"]["formData"]["name"], "John Doe")
        self.assertEqual(action["response"]["user_form"]["formData"]["email"], "john@example.com")
        
        # Verify that the response has the is_async field
        self.assertIn("is_async", action["response"])
        self.assertTrue(action["response"]["is_async"])


if __name__ == "__main__":
    unittest.main()