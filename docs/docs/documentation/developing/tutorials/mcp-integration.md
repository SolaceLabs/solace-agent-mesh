---
title: MCP Integration
sidebar_position: 10
---

# MCP Integration

This tutorial walks you through the process of integrating a Model Context Protocol (MCP) Server into Agent Mesh.

:::info[Learn about agents]
You should have an understanding of agents in Agent Mesh. For more information, see [Agents](../../components/agents.md).
:::

Agent Mesh now provides **native MCP support** through the framework itself. No additional plugins are required - you can connect to MCP servers directly by configuring your agent YAML file with MCP tools.

MCP integration allows your agents to connect to external MCP servers and use their tools, resources, and prompts seamlessly within the A2A protocol ecosystem.

## Setting Up the Environment

You must [install Agent Mesh and the CLI](../../installing-and-configuring/installation.md), and then [create a new Agent Mesh project](../../installing-and-configuring/run-project.md).

For this tutorial using the filesystem MCP server, you also need Node.js and NPM installed.

## MCP Tool Configuration Reference

All MCP tools are configured in your agent's YAML file under the `tools` list with `tool_type: mcp`. The following configuration fields are available:

### Common Configuration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tool_type` | string | Yes | Must be `mcp` |
| `tool_name` | string | No | Optional filter for specific MCP tool (if omitted, all tools from the server are available) |
| `connection_params` | object | Yes | Connection parameters (see connection types below) |
| `environment_variables` | object | No | Environment variables for the MCP process |
| `tool_config` | object | No | MCP-specific configuration |
| `required_scopes` | array[string] | No | Required security scopes for RBAC |

## Connection Types

MCP integration supports multiple connection types for different deployment scenarios:

### 1. Stdio Connection (Local MCP Servers)

This is the most common method for connecting to MCP servers that run as local processes.

**Configuration Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `connection_params.type` | string | Yes | Must be `stdio` |
| `connection_params.command` | string | Yes | Executable command to start the MCP server |
| `connection_params.args` | array[string] | No | Command-line arguments |
| `connection_params.timeout` | integer | No | Connection timeout in seconds (default: 30) |

**Example:**
```yaml
tools:
  - tool_type: mcp
    connection_params:
      type: stdio
      command: "npx"
      args:
        - "-y"
        - "@modelcontextprotocol/server-filesystem"
        - "/tmp/samv2"
      timeout: 300
    environment_variables:
      DEBUG_MODE: "true"
      CONFIG_PATH: "/etc/config"
```

### 2. SSE Connection (Remote MCP Servers)

For connecting to remote MCP servers using Server-Sent Events over HTTP/HTTPS.

**Configuration Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `connection_params.type` | string | Yes | Must be `sse` |
| `connection_params.url` | string | Yes | MCP server URL |
| `connection_params.headers` | object | No | HTTP headers for requests |
| `auth.type` | string | No | Authentication type (e.g., `oauth2`) |
| `manifest` | array[object] | No | Tool manifest for remote MCP |

**Example:**
```yaml
tools:
  - tool_type: mcp
    connection_params:
      type: sse
      url: "https://mcp.example.com/v1/sse"
      headers:
        Authorization: "Bearer ${MCP_AUTH_TOKEN}"
    tool_config:
      custom_setting: "value"
```

### 3. StreamableHTTP Connection (Remote MCP Servers)

For connecting to remote MCP servers using streamable HTTP connections.

**Configuration Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `connection_params.type` | string | Yes | Must be `streamable-http` |
| `connection_params.url` | string | Yes | MCP server URL with port |
| `connection_params.headers` | object | No | HTTP headers for requests |

**Example:**
```yaml
tools:
  - tool_type: mcp
    connection_params:
      type: streamable-http
      url: "https://mcp.example.com:<port>/mcp/message"
      headers:
        Authorization: "Bearer ${MCP_AUTH_TOKEN}"
```

### 4. Docker Connection (Containerized MCP Servers)

For running MCP servers in Docker containers. This uses the stdio connection type with Docker as the command.

**Example:**
```yaml
tools:
  - tool_type: mcp
    connection_params:
      type: stdio
      command: "docker"
      args:
        - "run"
        - "-i"
        - "--rm"
        - "-e"
        - "API_KEY"
        - "mcp-server-image:latest"
    environment_variables:
      API_KEY: ${MY_API_KEY}
```

## Complete Example: Filesystem MCP Agent

Here is a complete example of an agent that uses the filesystem MCP server:

