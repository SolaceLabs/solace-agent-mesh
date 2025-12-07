# Claude Code Tools for SAM Agents

AI-assisted coding capabilities for SAM agents using Claude Code CLI in isolated Docker containers.

## Overview

The Claude Code tools provide SAM agents with autonomous software development capabilities through Claude Code, Anthropic's AI-powered CLI. Agents can create projects, write code, run tests, and manage workspaces with persistent state across invocations.

**Key Features:**

- **Persistent Workspaces**: Real filesystem directories that survive across invocations
- **Session Continuity**: Automatic session management for multi-turn conversations
- **Docker Isolation**: Secure execution in containerized environments
- **Multiple Environments**: Support for Node.js, Python, and Go development
- **Version Control**: Git-based semantic versioning
- **Import/Export**: Workspace portability via tar.gz archives

## Architecture

```
SAM Agent
    ↓ (calls tool with prompt)
Claude Code Tool (DynamicTool)
    ├─ Manages session_id internally
    ├─ Gets workspace path from WorkspaceService
    └─ Prepares settings from tool_config
    ↓
Docker Container
    ├─ Claude Code CLI (headless mode)
    ├─ Workspace Volume (real filesystem mount)
    ├─ Settings Volume (config & sessions)
    └─ Environment (Node/Python/Go)
    ↓ (autonomous execution: gather → act → verify)
Returns structured JSON
    ├─ output (result text)
    ├─ metadata (cost, duration, turns)
    └─ workspace_path
```

## Setup

### 1. Build Container Images

Build the environment-specific container images:

```bash
cd docker
./build-all.sh
```

The build script automatically detects whether you have Docker or Podman installed and uses the appropriate one.

This creates three images:
- `claude-code-node:latest` - Node.js 20 + Claude Code
- `claude-code-python:latest` - Python 3.11 + Claude Code
- `claude-code-go:latest` - Go 1.21 + Claude Code

**Manual Build (if needed):**
```bash
# With Docker
docker build -t claude-code-node:latest ./claude-code-node/
docker build -t claude-code-python:latest ./claude-code-python/
docker build -t claude-code-go:latest ./claude-code-go/

# With Podman
podman build -t claude-code-node:latest ./claude-code-node/
podman build -t claude-code-python:latest ./claude-code-python/
podman build -t claude-code-go:latest ./claude-code-go/
```

**Auto-Detection:** Both the build script and the runtime tools automatically detect whether you have Docker or Podman installed (checking Docker first, then Podman). You can override runtime detection by setting `container_runtime: "podman"` in your agent configuration.

### 2. Create Workspace Directories

The default configuration uses `/tmp` for workspace storage. Directories will be created automatically on first use:

```bash
# Directories are created automatically, but you can pre-create them:
mkdir -p /tmp/claude-workspaces /tmp/claude-settings /tmp/claude-exports
```

**Note:** `/tmp` is cleared on system restart. For persistent workspaces, configure custom paths in your agent YAML and ensure they're writable.

### 3. Configure Agent

Add Claude Code tools to your agent configuration:

```yaml
agent_name: "coding-assistant"

model:
  name: "claude-3-7-sonnet-20250219"

tools:
  dynamic:
    - provider: "solace_agent_mesh.agent.tools.claude_code.ClaudeCodeToolProvider"
      config:
        api_key: "${ANTHROPIC_API_KEY}"
        model: "claude-sonnet-4"
        max_iterations: 15
        workspace_base: "/claude-workspaces"
        settings_base: "/claude-settings"
        environment_variables:
          ANTHROPIC_BASE_URL: "${ANTHROPIC_BASE_URL}"
```

See `config/examples/coding-agent.yaml` for a complete example.

## Available Tools

### 1. claude_code_execute

**Primary tool for executing Claude Code in a workspace.**

```python
result = agent.use_tool("claude_code_execute", {
    "prompt": "Create a REST API client for the GitHub API",
    "workspace_id": "github-client",
    "environment": "node"
})
```

**Parameters:**
- `prompt` (required): Instruction for Claude Code
- `workspace_id` (required): Unique workspace identifier
- `workspace_type`: "session" (temporary) or "app" (persistent) - default: "session"
- `environment`: "node", "python", or "go" - default: "node"
- `workspace_name`: Display name for workspace
- `workspace_description`: Description for CLAUDE.md

**Returns:**
```python
{
    "status": "success" | "error",
    "output": str,              # Claude Code's response
    "workspace_id": str,
    "workspace_path": str,
    "workspace_type": str,
    "session_id": str,          # For internal use
    "metadata": {
        "cost_usd": float,
        "duration_ms": int,
        "num_turns": int,
    },
    "error": Optional[str]
}
```

