# MCP Gateway Adapter

The MCP Gateway Adapter exposes Solace Agent Mesh (SAM) agents as a Model Context Protocol (MCP) server using FastMCP. This allows any MCP-compatible client to interact with SAM agents through a standardized interface.

## Overview

The MCP adapter:
- **Dynamically discovers agents** from the SAM agent registry
- **Creates MCP tools automatically** based on agent skills
- **Streams responses** in real-time back to MCP clients
- **Supports HTTP and stdio transports** for different deployment scenarios

## Architecture

```
MCP Client → FastMCP Server → McpAdapter → SAM Agent Mesh
                    ↓
            [Dynamic Tool Registration]
            - agent1_skill1
            - agent1_skill2
            - agent2_skill1
            ...
```

## Configuration

See `examples/gateways/mcp_gateway_example.yaml` for a complete configuration example.

### Key Configuration Options

```yaml
gateway_adapter: solace_agent_mesh.gateway.mcp.adapter.McpAdapter

adapter_config:
  # Server identity
  mcp_server_name: "SAM MCP Gateway"
  mcp_server_description: "Access to SAM agents via MCP"

  # Transport: "http" or "stdio"
  transport: http

  # HTTP settings (when transport = "http")
  host: "0.0.0.0"
  port: 8000

  # Authentication
  default_user_identity: "mcp_user"

  # Streaming
  stream_responses: true
```

## Tool Naming

Each agent skill becomes an MCP tool with the naming pattern:

```
{agent_name}_{skill_name}
```

For example:
- Agent: `weather_agent`, Skill: `get_forecast` → Tool: `weather_agent_get_forecast`
- Agent: `code_assistant`, Skill: `review_code` → Tool: `code_assistant_review_code`

Tool names are automatically sanitized to be valid MCP identifiers (lowercase, alphanumeric with underscores).

## Tool Parameters

All MCP tools accept a single parameter:
- **message** (string): The input message/query for the agent

## Usage Examples

### 1. Starting the MCP Gateway

```bash
# Start SAM with the MCP gateway configuration
sam start --config examples/gateways/mcp_gateway_example.yaml
```

### 2. Connecting with FastMCP CLI

```bash
# Test the MCP server with FastMCP's inspector
fastmcp dev http://localhost:8000/mcp
```

### 3. Connecting from Claude Desktop

Add to your Claude Desktop configuration (`~/.config/claude/config.json` on Linux/Mac):

```json
{
  "mcpServers": {
    "sam": {
      "url": "http://localhost:8000/mcp",
      "transport": "http"
    }
  }
}
```

### 4. Programmatic Usage (Python)

```python
from fastmcp import Client

async def use_sam_via_mcp():
    async with Client("http://localhost:8000/mcp") as client:
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {tools}")

        # Call a tool
        result = await client.call_tool(
            "weather_agent_get_forecast",
            {"message": "What's the weather in San Francisco?"}
        )
        print(result)
```

## How It Works

### Initialization

1. Adapter creates FastMCP server instance
2. Queries `context.list_agents()` to register any already-discovered agents
3. Registers callbacks with agent registry for dynamic updates
4. Starts FastMCP server on configured transport

### Dynamic Agent Discovery

As agents join and leave the SAM mesh:

1. **Agent Joins**: When a new agent publishes its AgentCard:
   - `AgentRegistry` detects the new agent
   - Calls `GenericGatewayComponent._on_agent_added()`
   - Component calls `McpAdapter.handle_agent_registered()`
   - Adapter registers new MCP tools via `mcp_server.add_tool()`
   - FastMCP sends `tools/list_changed` notification to connected clients
   - MCP clients automatically refresh their tool list

2. **Agent Leaves**: When an agent is removed (e.g., TTL expiry):
   - `AgentRegistry` detects the removal
   - Calls `GenericGatewayComponent._on_agent_removed()`
   - Component calls `McpAdapter.handle_agent_deregistered()`
   - Adapter removes tools via `mcp_server.remove_tool()`
   - FastMCP sends `tools/list_changed` notification to clients
   - Stale tools disappear from client's tool list

### Tool Invocation

1. MCP client calls a tool (e.g., `weather_agent_get_forecast`)
2. Adapter maps tool name back to agent and skill
3. Creates a `SamTask` with the message text
4. Submits task via `context.handle_external_input()`
5. Returns task ID to track execution

### Response Handling

