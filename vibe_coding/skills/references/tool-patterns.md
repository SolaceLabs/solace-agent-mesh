# Tool Implementation Patterns

This document provides detailed examples of the three tool implementation patterns for Solace Agent Mesh plugins.

## Pattern 1: Function-Based Tools

Best for simple, self-contained tools with static inputs. Quick and easy to implement.

### Requirements

- Must be `async def`
- Docstring is used as tool description for the LLM
- Type hints (`str`, `int`, `bool`) generate parameter schema
- Accept `tool_context` and `tool_config` as optional keyword arguments

### Basic Example

```python
from typing import Any, Dict, Optional
from google.adk.tools import ToolContext

async def greet_user(
    name: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Greets a user with a personalized message.

    Args:
        name: The name of the person to greet

    Returns:
        A dictionary with the greeting message
    """
    greeting_prefix = "Hello"
    if tool_config:
        greeting_prefix = tool_config.get("greeting_prefix", "Hello")

    greeting_message = f"{greeting_prefix}, {name}! Welcome!"

    return {
        "status": "success",
        "message": greeting_message
    }
```

### With Artifact Handling

```python
from datetime import datetime, timezone
from solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata
from solace_agent_mesh.agent.utils.context_helpers import get_original_session_id

async def save_greeting(
    name: str,
    save_to_file: bool = False,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Greets a user and optionally saves greeting to a file.

    Args:
        name: The name of the person to greet
        save_to_file: Whether to save the greeting as an artifact
    """
    greeting = f"Hello, {name}!"
    result = {"status": "success", "message": greeting}

    if save_to_file and tool_context:
        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service

        filename = f"greeting_{name}.txt"
        content = f"Greeting: {greeting}\nTime: {datetime.now(timezone.utc)}\n"

        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=filename,
            content_bytes=content.encode('utf-8'),
            mime_type="text/plain",
            metadata_dict={"description": "Greeting message"},
            timestamp=datetime.now(timezone.utc)
        )

        result["filename"] = filename
        result["version"] = save_result["data_version"]

    return result
```

### YAML Configuration

```yaml
tools:
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "greet_user"
    tool_config:
      greeting_prefix: "Greetings"
```

## Pattern 2: DynamicTool Class

Best for tools requiring complex logic or programmatically defined interfaces.

### Requirements

- Inherit from `DynamicTool`
- Implement required properties: `tool_name`, `tool_description`, `parameters_schema`
- Override `_run_async_impl(self, args: Dict[str, Any], **kwargs)`

### Example

```python
from typing import Dict, Any
from google.genai import types as adk_types
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool

class WeatherTool(DynamicTool):
    """A dynamic tool that fetches weather information."""

    @property
    def tool_name(self) -> str:
        return "get_current_weather"

    @property
    def tool_description(self) -> str:
        return "Get the current weather for a specified location."

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "location": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="The city and state/country"
                ),
                "units": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    enum=["celsius", "fahrenheit"],
                    nullable=True
                ),
            },
            required=["location"],
        )

    async def _run_async_impl(self, args: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        location = args["location"]
        units = args.get("units", "celsius")

        # Access config via self.tool_config
        api_key = self.tool_config.get("api_key")
        if not api_key:
            return {"status": "error", "message": "API key not configured"}

        # Implementation here...
        return {"status": "success", "temperature": 72, "units": units}
```

### YAML Configuration

```yaml
tools:
  - tool_type: python
    component_module: "my_plugin.tools"
    class_name: "WeatherTool"  # Optional if only one DynamicTool in module
    tool_config:
      api_key: ${WEATHER_API_KEY}
```

## Pattern 3: DynamicToolProvider

Best for generating multiple related tools from a single configurable source. Maximum scalability and code reuse.

### Requirements

- Inherit from `DynamicToolProvider`
- Implement `create_tools(self, tool_config: Optional[dict]) -> List[DynamicTool]`
- Can use `@register_tool` decorator for simple function-based tools
- Returns list of `DynamicTool` instances

