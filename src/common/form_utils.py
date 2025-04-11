"""Utilities for creating and validating user forms using RJSF (React JSON Schema Form)."""

from typing import Dict, List, Any, Optional, Union


def create_form(
    title: str,
    description: str,
    fields: Dict[str, Any],
    required_fields: Optional[List[str]] = None,
    ui_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a form using RJSF format.
    
    Args:
        title: The title of the form
        description: A description of the form's purpose
        fields: Dictionary of fields where:
               - Keys are field names
               - Values can be:
                 - Field definitions (dict with type, title, etc.)
                 - Actual values (str, int, bool, etc.) which will be used as pre-filled values
                   and appropriate field definitions will be created automatically
                 - None to indicate an empty field that needs to be filled by the user
        required_fields: List of field names that are required
        ui_schema: Additional UI Schema for customizing form appearance
        
    Returns:
        A dictionary representing the form in RJSF format
    """
    # Process fields to separate schema and form data
    schema_properties = {}
    form_data = {}
    
    for field_name, field_value in fields.items():
        # Check if this is a field definition (a dict with at least a 'type' key)
        if isinstance(field_value, dict) and 'type' in field_value:
            # It's a field definition
            schema_properties[field_name] = field_value
        else:
            # It's a value or None
            if field_value is None:
                # Empty field to be filled by user
                schema_properties[field_name] = {
                    "type": "string",
                    "title": field_name.replace('_', ' ').title(),
                }
            else:
                # Pre-filled value, create appropriate field definition based on type
                if isinstance(field_value, bool):
                    schema_properties[field_name] = {
                        "type": "boolean",
                        "title": field_name.replace('_', ' ').title(),
                    }
                elif isinstance(field_value, int):
                    schema_properties[field_name] = {
                        "type": "integer",
                        "title": field_name.replace('_', ' ').title(),
                    }
                elif isinstance(field_value, float):
                    schema_properties[field_name] = {
                        "type": "number",
                        "title": field_name.replace('_', ' ').title(),
                    }
                elif isinstance(field_value, list):
                    schema_properties[field_name] = {
                        "type": "array",
                        "title": field_name.replace('_', ' ').title(),
                        "items": {"type": "string"}
                    }
                else:
                    # Default to string for everything else
                    schema_properties[field_name] = {
                        "type": "string",
                        "title": field_name.replace('_', ' ').title(),
                    }
                
                # Add the value to form_data
                form_data[field_name] = field_value
    
    # Create the schema
    schema = {
        "type": "object",
        "title": title,
        "description": description,
        "properties": schema_properties,
    }
    
    # Add required fields if specified
    if required_fields:
        schema["required"] = required_fields
    
    # Create the complete form object
    form = {
        "schema": schema,
    }
    
    # Add form data if we have any
    if form_data:
        form["formData"] = form_data
    
    # Add UI schema if provided
    if ui_schema:
        form["uiSchema"] = ui_schema
    
    return form


def create_approval_form(
    title: str,
    description: str,
    fields: Optional[Dict[str, Any]] = None,
    approve_label: str = "Approve",
    deny_label: str = "Deny",
    comment_label: str = "Comment",
    require_comment: bool = False,
    ui_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a standard approval form with approve/deny options and optional comment.
    
    Args:
        title: The title of the form
        description: A description of what is being approved
        fields: Additional fields to include (can be pre-filled values or field definitions)
        approve_label: Label for the approve option
        deny_label: Label for the deny option
        comment_label: Label for the comment field
        require_comment: Whether a comment is required
        ui_schema: Additional UI schema properties
        
    Returns:
        A dictionary representing the approval form in RJSF format
    """
    # Define the base fields
    base_fields = {
        "decision": {
            "type": "string",
            "title": "Decision",
            "enum": ["approve", "deny"],
            "enumNames": [approve_label, deny_label],
        },
        "comment": {
            "type": "string",
            "title": comment_label,
        }
    }
    
    # Combine with additional fields if provided
    all_fields = {}
    if fields:
        all_fields.update(fields)
    all_fields.update(base_fields)
    
    # Define required fields
    required_fields = ["decision"]
    if require_comment:
        required_fields.append("comment")
    
    # Define base UI schema
    base_ui_schema = {
        "decision": {
            "ui:widget": "radio"
        },
        "comment": {
            "ui:widget": "textarea"
        }
    }
    
    # Combine with additional UI schema if provided
    all_ui_schema = base_ui_schema.copy()
    if ui_schema:
        all_ui_schema.update(ui_schema)
    
    return create_form(
        title=title,
        description=description,
        fields=all_fields,
        required_fields=required_fields,
        ui_schema=all_ui_schema
    )