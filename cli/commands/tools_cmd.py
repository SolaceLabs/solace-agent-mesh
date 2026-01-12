import click
import json
from typing import Optional, List, Dict, Any
from collections import defaultdict

# Import to trigger tool registration
import solace_agent_mesh.agent.tools  # noqa: F401
from solace_agent_mesh.agent.tools.registry import tool_registry
from cli.utils import error_exit


def format_parameter_schema(schema) -> str:
    """
    Format the parameter schema into a readable string.

    Args:
        schema: A google.genai.types.Schema object

    Returns:
        Formatted string representation of parameters
    """
    if not schema or not hasattr(schema, 'properties') or not schema.properties:
        return "  No parameters"

    lines = []
    required = schema.required if hasattr(schema, 'required') else []

    for prop_name, prop_schema in schema.properties.items():
        is_required = prop_name in required
        req_str = "required" if is_required else "optional"
        type_str = getattr(prop_schema, 'type', 'unknown')
        desc = getattr(prop_schema, 'description', '')
        lines.append(f"  - {prop_name} ({type_str}, {req_str}): {desc}")

    return "\n".join(lines)


def format_tool_table_brief(tools: List) -> None:
    """
    Format tools as a brief list and echo to console.

    Groups tools by category and displays only names and descriptions.

    Args:
        tools: List of BuiltinTool objects
    """
    if not tools:
        click.echo("No tools found.")
        return

    # Group tools by category
    tools_by_category = defaultdict(list)
    for tool in tools:
        tools_by_category[tool.category].append(tool)

    # Sort categories alphabetically
    sorted_categories = sorted(tools_by_category.keys())

    total_tools = len(tools)

    for category in sorted_categories:
        category_tools = sorted(tools_by_category[category], key=lambda t: t.name)

        # Get category metadata from first tool in category
        first_tool = category_tools[0]
        category_name = first_tool.category_name or category

        # Display category header
        click.echo()
        click.echo(click.style(f"═══ {category_name} ═══", bold=True, fg='cyan'))
        click.echo()

        # Display tools in category (brief format)
        for tool in category_tools:
            click.echo(f"  • {click.style(tool.name, bold=True, fg='green')}")
            # Wrap description at 70 characters
            desc_words = tool.description.split()
            lines = []
            current_line = "    "
            for word in desc_words:
                if len(current_line) + len(word) + 1 <= 74:
                    current_line += (" " if len(current_line) > 4 else "") + word
                else:
                    lines.append(current_line)
                    current_line = "    " + word
            if current_line.strip():
                lines.append(current_line)
            for line in lines:
                click.echo(line)
            click.echo()

    # Display summary
    click.echo(click.style(f"Total: {total_tools} tool{'s' if total_tools != 1 else ''}", bold=True, fg='blue'))


def format_tool_table(tools: List) -> None:
    """
    Format tools as a detailed table and echo to console.

    Groups tools by category and displays detailed information for each tool.

    Args:
        tools: List of BuiltinTool objects
    """
    if not tools:
        click.echo("No tools found.")
        return

    # Group tools by category
    tools_by_category = defaultdict(list)
    for tool in tools:
        tools_by_category[tool.category].append(tool)

    # Sort categories alphabetically
    sorted_categories = sorted(tools_by_category.keys())

    total_tools = len(tools)

    for category in sorted_categories:
        category_tools = sorted(tools_by_category[category], key=lambda t: t.name)

        # Get category metadata from first tool in category
        first_tool = category_tools[0]
        category_name = first_tool.category_name or category
        category_desc = first_tool.category_description or ""

        # Display category header
        header_width = 60
        click.echo()
        click.echo("╭" + "─" * (header_width - 2) + "╮")
        click.echo("│ " + click.style(category_name, bold=True, fg='cyan') +
                  " " * (header_width - len(category_name) - 3) + "│")
        if category_desc:
            # Wrap description if needed
            desc_lines = []
            current_line = ""
            for word in category_desc.split():
                if len(current_line) + len(word) + 1 <= header_width - 4:
                    current_line += (" " if current_line else "") + word
                else:
                    desc_lines.append(current_line)
                    current_line = word
            if current_line:
                desc_lines.append(current_line)

            for desc_line in desc_lines:
                click.echo("│ " + desc_line + " " * (header_width - len(desc_line) - 3) + "│")
        click.echo("╰" + "─" * (header_width - 2) + "╯")
        click.echo()

        # Display tools in category
        for tool in category_tools:
            click.echo(click.style(f"Tool: {tool.name}", bold=True, fg='green'))
            click.echo(f"Description: {tool.description}")

            # Format and display parameters
            click.echo("Parameters:")
            params_str = format_parameter_schema(tool.parameters)
            click.echo(params_str)

            # Display required scopes
            if tool.required_scopes:
                scopes_str = ", ".join(tool.required_scopes)
                click.echo(f"Required Scopes: {click.style(scopes_str, fg='yellow')}")
            else:
                click.echo("Required Scopes: None")

            click.echo()  # Blank line between tools

    # Display summary
    click.echo(click.style(f"Total: {total_tools} tool{'s' if total_tools != 1 else ''}",
                          bold=True, fg='blue'))


