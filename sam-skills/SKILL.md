---
name: solace-agent-mesh-plugin-creator
description: Guide for creating Solace Agent Mesh agent plugins. Use when creating SAM plugins, agent plugins, adding custom tools (Python, MCP, or built-in), or working with SAM plugin architecture. Covers directory structure, configuration, Python tool implementation patterns (function-based, DynamicTool, DynamicToolProvider), lifecycle management, building, and testing workflows.
---

# Solace Agent Mesh Plugin Creator

This skill guides you through creating agent plugins for Solace Agent Mesh (SAM). Plugins are the recommended way to create reusable, distributable agents with custom tools.

## When to Use This Skill

- Creating a new SAM agent plugin
- Adding Python tools to an existing plugin
- Understanding plugin architecture and structure
- Configuring agent behavior and tools
- Building and packaging plugins

## Quick Start Workflow

### 1. Create Plugin Structure

Use SAM CLI to initialize:

```bash
sam plugin create my-plugin --type agent
```

This creates:
```
my-plugin/
├── src/
│   └── my_plugin/
│       ├── __init__.py
│       └── tools.py
├── config.yaml
├── pyproject.toml
└── README.md
```

### 2. Implement Tools

Edit `src/my_plugin/tools.py`. See `references/tool-patterns.md` for the three implementation patterns:

**Pattern 1: Simple Function** (recommended for most cases)
```python
async def my_tool(
    param: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Tool description for LLM."""
    # Implementation
    return {"status": "success", "result": "..."}
```

**Pattern 2: DynamicTool Class** (for complex logic)
**Pattern 3: DynamicToolProvider** (for multiple related tools)

See `references/tool-patterns.md` for detailed examples.

### 3. Configure Agent

Edit `config.yaml`:

```yaml
app_config:
  agent_name: "MyAgent"
  display_name: "My Agent"

  instruction: |
    You are an agent that...

  tools:
    - tool_type: python
      component_module: "my_plugin.tools"
      function_name: "my_tool"
      tool_config:
        param1: "value1"
```

See `references/configuration-reference.md` for complete options.

### 4. Add Dependencies

Edit `pyproject.toml`:

```toml
dependencies = [
    "requests>=2.31.0",
    "pillow>=10.0.0",
]
```

### 5. Build & Install

```bash
# Build plugin wheel
sam plugin build

# Install in SAM project
cd /path/to/sam-project
sam plugin add my-plugin --plugin /path/to/my-plugin/dist/my_plugin-0.1.0-py3-none-any.whl
```

### 6. Run & Test

```bash
# Run all agents
sam run

# Or run specific agent
sam run configs/agents/my-plugin.yaml

# Quick debug mode (no install needed)
cd my-plugin/src
sam run ../config.yaml
```

## Directory Structure

```
my-plugin/
├── src/
│   └── my_plugin/              # Python package
│       ├── __init__.py          # Package init
│       ├── tools.py             # Tool implementations
│       └── lifecycle.py         # Optional: init/cleanup functions
├── config.yaml                  # Agent configuration template
├── pyproject.toml               # Python package metadata
└── README.md                    # Plugin documentation
```

## Key Concepts

### Tools

Tools are Python functions that give your agent capabilities. Three patterns:

1. **Function-based** - Simple async functions (use this for most tools)
2. **DynamicTool class** - For complex logic or programmatic interfaces
3. **DynamicToolProvider** - For generating multiple related tools

Always:
- Use `async def`
- Accept `tool_context` and `tool_config` parameters
- Return `Dict[str, Any]` with at least `status` field
- Write comprehensive docstrings (LLM uses these)

### Configuration

`config.yaml` defines:
- Agent identity (name, namespace, instructions)
- LLM model configuration
- Tools list and their configurations
- Services (session, artifact storage)
- Agent card (metadata, skills)

Uses placeholders like `__COMPONENT_PASCAL_CASE_NAME__` that get replaced when plugin is instantiated.

### Artifacts

Tools can save/load files via the artifact service:
- **Save**: Use `save_artifact_with_metadata` helper
- **Load**: Handle `filename:version` format, check async/sync methods

See `references/artifact-handling.md` for examples.

### Lifecycle Functions

Optional init/cleanup functions in `lifecycle.py`:
- **init_function** - Runs on agent start (database connections, etc.)
- **cleanup_function** - Runs on shutdown (close connections, save state)

See `references/lifecycle-functions.md` for patterns.

## Tool Implementation Patterns

### Pattern 1: Function-Based (Recommended)