### 2. claude_code_list_workspaces

**List all workspaces for the current user.**

```python
result = agent.use_tool("claude_code_list_workspaces", {
    "workspace_type": "app"  # Optional filter
})
```

**Returns:**
```python
{
    "status": "success",
    "workspaces": [
        {
            "workspace_id": str,
            "workspace_type": "session" | "app",
            "path": str,
            "name": str,
            "description": str,
            "environment": str,
            "created_at": float,
            "updated_at": float,
        },
        ...
    ],
    "count": int
}
```

### 3. claude_code_read_files

**Read files from a workspace using glob patterns.**

```python
result = agent.use_tool("claude_code_read_files", {
    "workspace_id": "my-project",
    "file_pattern": "**/*.ts"  # Optional, default: "**/*"
})
```

**Returns:**
```python
{
    "status": "success",
    "files": {
        "path/to/file1.ts": "content...",
        "path/to/file2.ts": "content...",
    },
    "tree": str  # Directory tree visualization
}
```

### 4. claude_code_create_version

**Create a semantic version snapshot using git tags.**

```python
result = agent.use_tool("claude_code_create_version", {
    "workspace_id": "my-project",
    "bump": "minor",  # "major" | "minor" | "patch"
    "description": "Added new feature X"
})
```

**Auto-increment Logic:**
```
Current version: v1.2.3
bump="patch" → v1.2.4
bump="minor" → v1.3.0
bump="major" → v2.0.0
```

**Returns:**
```python
{
    "status": "success",
    "version": {
        "version_number": "1.3.0",
        "git_tag": "v1.3.0",
        "commit_hash": str,
        "timestamp": float,
        "description": str,
    }
}
```

### 5. claude_code_export_workspace

**Export workspace as tar.gz artifact.**

```python
result = agent.use_tool("claude_code_export_workspace", {
    "workspace_id": "my-project",
    "include_git_history": True
})
```

**Returns:**
```python
{
    "status": "success",
    "artifact_uri": str,  # file:// URI to archive
    "size_bytes": int,
    "checksum": str,      # SHA256
}
```

### 6. claude_code_import_workspace

**Import workspace from tar.gz artifact.**

```python
result = agent.use_tool("claude_code_import_workspace", {
    "artifact_uri": "file:///tmp/claude-exports/my-project.tar.gz",
    "new_workspace_id": "imported-project"  # Optional rename
})
```

**Returns:**
```python
{
    "status": "success",
    "workspace_id": str,
    "workspace_type": str,
    "workspace_path": str,
    "original_metadata": Dict,
}
```

## Usage Examples

### Example 1: Multi-turn Development

```python
# Turn 1: Initialize project
result1 = agent.use_tool("claude_code_execute", {
    "prompt": "Create a React todo list app with Vite and Tailwind",
    "workspace_id": "todo-app",
    "workspace_type": "app",
    "environment": "node"
})

# Turn 2: Add features (session continues automatically)
result2 = agent.use_tool("claude_code_execute", {
    "prompt": "Add local storage persistence",
    "workspace_id": "todo-app"  # Same workspace_id = same session
})

# Turn 3: Create version
await agent.use_tool("claude_code_create_version", {
    "workspace_id": "todo-app",
    "workspace_type": "app",
    "bump": "major",  # v1.0.0
    "description": "Initial release with persistence"
})
```

### Example 2: Data Analysis

```python
# Ad-hoc Python analysis
result = agent.use_tool("claude_code_execute", {
    "prompt": "Analyze data.csv and create visualizations using matplotlib",
    "workspace_id": "data-analysis",
    "environment": "python"
})
```

### Example 3: Export and Share

```python
# Export workspace
export_result = agent.use_tool("claude_code_export_workspace", {
    "workspace_id": "my-project",
    "workspace_type": "app"
})

# Later, import on another system
import_result = agent.use_tool("claude_code_import_workspace", {
    "artifact_uri": export_result["artifact_uri"]
})
```

## Configuration Reference

### Tool Config Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | string | - | Anthropic API key (required) |
| `model` | string | - | Claude model to use |
| `max_iterations` | int | - | Max iterations for Claude Code |
| `container_runtime` | string | auto-detect | Container runtime: "docker" or "podman" (auto-detects if not specified) |
| `workspace_base` | string | `/tmp/claude-workspaces` | Base path for workspaces |
| `settings_base` | string | `/tmp/claude-settings` | Base path for settings |
| `export_base` | string | `/tmp/claude-exports` | Base path for exports |
| `prepull_images` | bool | false | Pre-pull images on startup |
| `environments` | list | `["node"]` | Environments to pre-pull |
| `environment_variables` | dict | `{}` | Arbitrary env vars for container |
| `settings` | dict | `{}` | Overrides for settings.json |

