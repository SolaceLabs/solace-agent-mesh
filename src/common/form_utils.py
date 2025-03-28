"""Utility functions for creating and handling forms."""

from typing import Dict, Any, List, Union


def create_approval_form(
    approval_data: Dict[str, Any], 
    title: str = "Approval Request",
    description: str = None
) -> Dict[str, Any]:
    """
    Create an RJFS form schema from approval data.
    
    Args:
        approval_data: Dictionary containing data to display in the form
        title: Form title
        description: Optional form description
        
    Returns:
        RJFS form schema
    """
    form_schema = {
        "title": title,
        "type": "object",
        "properties": {},
        "required": []
    }
    
    if description:
        form_schema["description"] = description
    
    # Add fields for each item in approval_data
    for key, value in approval_data.items():
        field_type = "string"
        field_format = None
        field_enum = None
        field_enum_names = None
        
        # Determine field type based on value type
        if isinstance(value, bool):
            field_type = "boolean"
        elif isinstance(value, int):
            field_type = "integer"
        elif isinstance(value, float):
            field_type = "number"
        elif isinstance(value, list):
            if all(isinstance(item, str) for item in value):
                field_type = "string"
                field_enum = value
                field_enum_names = value
            elif all(isinstance(item, (int, float)) for item in value):
                field_type = "number" if any(isinstance(item, float) for item in value) else "integer"
                field_enum = value
        
        # Create field schema
        field_schema = {
            "type": field_type,
            "title": key.replace("_", " ").title(),
            "default": value,
            "readOnly": True  # Make fields read-only for display purposes
        }
        
        if field_format:
            field_schema["format"] = field_format
        
        if field_enum:
            field_schema["enum"] = field_enum
            
        if field_enum_names:
            field_schema["enumNames"] = field_enum_names
            
        form_schema["properties"][key] = field_schema
    
    # Add decision field (approve/reject)
    form_schema["properties"]["decision"] = {
        "type": "string",
        "title": "Decision",
        "enum": ["approve", "reject"],
        "enumNames": ["Approve", "Reject"]
    }
    form_schema["required"].append("decision")
    
    # Add optional comment field
    form_schema["properties"]["comment"] = {
        "type": "string",
        "title": "Comment",
        "description": "Optional comment for your decision"
    }
    
    return form_schema


def rjfs_to_slack_blocks(form_schema: Dict[str, Any], approval_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert RJFS form schema to Slack blocks.
    
    Args:
        form_schema: RJFS form schema
        approval_data: Data to display in the form
        
    Returns:
        List of Slack blocks
    """
    blocks = []
    
    # Add title
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": form_schema.get("title", "Approval Request"),
            "emoji": True
        }
    })
    
    # Add description if available
    if form_schema.get("description"):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": form_schema.get("description")
            }
        })
    
    # Add divider
    blocks.append({"type": "divider"})
    
    # Add fields for each property
    for key, prop in form_schema.get("properties", {}).items():
        if key in ["decision", "comment"]:  # Skip decision and comment fields, we'll add them later
            continue
            
        value = approval_data.get(key, prop.get("default", ""))
        
        # Format value based on type
        if prop.get("type") == "boolean":
            value = "Yes" if value else "No"
        elif prop.get("type") in ["integer", "number"]:
            value = str(value)
        elif isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*{prop.get('title', key)}*"
                },
                {
                    "type": "mrkdwn",
                    "text": value
                }
            ]
        })
    
    # Add comment input
    blocks.append({
        "type": "input",
        "block_id": "comment_block",
        "element": {
            "type": "plain_text_input",
            "action_id": "comment_input",
            "placeholder": {
                "type": "plain_text",
                "text": "Add an optional comment"
            },
            "multiline": True
        },
        "label": {
            "type": "plain_text",
            "text": "Comment"
        },
        "optional": True
    })
    
    # Add divider
    blocks.append({"type": "divider"})
    
    # Add approve/reject buttons
    blocks.append({
        "type": "actions",
        "block_id": "approval_actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Approve",
                    "emoji": True
                },
                "style": "primary",
                "value": "approve",
                "action_id": "approve_button"
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Reject",
                    "emoji": True
                },
                "style": "danger",
                "value": "reject",
                "action_id": "reject_button"
            }
        ]
    })
    
    return blocks


def extract_form_data_from_slack_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract form data from Slack interaction payload.
    
    Args:
        payload: Slack interaction payload
        
    Returns:
        Dictionary containing form data
    """
    form_data = {}
    
    # Extract decision from button action
    if payload.get("type") == "block_actions":
        actions = payload.get("actions", [])
        for action in actions:
            if action.get("action_id") in ["approve_button", "reject_button"]:
                form_data["decision"] = action.get("value")
    
    # Extract comment from state values
    state_values = payload.get("state", {}).get("values", {})
    for block_id, block_values in state_values.items():
        if block_id == "comment_block":
            for action_id, action_value in block_values.items():
                if action_id == "comment_input":
                    form_data["comment"] = action_value.get("value", "")
    
    return form_data