```python
# src/my_plugin/tools.py
from typing import Any, Dict, Optional
from google.adk.tools import ToolContext
import logging

log = logging.getLogger(__name__)

async def process_text(
    text: str,
    uppercase: bool = False,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process input text with optional uppercase conversion.

    Args:
        text: Input text to process
        uppercase: Whether to convert to uppercase
    """
    log.info(f"Processing text: {text[:50]}...")

    result = text.upper() if uppercase else text

    return {
        "status": "success",
        "original": text,
        "processed": result
    }
```

Configure in `config.yaml`:
```yaml
tools:
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "process_text"
    tool_config: {}
```

### Working with Files

For tools that need to load/save files, see the complete pattern in `references/artifact-handling.md`.

Key points:
- Parse `filename:version` format
- Handle both async and sync artifact service methods
- Use `get_original_session_id` helper
- Include metadata when saving

## Configuration Details

### Agent Instructions

The `instruction` field is the system prompt:

```yaml
instruction: |
  You are a helpful agent that can process text and images.

  Your capabilities:
  1. Process text with various transformations
  2. Analyze images and extract information
  3. Save and retrieve files

  Always be clear and concise in your responses.
```

### Tool Configuration

Each tool can have custom configuration:

```yaml
tools:
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "api_call_tool"
    tool_config:
      api_endpoint: ${API_ENDPOINT}
      api_key: ${API_KEY}
      timeout: 30
```

Access in tool via `tool_config.get("api_endpoint")`.

### Agent Card

Describes agent capabilities for discovery:

```yaml
agent_card:
  description: "Agent that processes text and images"
  defaultInputModes: ["text", "file"]
  defaultOutputModes: ["text", "file"]
  skills:
    - id: "process_text"
      name: "Process Text"
      description: "Transform and process text input"
```

Skill IDs should match tool names.

## Building & Packaging

### Build Plugin

```bash
sam plugin build
```

Creates wheel file in `dist/` directory.

### Install in Project

```bash
cd /path/to/sam-project
sam plugin add my-agent --plugin /path/to/plugin/dist/my_plugin-0.1.0-py3-none-any.whl
```

This:
- Installs plugin as Python package
- Creates config file in `configs/agents/`
- Makes tools importable

### Debug Mode

For rapid development without reinstalling:

```bash
cd my-plugin/src
sam run ../config.yaml
```

Changes take effect immediately.

## Templates

All template files are in `assets/templates/`:

- `config_template.yaml` - Complete agent configuration
- `pyproject_template.toml` - Python package metadata
- `README_template.md` - Plugin README
- `tools_template.py` - Example tool implementations
- `__init___template.py` - Empty package init file

These use placeholders that SAM CLI replaces during plugin creation.

## Common Patterns

### Multiple Tool Configurations

Reuse same function with different configs:

```yaml
tools:
  # Formal greeting
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "greet"
    tool_name: "formal_greeting"
    tool_config:
      prefix: "Good day"

  # Casual greeting
  - tool_type: python
    component_module: "my_plugin.tools"
    function_name: "greet"
    tool_name: "casual_greeting"
    tool_config:
      prefix: "Hey"
```

### Built-in Tools

Include SAM built-in tool groups:

```yaml
tools:
  - tool_type: builtin-group
    group_name: "artifact_management"
```

## Reference Documentation

- `references/tool-patterns.md` - Detailed examples of all three patterns
- `references/configuration-reference.md` - Complete YAML configuration options
- `references/artifact-handling.md` - File operations and artifact service
- `references/lifecycle-functions.md` - Init and cleanup function patterns

## Example Plugin

The object-detection plugin (recently built) demonstrates:
- Function-based tools
- Image artifact handling
- YOLO model integration
- Configuration with dependencies
- Complete working example

Refer to it as a reference implementation.

## Best Practices

1. **Tool Design**
   - One tool, one responsibility
   - Comprehensive docstrings (LLM uses these!)
   - Return structured responses with `status` field
   - Handle errors gracefully

2. **Configuration**
   - Use environment variables for secrets
   - Validate configuration early
   - Comment YAML thoroughly

3. **Testing**
   - Use debug mode during development
   - Test tools independently with mocks
   - Verify plugin builds correctly

4. **Logging**
   - Use consistent log identifiers
   - Log important events and errors
   - Include context in log messages

## Troubleshooting

**Plugin won't import**: Ensure `src/` directory structure matches package name in `pyproject.toml`

**Tool not found**: Verify `component_module` path and `function_name` match actual code

**Configuration errors**: Check placeholder replacement and YAML syntax

**Artifact errors**: Confirm artifact service is configured and accessible

For more help, consult the SAM documentation at https://solacelabs.github.io/solace-agent-mesh/
