"""Tests for the format_agent_response compatibility with our fix."""

import unittest
from datetime import datetime
from src.orchestrator.action_manager import ActionRequestList
from src.common.utils import format_agent_response


class TestFormatAgentResponseCompatibility(unittest.TestCase):
    """Test cases for the format_agent_response compatibility with our fix."""

    def test_format_agent_response_with_user_form(self):
        """Test that format_agent_response works with responses that have user_form."""
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
        
        # Format the action response
        formatted_response, files = format_agent_response(action_request_list.actions)
        
        # Verify that the formatted response contains the text
        self.assertIn("Please fill out the form", formatted_response)
        
        # Verify that the files list is empty
        self.assertEqual(files, [])


if __name__ == "__main__":
    unittest.main()