### Example

```python
from typing import Optional, Dict, Any, List
from google.genai import types as adk_types
from solace_agent_mesh.agent.tools.dynamic_tool import (
    DynamicTool,
    DynamicToolProvider,
    register_tool
)

# Tool implementations
class DatabaseQueryTool(DynamicTool):
    @property
    def tool_name(self) -> str:
        return "query_database"

    @property
    def tool_description(self) -> str:
        return "Execute SQL queries on the configured database."

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "query": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="SQL query to execute"
                ),
            },
            required=["query"],
        )

    async def _run_async_impl(self, args: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        query = args["query"]
        connection_string = self.tool_config.get("connection_string")
        # Execute query...
        return {"status": "success", "results": []}

# Provider that creates multiple tools
class DatabaseToolProvider(DynamicToolProvider):
    """Factory for database-related tools."""

    def create_tools(self, tool_config: Optional[dict] = None) -> List[DynamicTool]:
        """Generate database tools based on configuration."""
        tools = []

        # Create tools from decorated functions
        tools.extend(self._create_tools_from_decorators(tool_config))

        # Programmatically add complex tools
        if tool_config and tool_config.get("connection_string"):
            tools.append(DatabaseQueryTool(tool_config=tool_config))

        return tools

# Simple function registered with the provider
@register_tool(DatabaseToolProvider)
async def list_tables(
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Lists all tables in the database."""
    connection_string = tool_config.get("connection_string") if tool_config else None
    # Implementation...
    return {"status": "success", "tables": ["users", "orders"]}
```

### YAML Configuration

```yaml
tools:
  - tool_type: python
    component_module: "my_plugin.database_tools"
    class_name: "DatabaseToolProvider"
    tool_config:
      connection_string: ${DATABASE_URL}
```

## Loading Image Artifacts Example

Based on the image_tools.py pattern:

```python
import asyncio
import inspect
from io import BytesIO
from PIL import Image

async def process_image(
    image_filename: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Process an image artifact."""

    inv_context = tool_context._invocation_context
    artifact_service = inv_context.artifact_service

    # Parse filename:version format
    parts = image_filename.rsplit(":", 1)
    filename_base = parts[0]
    version_to_load = int(parts[1]) if len(parts) > 1 else None

    # Get latest version if not specified
    if version_to_load is None:
        list_versions_method = getattr(artifact_service, "list_versions")
        if inspect.iscoroutinefunction(list_versions_method):
            versions = await list_versions_method(
                app_name=inv_context.app_name,
                user_id=inv_context.user_id,
                session_id=get_original_session_id(inv_context),
                filename=filename_base,
            )
        else:
            versions = await asyncio.to_thread(
                list_versions_method,
                app_name=inv_context.app_name,
                user_id=inv_context.user_id,
                session_id=get_original_session_id(inv_context),
                filename=filename_base,
            )

        if not versions:
            raise FileNotFoundError(f"Image '{filename_base}' not found")
        version_to_load = max(versions)

    # Load artifact
    load_artifact_method = getattr(artifact_service, "load_artifact")
    if inspect.iscoroutinefunction(load_artifact_method):
        artifact_part = await load_artifact_method(
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=filename_base,
            version=version_to_load,
        )
    else:
        artifact_part = await asyncio.to_thread(
            load_artifact_method,
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=filename_base,
            version=version_to_load,
        )

    # Convert to PIL Image
    image_bytes = artifact_part.inline_data.data
    pil_image = Image.open(BytesIO(image_bytes))

    # Process image...
    return {"status": "success", "size": pil_image.size}
```

## Best Practices

1. **Always return structured responses** with at least a `status` field
2. **Use comprehensive logging** with clear log identifiers
3. **Handle errors gracefully** - return error dictionaries, don't raise exceptions
4. **Validate configuration** early in the tool execution
5. **Use type hints** to help the LLM understand parameter types
6. **Write detailed docstrings** - they become the tool description for the LLM
7. **Keep tools focused** - one tool, one responsibility