### Environment Variables

All environment variables in `tool_config.environment_variables` are injected into the container:

```yaml
environment_variables:
  ANTHROPIC_BASE_URL: "${ANTHROPIC_BASE_URL}"
  GITHUB_TOKEN: "${GITHUB_TOKEN}"
  CUSTOM_VAR: "value"
```

Variables with `${VAR}` syntax are resolved from the host environment.

### Settings Overrides

Customize Claude Code behavior via `tool_config.settings`:

```yaml
settings:
  allowedTools: ["*"]
  autoApproveTools: true
  maxThinkingTokens: 4000
  sandbox:
    enabled: true
    allowedNetworkDomains: ["*"]
  hooks:
    - name: "post-write-lint"
      trigger: "after:write"
      command: "npm run lint:fix || true"
```

## Workspace Organization

```
/tmp/claude-workspaces/
  {user_id}/
    sessions/{workspace_id}/     # Temporary workspaces
      .workspace-metadata.json
      CLAUDE.md
      .git/
      ... project files ...

    apps/{workspace_id}/          # Persistent workspaces
      .workspace-metadata.json
      CLAUDE.md
      .git/
      ... project files ...

/tmp/claude-settings/
  {user_id}/
    {workspace_id}/
      settings.json               # Generated from tool_config
      __store.db                  # Claude Code session storage
      projects/                   # Session data
```

## WorkspaceService Abstraction

The tools use a `WorkspaceService` abstraction for filesystem management:

- **LocalFilesystemWorkspaceService**: Local filesystem (default)
- **NFSWorkspaceService**: NFS-mounted storage (for distributed systems)
- **S3FuseWorkspaceService**: S3 via s3fs-fuse (for cloud deployments)

All implementations return real filesystem `Path` objects that can be mounted into containers.

## Security

### Docker Isolation

- Each Claude Code execution runs in an ephemeral container
- Host filesystem only accessible via explicit volume mounts
- Container removed after execution (--rm flag)

### Sandboxing

- Claude Code's built-in sandbox is enabled by default
- Very permissive settings (allowedTools: ["*"]) since we're already in Docker
- Network access allowed within container

### API Key Management

- API keys injected from environment variables
- Never stored in workspace files
- Passed to container via environment variables

## Troubleshooting

**For comprehensive debugging information, see [DEBUGGING.md](DEBUGGING.md)**

The tools include enhanced logging to help diagnose issues. Set log level to DEBUG:
```yaml
log:
  stdout_log_level: DEBUG
  log_file_level: DEBUG
  log_file: coding-agent.log
```

### Docker Not Found

```
Error: Docker is not installed
```

**Solution:** Install Docker or Podman

### Permission Denied

```
Error: Permission denied: /tmp/claude-workspaces
```

**Solution:** Ensure directories are writable. The default `/tmp` location should be writable by default. For custom paths, ensure they exist and have correct permissions:
```bash
mkdir -p /path/to/custom-workspaces /path/to/custom-settings
chmod 755 /path/to/custom-workspaces /path/to/custom-settings
```

### Image Not Found

```
Error: Unable to find image 'claude-code-node:latest'
```

**Solution:** Build the Docker images:
```bash
cd docker && ./build-all.sh
```

### Session Not Found

If sessions aren't persisting, verify:
1. Settings volume is mounted correctly
2. `session_id` is being saved (check logs)
3. `/tmp/claude-settings/{user_id}/{workspace_id}/__store.db` exists
4. `/tmp` hasn't been cleared (some systems clear `/tmp` on restart)

## Development

### Adding New Environments

1. Create `docker/claude-code-{env}/Dockerfile`
2. Update `docker/build-all.sh`
3. Update `utils.py` environment info dict
4. Add to `tool_config.environments`

### Custom Workspace Services

Implement `BaseWorkspaceService` for custom storage backends:

```python
from solace_agent_mesh.common.workspace import BaseWorkspaceService

class CustomWorkspaceService(BaseWorkspaceService):
    async def create_workspace(self, workspace_id, user_id, workspace_type, metadata):
        # Return Path to mountable directory
        pass
```

## References

- [Claude Code Documentation](https://docs.anthropic.com/claude-code)
- [Design Document](../../../../../../docs/claude-code-tool-design.md)
- [Example Agent Config](../../../../../../config/examples/coding-agent.yaml)
