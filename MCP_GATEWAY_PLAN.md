# SAM MCP Gateway Implementation Plan

## Overview
Create an MCP gateway that exposes SAM agents as individual MCP tools, allowing external MCP clients (like Claude Desktop) to directly interact with SAM's agent mesh.

## Phase 1: Basic MCP Gateway

### 1.1 Gateway Structure
- Use `sam add gateway mcp-gateway` to create scaffold
- Implement `MCPGatewayApp` extending `BaseGatewayApp`
- Implement `MCPGatewayComponent` extending `BaseGatewayComponent`
- Use `fastmcp` library (already in SAM dependencies)

### 1.2 Core Functionality
- **Agent Discovery**: Periodic discovery of available agents from agent registry
- **Tool Registration**: Each agent becomes an MCP tool (`data_analyst_agent`, `report_generator_agent`, etc.)
- **A2A Integration**: Use existing `submit_a2a_task()` method for agent delegation
- **Text Responses**: Simple text responses from agents (no file handling initially)

### 1.3 Required Methods (Following SAM Gateway Pattern)
- `_start_listener()`: Start MCP server and periodic agent discovery
- `_stop_listener()`: Cleanup MCP server
- `_extract_initial_claims()`: Placeholder for auth (implement in Phase 2)
- `_translate_external_input()`: Convert MCP tool call to A2A task format
- `_send_final_response_to_external()`: Format agent response for MCP client

### 1.4 Configuration
```yaml
apps:
  - name: mcp_gateway_app
    app_config:
      mcp_transport: "stdio"  # for Claude Desktop
      agent_discovery_interval: 60  # seconds
      tool_name_format: "{agent_name}_agent"
      require_auth: false  # Phase 1: no auth
```

## Phase 2: API Token Authentication

### 2.1 Token Management
- **Token Store**: JSON file with token → user identity mapping
- **Token Format**: `sam_` prefix + random string
- **User Linking**: Each token linked to user identity (email/username)
- **Organization Scoping**: User identity unique per organization

### 2.2 Token Operations
- **CLI Commands**:
  - `sam mcp create-token --user "john@company.com" --permissions "delegate,discover"`
  - `sam mcp list-tokens`
  - `sam mcp revoke-token sam_abc123...`
  - `sam mcp test-token sam_abc123...`

### 2.3 Authentication Flow
1. MCP client provides API key via environment variable or header
2. Gateway validates token against token store
3. Extract user identity and permissions from token
4. Apply permissions to agent access and A2A task submission
5. Include user context in A2A messages for audit/tracking

### 2.4 Configuration Updates
```yaml
apps:
  - name: mcp_gateway_app
    app_config:
      mcp_transport: "stdio"
      agent_discovery_interval: 60
      tool_name_format: "{agent_name}_agent"
      require_auth: true
      auth:
        token_store_path: "./mcp_tokens.json"
        default_permissions: ["delegate", "discover"]
```

## Phase 3: Enhanced Features (Future)

### 3.1 File Support
- Handle file attachments in MCP tool calls
- Integration with SAM's artifact service
- File upload/download capabilities

### 3.2 Streaming Responses
- Real-time task updates via MCP streaming
- Progress indicators for long-running agent tasks

### 3.3 Advanced Authentication
- Integration with SAM's OAuth system
- Role-based permissions from identity service
- Token refresh mechanisms

### 3.4 Monitoring & Analytics
- MCP usage metrics
- Per-user agent usage tracking
- Integration with live context analyzer

## Implementation Order

1. **Basic Gateway Structure** - Get MCP server running with agent discovery
2. **Tool Registration** - Dynamic agent-to-tool mapping
3. **A2A Integration** - Agent delegation via existing infrastructure
4. **Basic Auth** - API token validation and user mapping
5. **CLI Token Management** - Token lifecycle commands
6. **Testing & Documentation** - MCP client setup guides

## Key Design Decisions

- **Library**: Use `fastmcp` (already in SAM dependencies)
- **Transport**: Start with `stdio` for Claude Desktop compatibility
- **Naming**: Configurable tool naming format (`{agent_name}_agent`)
- **Discovery**: Periodic agent refresh (configurable interval)
- **Authentication**: Simple API tokens linked to user identity
- **Permissions**: Basic permission system (delegate, discover, etc.)
- **Integration**: Leverage existing SAM infrastructure (A2A, agent registry, etc.)

## Success Criteria

### Phase 1
- [ ] Claude Desktop can discover SAM agents as MCP tools
- [ ] Users can call agents via MCP and receive text responses
- [ ] Agent discovery refreshes automatically
- [ ] No authentication required (development mode)

### Phase 2
- [ ] Per-user API tokens working
- [ ] Token management via CLI
- [ ] User identity tracked in agent calls
- [ ] Permissions enforced (user can only access permitted agents)

This plan follows SAM's existing gateway patterns while providing a clean MCP integration that exposes the full power of SAM's agent mesh to external MCP clients.