# Claude Code Tools - User Guide

## 1. Introduction

The Claude Code tools provide AI-assisted software development capabilities to SAM agents. You can configure an agent with these tools to enable it to autonomously write code, create applications, debug issues, and manage development projects in isolated workspaces.

Claude Code runs in secure Docker/Podman containers with support for Node.js, Python, and Go development environments. The agent maintains persistent workspaces and conversation sessions across multiple invocations, enabling complex multi-turn development tasks.

## 2. Core Concepts

### Workspaces

A workspace is an isolated directory containing project files, source code, and development artifacts. You can create two types of workspaces:

- **session**—Temporary workspaces that exist for the duration of the agent conversation. Session workspaces are automatically cleaned up after use.
- **app**—Persistent workspaces for long-lived projects. App workspaces remain available across multiple agent sessions and can be versioned, exported, and imported.

### Development Environments

Claude Code supports three containerized development environments:

- **node**—Node.js 20 environment with npm, git, and common development tools
- **python**—Python 3.11 environment with pip, pytest, and development tools
- **go**—Go 1.21 environment with go toolchain and development utilities

Each environment runs in a dedicated container image with appropriate tools and dependencies pre-installed.

### Session Continuity

The tool provider automatically tracks Claude Code session IDs per workspace. When an agent makes multiple calls to the same workspace, the conversation context is preserved, enabling:

- Multi-turn conversations where Claude Code can ask clarifying questions
- Incremental development across multiple agent invocations
- Context-aware code modifications and debugging

## 3. Available Tools

The Claude Code tool provider offers seven tools for development operations.

### claude_code_execute

Execute Claude Code AI assistant in a persistent workspace. Claude Code autonomously reads files, writes code, runs tests, and verifies results. Sessions persist automatically when you reuse the same workspace_id.

**Parameters:**

- **prompt** (string, required)—Instruction for Claude Code. The assistant will execute this task autonomously.
- **workspace_id** (string, required)—Unique workspace identifier. Use the same ID across calls to maintain session continuity.
- **workspace_type** (string, optional)—Either <code>session</code> (temporary) or <code>app</code> (persistent). Defaults to <code>session</code>.
- **environment** (string, optional)—Development environment: <code>node</code>, <code>python</code>, or <code>go</code>. Defaults to <code>node</code>.
- **workspace_name** (string, optional)—Display name for the workspace. Defaults to workspace_id.
- **workspace_description** (string, optional)—Description for CLAUDE.md file in workspace.
- **resume_session_id** (string, optional)—Claude Code session ID to resume from previous response. Only needed when explicitly answering a question from Claude Code.

**Returns:**

- **status**—<code>success</code> or <code>error</code>
- **output**—Claude Code's response text
- **session_id**—Session ID for future invocations
- **workspace_id**—Workspace identifier
- **workspace_path**—Absolute path to workspace directory
- **workspace_type**—Type of workspace (<code>session</code> or <code>app</code>)
- **metadata**—Execution metadata including:
  - **cost_usd**—Cost of API calls
  - **duration_ms**—Execution duration in milliseconds
  - **num_turns**—Number of conversation turns

### claude_code_list_workspaces

List all available workspaces for the current user.

**Parameters:**

- **workspace_type** (string, optional)—Filter by type: <code>session</code> or <code>app</code>. Returns all types if not specified.

**Returns:**

List of workspace objects, each containing:
- **workspace_id**—Unique identifier
- **workspace_type**—<code>session</code> or <code>app</code>
- **path**—Absolute path to workspace
- **created_at**—ISO 8601 timestamp
- **metadata**—Workspace metadata (environment, name, description)

### claude_code_list_sessions

List all active Claude Code sessions for the current user.

**Parameters:** None

**Returns:**

List of session objects, each containing:
- **workspace_key**—Key identifying the workspace ({user_id}/{workspace_id})
- **session_id**—Claude Code session identifier

### claude_code_read_files

Read files from a workspace.

**Parameters:**

- **workspace_id** (string, required)—Workspace identifier
- **file_paths** (array of strings, required)—Paths to files relative to workspace root

