"""Tests for the form utilities."""

import unittest
from src.common.form_utils import create_form, create_approval_form
from src.common.action_response import ActionResponse


class TestFormUtils(unittest.TestCase):
    """Test cases for form utilities."""

    def test_create_form_with_empty_fields(self):
        """Test creating a form with empty fields."""
        form = create_form(
            title="Test Form",
            description="A test form",
            fields={
                "name": None,
                "email": None,
            },
            required_fields=["name"],
        )
        
        # Check the structure of the form
        self.assertEqual(form["schema"]["title"], "Test Form")
        self.assertEqual(form["schema"]["description"], "A test form")
        self.assertEqual(form["schema"]["required"], ["name"])
        
        # Check that the fields are defined correctly
        self.assertEqual(form["schema"]["properties"]["name"]["type"], "string")
        self.assertEqual(form["schema"]["properties"]["email"]["type"], "string")
        
        # Check that there's no form data
        self.assertNotIn("formData", form)

    def test_create_form_with_prefilled_values(self):
        """Test creating a form with pre-filled values."""
        form = create_form(
            title="User Info",
            description="User information form",
            fields={
                "name": "John Doe",
                "age": 30,
                "is_active": True,
                "score": 85.5,
                "tags": ["user", "admin"],
            },
        )
        
        # Check the structure of the form
        self.assertEqual(form["schema"]["title"], "User Info")
        
        # Check that the fields are defined correctly with appropriate types
        self.assertEqual(form["schema"]["properties"]["name"]["type"], "string")
        self.assertEqual(form["schema"]["properties"]["age"]["type"], "integer")
        self.assertEqual(form["schema"]["properties"]["is_active"]["type"], "boolean")
        self.assertEqual(form["schema"]["properties"]["score"]["type"], "number")
        self.assertEqual(form["schema"]["properties"]["tags"]["type"], "array")
        
        # Check that the form data contains the pre-filled values
        self.assertEqual(form["formData"]["name"], "John Doe")
        self.assertEqual(form["formData"]["age"], 30)
        self.assertEqual(form["formData"]["is_active"], True)
        self.assertEqual(form["formData"]["score"], 85.5)
        self.assertEqual(form["formData"]["tags"], ["user", "admin"])

    def test_create_form_with_custom_field_definitions(self):
        """Test creating a form with custom field definitions."""
        form = create_form(
            title="Custom Form",
            description="Form with custom field definitions",
            fields={
                "role": {
                    "type": "string",
                    "title": "User Role",
                    "enum": ["admin", "user", "guest"],
                    "enumNames": ["Administrator", "Regular User", "Guest"],
                },
                "notes": {
                    "type": "string",
                    "title": "Additional Notes",
                },
            },
            ui_schema={
                "notes": {
                    "ui:widget": "textarea",
                },
            },
        )
        
        # Check that the custom field definitions are preserved
        self.assertEqual(form["schema"]["properties"]["role"]["enum"], ["admin", "user", "guest"])
        self.assertEqual(form["schema"]["properties"]["role"]["enumNames"], ["Administrator", "Regular User", "Guest"])
        
        # Check that the UI schema is included
        self.assertEqual(form["uiSchema"]["notes"]["ui:widget"], "textarea")

    def test_create_approval_form(self):
        """Test creating an approval form."""
        form = create_approval_form(
            title="Approve Request",
            description="Please approve or deny this request",
            require_comment=True,
            fields={
                "request_id": "REQ-12345",
                "requested_by": "Jane Smith",
            },
        )
        
        # Check the structure of the form
        self.assertEqual(form["schema"]["title"], "Approve Request")
        self.assertEqual(form["schema"]["description"], "Please approve or deny this request")
        
        # Check that the decision field is defined correctly
        self.assertEqual(form["schema"]["properties"]["decision"]["type"], "string")
        self.assertEqual(form["schema"]["properties"]["decision"]["enum"], ["approve", "deny"])
        
        # Check that the comment field is required
        self.assertIn("comment", form["schema"]["required"])
        
        # Check that the additional fields are included
        self.assertEqual(form["formData"]["request_id"], "REQ-12345")
        self.assertEqual(form["formData"]["requested_by"], "Jane Smith")
        
        # Check that the UI schema is set correctly
        self.assertEqual(form["uiSchema"]["decision"]["ui:widget"], "radio")
        self.assertEqual(form["uiSchema"]["comment"]["ui:widget"], "textarea")

    def test_action_response_with_form(self):
        """Test creating an ActionResponse with a form."""
        form = create_approval_form(
            title="Approve Request",
            description="Please approve or deny this request",
        )
        
        response = ActionResponse(
            message="Please review the following request",
            user_form=form,
            is_async=True,
            async_response_id="approval_123",
        )
        
        # Check that the form is included in the response
        self.assertEqual(response.user_form, form)
        
        # Check that the form is included in the dictionary representation
        response_dict = response.to_dict()
        self.assertEqual(response_dict["user_form"], form)
        self.assertEqual(response_dict["message"], "Please review the following request")
        self.assertTrue(response_dict["is_async"])
        self.assertEqual(response_dict["async_response_id"], "approval_123")


if __name__ == "__main__":
    unittest.main()