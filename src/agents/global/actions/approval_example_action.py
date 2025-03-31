"""Example action that demonstrates the approval flow."""

from typing import Dict, Any

from ....common.action import Action
from ....common.action_response import ActionResponse, ApprovalRequest
from ....common.form_utils import create_approval_form


class ApprovalExampleAction(Action):
    """Example action that demonstrates the approval flow."""

    def __init__(self, attributes, agent=None, config_fn=None, **kwargs):
        """Initialize the action."""
        attributes = {
            "name": "approval_example",
            "prompt_directive": "Request approval for a task",
            "params": [
                {
                    "name": "task_description",
                    "desc": "Description of the task requiring approval",
                    "type": "string",
                    "required": True,
                },
                {
                    "name": "task_details",
                    "desc": "Additional details about the task",
                    "type": "string",
                    "required": False,
                },
                {
                    "name": "priority",
                    "desc": "Priority of the task (high, medium, low)",
                    "type": "string",
                    "required": False,
                },
            ]
        }
        super().__init__(attributes, agent, config_fn, **kwargs)

    def invoke(self, params: Dict[str, Any], meta: Dict[str, Any] = None) -> ActionResponse:
        """
        Request approval for a task.

        Args:
            params: Parameters for the action
            meta: Additional metadata

        Returns:
            ActionResponse with approval request
        """
        task_description = params.get("task_description", "")
        task_details = params.get("task_details", "")
        priority = params.get("priority", "medium")

        # Create approval data
        approval_data = {
            "task_description": task_description,
            "task_details": task_details,
            "priority": priority,
            "requested_by": meta.get("user", "Unknown"),
            "timestamp": meta.get("timestamp", "Unknown"),
        }

        # Create form schema
        form_schema = create_approval_form(
            approval_data=approval_data,
            title="Task Approval Request",
            description="Please review the following task and approve or reject it."
        )

        # Create approval request
        approval_request = ApprovalRequest(
            form_schema=form_schema,
            approval_data=approval_data,
            approval_type="binary",  # binary (approve/reject)
            timeout_seconds=3600,  # 1 hour timeout
        )

        # Create action response with approval request
        return ActionResponse(
            message=f"Requesting approval for: {task_description}",
            approval_request=approval_request,
        )