**Returns:**

Object with file paths as keys and file contents as values. Binary files are base64-encoded.

### claude_code_create_version

Create a git-based version of a workspace. This captures the current state of all files as a git commit.

**Parameters:**

- **workspace_id** (string, required)—Workspace identifier
- **version_name** (string, required)—Name for the version (used as git tag)
- **description** (string, optional)—Description for the version

**Returns:**

- **workspace_id**—Workspace identifier
- **version_name**—Version name
- **commit_sha**—Git commit SHA
- **message**—Success message

### claude_code_export_workspace

Export a workspace as a tar.gz archive.

**Parameters:**

- **workspace_id** (string, required)—Workspace identifier
- **export_path** (string, optional)—Path for export file. Defaults to <code>{workspace_id}.tar.gz</code> in workspace base directory.

**Returns:**

- **workspace_id**—Workspace identifier
- **export_path**—Absolute path to exported archive
- **size_bytes**—Archive size in bytes

### claude_code_import_workspace

Import a workspace from a tar.gz archive.

**Parameters:**

- **archive_path** (string, required)—Path to tar.gz archive
- **workspace_id** (string, optional)—ID for imported workspace. Auto-generated if not provided.
- **workspace_type** (string, optional)—<code>session</code> or <code>app</code>. Defaults to <code>app</code>.

**Returns:**

- **workspace_id**—Workspace identifier
- **workspace_path**—Absolute path to workspace
- **workspace_type**—Type of workspace

## 4. Configuration

### Basic Tool Configuration

To add Claude Code tools to an agent, configure them in the agent's YAML file using the dynamic tool pattern.

```yaml
tools:
  - tool_type: dynamic
    provider_module: "solace_agent_mesh.agent.tools.claude_code.tool_provider"
    provider_class: "ClaudeCodeToolProvider"
    tool_config:
      api_key: "${ANTHROPIC_API_KEY}"
      model: "claude-sonnet-4"
      workspace_base: "/path/to/workspaces"
      settings_base: "/path/to/settings"
```

### Required Configuration Parameters

The following parameters are required in tool_config:

- **api_key** (string)—Anthropic API key for Claude Code CLI. You can use environment variable references like <code>${ANTHROPIC_API_KEY}</code>.
- **workspace_base** (string)—Base directory for storing workspaces. Each workspace gets a subdirectory under this path.
- **settings_base** (string)—Base directory for Claude Code settings. Each workspace gets a settings subdirectory.

### Optional Configuration Parameters

- **model** (string)—Claude model to use. Defaults to the latest Claude Sonnet model. Common values:
  - <code>claude-sonnet-4</code>—Latest Claude 4 Sonnet
  - <code>claude-opus-4</code>—Latest Claude 4 Opus (higher quality, slower)
  - <code>claude-haiku-3.5</code>—Faster, more cost-effective option
- **container_runtime** (string)—Container runtime to use: <code>docker</code> or <code>podman</code>. Auto-detects if not specified.
- **enable_streaming** (boolean)—Enable real-time status updates during execution. Defaults to <code>true</code>.
- **environment_variables** (object)—Additional environment variables to pass to Claude Code containers. Keys are variable names, values can be static strings or references like <code>${VAR_NAME}</code>.
- **settings** (object)—Overrides for Claude Code settings.json. Any fields specified here override the default settings. Common overrides:
  - **maxThinkingTokens** (number)—Maximum tokens for Claude's reasoning. Default: 4000
  - **alwaysThinkingEnabled** (boolean)—Enable extended thinking mode. Default: false
  - **sandbox.allowedNetworkDomains** (array)—Network access control. Default: <code>["*"]</code> (permissive in container)

### Complete Configuration Example

