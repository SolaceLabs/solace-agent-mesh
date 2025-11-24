# Configuration Reference

Complete reference for `config.yaml` in Solace Agent Mesh agent plugins.

## File Structure

```yaml
# Plugin Metadata (at top of file)
# Name: plugin-name
# Version: 0.1.0
# Description: Plugin description
# Author: Name <email@example.com>

log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: component-name.log

# Include shared config or define inline
!include ../shared_config.yaml
# OR define shared_config section inline (see below)

apps:
  - name: component-name-app
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      # Agent identity
      namespace: ${NAMESPACE}
      supports_streaming: true
      agent_name: "AgentName"
      display_name: "Agent Display Name"

      # LLM configuration
      model: *general_model

      # Agent instructions (system prompt)
      instruction: |
        Agent instructions here...

      # Tools configuration
      tools:
        - tool_type: python
          component_module: "plugin_name.tools"
          function_name: "tool_function"
          tool_config:
            # Tool-specific configuration

      # Services
      session_service: *default_session_service
      artifact_service: *default_artifact_service

      # Artifact handling
      artifact_handling_mode: "reference"
      enable_embed_resolution: true
      enable_artifact_content_instruction: true

      # Agent card (metadata)
      agent_card:
        description: "Agent description"
        defaultInputModes: ["text", "file"]
        defaultOutputModes: ["text", "file"]
        skills:
          - id: "skill_id"
            name: "Skill Name"
            description: "Skill description"

      # Publishing & discovery
      agent_card_publishing:
        interval_seconds: 10
      agent_discovery:
        enabled: false

      # Inter-agent communication
      inter_agent_communication:
        allow_list: []
        request_timeout_seconds: 30
```

## Placeholders

Templates use these placeholders that get replaced during plugin instantiation:

- `__PLUGIN_KEBAB_CASE_NAME__` - Plugin name in kebab-case (e.g., "my-plugin")
- `__PLUGIN_SNAKE_CASE_NAME__` - Plugin name in snake_case (e.g., "my_plugin")
- `__PLUGIN_PASCAL_CASE_NAME__` - Plugin name in PascalCase (e.g., "MyPlugin")
- `__PLUGIN_SPACED_NAME__` - Plugin name with spaces (e.g., "My Plugin")
- `__PLUGIN_VERSION__` - Plugin version (e.g., "0.1.0")
- `__PLUGIN_DESCRIPTION__` - Plugin description
- `__PLUGIN_AUTHOR_NAME__` - Author name
- `__PLUGIN_AUTHOR_EMAIL__` - Author email
- `__COMPONENT_KEBAB_CASE_NAME__` - Component instance name in kebab-case
- `__COMPONENT_PASCAL_CASE_NAME__` - Component instance name in PascalCase
- `__COMPONENT_SPACED_CAPITALIZED_NAME__` - Component with spaces and capitals
- `__COMPONENT_UPPER_SNAKE_CASE_NAME__` - Component in UPPER_SNAKE_CASE

## Logging Configuration

```yaml
log:
  stdout_log_level: INFO   # Console log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  log_file_level: DEBUG    # File log level
  log_file: agent-name.log # Log file path
```

## Shared Configuration

Either include from external file or define inline:

```yaml
# Option 1: Include shared config
!include ../shared_config.yaml

# Option 2: Define inline
shared_config:
  - broker_connection: &broker_connection
      dev_mode: ${SOLACE_DEV_MODE, false}
      broker_url: ${SOLACE_BROKER_URL, ws://localhost:8008}
      broker_username: ${SOLACE_BROKER_USERNAME, default}
      broker_password: ${SOLACE_BROKER_PASSWORD, default}
      broker_vpn: ${SOLACE_BROKER_VPN, default}
      temporary_queue: ${USE_TEMPORARY_QUEUES, true}

  - models:
    general: &general_model
      model: ${LLM_SERVICE_GENERAL_MODEL_NAME}
      api_base: ${LLM_SERVICE_ENDPOINT}
      api_key: ${LLM_SERVICE_API_KEY}

  - services:
    session_service: &default_session_service
      type: "memory"
      default_behavior: "PERSISTENT"

    artifact_service: &default_artifact_service
      type: "filesystem"
      base_path: "/tmp/samv2"
      artifact_scope: namespace
```

## App Configuration

```yaml
apps:
  - name: my-agent-app
    app_base_path: .                           # Base path for module resolution
    app_module: solace_agent_mesh.agent.sac.app  # SAM application module
    broker:
      <<: *broker_connection                   # Broker configuration from shared_config
```

