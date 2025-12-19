---
title: Creating Python Tools
sidebar_position: 440
---

# Creating Python Tools

Agent Mesh provides a powerful and unified system for creating custom agent tools using Python. This is the primary way to extend an agent's capabilities with your own business logic, integrate with proprietary APIs, or perform specialized data processing.


## Python Tool Configuration Reference

All Python tools are configured in your agent's YAML file under the `tools` list with `tool_type: python`. The following configuration fields are available:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tool_type` | string | Yes | Must be `python` |
| `tool_name` | string | No | Tool name for the LLM (auto-generated from function/class name if omitted) |
| `tool_description` | string | No | Tool description for the LLM (auto-generated from docstring if omitted) |
| `component_module` | string | Yes | Python module path (e.g., `my_company.tools.calculators`) |
| `function_name` | string | Conditional | Function name within the module (required for function-based tools) |
| `class_name` | string | No | Class name for `DynamicTool` or `DynamicToolProvider` (auto-discovered if only one exists in module) |
| `component_base_path` | string | No | Base path for module resolution (defaults to project root) |
| `tool_config` | object | No | Custom tool configuration passed to the function/class |
| `init_function` | string | No | Name of initialization function to call on agent startup |
| `cleanup_function` | string | No | Name of cleanup function to call on agent shutdown |

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

This is the most straightforward way to create a custom tool. You define a standard Python `async` function, and Agent Mesh automatically introspects its signature and docstring to create the tool definition for the LLM.

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

    greeting_message = f"{greeting_prefix}, {name}! Welcome to Agent Mesh!"

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

The YAML configuration is very similar. You can either specify the `class_name` or let Agent Mesh auto-discover it if it's the only `DynamicTool` in the module.

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

You only need a single YAML block. Agent Mesh will automatically detect the `DynamicToolProvider` and use it to load all the tools it generates.

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

---

## Managing Tool Lifecycles with `init` and `cleanup`

For tools that need to manage resources—such as database connections, API clients, or temporary files—Agent Mesh provides optional `init` and `cleanup` lifecycle hooks. These allow you to run code when the agent starts up and shuts down, ensuring that resources are acquired and released gracefully.

There are two ways to define these hooks:
- **YAML-based (`init_function`, `cleanup_function`):** A flexible method that works for *any* Python tool, including simple function-based ones.
- **Class-based (`init`, `cleanup` methods):** The idiomatic and recommended way for `DynamicTool` and `DynamicToolProvider` classes.

### YAML-Based Lifecycle Hooks

You can add `init_function` and `cleanup_function` to any Python tool's configuration in your agent's YAML. The lifecycle functions must be defined in the same module as the tool itself.

#### Step 1: Define the Tool and Hook Functions

In your tool's Python file (e.g., `src/my_agent/db_tools.py`), define the tool function and its corresponding `init` and `cleanup` functions. These functions must be `async` and will receive the agent component instance and the tool's configuration model object as arguments.

```python
# src/my_agent/db_tools.py
from solace_agent_mesh.agent.sac.component import SamAgentComponent
from solace_agent_mesh.agent.tools.tool_config_types import AnyToolConfig
from google.adk.tools import ToolContext
from typing import Dict, Any

# --- Lifecycle Hooks ---

async def initialize_db_connection(component: SamAgentComponent, tool_config_model: AnyToolConfig):
    """Initializes a database connection and stores it for the agent to use."""
    print("INFO: Initializing database connection...")
    # In a real scenario, you would create a client instance
    db_client = {"connection_string": tool_config_model.tool_config.get("connection_string")}
    # Store the client in a shared state accessible by the component
    component.set_agent_specific_state("db_client", db_client)
    print("INFO: Database client initialized.")

async def close_db_connection(component: SamAgentComponent, tool_config_model: AnyToolConfig):
    """Retrieves and closes the database connection."""
    print("INFO: Closing database connection...")
    db_client = component.get_agent_specific_state("db_client")
    if db_client:
        # In a real scenario, you would call db_client.close()
        print("INFO: Database connection closed.")

# --- Tool Function ---

async def query_database(query: str, tool_context: ToolContext, **kwargs) -> Dict[str, Any]:
    """Queries the database using the initialized connection."""
    host_component = tool_context._invocation_context.agent.host_component
    db_client = host_component.get_agent_specific_state("db_client")
    if not db_client:
        return {"error": "Database connection not initialized."}
    # ... use db_client to run query ...
    return {"result": "some data"}
```

#### Step 2: Configure the Hooks in YAML

In your YAML configuration, reference the lifecycle functions by name. The framework will automatically look for them in the `component_module`.

