"""Action to collect form data from a user."""

from solace_ai_connector.common.log import log

from ....common.action import Action
from ....common.action_response import ActionResponse
from ....common.form_utils import create_form


class CollectFormDataAction(Action):
    """Action to collect form data from a user."""

    def __init__(self, **kwargs):
        super().__init__(
            {
                "name": "collect_form_data",
                "prompt_directive": "Collect form data from a user",
                "params": [
                    {
                        "name": "title",
                        "desc": "Title of the form",
                        "type": "string",
                    },
                    {
                        "name": "description",
                        "desc": "Description of the form",
                        "type": "string",
                    },
                    {
                        "name": "fields",
                        "desc": "Dictionary of fields to include in the form",
                        "type": "object",
                    },
                    {
                        "name": "required_fields",
                        "desc": "List of field names that are required",
                        "type": "array",
                    },
                ],
                "required_scopes": ["*:*:*"],
                "examples": [
                    {
                        "title": "User Registration",
                        "description": "Please provide your information to register",
                        "fields": {
                            "name": None,
                            "email": None,
                            "age": None,
                            "role": {
                                "type": "string",
                                "title": "Role",
                                "enum": ["user", "admin"],
                                "enumNames": ["Regular User", "Administrator"],
                            },
                        },
                        "required_fields": ["name", "email"],
                    }
                ],
            },
            **kwargs,
        )

    def invoke(self, params, meta={}) -> ActionResponse:
        """
        Collect form data from a user.
        
        Args:
            params: Dictionary containing:
                - title: Title of the form
                - description: Description of the form
                - fields: Dictionary of fields to include
                - required_fields: List of field names that are required
            meta: Additional metadata
            
        Returns:
            ActionResponse containing the form
        """
        title = params["title"]
        description = params["description"]
        fields = params["fields"]
        required_fields = params.get("required_fields", [])
        
        log.debug(
            "Creating form: %s with %d fields",
            title,
            len(fields),
        )
        
        # Create UI schema with some sensible defaults
        ui_schema = {}
        
        # Add textarea widget for fields that likely need more space
        for field_name in fields:
            if field_name in ["description", "comments", "notes", "address", "bio"]:
                ui_schema[field_name] = {"ui:widget": "textarea"}
        
        # Create the form
        form = create_form(
            title=title,
            description=description,
            fields=fields,
            required_fields=required_fields,
            ui_schema=ui_schema,
        )
        
        # Generate a unique ID for this form
        form_id = f"form_{id(self)}_{id(form)}"
        
        # Return the form in the ActionResponse
        return ActionResponse(
            message=f"Please fill out the following form: {title}",
            user_form=form,
            is_async=True,  # Mark as async since we're waiting for user input
            async_response_id=form_id,
        )