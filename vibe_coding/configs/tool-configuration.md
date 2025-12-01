# Tool Configuration

Defines tools that agents can use to perform actions. Tools extend agent capabilities beyond language understanding to interact with systems, process data, and execute tasks.

## Overview

Tool configuration enables:
- **Python Tools** - Custom Python functions
- **Built-in Tools** - Pre-packaged tool groups
- **MCP Tools** - Model Context Protocol integration
- **Tool Providers** - Dynamic tool generation

## Tool Types

| Type | Description | Use Case |
|------|-------------|----------|
| `python` | Custom Python function | Custom business logic |
| `builtin-group` | Pre-packaged tool group | Common operations |
| `mcp` | Model Context Protocol tool | External MCP servers |

## Python Tool Configuration

### Configuration Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `tool_type` | String | Yes | - | Value: `"python"` |
| `component_module` | String | Yes | - | Python module path |
| `function_name` | String | Yes | - | Function name to call |
| `tool_name` | String | No | `function_name` | Name exposed to LLM |
| `tool_config` | Object | No | `{}` | Configuration passed to tool |
| `init_function` | String | No | - | Initialization function name |
| `cleanup_function` | String | No | - | Cleanup function name |

### Basic Example

```yaml
tools:
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "process_data"
    tool_config:
      max_items: 100
      timeout: 30
```

### Multiple Tool Configurations

Same function with different configs:

```yaml
tools:
  # Formal greeting
  - tool_type: python
    component_module: "greeting_plugin.tools"
    function_name: "greet"
    tool_name: "formal_greeting"
    tool_config:
      style: "formal"
      prefix: "Good day"
  
  # Casual greeting
  - tool_type: python
    component_module: "greeting_plugin.tools"
    function_name: "greet"
    tool_name: "casual_greeting"
    tool_config:
      style: "casual"
      prefix: "Hey"
```

### Tool Function Pattern

```python
from typing import Any, Dict, Optional
from google.adk.tools import ToolContext

async def my_tool(
    param1: str,
    param2: int = 10,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Tool description for the LLM.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Dictionary with status and result
    """
    # Get configuration
    max_value = tool_config.get("max_value", 100) if tool_config else 100
    
    # Tool logic
    result = f"Processed {param1} with {param2}"
    
    return {
        "status": "success",
        "result": result
    }
```

## Built-in Tool Groups

### Available Groups

| Group Name | Description | Tools Included |
|------------|-------------|----------------|
| `artifact_management` | File operations | create_artifact, save_artifact, list_artifacts, get_artifact |
| `text_to_speech` | Audio generation | text_to_speech, multi_speaker_text_to_speech |
| `data_analysis` | Data processing | analyze_data, create_chart, query_database |
| `image_tools` | Image processing | create_image, edit_image, describe_image |
| `audio_tools` | Audio processing | transcribe_audio, generate_audio |

### Configuration

```yaml
tools:
  - tool_type: builtin-group
    group_name: "artifact_management"
  
  - tool_type: builtin-group
    group_name: "text_to_speech"
    tool_config:
      voice: "alloy"
      speed: 1.0
      output_format: "mp3"
```

### Artifact Management Tools

```yaml
tools:
  - tool_type: builtin-group
    group_name: "artifact_management"
```

**Included Tools**:
- `create_artifact` - Create new artifact
- `save_artifact` - Save artifact with metadata
- `list_artifacts` - List user artifacts
- `get_artifact` - Retrieve artifact by name/version
- `delete_artifact` - Delete artifact

### Text-to-Speech Tools

```yaml
tools:
  - tool_type: builtin-group
    group_name: "text_to_speech"
    tool_config:
      voice: "alloy"
      speed: 1.0
      output_format: "mp3"
      default_speakers:
        speaker_1:
          voice: "alloy"
        speaker_2:
          voice: "echo"
```

### Data Analysis Tools