```yaml
# In your agent's app_config:
tools:
  - tool_type: python
    component_module: "my_agent.db_tools"
    function_name: "query_database"
    tool_config:
      connection_string: "postgresql://user:pass@host/db"

    # Initialize the tool on startup
    init_function: "initialize_db_connection"

    # Clean up the tool on shutdown
    cleanup_function: "close_db_connection"
```

### Class-Based Lifecycle Methods (for `DynamicTool`)

For tools built with `DynamicTool` or `DynamicToolProvider`, the recommended approach is to override the `init` and `cleanup` methods directly within the class. This co-locates the entire tool's logic and improves encapsulation.

**Example: Adding Lifecycle Methods to a `DynamicTool`**

Here, we extend a `DynamicTool` to manage its own API client.

```python
# src/my_agent/api_tool.py
from solace_agent_mesh.agent.sac.component import SamAgentComponent
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool
from solace_agent_mesh.agent.tools.tool_config_types import AnyToolConfig
# Assume WeatherApiClient is a custom class for an external service
from my_agent.api_client import WeatherApiClient

class WeatherTool(DynamicTool):
    """A dynamic tool that fetches weather and manages its own API client."""

    async def init(self, component: "SamAgentComponent", tool_config: "AnyToolConfig") -> None:
        """Initializes the API client when the agent starts."""
        print("INFO: Initializing Weather API client...")
        # self.tool_config is the validated Pydantic model or dict from YAML
        api_key = self.tool_config.get("api_key")
        self.api_client = WeatherApiClient(api_key=api_key)
        print("INFO: Weather API client initialized.")

    async def cleanup(self, component: "SamAgentComponent", tool_config: "AnyToolConfig") -> None:
        """Closes the API client connection when the agent shuts down."""
        print("INFO: Closing Weather API client...")
        if hasattr(self, "api_client"):
            await self.api_client.close()
            print("INFO: Weather API client closed.")

    # ... other required properties like tool_name, tool_description, etc. ...

    async def _run_async_impl(self, args: dict, **kwargs) -> dict:
        """Uses the initialized client to perform its task."""
        location = args.get("location")
        if not hasattr(self, "api_client"):
            return {"error": "API client not initialized. Check lifecycle hooks."}
        weather_data = await self.api_client.get_weather(location)
        return {"weather": weather_data}
```

The YAML configuration remains simple, as the lifecycle logic is now part of the tool's code.

```yaml
# In your agent's app_config:
tools:
  - tool_type: python
    component_module: "my_agent.api_tool"
    class_name: "WeatherTool"
    tool_config:
      api_key: ${WEATHER_API_KEY}
```

### Execution Order and Guarantees

It's important to understand the order in which lifecycle hooks are executed, especially if you mix both YAML-based and class-based methods for a single tool.

- **Initialization (`init`):** All `init` hooks are awaited during agent startup. A failure in any `init` hook will prevent the agent from starting.
  1. The YAML-based `init_function` is executed first.
  2. The class-based `init()` method is executed second.

- **Cleanup (`cleanup`):** All registered `cleanup` hooks are executed during agent shutdown. They run in **LIFO (Last-In, First-Out)** order relative to initialization.
  1. The class-based `cleanup()` method is executed first.
  2. The YAML-based `cleanup_function` is executed second.

This LIFO order for cleanup is intuitive: the resource that was initialized last is the first one to be torn down.

---

## Adding Validated Configuration to Dynamic Tools

For any class-based tool (`DynamicTool` or `DynamicToolProvider`) that requires configuration, this is the recommended pattern. By linking a Pydantic model to your tool class, you can add automatic validation and type safety to your `tool_config`. This provides several key benefits:

- **Automatic Validation:** The agent will fail to start if the YAML configuration doesn't match your model, providing clear error messages.
- **Type Safety:** Inside your tool, `self.tool_config` is a fully typed Pydantic object, not a dictionary, enabling autocompletion and preventing common errors.
- **Self-Documentation:** The Pydantic model itself serves as clear, machine-readable documentation for your tool's required configuration.

### Example 1: Using a Pydantic Model with a Single `DynamicTool`

This example shows how to add a validated configuration to a standalone `DynamicTool` class.

#### Step 1: Define the Model and Tool Class

In your tools file, define a `pydantic.BaseModel` for your configuration. Then, in your `DynamicTool` class, link to it using the `config_model` class attribute.