```yaml
# configs/agents/filesystem_agent.yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: filesystem_agent.log

!include ../shared_config.yaml

apps:
  - name: filesystem_mcp_agent_app
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      supports_streaming: true
      agent_name: "FileSystemAgent"
      display_name: "File System"
      model: *general_model
      
      instruction: |
        You can interact with the local filesystem using MCP tools.
        Use the available tools to read, write, and manage files as requested.

      tools:
        - tool_type: mcp
          connection_params:
            type: stdio
            command: "npx"
            args:
              - "-y"
              - "@modelcontextprotocol/server-filesystem"
              - "/tmp/samv2"
        - tool_type: builtin-group
          group_name: "artifact_management"

      session_service: *default_session_service
      artifact_service: *default_artifact_service

      # Agent discovery and communication
      agent_card:
        description: "An agent that interacts with the local filesystem via MCP."
        defaultInputModes: ["text"]
        defaultOutputModes: ["text", "file"]
        skills: []

      agent_card_publishing: { interval_seconds: 10 }
      agent_discovery: { enabled: true }
      inter_agent_communication:
        allow_list: ["*"]
        request_timeout_seconds: 30
```

## Advanced Configuration Options

### Tool Filtering

You can control which tools from an MCP server are available to your agent using three mutually exclusive filtering options.

:::info[Install node package]
The examples below use the filesystem MCP server. You must install node package @modelcontextprotocol/server-filesystem securely in your local system and set the `command` parameter to your local path that points to the `mcp-server-filesystem` binary executable.
:::

#### Single Tool (tool_name)

Use `tool_name` to expose only a single specific tool:

```yaml
tools:
  - tool_type: mcp
    tool_name: "read_file"  # Only expose the read_file tool
    connection_params:
      type: stdio
      command: "./node_modules/.bin/mcp-server-filesystem"
      args:
        - "/tmp/samv2"
```

#### Allow List

Use `allow_list` to expose multiple specific tools:

```yaml
tools:
  - tool_type: mcp
    allow_list:  # Only expose these tools
      - read_file
      - write_file
      - list_directory
    connection_params:
      type: stdio
      command: "./node_modules/.bin/mcp-server-filesystem"
      args:
        - "/tmp/samv2"
```

#### Deny List

Use `deny_list` to expose all tools except specific ones:

```yaml
tools:
  - tool_type: mcp
    deny_list:  # Expose all tools EXCEPT these
      - delete_file
      - move_file
    connection_params:
      type: stdio
      command: "./node_modules/.bin/mcp-server-filesystem"
      args:
        - "/tmp/samv2"
```

:::warning[Mutual Exclusivity]
The `tool_name`, `allow_list`, and `deny_list` options are mutually exclusive. You can only use one of these filtering options per MCP tool configuration.
:::

### Environment Variables

Pass environment variables to MCP servers using the `environment_variables` block. This is particularly useful for:
- API keys and authentication tokens
- Configuration paths
- Debug flags
- Custom server settings

```yaml
tools:
  - tool_type: mcp
    connection_params:
      type: stdio
      command: "my-mcp-server"
    environment_variables:
      API_KEY: ${MY_API_KEY}
      DEBUG_MODE: "true"
      CONFIG_PATH: "/etc/myconfig"
      MAX_RETRIES: "3"
```

### Connection Timeouts

For stdio connections, you can specify a timeout to prevent hanging connections:

```yaml
tools:
  - tool_type: mcp
    connection_params:
      type: stdio
      command: "slow-mcp-server"
      timeout: 600  # 10 minutes
```

### Security Scopes (RBAC)

Restrict MCP tool access using role-based access control:

```yaml
tools:
  - tool_type: mcp
    connection_params:
      type: stdio
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/secure/data"]
    required_scopes: ["filesystem_access", "admin"]
```

## Running Your MCP-Enabled Agent

1. **Create the working directory** (for filesystem example):
   ```sh
   mkdir -p /tmp/samv2
   echo "Hello MCP!" > /tmp/samv2/test.txt
   ```

2. **Set required environment variables**:
   ```sh
   export NAMESPACE="myorg/dev"
   export SOLACE_BROKER_URL="ws://localhost:8008"
   # ... other Solace broker settings
   ```

3. **Run the agent**:
   ```sh
   sam run configs/agents/filesystem_agent.yaml
   ```

## How MCP Integration Works

When your agent starts:

1. **Connection**: The framework establishes a connection to the MCP server using the specified connection parameters
2. **Discovery**: It queries the MCP server for available tools, resources, and prompts
3. **Registration**: Available capabilities are registered as agent tools.
4. **Communication**: The agent can use these tools through the standard A2A protocol, with the framework handling MCP protocol translation


## Testing Your MCP Integration

Once your MCP-enabled agent is running, you can test it through any gateway in your project (such as the Web UI gateway):

1. **Access your gateway** (for example, Web UI at `http://localhost:8000`)
2. **Send a request** to test the MCP functionality:
   - "List the files in the directory"
   - "Create a simple text file with some content"
   - "Read the contents of test.txt"

The agent uses the MCP tools to interact with the filesystem and provide responses through the A2A protocol.