def tools_to_json(tools: List, detailed: bool = False) -> str:
    """
    Convert tools list to JSON format.

    Args:
        tools: List of BuiltinTool objects
        detailed: If True, include parameters and all metadata. If False, only name and description.

    Returns:
        JSON string representation of tools
    """
    result = []

    for tool in tools:
        if detailed:
            # Convert Schema to dict if possible
            try:
                if hasattr(tool.parameters, 'model_dump'):
                    params_dict = tool.parameters.model_dump()
                elif hasattr(tool.parameters, 'to_dict'):
                    params_dict = tool.parameters.to_dict()
                else:
                    # Fallback: manually construct dict from Schema
                    params_dict = {
                        "type": getattr(tool.parameters, 'type', None),
                        "properties": {},
                        "required": getattr(tool.parameters, 'required', [])
                    }
                    if hasattr(tool.parameters, 'properties') and tool.parameters.properties:
                        for prop_name, prop_schema in tool.parameters.properties.items():
                            params_dict["properties"][prop_name] = {
                                "type": getattr(prop_schema, 'type', None),
                                "description": getattr(prop_schema, 'description', '')
                            }
            except Exception:
                params_dict = {"error": "Could not serialize parameters"}

            tool_dict = {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "category_name": tool.category_name,
                "category_description": tool.category_description,
                "required_scopes": tool.required_scopes,
                "parameters": params_dict,
                "examples": tool.examples,
                "raw_string_args": tool.raw_string_args
            }
        else:
            # Brief format: only name and description
            tool_dict = {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "category_name": tool.category_name
            }

        result.append(tool_dict)

    return json.dumps(result, indent=2)


@click.group("tools")
def tools():
    """Manage and explore SAM built-in tools."""
    pass


@tools.command("list")
@click.option(
    "--category", "-c",
    type=str,
    default=None,
    help="Filter tools by category (e.g., 'artifact_management', 'data_analysis')"
)
@click.option(
    "--detailed", "-d",
    is_flag=True,
    help="Show detailed information including parameters and required scopes"
)
@click.option(
    "--json", "output_json",
    is_flag=True,
    help="Output in JSON format instead of pretty table"
)
def list_tools(category: Optional[str], detailed: bool, output_json: bool):
    """
    List all built-in tools available in Solace Agent Mesh.

    By default, shows brief information with tool names and descriptions.
    Use --detailed flag to see parameters and required scopes.

    Examples:

        # List all tools (brief)
        sam tools list

        # List with full details
        sam tools list --detailed

        # Filter by category
        sam tools list --category artifact_management

        # Detailed view with category filter
        sam tools list -c web --detailed

        # Output as JSON
        sam tools list --json

        # Filter and output as JSON
        sam tools list -c web --json
    """
    # Fetch tools from registry
    if category:
        tools_list = tool_registry.get_tools_by_category(category)
        if not tools_list:
            # Get all categories to show valid options
            all_tools = tool_registry.get_all_tools()
            if not all_tools:
                error_exit("No tools are registered in the tool registry.")

            categories = sorted(set(t.category for t in all_tools))
            error_exit(
                f"No tools found for category '{category}'.\n"
                f"Valid categories: {', '.join(categories)}"
            )
    else:
        tools_list = tool_registry.get_all_tools()
        if not tools_list:
            error_exit("No tools are registered in the tool registry.")

    # Output based on format preference
    if output_json:
        json_output = tools_to_json(tools_list, detailed=detailed)
        click.echo(json_output)
    else:
        # Use detailed format only if --detailed flag is provided
        if detailed:
            format_tool_table(tools_list)
        else:
            format_tool_table_brief(tools_list)
