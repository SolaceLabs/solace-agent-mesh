# Agent Plugin Manager

The Agent Plugin Manager is a component that dynamically creates and manages agent applications based on a configuration file. It allows users to easily create agents from existing agent plugins without having to manually install and configure each plugin.

## Features

- Dynamically install agent plugins from URLs or local paths
- Load flow templates from plugins
- Substitute placeholders in flow configurations
- Apply user-provided configuration to agent components
- Set environment variables for agents
- Create and start apps using the connector's `create_internal_app` method
- Automatically create agents on startup (configurable)
- Configurable agent definition file path
- Component-based integration with the system
- Track and manage running apps

## Configuration

The Agent Plugin Manager uses a YAML configuration file to define the agents to create. The configuration file has the following structure:

```yaml
agents:
  - name: mcp-fileserver
    plugin: https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-mcp-server
    config:
      server_description: "This agent handles actions for a fileservice"
      server_name: filesystem
      server_command: "npx -y @modelcontextprotocol/server-filesystem /path"
    env-vars:
      MCP_SERVER_DEBUG: "true"
      MCP_SERVER_LOG_LEVEL: "info"

  - name: acme-sales
    plugin: https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-sql-database
    config:
      db_type: sqlite
      database: acme_sales
      database_purpose: "Database of sales data for ACME Corp"
      data_description: "Contains the sales data for ACME Corp"
      csv_directories:
        - /tmp/example/csv/files
    env-vars:
      DATABASE_DEBUG: "true"
      GOOGLE_API_KEY: "ak4dd23453"
      GOOGLE_LLM_URL: "https://api.google.com/v1/llm"
```

Each agent definition includes:

- `name`: The name of the agent
- `plugin`: The URL or path to the plugin
- `config`: The configuration object for the agent
- `env-vars`: (Optional) Environment variables to set before running the agent

## Usage

## Integration with the System

The AgentPluginManager can be integrated with the system in two ways:

### 1. Component-Based Integration (Recommended)

The AgentPluginManager is available as a component that can be included in your application's configuration:

```yaml
# configs/service_agent_plugin_manager.yaml
flows:
  - name: agent-plugin-manager-service
    components:
      - component_name: agent_plugin_manager
        component_base_path: .
        component_module: src.services.agent_plugin_manager.components.agent_plugin_manager_component
        component_config:
          module_directory: ${MODULE_DIRECTORY, src}
          agents_definition_file: ${AGENT_DEFINITION_FILE, configs/agents.yaml}
          auto_create: ${AGENT_PLUGIN_MANAGER_AUTO_CREATE, true}
```

This component will automatically initialize the AgentPluginManager and create agents during system startup.

### 2. Direct Integration

You can also create and use the AgentPluginManager directly in your code:

```python
from src.services.agent_plugin_manager import AgentPluginManager

# Create the agent plugin manager
agent_manager = AgentPluginManager(
    connector=connector,
    module_directory="src",
    agents_definition_file="configs/agents.yaml",
    auto_create=True
)
```

## Configuration

The agent definition file path can be configured in several ways, with the following order of precedence:

1. Path provided in the constructor
2. Path from environment variable `AGENT_DEFINITION_FILE`
3. Path from Solace Agent Mesh config file
4. Default path: `configs/agents.yaml`

### Solace Agent Mesh Configuration

You can configure the AgentPluginManager in the Solace Agent Mesh configuration file:

```yaml
# solace-agent-mesh.yaml
solace_agent_mesh:
  # ... existing config ...
  runtime:
    agent_plugin_manager:
      definition_file: "configs/custom_agents.yaml"
      auto_create: true
```

### Initialization

```python
from src.services.agent_plugin_manager import AgentPluginManager

# Basic usage with all defaults (auto-creates agents)
agent_manager = AgentPluginManager(connector=connector)

# Specify a custom definition file
agent_manager = AgentPluginManager(
    connector=connector,
    agents_definition_file='configs/custom_agents.yaml'
)

# Disable automatic agent creation
agent_manager = AgentPluginManager(
    connector=connector,
    auto_create=False
)
```

### Creating Agents

```python
# If auto_create is disabled, create agents explicitly
agent_manager.create_agents()

# Create a single agent
agent_manager.create_agent(
    name='my-agent',
    plugin_url='https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-mcp-server',
    user_config={
        'server_name': 'my-server',
        'server_command': 'npx -y @modelcontextprotocol/server-filesystem /path'
    },
    env_vars={
        'MCP_SERVER_DEBUG': 'true',
        'MCP_SERVER_LOG_LEVEL': 'info'
    }
)
```

### Managing Agents

```python
# List all running agents
agents = agent_manager.list_agents()

# Stop a specific agent
agent_manager.stop_agent('my-agent')

# Stop all agents
agent_manager.stop_all_agents()
```

## Placeholders

The Agent Plugin Manager supports the following placeholders in flow configurations:

- `{{SNAKE_CASE_NAME}}`: The agent name in snake_case (e.g., `my_agent`)
- `{{SNAKE_UPPER_CASE_NAME}}`: The agent name in UPPER_SNAKE_CASE (e.g., `MY_AGENT`)
- `{{MODULE_DIRECTORY}}`: The module directory (e.g., `src`)

These placeholders are automatically replaced with the appropriate values when creating agents.

## Plugin Installation

The Agent Plugin Manager automatically installs plugins if they are not already installed. It supports the following plugin URL formats:

- GitHub URLs: `https://github.com/username/repo`
- GitHub URLs with subdirectory: `https://github.com/username/repo#subdirectory=subdir`
- Local paths: `/path/to/plugin`

For GitHub URLs, the manager automatically adds the `git+` prefix when installing with pip.

## Example

See the `examples/agent_plugin_manager_example.py` file for a complete example of how to use the Agent Plugin Manager.