```yaml
tools:
  - tool_type: dynamic
    provider_module: "solace_agent_mesh.agent.tools.claude_code.tool_provider"
    provider_class: "ClaudeCodeToolProvider"
    tool_config:
      # Required
      api_key: "${ANTHROPIC_API_KEY}"
      workspace_base: "/var/sam/workspaces"
      settings_base: "/var/sam/settings"

      # Model configuration
      model: "claude-sonnet-4"

      # Container runtime (optional, auto-detects if omitted)
      container_runtime: "docker"

      # Streaming (optional, defaults to true)
      enable_streaming: true

      # Additional environment variables
      environment_variables:
        ANTHROPIC_BASE_URL: "https://api.anthropic.com"
        NPM_REGISTRY: "https://registry.npmjs.org"

      # Claude Code settings overrides
      settings:
        maxThinkingTokens: 8000
        alwaysThinkingEnabled: true
        sandbox:
          allowedNetworkDomains:
            - "*.npmjs.org"
            - "*.pypi.org"
            - "*.github.com"
```

### Environment Variable Reference

Environment variables in tool_config are resolved at runtime. Use the <code>${VAR_NAME}</code> syntax to reference environment variables.

The following environment variables are commonly used:

- **ANTHROPIC_API_KEY**—API key for Anthropic Claude
- **ANTHROPIC_BASE_URL**—Base URL for Anthropic API (for proxies or custom endpoints)
- **ANTHROPIC_AUTH_TOKEN**—Alternative authentication token
- **ANTHROPIC_MODEL**—Default model override

## 5. Docker Container Requirements

### Container Images

The Claude Code tools require three Docker/Podman container images to be built and available locally:

- <code>claude-code-node:latest</code>—For Node.js development
- <code>claude-code-python:latest</code>—For Python development
- <code>claude-code-go:latest</code>—For Go development

These images are built from Dockerfiles located in the <code>docker/</code> directory of the repository.

### Building Containers

To build all three container images, perform these steps:

1. Navigate to the repository root
2. Build the Node.js container:
   ```bash
   cd docker/claude-code-node
   docker build -t claude-code-node:latest .
   ```
3. Build the Python container:
   ```bash
   cd docker/claude-code-python
   docker build -t claude-code-python:latest .
   ```
4. Build the Go container:
   ```bash
   cd docker/claude-code-go
   docker build -t claude-code-go:latest .
   ```

If you use Podman instead of Docker, substitute <code>podman</code> for <code>docker</code> in the commands.

### Container Requirements

The containers run as non-root users for security:
- Node container runs as <code>node</code> user
- Python container runs as <code>python</code> user
- Go container runs as <code>go</code> user

Each container includes:
- Claude Code CLI installed globally via npm
- Development tools (git, ripgrep, curl)
- Process management utilities (procps)
- Language-specific toolchains

### Volume Mounts

The tool automatically mounts two directories into containers:

- **Workspace directory**—Mounted at <code>/workspace</code> (read/write)
- **Settings directory**—Mounted at <code>~/.claude</code> for the container user (read/write)

The <code>:Z</code> suffix on volume mounts enables SELinux compatibility for systems using SELinux (like RHEL/Fedora).

## 6. Usage Patterns

### Simple Code Generation

To generate a simple application, provide a clear task description:

```python
result = await agent.call_tool("claude_code_execute", {
    "prompt": "Create a simple Express.js REST API with /health and /users endpoints",
    "workspace_id": "my-api-project",
    "workspace_type": "app",
    "environment": "node"
})
```

### Multi-Turn Development

For complex tasks requiring multiple interactions, reuse the same workspace_id:

```python
# First call: Create initial application
result1 = await agent.call_tool("claude_code_execute", {
    "prompt": "Create a Python FastAPI application with user authentication",
    "workspace_id": "user-api",
    "environment": "python"
})

# Second call: Add features (session continues automatically)
result2 = await agent.call_tool("claude_code_execute", {
    "prompt": "Add password hashing using bcrypt and JWT token generation",
    "workspace_id": "user-api",
    "environment": "python"
})

# Third call: Add tests
result3 = await agent.call_tool("claude_code_execute", {
    "prompt": "Create pytest tests with 80% code coverage",
    "workspace_id": "user-api",
    "environment": "python"
})
```

### Answering Claude Code Questions

If Claude Code asks a clarifying question, use the resume_session_id parameter:

```python
# First call
result1 = await agent.call_tool("claude_code_execute", {
    "prompt": "Create a web scraper",
    "workspace_id": "scraper"
})

# If result1['output'] contains a question like "Which website should I scrape?"
result2 = await agent.call_tool("claude_code_execute", {
    "prompt": "Scrape news articles from example.com",
    "workspace_id": "scraper",
    "resume_session_id": result1['session_id']
})
```

### Reading Generated Files

To inspect files created by Claude Code:

```python
files = await agent.call_tool("claude_code_read_files", {
    "workspace_id": "my-project",
    "file_paths": ["package.json", "src/index.js", "README.md"]
})

for path, content in files.items():
    print(f"=== {path} ===")
    print(content)
```

### Versioning Workspaces

To create snapshots of workspace state:

```python
# Create initial version
version1 = await agent.call_tool("claude_code_create_version", {
    "workspace_id": "my-app",
    "version_name": "v1.0.0",
    "description": "Initial release"
})

# Make changes...
await agent.call_tool("claude_code_execute", {
    "prompt": "Add user authentication",
    "workspace_id": "my-app"
})

# Create new version
version2 = await agent.call_tool("claude_code_create_version", {
    "workspace_id": "my-app",
    "version_name": "v1.1.0",
    "description": "Added authentication"
})
```

### Exporting and Importing Workspaces

To share or backup workspaces:

```python
# Export workspace
export_result = await agent.call_tool("claude_code_export_workspace", {
    "workspace_id": "my-app",
    "export_path": "/backups/my-app-backup.tar.gz"
})

# Import into new workspace
import_result = await agent.call_tool("claude_code_import_workspace", {
    "archive_path": "/backups/my-app-backup.tar.gz",
    "workspace_id": "my-app-restored",
    "workspace_type": "app"
})
```

## 7. Agent Instruction Guidelines

When configuring an agent to use Claude Code tools, include clear instructions in the agent's <code>instruction</code> field. Use these guidelines:

- Specify when to use temporary vs persistent workspaces
- Provide guidance on workspace naming conventions
- Define quality standards (testing, documentation, error handling)
- Set expectations for code review before delivery
- Include security requirements (input validation, credential handling)

Example agent instruction:

```yaml
instruction: |
  You are a software development agent that creates production-ready applications.

  When building applications:
  - Use persistent workspaces (workspace_type: app) for user projects
  - Use descriptive workspace IDs like "user123-todo-app"
  - Always include comprehensive tests with the code
  - Follow security best practices for the language/framework
  - Create clear README.md documentation
  - Run builds and tests before marking tasks complete

  For quick prototypes or temporary work, use session workspaces.
```

## 8. Status Updates

When <code>enable_streaming</code> is true in tool_config, the Claude Code tools publish real-time status updates during execution. The status updates are published as <code>AgentProgressUpdateData</code> signals via the SAM event mesh.

Status updates are prefixed with "Coding tool: " and include information about:
- File operations (reading, writing, editing)
- Tool usage (bash commands, searches)
- Build and test execution
- Error conditions

These updates provide visibility into long-running code generation tasks and help users understand what the coding agent is doing.

## 9. Workspace Management

### Workspace Directory Structure

Workspaces are organized by user and type:

```
{workspace_base}/
├── {user_id}/
│   ├── sessions/          # Temporary workspaces
│   │   └── {workspace_id}/
│   └── apps/             # Persistent workspaces
│       └── {workspace_id}/
```

### Workspace Initialization

When you create a new workspace, the tool automatically:
1. Creates the workspace directory
2. Initializes a git repository
3. Creates a CLAUDE.md file with workspace context
4. Commits CLAUDE.md as the initial commit

The CLAUDE.md file contains instructions for Claude Code about the workspace environment and development practices.

### Workspace Cleanup

Session workspaces can be cleaned up manually by deleting the workspace directory. App workspaces persist until explicitly deleted.

The tool does not automatically clean up workspaces. Implement cleanup logic in your agent or infrastructure as needed.