## Agent Identity

```yaml
app_config:
  namespace: ${NAMESPACE}                      # Agent namespace (env var)
  supports_streaming: true                     # Enable streaming responses
  agent_name: "MyAgent"                        # Internal agent name
  display_name: "My Agent Display Name"        # Human-readable name
```

## Model Configuration

```yaml
app_config:
  model: *general_model  # Reference to shared model config

# Or define inline:
  model:
    model: "gpt-4"                             # Model identifier
    api_base: "https://api.openai.com/v1"      # API endpoint
    api_key: ${OPENAI_API_KEY}                 # API key from env var
```

## Agent Instructions

The system prompt that defines agent behavior:

```yaml
app_config:
  instruction: |
    You are a helpful assistant that...

    Your capabilities include:
    1. Capability one
    2. Capability two

    Always be polite and clear in your responses.
```

## Tools Configuration

### Python Function Tool

```yaml
tools:
  - tool_type: python
    component_module: "my_plugin.tools"        # Python module path
    component_base_path: .                     # Base path for imports
    function_name: "my_tool_function"          # Function name
    tool_name: "custom_tool_name"              # Optional: Override function name
    tool_description: "Custom description"     # Optional: Override docstring
    tool_config:                               # Optional: Tool-specific config
      param1: "value1"
      param2: ${ENV_VAR}
```

### Python Class Tool

```yaml
tools:
  - tool_type: python
    component_module: "my_plugin.tools"
    component_base_path: .
    class_name: "MyDynamicTool"                # DynamicTool class name
    tool_config:
      api_key: ${API_KEY}
```

### Built-in Tool Group

```yaml
tools:
  - tool_type: builtin-group
    group_name: "artifact_management"          # Pre-defined tool group
    tool_config: {}                            # Optional configuration
```

### MCP Tool

```yaml
tools:
  - tool_type: mcp
    connection_params:
      type: stdio
      command: "my-mcp-server"
      args: ["--arg1", "value1"]
      timeout: 30
```

## Services Configuration

### Session Service

```yaml
app_config:
  session_service:
    type: "memory"                             # or "redis", "database"
    default_behavior: "PERSISTENT"             # or "EPHEMERAL"
```

### Artifact Service

```yaml
app_config:
  artifact_service:
    type: "filesystem"                         # or "s3", "gcs"
    base_path: "/tmp/samv2"                    # Storage location
    artifact_scope: namespace                  # "namespace", "app", or "custom"
```

## Artifact Handling

```yaml
app_config:
  artifact_handling_mode: "reference"          # How artifacts are passed to tools
  enable_embed_resolution: true                # Resolve embedded artifact references
  enable_artifact_content_instruction: true    # Include artifact content in instructions
```

## Agent Card

Metadata describing the agent's capabilities:

```yaml
app_config:
  agent_card:
    description: "Agent description shown to users"
    defaultInputModes: ["text", "file"]        # Supported input types
    defaultOutputModes: ["text", "file"]       # Supported output types
    skills:
      - id: "skill_1"                          # Unique skill ID (matches tool name)
        name: "Skill Name"                     # Human-readable name
        description: "What this skill does"    # Skill description
      - id: "skill_2"
        name: "Another Skill"
        description: "Another capability"
```

## Agent Discovery & Publishing

```yaml
app_config:
  agent_card_publishing:
    interval_seconds: 10                       # How often to publish agent card

  agent_discovery:
    enabled: false                             # Enable discovery by other agents

  inter_agent_communication:
    allow_list: []                             # List of agents allowed to communicate
    request_timeout_seconds: 30                # Timeout for inter-agent requests
```

## Lifecycle Functions

```yaml
app_config:
  agent_init_function:
    module: "my_plugin.lifecycle"              # Module containing init function
    name: "initialize_agent"                   # Function name
    base_path: .                               # Base path for imports
    config:                                    # Passed to init function
      startup_message: "Agent starting..."
      log_level: "INFO"

  agent_cleanup_function:
    module: "my_plugin.lifecycle"
    name: "cleanup_agent"
    base_path: .
```

## Environment Variables

Use `${VAR_NAME}` syntax with optional defaults:

```yaml
# Required environment variable
namespace: ${NAMESPACE}

# With default value
broker_url: ${SOLACE_BROKER_URL, ws://localhost:8008}

# In tool config
tool_config:
  api_key: ${OPENAI_API_KEY}
  model_name: ${MODEL_NAME, gpt-4}
```

## Complete Example

See `assets/templates/config_template.yaml` for a complete working example based on the official SAM template.