```python
# src/my_agent/weather_tools.py
from typing import Dict, Any
from pydantic import BaseModel, Field
from google.genai import types as adk_types
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool

# 1. Define the configuration model
class WeatherConfig(BaseModel):
    api_key: str = Field(..., description="The API key for the weather service.")
    default_unit: str = Field(default="celsius", description="The default temperature unit.")

# 2. Create a tool and link the config model
class GetCurrentWeatherTool(DynamicTool):
    config_model = WeatherConfig

    def __init__(self, tool_config: WeatherConfig):
        super().__init__(tool_config)
        # self.tool_config is now a validated WeatherConfig instance
        # You can safely access attributes with type safety
        self.api_key = self.tool_config.api_key
        self.unit = self.tool_config.default_unit

    @property
    def tool_name(self) -> str:
        return "get_current_weather"

    @property
    def tool_description(self) -> str:
        return f"Get the current weather. The default unit is {self.unit}."

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "location": adk_types.Schema(type=adk_types.Type.STRING, description="The city and state/country."),
            },
            required=["location"],
        )

    async def _run_async_impl(self, args: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        # ... implementation using self.api_key ...
        return {"weather": f"Sunny in {args['location']}"}
```

#### Step 2: Configure the Tool in YAML

The YAML configuration remains simple. The framework handles the validation against your Pydantic model automatically.

```yaml
# In your agent's app_config:
tools:
  - tool_type: python
    component_module: "my_agent.weather_tools"
    # The framework will auto-discover the GetCurrentWeatherTool class
    tool_config:
      api_key: ${WEATHER_API_KEY}
      default_unit: "fahrenheit" # Optional, overrides the model's default
```

If you were to forget `api_key` in the YAML, the agent would fail to start and print a clear error message indicating that the `api_key` field is required, making debugging configuration issues much easier.

### Example 2: Using a Pydantic Model with a `DynamicToolProvider`

The same pattern applies to tool providers, allowing you to pass a validated, type-safe configuration object to your tool factory.

#### Step 1: Define the Model and Provider Class

```python
# src/my_agent/weather_tools_provider.py
from typing import List
from pydantic import BaseModel, Field
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool, DynamicToolProvider
# ... assume GetCurrentWeatherTool is defined in this file or imported ...

# 1. Define the configuration model
class WeatherProviderConfig(BaseModel):
    api_key: str = Field(..., description="The API key for the weather service.")
    default_unit: str = Field(default="celsius", description="The default temperature unit.")

# 2. Create a provider and link the config model
class WeatherToolProvider(DynamicToolProvider):
    config_model = WeatherProviderConfig

    def create_tools(self, tool_config: WeatherProviderConfig) -> List[DynamicTool]:
        # The framework passes a validated WeatherProviderConfig instance here
        return [
            GetCurrentWeatherTool(tool_config=tool_config)
            # You could create other tools here that also use the config
        ]
```

#### Step 2: Configure the Provider in YAML

```yaml
# In your agent's app_config:
tools:
  - tool_type: python
    component_module: "my_agent.weather_tools_provider"
    # The framework will auto-discover the WeatherToolProvider
    tool_config:
      api_key: ${WEATHER_API_KEY}
      default_unit: "fahrenheit" # Optional, overrides the model's default
```

---

## Complete Configuration Examples

### Example 1: Simple Function-Based Tool with All Options

```yaml
tools:
  - tool_type: python
    tool_name: "custom_calculator"
    tool_description: "Performs custom mathematical calculations"
    component_module: "my_company.tools.calculators"
    function_name: "calculate_advanced_metrics"
    component_base_path: "src/plugins"
    tool_config:
      precision: 6
      use_cache: true
```

### Example 2: DynamicTool Class with Lifecycle Hooks

```yaml
tools:
  - tool_type: python
    component_module: "my_agent.db_tools"
    class_name: "DatabaseQueryTool"
    tool_config:
      connection_string: "postgresql://user:pass@host/db"
      max_rows: 1000
```

### Example 3: Function-Based Tool with YAML Lifecycle Hooks

```yaml
tools:
  - tool_type: python
    component_module: "my_agent.db_tools"
    function_name: "query_database"
    init_function: "initialize_db_connection"
    cleanup_function: "close_db_connection"
    tool_config:
      connection_string: "postgresql://user:pass@host/db"
```

### Example 4: DynamicToolProvider for Multiple Tools

```yaml
tools:
  - tool_type: python
    component_module: "my_agent.database_tools"
    # The provider will be auto-discovered and will create multiple tools
    tool_config:
      connection_string: ${DB_CONNECTION_STRING}
      max_rows: 1000
```

---

For additional ways to extend agent capabilities:
- **Built-in Tools**: See [Configuring Built-in Tools](../components/builtin-tools/builtin-tools.md) for pre-packaged tools for file management, data analysis, web requests, and more
- **MCP Integration**: See [MCP Integration Tutorial](../developing/tutorials/mcp-integration.md) for connecting to Model Context Protocol servers to access external tools and resources