```yaml
tools:
  - tool_type: builtin-group
    group_name: "data_analysis"
    tool_config:
      max_rows: 10000
      enable_caching: true
```

## MCP Tool Configuration

### stdio Transport

For local MCP servers:

```yaml
tools:
  - tool_type: mcp
    server_name: "filesystem"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    transport: "stdio"
    env:
      LOG_LEVEL: "info"
```

### SSE Transport

For remote MCP servers:

```yaml
tools:
  - tool_type: mcp
    server_name: "remote-service"
    transport: "sse"
    url: "${MCP_SERVER_URL}"
```

### MCP with OAuth2

```yaml
tools:
  - tool_type: mcp
    server_name: "atlassian"
    transport: "sse"
    url: "${ATLASSIAN_MCP_URL}"
    authentication:
      type: "oauth2"
      authorization_url: "https://auth.atlassian.com/authorize"
      token_url: "https://auth.atlassian.com/oauth/token"
      client_id: "${ATLASSIAN_CLIENT_ID}"
      client_secret: "${ATLASSIAN_CLIENT_SECRET}"
      scopes: ["read:jira-work", "write:jira-work"]
    manifest:
      tools:
        - name: "create_issue"
          description: "Create a Jira issue"
          inputSchema:
            type: "object"
            properties:
              project: { type: "string" }
              summary: { type: "string" }
              description: { type: "string" }
```

### MCP Configuration Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tool_type` | String | Yes | Value: `"mcp"` |
| `server_name` | String | Yes | MCP server identifier |
| `transport` | String | No | `"stdio"` or `"sse"` (default: `"stdio"`) |
| `command` | String | Yes (stdio) | Command to start server |
| `args` | List | No | Command arguments |
| `env` | Object | No | Environment variables |
| `url` | String | Yes (sse) | SSE endpoint URL |
| `authentication` | Object | No | Authentication config |
| `manifest` | Object | No | Tool manifest for remote MCP |

## Complete Examples

### Calculator Agent Tools

```yaml
tools:
  - tool_type: python
    component_module: "calculator_plugin.tools"
    function_name: "add_numbers"
    tool_name: "add"
    tool_config:
      precision: 2
  
  - tool_type: python
    component_module: "calculator_plugin.tools"
    function_name: "subtract_numbers"
    tool_name: "subtract"
  
  - tool_type: python
    component_module: "calculator_plugin.tools"
    function_name: "divide_numbers"
    tool_name: "divide"
    tool_config:
      check_zero: true
```

### Data Analyst Agent Tools

```yaml
tools:
  # Built-in data analysis
  - tool_type: builtin-group
    group_name: "data_analysis"
    tool_config:
      max_rows_to_analyze: 5000
      enable_query_caching: true
  
  # Built-in artifact management
  - tool_type: builtin-group
    group_name: "artifact_management"
  
  # Custom data processing
  - tool_type: python
    component_module: "data_plugin.tools"
    function_name: "advanced_analysis"
    tool_config:
      algorithms: ["regression", "clustering"]
```

### Multimodal Agent Tools

```yaml
tools:
  # Image generation
  - tool_type: python
    component_module: "image_tools.tools"
    function_name: "create_image_from_description"
    tool_config:
      model: "dall-e-3"
      size: "1024x1024"
  
  # Image analysis
  - tool_type: python
    component_module: "image_tools.tools"
    function_name: "describe_image"
  
  # Audio transcription
  - tool_type: python
    component_module: "audio_tools.tools"
    function_name: "transcribe_audio"
    tool_config:
      model: "whisper-1"
  
  # Text-to-speech
  - tool_type: builtin-group
    group_name: "text_to_speech"
    tool_config:
      voice: "alloy"
```

### MCP Integration Example

