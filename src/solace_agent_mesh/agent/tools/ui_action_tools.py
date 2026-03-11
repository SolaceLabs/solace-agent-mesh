"""
Collection of tools for performing UI actions via command palette.
These tools allow agents to interact with the web UI to perform operations
like creating projects, managing settings, etc.
"""

import logging
import httpx
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext
from google.genai import types as adk_types

from .tool_definition import BuiltinTool
from .tool_result import ToolResult
from .registry import tool_registry

log = logging.getLogger(__name__)

CATEGORY_NAME = "UI Actions"
CATEGORY_DESCRIPTION = "Perform actions in the web UI such as creating projects, managing settings, and navigating pages."


async def create_project(
    project_name: str,
    description: Optional[str] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Creates a new project in the system.

    Args:
        project_name: The name of the project to create.
        description: Optional description for the project.
        tool_context: The context provided by the ADK framework.
        tool_config: Optional configuration passed by the ADK.

    Returns:
        ToolResult with the created project information including project ID.
    """
    log_identifier = "[UIActionTools:create_project]"

    if not tool_context:
        log.error(f"{log_identifier} ToolContext is missing.")
        return ToolResult.error("ToolContext is missing.")

    try:
        inv_context = tool_context._invocation_context
        if not inv_context:
            raise ValueError("InvocationContext is not available.")

        # Get user ID from context
        user_id = getattr(inv_context, "user_id", None)
        if not user_id:
            log.error(f"{log_identifier} user_id not found in invocation context")
            return ToolResult.error("User ID not available in context")

        log.info(
            f"{log_identifier} Creating project for user {user_id}: name='{project_name}', description='{description}'"
        )

        # Call the internal HTTP API endpoint
        # This endpoint is exposed on the WebUI gateway
        base_url = "http://127.0.0.1:8000"  # WebUI gateway default

        # Prepare form data
        form_data = {"name": project_name}
        if description:
            form_data["description"] = description

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/api/v1/projects",
                data=form_data,
                headers={
                    "Authorization": f"Bearer {user_id}",  # Use user_id as bearer token for internal calls
                },
            )

            if response.status_code != 201:
                error_msg = response.text
                log.error(f"{log_identifier} API call failed: {error_msg}")
                return ToolResult.error(f"Failed to create project: {error_msg}")

            project_data = response.json()

        log.info(
            f"{log_identifier} Successfully created project '{project_name}' with ID: {project_data['id']}"
        )

        return ToolResult.ok(
            f"Successfully created project '{project_name}'",
            data={
                "project_id": project_data["id"],
                "project_name": project_data["name"],
                "description": project_data.get("description"),
                "action": "navigate_to_project",  # Signal to UI to navigate
            },
        )

    except Exception as e:
        log.exception(f"{log_identifier} Error creating project: {e}")
        return ToolResult.error(f"Failed to create project: {str(e)}")


create_project_tool_def = BuiltinTool(
    name="create_project",
    implementation=create_project,
    description="Creates a new project with the specified name and optional description. Use this when the user wants to create, make, or start a new project. Returns the project ID and signals the UI to navigate to the newly created project.",
    category="ui_actions",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:ui:write"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "project_name": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The name of the project to create",
            ),
            "description": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional description for the project",
            ),
        },
        required=["project_name"],
    ),
    examples=[],
)

tool_registry.register(create_project_tool_def)
