# Implementation Plan: Pydantic-Based Configuration for Dynamic Tools

## 1. Objective

Introduce a robust, opt-in mechanism for `DynamicTool` and `DynamicToolProvider` classes to declare their expected configuration using Pydantic models. This will enable automatic validation of YAML `tool_config` blocks and provide type-safe configuration objects to tool implementations, improving developer experience and reducing runtime errors.

## 2. Background

Currently, `DynamicTool` and `DynamicToolProvider` receive their configuration as a raw dictionary (`tool_config`). This requires developers to perform manual validation and dictionary access (e.g., `self.tool_config.get("my_key")`), which is error-prone and lacks type safety.

By leveraging Pydantic, we can shift this validation burden to the framework, catch configuration errors at startup, and provide developers with strongly-typed configuration objects.

## 3. High-Level Plan

1.  **Extend Base Classes:** Add a new class attribute, `config_model`, to `DynamicTool` and `DynamicToolProvider` to allow developers to declaratively link a Pydantic model to their tool.
2.  **Update Tool Loading Logic:** Modify the `load_adk_tools` function in `src/solace_agent_mesh/agent/adk/setup.py` to detect this `config_model`, perform validation, and instantiate tools with the validated Pydantic model instance.
3.  **Ensure Backward Compatibility:** The implementation will be opt-in. If a tool does not define a `config_model`, the framework will fall back to the current behavior of passing a raw dictionary.

## 4. Detailed Implementation Steps

### File: `src/solace_agent_mesh/agent/tools/dynamic_tool.py`

1.  **Import `BaseModel` and `Type`:**
    ```python
    from pydantic import BaseModel
    from typing import Type
    ```
2.  **Update `DynamicTool`:**
    -   Add a `config_model` class attribute.
    -   Update the `__init__` method's type hint for `tool_config`.

    ```python
    class DynamicTool(BaseTool, ABC):
        """
        Base class for dynamic tools...
        """
        config_model: Optional[Type[BaseModel]] = None

        def __init__(self, tool_config: Optional[Union[dict, BaseModel]] = None):
            # ... existing implementation
            self.tool_config = tool_config or {}
    ```

3.  **Update `DynamicToolProvider`:**
    -   Add a `config_model` class attribute.
    -   Update method signatures to accept the validated model.

    ```python
    class DynamicToolProvider(ABC):
        """
        Base class for dynamic tool providers...
        """
        config_model: Optional[Type[BaseModel]] = None
        _decorated_tools: List[Callable] = []

        # ...

        def get_all_tools_for_framework(
            self, tool_config: Optional[Union[dict, BaseModel]] = None
        ) -> List[DynamicTool]:
            # ... existing implementation
            pass

        @abstractmethod
        def create_tools(self, tool_config: Optional[Union[dict, BaseModel]] = None) -> List[DynamicTool]:
            # ... existing implementation
            pass
    ```

### File: `src/solace_agent_mesh/agent/adk/setup.py`

1.  **Import `BaseModel` and `ValidationError`:**
    ```python
    from pydantic import BaseModel, ValidationError
    ```
2.  **Modify `load_adk_tools`:**
    -   Inside the `for tool_config in tools_config:` loop, specifically within the `tool_type == "python"` block where `DynamicTool` and `DynamicToolProvider` classes are handled.
    -   After the `tool_class` is determined, add the validation and instantiation logic.

    ```python
    # ... inside load_adk_tools, after `tool_class` is found
    
    # --- Start of new logic ---
    
    # Check for a Pydantic model declaration on the tool class
    config_model: Optional[Type[BaseModel]] = getattr(tool_class, "config_model", None)
    validated_config: Union[dict, BaseModel] = specific_tool_config # Default to raw dict

    if config_model:
        log.debug(
            "%s Found config_model '%s' for tool class '%s'. Validating...",
            component.log_identifier,
            config_model.__name__,
            tool_class.__name__,
        )
        try:
            # Validate the raw dict and get a Pydantic model instance
            validated_config = config_model.model_validate(specific_tool_config)
            log.debug(
                "%s Successfully validated tool_config for '%s'.",
                component.log_identifier,
                tool_class.__name__,
            )
        except ValidationError as e:
            # Provide a clear error message and raise
            error_msg = (
                f"Configuration error for tool '{tool_class.__name__}' from module '{module_name}'. "
                f"The provided 'tool_config' in your YAML is invalid:\n{e}"
            )
            log.error("%s %s", component.log_identifier, error_msg)
            raise ValueError(error_msg) from e
    
    # --- End of new logic ---

    # Instantiate tools from the class
    if issubclass(tool_class, DynamicToolProvider):
        # Pass the validated_config (either model instance or dict)
        provider_instance = tool_class()
        dynamic_tools = (
            provider_instance.get_all_tools_for_framework(
                tool_config=validated_config
            )
        )
        # ...
    elif issubclass(tool_class, DynamicTool):
        # Pass the validated_config (either model instance or dict)
        tool_instance = tool_class(tool_config=validated_config)
        dynamic_tools = [tool_instance]
    # ...
    ```

## 5. Example Usage (For Documentation)

This is how a developer would use the new feature:

```python
# In my_tools/weather.py
from pydantic import BaseModel, Field
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicToolProvider, DynamicTool

# 1. Define the configuration model
class WeatherProviderConfig(BaseModel):
    api_key: str = Field(..., description="API key for the weather service.")
    default_unit: str = "celsius"

# 2. Create a tool provider and link the config model
class WeatherToolProvider(DynamicToolProvider):
    config_model = WeatherProviderConfig

    def create_tools(self, tool_config: WeatherProviderConfig) -> List[DynamicTool]:
        # tool_config is now a validated WeatherProviderConfig instance
        return [
            GetWeatherTool(tool_config=tool_config),
            GetForecastTool(tool_config=tool_config)
        ]

# 3. Implement a tool that uses the typed config
class GetWeatherTool(DynamicTool):
    def __init__(self, tool_config: WeatherProviderConfig):
        super().__init__(tool_config)
        # Access config with type safety
        self.api_client = WeatherAPI(api_key=self.tool_config.api_key)

    # ... rest of implementation
```

```yaml
# In agent.yaml
# ...
tools:
  - tool_type: python
    component_module: my_tools.weather
    tool_config:
      api_key: "secret-key-here" # Valid
      # default_unit: "fahrenheit" # Optional
```

If `api_key` were missing from the YAML, the agent would fail to start with a clear Pydantic validation error.

## 6. Benefits

-   **Automatic Validation:** Catches configuration errors early.
-   **Type Safety:** Provides full type hinting and autocompletion for `tool_config` within tool code.
-   **Self-Documenting:** The Pydantic model is the single source of truth for a tool's configuration schema.
-   **Backward Compatible:** Existing dynamic tools without a `config_model` will continue to function as before.
