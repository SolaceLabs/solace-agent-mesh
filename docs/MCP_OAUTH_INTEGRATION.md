# MCP Gateway OAuth Integration

## Overview

Integration of Solace Agent Mesh MCP Gateway with MCP clients using OAuth authentication via the `mcp-remote` bridge.

## Why We Use `mcp-remote`

Claude Desktop may still require remote MCP deployment rather than localhost. The `mcp-remote` package provides:

- **OAuth flow handling** - Manages Azure OAuth authentication 
- **Localhost bridge** - Enables OAuth-protected localhost servers to work with MCP clients
- **Token management** - Automatic token refresh and caching

## Configuration (Working: Roo/Cline, Claude Desktop)

Add to MCP client configuration:

**Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Roo/Cline**: MCP settings in VS Code

```json
{
  "mcpServers": {
    "solace-agent-mesh": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "http://localhost:8080/mcp/"
      ],
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

## Command Breakdown

- `npx` - Node package runner
- `-y` - Auto-accept installation
- `mcp-remote@latest` - Latest mcp-remote version
- `http://localhost:8080/mcp/` - MCP Gateway URL

## Token Management

Clear cached tokens (forces fresh OAuth):
```bash
rm -rf ~/.mcp-auth
```

**Note**: For Claude Desktop, you may need to clear tokens and restart Claude for initial setup.

## Available Agents

- MarkitdownAgent - File format conversion
- MermaidAgent - Diagram generation  
- OrchestratorAgent - Multi-agent workflows
- WebAgent - Web content fetching