1. `_handle_tool_call()` creates an `asyncio.Future` for the task
2. Task is submitted to SAM, and the method **waits** on the Future
3. As agent processes the task, `handle_update()` receives chunks:
   - Text parts are buffered for the final response
   - Optionally streamed to MCP client via `mcp_context.info()` (progress updates)
   - File and data parts are logged and reported
4. On completion, `handle_task_complete()`:
   - Assembles final text from buffer
   - **Resolves the Future** with the complete response
   - This unblocks `_handle_tool_call()`, which returns the result to MCP client
5. On error, `handle_error()` resolves the Future with an error message

## File Handling in Tool Responses

The MCP gateway intelligently returns files based on their type and size, using appropriate MCP content types:

### Content Type Strategy

**Images** (`image/*` MIME types):
- **Small (< 5MB)**: Returned inline as `ImageContent` with base64 encoding
- **Large (≥ 5MB)**: Returned as `ResourceLink` for separate download

**Audio** (`audio/*` MIME types):
- **Small (< 10MB)**: Returned inline as `AudioContent` with base64 encoding
- **Large (≥ 10MB)**: Returned as `ResourceLink`

**Text Files** (detected via MIME type using SAM's `is_text_based_file` utility):
- **Small (< 1MB)**: Returned as `EmbeddedResource` with `TextResourceContents`
- **Large (≥ 1MB)**: Returned as `ResourceLink`

**Other Binary Files**:
- **Small (< 512KB)**: Returned as `EmbeddedResource` with `BlobResourceContents` (base64)
- **Large (≥ 512KB)**: Returned as `ResourceLink`

### Configuration

Size thresholds are configurable in `adapter_config`:

```yaml
adapter_config:
  inline_image_max_bytes: 5242880      # 5MB
  inline_audio_max_bytes: 10485760     # 10MB
  inline_text_max_bytes: 1048576       # 1MB
  inline_binary_max_bytes: 524288      # 512KB
```

### Mixed Content Responses

When a tool response includes both text and files, the MCP gateway returns a list of content blocks:

```python
[
    TextContent(type="text", text="Here is the result..."),
    ImageContent(type="image", data="base64...", mimeType="image/png"),
    ResourceLink(type="resource_link", uri="artifact://session/report.pdf", ...)
]
```

## Artifact Resources

When files are too large to inline, or when explicitly requested, they are exposed as MCP resources that clients can fetch separately.

### Resource URI Format

```
artifact://{session_id}/{filename}
```

Example: `artifact://mcp-tool-abc123/report.pdf`

### Resource Features

- **Session-scoped**: Only accessible within the session that created them
- **Auto-cleanup**: Removed when the task completes
- **Versioned (optional)**: Can access specific versions with `?version=N` parameter (future enhancement)

### Accessing Resources

MCP clients can fetch resource contents using the standard `resources/read` request:

```python
# Using FastMCP client
content = await client.read_resource("artifact://session_id/filename")
```

The resource returns either `TextResourceContents` or `BlobResourceContents` depending on the file type.

### Configuration

```yaml
adapter_config:
  enable_artifact_resources: true      # Enable/disable resource exposure
  resource_uri_prefix: "artifact"      # URI prefix for resources
```

## Session Management and Execution Model

### Connection-Based Sessions

The MCP gateway uses **connection-based persistent sessions**:

- **Session Creation**: When an MCP client connects and makes its first tool call, a session is created using FastMCP's `client_id`
- **Session ID Format**: `mcp-client-{client_id}`
- **Session Lifetime**: Persists for the entire MCP connection lifetime
- **Cross-Tool Sharing**: All tool calls from the same connection share the same session
- **Isolation**: Each MCP connection gets its own isolated session

### RUN_BASED Execution

Each tool call uses **RUN_BASED** execution mode:

- **No Chat History**: Each tool call starts fresh with only the provided message
- **Agents Don't Remember**: Previous tool calls are not in the agent's context
- **Stateless Tools**: Each invocation is independent from previous calls
- **How It Works**: SAM creates a temporary session `{session}:{task_id}:run` for the LLM's chat history, then deletes it after the run completes

### Artifact Persistence Across Tool Calls

Despite RUN_BASED execution, **artifacts persist in the session**:

- **Session Storage**: Artifacts are stored in the persistent connection session (not the temporary run session)
- **Cross-Call Access**: All artifacts created in any tool call remain accessible
- **No Auto-Cleanup**: Resources never expire (live until server restart)
- **Accumulation**: Artifacts accumulate across all tool calls from the same connection

### Complete Example Flow

```
1. MCP Client Connects
   → FastMCP assigns client_id: "abc123"
   → Session created: "mcp-client-abc123"

2. Client calls: weather_agent_get_forecast("San Francisco weather")
   → Run session created: "mcp-client-abc123:task-xyz:run"
   → Agent generates response + forecast.png artifact (342 KB)
   → Artifact stored in: "mcp-client-abc123" session
   → forecast.png < 5MB → Returned inline as ImageContent
   → Run session deleted (no chat history kept)
   → Returns: [TextContent("The forecast..."), ImageContent(data="base64...")]

3. Client calls: data_agent_analyze("Generate report")
   → Run session created: "mcp-client-abc123:task-def:run"
   → Agent has NO memory of weather request (RUN_BASED)
   → Agent generates report.pdf (2.5 MB)
   → Artifact stored in: "mcp-client-abc123" session
   → report.pdf > 512KB → Registered as MCP resource
   → Run session deleted
   → Returns: [TextContent("Report generated"), ResourceLink(uri="artifact://mcp-client-abc123/report.pdf")]

4. Client fetches resource: resources/read(uri="artifact://mcp-client-abc123/report.pdf")
   → Successfully downloads report.pdf from session storage

5. Client calls: another_agent_process("Do something")
   → Run session created: "mcp-client-abc123:task-ghi:run"
   → Agent has NO memory of previous calls (RUN_BASED)
   → But forecast.png and report.pdf still exist in session storage
   → Can access via artifact service if needed
   → Creates output.json (145 KB)
   → output.json < 1MB + is text → Returned as EmbeddedResource
   → Run session deleted
   → Returns: [TextContent("Done"), EmbeddedResource(resource=TextResourceContents(...))]

6. Client Disconnects
   → Session artifacts remain accessible (no auto-cleanup implemented)
   → Resources live until server restart
```

### Session Isolation and Security

- Each MCP connection gets a unique `client_id` from FastMCP
- Session IDs include the client_id: `mcp-client-{client_id}`
- Resources use session-scoped URIs: `artifact://{session_id}/{filename}`
- **Result**: Client A cannot access artifacts from Client B's session
- No cross-session data leakage

## Features

### ✅ Implemented

- **Dynamic agent discovery**: Tools automatically added/removed as agents join/leave mesh
- **Live tool updates**: Connected MCP clients notified of tool list changes
- **Smart file handling**: Intelligent inline vs resource-link decisions based on file type and size
- **MCP resource exposure**: Artifacts exposed as MCP resources for client download
- **Mixed content responses**: Support for text + images + files in single response
- **Content type variety**: ImageContent, AudioContent, EmbeddedResource, ResourceLink
- HTTP and stdio transport support
- Streaming progress updates via FastMCP Context
- Synchronous request-response with proper Future-based waiting
- Basic authentication (default user identity)
- Error handling and reporting
- Session management
- Session-scoped resource isolation
- Auto-cleanup of resources on task completion
- Configurable timeout protection (default 5 minutes)
- Configurable size thresholds for inline vs resource
- Thread-safe callback mechanism for agent registry changes

### 🚧 Future Enhancements

- Token-based authentication
- Tool parameter schema inference from skill examples
- File upload support (inbound)
- Artifact version support in resource URIs (`?version=N`)
- Prompt templates
- Tool result caching
- Agent health monitoring
- Resource subscription (notifications when artifacts change)

## Dependencies

The MCP gateway requires:
- `fastmcp` - FastMCP framework for MCP server implementation
- `a2a` - A2A protocol types (AgentCard, AgentSkill)

## Troubleshooting

### No tools appearing in MCP client

- Check that agents are registered in the agent registry
- Verify agents have skills defined in their AgentCard
- Check gateway logs for tool registration messages

### Connection refused

- Verify the MCP server is running (check logs)
- Ensure the configured port is not in use
- Check firewall settings (for HTTP transport)

### Streaming not working

- Ensure `stream_responses: true` in config
- Verify MCP client supports streaming
- Check that `mcp_context` is being passed through correctly

## File Structure

```
src/solace_agent_mesh/gateway/mcp/
├── __init__.py           # Package exports
├── adapter.py            # Main McpAdapter implementation
├── utils.py              # Helper functions
└── README.md            # This file

examples/gateways/
└── mcp_gateway_example.yaml  # Example configuration
```

## Related Documentation

- [FastMCP Developer Guide](../../../sam-info-docs/fastmcp-dev-guide.md)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io/)
- [SAM Gateway Adapter Pattern](../adapter/README.md)
