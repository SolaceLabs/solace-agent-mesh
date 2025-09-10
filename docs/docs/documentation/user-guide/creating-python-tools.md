---
title: Creating Python Tools
sidebar_position: 35
---

# Creating Python Tools

Solace Agent Mesh (SAM) provides a powerful and unified system for creating custom agent tools using Python. This is the primary way to extend an agent's capabilities with your own business logic, integrate with proprietary APIs, or perform specialized data processing.

This guide covers the different patterns for creating custom tools, all of which are configured using the versatile `tool_type: python`.

## Tool Creation Patterns

There are three primary patterns for creating Python tools, ranging from simple to advanced. You can choose the best pattern for your needs, and even mix and match them within the same project.

| Pattern                   | Best For                                                                 | Key Feature                               |
| ------------------------- | ------------------------------------------------------------------------ | ----------------------------------------- |
| **Function-Based**        | Simple, self-contained tools with static inputs.                         | Quick and easy; uses function signature.  |
| **Single `DynamicTool` Class** | Tools that require complex logic or a programmatically defined interface. | Full control over the tool's definition.  |
| **`DynamicToolProvider` Class** | Generating multiple related tools from a single, configurable source.    | Maximum scalability and code reuse.       |

All three patterns are configured in your agent's YAML file under the `tools` list with `tool_type: python`.

---

## Pattern 1: Simple Function-Based Tools

This is the most straightforward way to create a custom tool. You define a standard Python `async` function, and SAM automatically introspects its signature and docstring to create the tool definition for the LLM.

### Step 1: Write the Tool Function

Create a Python file (e.g., `src/my_agent/tools.py`) and define your tool.

```python
# src/my_agent/tools.py
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
        name: The name of the person to greet.

    Returns:
        A dictionary with the greeting message.
    """
    greeting_prefix = "Hello"
    if tool_config:
        greeting_prefix = tool_config.get("greeting_prefix", "Hello")

    greeting_message = f"{greeting_prefix}, {name}! Welcome to Solace Agent Mesh!"

    return {
        "status": "success",
        "message": greeting_message
    }
```

**Key Requirements:**
- The function must be `async def`.
- The function's docstring is used as the tool's `description` for the LLM.
- Type hints (`str`, `int`, `bool`) are used to generate the parameter schema.
- The function should accept `tool_context` and `tool_config` as optional keyword arguments to receive framework context and YAML configuration.

### Step 2: Configure the Tool

In your agent's YAML configuration, add a `tool_type: python` block and point it to your function.

```yaml
# In your agent's app_config:
tools:
  - tool_type: python
    component_module: "my_agent.tools"
    function_name: "greet_user"
    tool_config:
      greeting_prefix: "Greetings"
```

- `component_module`: The Python module path to your tools file.
- `function_name`: The exact name of the function to load.
- `tool_config`: An optional dictionary passed to your tool at runtime.

---

## Pattern 2: Advanced Single-Class Tools

For tools that require more complex logic—such as defining their interface programmatically based on configuration—you can use a class that inherits from `DynamicTool`.

### Step 1: Create the `DynamicTool` Class

Instead of a function, define a class that implements the `DynamicTool` abstract base class.

```python
# src/my_agent/tools.py
from typing import Optional, Dict, Any
from google.genai import types as adk_types
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool

class WeatherTool(DynamicTool):
    """A dynamic tool that fetches current weather information."""

    @property
    def tool_name(self) -> str:
        return "get_current_weather"

    @property
    def tool_description(self) -> str:
        return "Get the current weather for a specified location."

    @property
    def parameters_schema(self) -> adk_types.Schema:
        # Programmatically define the tool's parameters
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "location": adk_types.Schema(type=adk_types.Type.STRING, description="The city and state/country."),
                "units": adk_types.Schema(type=adk_types.Type.STRING, enum=["celsius", "fahrenheit"], nullable=True),
            },
            required=["location"],
        )

    async def _run_async_impl(self, args: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        location = args["location"]
        # Access config via self.tool_config
        api_key = self.tool_config.get("api_key")
        if not api_key:
            return {"status": "error", "message": "API key not configured"}
        # ... implementation to call weather API ...
        return {"status": "success", "weather": "Sunny"}
```

### Step 2: Configure the Tool

The YAML configuration is very similar. You can either specify the `class_name` or let SAM auto-discover it if it's the only `DynamicTool` in the module.

```yaml
# In your agent's app_config:
tools:
  - tool_type: python
    component_module: "my_agent.tools"
    # class_name: WeatherTool # Optional if it's the only one
    tool_config:
      api_key: ${WEATHER_API_KEY}
```

---

## Pattern 3: The Tool Provider Factory

This is the most powerful pattern, designed for generating multiple, related tools from a single module and configuration block. It's perfect for creating toolsets based on external schemas, database tables, or other dynamic sources.

### Step 1: Create the Provider and Tools

In your tools module, you define your `DynamicTool` classes as before, but you also create a **provider** class that inherits from `DynamicToolProvider`. This provider acts as a factory.

You can also use the `@register_tool` decorator on simple functions to have them automatically included by the provider.

```python
# src/my_agent/database_tools.py
from typing import Optional, Dict, Any, List
from google.genai import types as adk_types
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool, DynamicToolProvider

# --- Tool Implementations ---
class DatabaseQueryTool(DynamicTool):
    # ... (implementation as in previous examples) ...
    pass

class DatabaseSchemaTool(DynamicTool):
    # ... (implementation as in previous examples) ...
    pass

# --- Tool Provider Implementation ---
class DatabaseToolProvider(DynamicToolProvider):
    """A factory that creates all database-related tools."""

    # Use a decorator for a simple, function-based tool

    def create_tools(self, tool_config: Optional[dict] = None) -> List[DynamicTool]:
        """
        Generates a list of all database tools, passing the shared
        configuration to each one.
        """
        # 1. Create tools from any decorated functions in this module
        tools = self._create_tools_from_decorators(tool_config)

        # 2. Programmatically create and add more complex tools
        if tool_config and tool_config.get("connection_string"):
            tools.append(DatabaseQueryTool(tool_config=tool_config))
            tools.append(DatabaseSchemaTool(tool_config=tool_config))

        return tools

# NOTE that you must use the decorator outside of any class with the provider's class name.
@DatabaseToolProvider.register_tool
async def get_database_server_version(tool_config: dict, **kwargs) -> dict:
    """Returns the version of the connected PostgreSQL server."""
    # ... implementation ...
    return {"version": "PostgreSQL 15.3"}

```

### Step 2: Configure the Provider

You only need a single YAML block. SAM will automatically detect the `DynamicToolProvider` and use it to load all the tools it generates.

```yaml
# In your agent's app_config:
tools:
  # This single block loads get_database_server_version,
  # execute_database_query, and get_database_schema.
  - tool_type: python
    component_module: "my_agent.database_tools"
    tool_config:
      connection_string: ${DB_CONNECTION_STRING}
      max_rows: 1000
```

This approach is incredibly scalable, as one configuration entry can bootstrap an entire suite of dynamically generated tools.
