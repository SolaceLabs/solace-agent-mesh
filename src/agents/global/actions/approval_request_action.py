"""Action to request approval from a user."""

from solace_ai_connector.common.log import log

from ....common.action import Action
from ....common.action_response import ActionResponse
from ....common.form_utils import create_approval_form


class ApprovalRequestAction(Action):
    """Action to request approval from a user."""

    def __init__(self, **kwargs):
        super().__init__(
            {
                "name": "request_approval",
                "prompt_directive": "Request approval from a user",
                "params": [
                    {
                        "name": "title",
                        "desc": "Title of the approval request",
                        "type": "string",
                    },
                    {
                        "name": "description",
                        "desc": "Description of what needs approval",
                        "type": "string",
                    },
                    {
                        "name": "additional_info",
                        "desc": "Additional information to include in the form (optional)",
                        "type": "string",
                    },
                    {
                        "name": "require_comment",
                        "desc": "Whether to require a comment with the decision",
                        "type": "boolean",
                    },
                ],
                "required_scopes": ["*:*:*"],
                "examples": [
                    {
                        "title": "Deploy to Production",
                        "description": "Approve deployment of new features to production environment",
                        "additional_info": "Changes include: user authentication updates, performance improvements",
                        "require_comment": True,
                    }
                ],
            },
            **kwargs,
        )

    def invoke(self, params, meta={}) -> ActionResponse:
        """
        Request approval from a user.
        
        Args:
            params: Dictionary containing:
                - title: Title of the approval request
                - description: Description of what needs approval
                - additional_info: Additional information to include (optional)
                - require_comment: Whether to require a comment (optional)
            meta: Additional metadata
            
        Returns:
            ActionResponse containing the approval form
        """
        title = params["title"]
        description = params["description"]
        additional_info = params.get("additional_info")
        require_comment = params.get("require_comment", False)
        
        log.debug(
            "Creating approval request: %s (require_comment=%s)",
            title,
            require_comment,
        )
        
        # Define additional fields if needed
        additional_fields = {}
        if additional_info:
            # Just pass the value directly - the system will create an appropriate field definition
            # and mark it as read-only
            additional_fields["additional_info"] = {
                "type": "string",
                "title": "Additional Information",
                "readOnly": True,
            }
            # Pre-fill the value
            additional_fields["additional_info"] = additional_info
        
        # Create an approval form
        form = create_approval_form(
            title=title,
            description=description,
            fields=additional_fields,
            require_comment=require_comment,
        )
        
        # Generate a unique ID for this approval request
        approval_id = f"approval_{id(self)}_{id(form)}"
        
        # Return the form in the ActionResponse
        return ActionResponse(
            message=f"Approval requested: {title}",
            user_form=form,
            is_async=True,  # Mark as async since we're waiting for user input
            async_response_id=approval_id,
        )