```yaml
tools:
  # Local filesystem access
  - tool_type: mcp
    server_name: "filesystem"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
    transport: "stdio"
  
  # Remote Jira integration
  - tool_type: mcp
    server_name: "jira"
    transport: "sse"
    url: "${JIRA_MCP_URL}"
    authentication:
      type: "oauth2"
      authorization_url: "${JIRA_AUTH_URL}"
      token_url: "${JIRA_TOKEN_URL}"
      client_id: "${JIRA_CLIENT_ID}"
      client_secret: "${JIRA_CLIENT_SECRET}"
      scopes: ["read:jira-work", "write:jira-work"]
```

## Tool Configuration Patterns

### Pattern 1: Simple Function

```python
async def simple_tool(
    input_text: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Process input text."""
    return {"status": "success", "result": input_text.upper()}
```

```yaml
tools:
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "simple_tool"
```

### Pattern 2: With Configuration

```python
async def configurable_tool(
    data: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Tool with configuration."""
    max_length = tool_config.get("max_length", 100) if tool_config else 100
    result = data[:max_length]
    return {"status": "success", "result": result}
```

```yaml
tools:
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "configurable_tool"
    tool_config:
      max_length: 200
```

### Pattern 3: With Lifecycle

```python
# In my_plugin/tools.py
async def init_database_tool(host_component, init_config):
    """Initialize database connection."""
    # Setup code
    pass

async def cleanup_database_tool(host_component):
    """Cleanup database connection."""
    # Cleanup code
    pass

async def query_database(
    query: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Query database."""
    # Use initialized connection
    return {"status": "success", "rows": []}
```

```yaml
tools:
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "query_database"
    init_function: "init_database_tool"
    cleanup_function: "cleanup_database_tool"
    tool_config:
      database_url: "${DATABASE_URL}"
```

## Best Practices

### 1. Clear Tool Descriptions

```python
async def my_tool(param: str) -> Dict[str, Any]:
    """
    Clear, concise description of what the tool does.
    
    The LLM uses this description to decide when to use the tool.
    Be specific about inputs, outputs, and behavior.
    
    Args:
        param: Description of the parameter
    
    Returns:
        Dictionary with status and result
    """
    pass
```

### 2. Consistent Return Format

```python
# Success
return {
    "status": "success",
    "result": "data"
}

# Error
return {
    "status": "error",
    "error": "Error message"
}
```

### 3. Use Tool Config for Flexibility

```yaml
tools:
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "api_call"
    tool_config:
      api_endpoint: "${API_ENDPOINT}"
      api_key: "${API_KEY}"
      timeout: 30
```

### 4. Handle Errors Gracefully

```python
async def safe_tool(param: str) -> Dict[str, Any]:
    """Tool with error handling."""
    try:
        result = process(param)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

### 5. Use Type Hints

```python
async def typed_tool(
    text: str,
    count: int = 1,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Tool with proper type hints."""
    pass
```

## Troubleshooting

### Tool Not Found

**Error**: `Tool not found` or `Unknown tool`

**Solutions**:
1. Verify `component_module` path is correct
2. Check `function_name` matches actual function
3. Ensure module is importable
4. Review Python path and imports

### Tool Execution Failed

**Error**: `Tool execution failed`

**Solutions**:
1. Check tool function signature
2. Verify tool returns proper format
3. Review tool logs for errors
4. Test tool function independently

### MCP Server Connection Failed

**Error**: `Failed to connect to MCP server`

**Solutions**:
1. Verify MCP server is running
2. Check command and args are correct
3. Review MCP server logs
4. Test MCP server independently

### Configuration Not Applied

**Issue**: Tool config not being used

**Solutions**:
1. Verify `tool_config` parameter in function
2. Check config is passed correctly
3. Review tool implementation
4. Add logging to verify config values

## Related Documentation

- [Agent Configuration](./agent-configuration.md) - Using tools in agents
- [Lifecycle Functions](./lifecycle-functions.md) - Tool initialization
- [Service Configuration](./service-configuration.md) - Tool dependencies
- [Best Practices](./best-practices.md) - Tool development guidelines