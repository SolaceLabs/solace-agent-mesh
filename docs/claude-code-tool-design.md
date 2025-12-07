# Claude Code Tool Design for SAM Agents

## Executive Summary

This document specifies the design for integrating Claude Code as a tool within Solace Agent Mesh (SAM). The goal is to provide SAM agents with AI-assisted development capabilities through a generic, reusable tool that manages persistent workspaces and maintains conversation state across invocations.

**Key Design Principles:**
- **Persistent Volumes**: Workspaces live on real filesystems, mountable into containers
- **Session Continuity**: Leverage Claude Code's built-in session management for multi-turn conversations
- **Docker Isolation**: Run Claude Code in containers for security and reproducibility
- **Tool Configuration**: Use `tool_config` to inject settings, API keys, and environment variables
- **Git-based Versioning**: Use semantic versioning with git tags
- **Environment Flexibility**: Support multiple environments (Node, Python, Go, etc.)
- **WorkspaceService Abstraction**: First-class filesystem workspace management for SAM

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [WorkspaceService: First-Class Filesystem Abstraction](#workspaceservice-first-class-filesystem-abstraction)
3. [Workspace Organization](#workspace-organization)
4. [Container Strategy](#container-strategy)
5. [Tool Interface Specification](#tool-interface-specification)
6. [Configuration Management](#configuration-management)
7. [Session Continuity](#session-continuity)
8. [Dynamic Tool Implementation](#dynamic-tool-implementation)
9. [Usage Examples](#usage-examples)
10. [Security Considerations](#security-considerations)
11. [Future Enhancements](#future-enhancements)

---

## Architecture Overview

### High-Level Flow

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

### Core Components

1. **WorkspaceService**: Manages workspace directories and metadata (NEW - first-class SAM service)
2. **ClaudeCodeToolProvider**: DynamicToolProvider with lifecycle management (init/cleanup)
3. **Container Executor**: Runs Claude Code in Docker with proper volume mounts
4. **Session Tracker**: Manages Claude Code session IDs internally per workspace
5. **Configuration Injector**: Generates settings.json from tool_config
6. **Environment Templates**: Pre-built Docker images for different languages

---

## WorkspaceService: First-Class Filesystem Abstraction

### The Container Mount Requirement

**Critical Constraint**: For tools running in containers (like Claude Code) to use normal filesystem operations (`open()`, `ls`, `git`, `npm`), the workspace **must be backed by a real filesystem that can be volume-mounted**.

The WorkspaceService provides filesystem workspace management similar to how SQLAlchemy abstracts databases, but with a key difference:

> **It returns real filesystem paths, not abstracted file operations.**

### Why This Design?

**What DOESN'T work:**
```python
# ❌ Can't mount pure object storage into containers
docker run -v s3://bucket/workspace:/workspace  # Doesn't work!
```

**What WORKS:**
```python
# ✅ Mount real filesystem path
workspace_path = await workspace_service.get_workspace_path(...)
# Returns: Path("/workspaces/user123/my-workspace")

docker run -v /workspaces/user123/my-workspace:/workspace  # Works!
```

### BaseWorkspaceService Interface

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Dict, Any

class BaseWorkspaceService(ABC):
    """
    Abstract service for managing workspace directories.

    CRITICAL: All implementations must provide real filesystem paths
    that can be volume-mounted into containers.
    """

    @abstractmethod
    async def create_workspace(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,  # "session" | "app"
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Create a new workspace directory.

        Returns:
            Path object pointing to workspace directory on host filesystem.
            This path MUST be mountable into containers.
        """
        pass

    @abstractmethod
    async def get_workspace_path(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str
    ) -> Optional[Path]:
        """
        Get filesystem path for existing workspace.

        Returns:
            Path object if workspace exists, None otherwise.
            Path MUST be mountable into containers.
        """
        pass

    @abstractmethod
    async def list_workspaces(
        self,
        user_id: str,
        workspace_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List user's workspaces with metadata.

        Returns:
            List of workspace info dicts containing:
                - workspace_id: str
                - path: Path (mountable)
                - workspace_type: str
                - created_at: float
                - metadata: Dict
        """
        pass

    @abstractmethod
    async def delete_workspace(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str
    ) -> bool:
        """Delete workspace directory and metadata."""
        pass

    @abstractmethod
    async def get_metadata(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get workspace metadata."""
        pass

    @abstractmethod
    async def update_metadata(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Update workspace metadata."""
        pass
```

### LocalFilesystemWorkspaceService Implementation

```python
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

class LocalFilesystemWorkspaceService(BaseWorkspaceService):
    """
    Workspace service backed by local filesystem.

    Directory structure:
        {base_path}/
            {user_id}/
                sessions/{workspace_id}/
                    .workspace-metadata.json
                    ... user files ...
                apps/{workspace_id}/
                    .workspace-metadata.json
                    ... user files ...
    """

    def __init__(self, base_path: str = "/claude-workspaces"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_workspace_dir(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str
    ) -> Path:
        """Get workspace directory path"""
        type_dir = "sessions" if workspace_type == "session" else "apps"
        return self.base_path / user_id / type_dir / workspace_id

    def _get_metadata_file(self, workspace_dir: Path) -> Path:
        """Get metadata file path"""
        return workspace_dir / ".workspace-metadata.json"

    async def create_workspace(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Create workspace directory"""
        workspace_dir = self._get_workspace_dir(workspace_id, user_id, workspace_type)
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # Store metadata
        metadata_file = self._get_metadata_file(workspace_dir)
        workspace_metadata = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "workspace_type": workspace_type,
            "created_at": datetime.now().timestamp(),
            "updated_at": datetime.now().timestamp(),
            **(metadata or {})
        }
        metadata_file.write_text(json.dumps(workspace_metadata, indent=2))

        return workspace_dir

    async def get_workspace_path(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str
    ) -> Optional[Path]:
        """Get workspace path if it exists"""
        workspace_dir = self._get_workspace_dir(workspace_id, user_id, workspace_type)
        return workspace_dir if workspace_dir.exists() else None

    async def list_workspaces(
        self,
        user_id: str,
        workspace_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List user's workspaces"""
        workspaces = []
        user_dir = self.base_path / user_id

        if not user_dir.exists():
            return []

        types_to_scan = ["sessions", "apps"] if not workspace_type else [
            "sessions" if workspace_type == "session" else "apps"
        ]

        for type_dir in types_to_scan:
            type_path = user_dir / type_dir
            if not type_path.exists():
                continue

            for workspace_dir in type_path.iterdir():
                if not workspace_dir.is_dir():
                    continue

                metadata_file = self._get_metadata_file(workspace_dir)
                if metadata_file.exists():
                    metadata = json.loads(metadata_file.read_text())
                else:
                    metadata = {
                        "workspace_id": workspace_dir.name,
                        "workspace_type": type_dir.rstrip('s'),
                    }

                metadata["path"] = workspace_dir
                workspaces.append(metadata)

        return workspaces

    async def delete_workspace(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str
    ) -> bool:
        """Delete workspace"""
        workspace_dir = self._get_workspace_dir(workspace_id, user_id, workspace_type)

        if workspace_dir.exists():
            import shutil
            shutil.rmtree(workspace_dir)
            return True
        return False

    async def get_metadata(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get workspace metadata"""
        workspace_dir = self._get_workspace_dir(workspace_id, user_id, workspace_type)
        metadata_file = self._get_metadata_file(workspace_dir)

        if metadata_file.exists():
            return json.loads(metadata_file.read_text())
        return None

    async def update_metadata(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Update workspace metadata"""
        workspace_dir = self._get_workspace_dir(workspace_id, user_id, workspace_type)
        metadata_file = self._get_metadata_file(workspace_dir)

        existing = {}
        if metadata_file.exists():
            existing = json.loads(metadata_file.read_text())

        existing.update(metadata)
        existing["updated_at"] = datetime.now().timestamp()

        metadata_file.write_text(json.dumps(existing, indent=2))
```

### Alternative Implementations

**NFSWorkspaceService** (for distributed systems):
```python
class NFSWorkspaceService(BaseWorkspaceService):
    """
    Workspace service backed by NFS.
    NFS must be mounted on host at mount_point.
    """

    def __init__(self, nfs_mount_point: str = "/mnt/nfs-workspaces"):
        self.mount_point = Path(nfs_mount_point)
        if not self.mount_point.exists():
            raise ValueError(f"NFS not mounted at {nfs_mount_point}")
        # Use mount_point as base_path, rest is same as LocalFilesystemWorkspaceService
```

**S3FuseWorkspaceService** (for cloud with s3fs-fuse):
```python
class S3FuseWorkspaceService(BaseWorkspaceService):
    """
    Workspace service backed by S3 via s3fs-fuse.
    Requires s3fs-fuse to be running on host.
    """

    def __init__(self, s3_fuse_mount: str = "/mnt/s3-workspaces"):
        self.mount_point = Path(s3_fuse_mount)
        if not self.mount_point.exists():
            raise ValueError(f"s3fs-fuse not mounted at {s3_fuse_mount}")
        # Use mount_point as base_path, rest is same as LocalFilesystemWorkspaceService
```

---

## Workspace Organization

### Directory Structure

```
/claude-workspaces/                 # WorkspaceService base_path
  {user_id}/
    sessions/                       # Temporary session-scoped workspaces
      {workspace_id}/
        .workspace-metadata.json    # Managed by WorkspaceService
        CLAUDE.md                   # Managed by Claude Code tool
        .git/                       # Git repo (versioning)
        ... project files ...

    apps/                           # Persistent application workspaces
      {workspace_id}/
        .workspace-metadata.json
        CLAUDE.md
        .git/
        ... project files ...

/claude-settings/                   # Claude Code configuration
  {user_id}/
    {workspace_id}/
      settings.json                 # Generated from tool_config
      __store.db                    # Claude Code session storage
      projects/                     # Session data
```

### Workspace Types

| Type | Lifetime | Use Case | Example |
|------|----------|----------|---------|
| **session** | Temporary (duration of SAM session) | Ad-hoc coding tasks, data analysis, debugging | "Analyze this log file", "Write a parser" |
| **app** | Persistent (survives session end) | Building applications, long-term projects | "Sales Dashboard", "API Client Library" |

### CLAUDE.md Template

Each workspace gets a `CLAUDE.md` file that provides persistent context:

```markdown
# {workspace_name}

{workspace_description}

## Environment
This is a {environment} development workspace.

## Instructions
- Follow best practices for {environment} development
- Run tests after making changes
- Keep dependencies up to date
- Commit changes to git after successful modifications

## Build Commands
{environment-specific build commands}

## Testing
{environment-specific test commands}

## Project Structure
{auto-generated tree if files exist}
```

---

## Container Strategy

### Base Images

We create specialized Docker images for each environment:

#### Node Environment (claude-code-node:latest)

```dockerfile
FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ripgrep \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Create workspace directory
RUN mkdir -p /workspace /root/.claude
WORKDIR /workspace

# Set git defaults
RUN git config --global user.name "Claude Code" && \
    git config --global user.email "cc@workspace" && \
    git config --global init.defaultBranch main

ENTRYPOINT ["claude"]
```

#### Python Environment (claude-code-python:latest)

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git \
    ripgrep \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

RUN mkdir -p /workspace /root/.claude
WORKDIR /workspace

RUN git config --global user.name "Claude Code" && \
    git config --global user.email "cc@workspace" && \
    git config --global init.defaultBranch main

ENTRYPOINT ["claude"]
```

#### Go Environment (claude-code-go:latest)

```dockerfile
FROM golang:1.21-alpine

RUN apk add --no-cache \
    git \
    ripgrep \
    curl \
    nodejs \
    npm

RUN npm install -g @anthropic-ai/claude-code

RUN mkdir -p /workspace /root/.claude
WORKDIR /workspace

RUN git config --global user.name "Claude Code" && \
    git config --global user.email "cc@workspace" && \
    git config --global init.defaultBranch main

ENTRYPOINT ["claude"]
```

### Volume Mounts

Each container execution mounts three volumes:

1. **Workspace Volume**: `-v {workspace_path}:/workspace:Z`
   - Read-write
   - Contains project files
   - Real filesystem from WorkspaceService
   - Persists between invocations

2. **Settings Volume**: `-v {settings_path}:/root/.claude:Z`
   - Read-write
   - Contains settings.json and session storage
   - Workspace-specific configuration

3. **Environment Variables**:
   - From tool_config.environment_variables (arbitrary key-value pairs)
   - Examples: `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_BEDROCK_BASE_URL`

---

## Tool Interface Specification

### Tool 1: claude_code_execute

**Primary tool for executing Claude Code in a workspace.**

```python
async def claude_code_execute(
    prompt: str,                           # REQUIRED: Instruction for Claude Code
    workspace_id: str,                     # REQUIRED: Workspace identifier
    workspace_type: str = "session",       # "session" | "app"
    environment: str = "node",             # "node" | "python" | "go"
    workspace_name: Optional[str] = None,  # Display name
    workspace_description: str = "",       # Description for CLAUDE.md
    tool_context: ToolContext = None,
    tool_config: Optional[Dict] = None,    # Configuration injection
) -> Dict[str, Any]
```

**Key Changes from Initial Design:**
- ❌ **REMOVED `session_id`**: Managed internally by the tool
- ❌ **REMOVED `model`**: Comes from tool_config
- ❌ **REMOVED `max_iterations`**: Comes from tool_config

**Returns:**
```python
{
    "status": "success" | "error",
    "output": str,                    # Claude Code's response
    "workspace_id": str,
    "workspace_path": str,
    "workspace_type": str,
    "metadata": {
        "cost_usd": float,
        "duration_ms": int,
        "num_turns": int,
    },
    "raw_output": str,                # Full JSON from Claude Code
    "error": Optional[str]            # If status == "error"
}
```

**Examples:**

```python
# Example 1: Start new task in session workspace
result = agent.use_tool("claude_code_execute", {
    "prompt": "Create a REST API client for the GitHub API",
    "workspace_id": "github-client",
    "environment": "node"
})

# Example 2: Continue working (session_id managed internally by tool)
result = agent.use_tool("claude_code_execute", {
    "prompt": "Add error handling and retry logic",
    "workspace_id": "github-client"  # Same workspace_id = continues session
})

# Example 3: Create persistent app
result = agent.use_tool("claude_code_execute", {
    "prompt": "Initialize a React dashboard with Vite and Tailwind",
    "workspace_id": "sales-dashboard",
    "workspace_type": "app",
    "workspace_name": "Sales Dashboard",
    "workspace_description": "Real-time sales analytics dashboard"
})
```

---

### Tool 2: claude_code_list_workspaces

**List all workspaces for the current user.**

```python
async def claude_code_list_workspaces(
    workspace_type: Optional[str] = None,  # Filter: "session" | "app"
    tool_context: ToolContext = None,
    tool_config: Optional[Dict] = None,
) -> Dict[str, Any]
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

---

### Tool 3: claude_code_read_files

**Read files from a workspace.**

```python
async def claude_code_read_files(
    workspace_id: str,
    workspace_type: str = "session",
    file_pattern: str = "**/*",     # Glob pattern
    tool_context: ToolContext = None,
    tool_config: Optional[Dict] = None,
) -> Dict[str, Any]
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

---

### Tool 4: claude_code_create_version

**Create a semantic version snapshot using git tags.**

```python
async def claude_code_create_version(
    workspace_id: str,
    workspace_type: str = "session",
    bump: str = "patch",            # "major" | "minor" | "patch"
    description: str = "",
    tool_context: ToolContext = None,
    tool_config: Optional[Dict] = None,
) -> Dict[str, Any]
```

**Auto-increment Logic:**
```python
# Example: Current version is v1.2.3
bump="patch" → v1.2.4
bump="minor" → v1.3.0
bump="major" → v2.0.0
```

**Returns:**
```python
{
    "status": "success",
    "version": {
        "version_number": "1.2.4",
        "git_tag": "v1.2.4",
        "commit_hash": str,
        "timestamp": float,
        "description": str,
    }
}
```

---

### Tool 5: claude_code_export_workspace

**Export workspace as tar.gz artifact.**

```python
async def claude_code_export_workspace(
    workspace_id: str,
    workspace_type: str = "session",
    include_git_history: bool = True,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict] = None,
) -> Dict[str, Any]
```

**Export includes metadata.json:**
```json
{
    "workspace_id": "sales-dashboard",
    "workspace_type": "app",
    "environment": "node",
    "version": "v1.2.3",
    "exported_at": 1234567890,
    "exported_by": "user_123"
}
```

**Returns:**
```python
{
    "status": "success",
    "artifact_uri": str,  # URI in artifact service
    "size_bytes": int,
    "checksum": str,
}
```

---

### Tool 6: claude_code_import_workspace

**Import workspace from tar.gz artifact.**

```python
async def claude_code_import_workspace(
    artifact_uri: str,
    new_workspace_id: Optional[str] = None,  # Optional: rename on import
    tool_context: ToolContext = None,
    tool_config: Optional[Dict] = None,
) -> Dict[str, Any]
```

**Key Changes:**
- ❌ **REMOVED `workspace_id`**: Read from archive metadata
- ❌ **REMOVED `workspace_type`**: Read from archive metadata
- ✅ **ADDED `new_workspace_id`**: Optional rename

**Logic:**
```python
# Extract metadata.json from archive
metadata = extract_metadata(artifact_uri)
workspace_id = new_workspace_id or metadata["workspace_id"]
workspace_type = metadata["workspace_type"]

# Create workspace and extract files
workspace_path = await workspace_service.create_workspace(...)
extract_archive_to(artifact_uri, workspace_path)
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

---

## Configuration Management

### Tool Config Structure

The `tool_config` parameter allows agents to customize Claude Code behavior:

```yaml
# In agent configuration
tools:
  builtin:
    - name: "claude_code_execute"
      config:
        # API Configuration
        api_key: "${ANTHROPIC_API_KEY}"
        model: "claude-sonnet-4"
        max_iterations: 15

        # Arbitrary Environment Variables (NEW)
        environment_variables:
          ANTHROPIC_BASE_URL: "https://api.anthropic.com"
          ANTHROPIC_BEDROCK_BASE_URL: "https://bedrock.amazonaws.com"
          GITHUB_TOKEN: "${GITHUB_TOKEN}"
          CUSTOM_VAR: "value"

        # Claude Code settings.json overrides
        settings:
          allowedTools: ["*"]  # Very permissive (in sandbox)
          autoApproveTools: true
          maxThinkingTokens: 4000
          sandbox:
            enabled: true
            allowedNetworkDomains: ["*"]  # Permissive in Docker sandbox
          hooks:
            - name: "post-write-lint"
              trigger: "after:write"
              command: "npm run lint:fix || true"
```

### Settings.json Generation

For each workspace, the tool generates a `settings.json` file:

```python
def generate_settings_json(tool_config: Dict, workspace_id: str) -> Dict:
    """Generate Claude Code settings.json from tool_config"""

    base_settings = {
        "allowedTools": ["*"],  # Permissive - we're in a sandbox
        "autoApproveTools": True,  # Required for headless mode
        "maxThinkingTokens": 4000,
        "sandbox": {
            "enabled": True,
            "allowedNetworkDomains": ["*"]  # Permissive in Docker
        }
    }

    # Merge with tool_config overrides
    if tool_config and "settings" in tool_config:
        deep_merge(base_settings, tool_config["settings"])

    return base_settings
```

The generated `settings.json` is written to:
```
/claude-settings/{user_id}/{workspace_id}/settings.json
```

And mounted at:
```
/root/.claude/settings.json
```

### Environment Variable Injection

```python
def get_container_env_vars(tool_config: Dict) -> Dict[str, str]:
    """Build environment variables for container"""

    env_vars = {
        "ANTHROPIC_API_KEY": tool_config.get("api_key", os.getenv("ANTHROPIC_API_KEY"))
    }

    # Add arbitrary environment variables from config
    if "environment_variables" in tool_config:
        for key, value in tool_config["environment_variables"].items():
            # Resolve ${VAR} references
            if value.startswith("${") and value.endswith("}"):
                env_name = value[2:-1]
                env_vars[key] = os.getenv(env_name, "")
            else:
                env_vars[key] = value

    return env_vars
```

---

## Session Continuity

### How It Works

Claude Code stores session state in SQLite databases under `~/.claude/projects/`. By mounting this as a volume, we achieve persistence across container invocations.

```
/claude-settings/{user_id}/{workspace_id}/
  settings.json
  __store.db              # Session storage
  projects/
    {session_id}/
      messages.json
      context.json
```

### Internal Session Management

**The tool manages session IDs internally** - agents don't need to track them:

```python
class ClaudeCodeToolProvider(DynamicToolProvider):
    def __init__(self):
        super().__init__()
        self.cc_sessions = {}  # {user_id}/{workspace_id} -> session_id

    async def _execute(self, workspace_id: str, user_id: str, prompt: str, ...):
        # Get existing session for this workspace
        session_key = f"{user_id}/{workspace_id}"
        session_id = self.cc_sessions.get(session_key)

        # Execute Claude Code (with session_id if exists)
        result = await run_claude_code_headless(
            prompt=prompt,
            session_id=session_id,  # Resume if exists
            ...
        )

        # Save session for next invocation
        self.cc_sessions[session_key] = result["session_id"]

        return result
```

### Multi-turn Conversation Flow

```
Turn 1:
Agent → claude_code_execute(
            workspace_id="my-project",
            prompt="Create a web scraper"
        )
Tool:   session_key = "user123/my-project"
        session_id = None (first call)
        → Execute CC without -r flag
        → Save returned session_id = "sess_001"

Turn 2:
Agent → claude_code_execute(
            workspace_id="my-project",  # Same workspace
            prompt="Add error handling"
        )
Tool:   session_key = "user123/my-project"
        session_id = "sess_001" (from Turn 1)
        → Execute CC with -r sess_001
        → Claude Code has full context from Turn 1

Turn 3:
Agent → claude_code_execute(
            workspace_id="my-project",
            prompt="Add rate limiting"
        )
Tool:   session_id = "sess_001"
        → Continue same session
        → Claude Code has context from Turns 1-2
```

**Key Insight**: Agents just keep calling the same `workspace_id` - the tool handles session continuity automatically.

---

## Dynamic Tool Implementation

### ClaudeCodeToolProvider with Lifecycle

```python
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicToolProvider, DynamicTool
from typing import List, Dict, Any, Optional

class ClaudeCodeToolProvider(DynamicToolProvider):
    """
    Dynamic tool provider for Claude Code integration.
    Manages session state and workspace lifecycle.
    """

    def __init__(self):
        super().__init__()
        self.cc_sessions = {}  # {user_id}/{workspace_id} -> session_id
        self.workspace_service = None

    async def init(
        self,
        component: "SamAgentComponent",
        tool_config: Dict[str, Any]
    ) -> None:
        """
        Initialize Claude Code tool resources.
        Called once when agent starts.
        """
        # Initialize workspace service
        workspace_base = tool_config.get("workspace_base", "/claude-workspaces")
        self.workspace_service = LocalFilesystemWorkspaceService(workspace_base)

        # Verify Docker daemon is accessible
        await self._verify_docker()

        # Pre-pull container images if configured
        if tool_config.get("prepull_images", False):
            await self._prepull_images(tool_config.get("environments", ["node"]))

        log.info("ClaudeCodeToolProvider initialized")

    async def cleanup(
        self,
        component: "SamAgentComponent",
        tool_config: Dict[str, Any]
    ) -> None:
        """
        Cleanup Claude Code tool resources.
        Called once when agent shuts down.
        """
        # Save session mappings to disk for recovery
        await self._persist_session_mappings()

        # Cleanup any orphaned session workspaces
        await self._cleanup_orphaned_workspaces()

        log.info("ClaudeCodeToolProvider cleaned up")

    def create_tools(
        self,
        tool_config: Optional[Dict] = None
    ) -> List[DynamicTool]:
        """
        Create the Claude Code tools.
        Called by framework to get tool instances.
        """
        return [
            ClaudeCodeExecuteTool(self.workspace_service, self.cc_sessions, tool_config),
            ClaudeCodeListWorkspacesTool(self.workspace_service, tool_config),
            ClaudeCodeReadFilesTool(self.workspace_service, tool_config),
            ClaudeCodeCreateVersionTool(self.workspace_service, tool_config),
            ClaudeCodeExportWorkspaceTool(self.workspace_service, tool_config),
            ClaudeCodeImportWorkspaceTool(self.workspace_service, tool_config),
        ]
```

### Example Tool Implementation

```python
class ClaudeCodeExecuteTool(DynamicTool):
    """Execute Claude Code in a workspace"""

    def __init__(
        self,
        workspace_service: BaseWorkspaceService,
        session_store: Dict[str, str],
        tool_config: Optional[Dict] = None
    ):
        super().__init__(tool_config)
        self.workspace_service = workspace_service
        self.session_store = session_store

    @property
    def tool_name(self) -> str:
        return "claude_code_execute"

    @property
    def tool_description(self) -> str:
        return """Execute Claude Code AI assistant in a persistent workspace.
        Claude Code autonomously reads files, writes code, runs tests, and verifies.
        Sessions persist automatically - just keep using the same workspace_id."""

    @property
    def parameters_schema(self) -> adk_types.Schema:
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "prompt": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Instruction for Claude Code"
                ),
                "workspace_id": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Unique workspace identifier"
                ),
                "workspace_type": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="'session' (temporary) or 'app' (persistent)",
                    default="session"
                ),
                "environment": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="'node', 'python', or 'go'",
                    default="node"
                ),
                "workspace_name": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Display name for workspace"
                ),
                "workspace_description": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Description for CLAUDE.md"
                ),
            },
            required=["prompt", "workspace_id"]
        )

    async def _run_async_impl(
        self,
        args: dict,
        tool_context: ToolContext,
        credential: Optional[str] = None
    ) -> dict:
        """Execute Claude Code"""

        user_id = get_user_id(tool_context)
        workspace_id = args["workspace_id"]
        workspace_type = args.get("workspace_type", "session")
        environment = args.get("environment", "node")

        # Get or create workspace
        workspace_path = await self.workspace_service.get_workspace_path(
            workspace_id, user_id, workspace_type
        )

        if not workspace_path:
            workspace_path = await self.workspace_service.create_workspace(
                workspace_id=workspace_id,
                user_id=user_id,
                workspace_type=workspace_type,
                metadata={
                    "environment": environment,
                    "name": args.get("workspace_name", workspace_id),
                    "description": args.get("workspace_description", "")
                }
            )

            # Initialize workspace (CLAUDE.md, git, etc.)
            await self._initialize_workspace(workspace_path, environment, args)

        # Get session ID for this workspace
        session_key = f"{user_id}/{workspace_id}"
        session_id = self.session_store.get(session_key)

        # Execute Claude Code
        settings_path = self._get_settings_path(user_id, workspace_id)
        result = await run_claude_code_headless(
            workspace_path=workspace_path,
            settings_path=settings_path,
            prompt=args["prompt"],
            session_id=session_id,
            tool_config=self.tool_config
        )

        # Save session ID for next invocation
        self.session_store[session_key] = result["session_id"]

        result["workspace_id"] = workspace_id
        result["workspace_path"] = str(workspace_path)
        result["workspace_type"] = workspace_type

        return result
```

---

## Usage Examples

### Example 1: Ad-hoc Data Analysis

```python
# User asks agent: "Analyze this CSV file and create visualizations"

# Agent uploads CSV to workspace, then:
result = await agent.use_tool("claude_code_execute", {
    "prompt": "Analyze data.csv and create visualizations using matplotlib",
    "workspace_id": "data-analysis",
    "environment": "python"
})

# Claude Code autonomously:
# 1. Reads data.csv
# 2. Analyzes data structure
# 3. Writes analysis script
# 4. Generates plots
# 5. Returns summary

agent.send_message(f"Analysis complete: {result['output']}")
```

### Example 2: Multi-turn Application Development

```python
# User: "Build me a todo list app"

# Turn 1: Initialize
result1 = await agent.use_tool("claude_code_execute", {
    "prompt": "Create a React todo list app with Vite and Tailwind",
    "workspace_id": "todo-app",
    "workspace_type": "app",
    "environment": "node"
})
# Tool manages session internally

# Turn 2: Add features (session continues automatically)
result2 = await agent.use_tool("claude_code_execute", {
    "prompt": "Add local storage persistence",
    "workspace_id": "todo-app"  # Same workspace = same session
})

# Turn 3: Add more features
result3 = await agent.use_tool("claude_code_execute", {
    "prompt": "Add categories and filtering",
    "workspace_id": "todo-app"
})

# Turn 4: Create version
await agent.use_tool("claude_code_create_version", {
    "workspace_id": "todo-app",
    "workspace_type": "app",
    "bump": "major",  # v1.0.0
    "description": "Initial release with persistence and categories"
})
```

### Example 3: GitHub Clone → Claude Code

```python
# User: "Clone myorg/myrepo and add error handling"

# Step 1: GitHub tool clones into workspace
github_result = agent.use_tool("github_clone", {
    "repo_url": "https://github.com/myorg/myrepo",
    "workspace_id": "myorg-myrepo"  # Both tools use WorkspaceService
})

# Step 2: Claude Code operates on same workspace
cc_result = agent.use_tool("claude_code_execute", {
    "workspace_id": "myorg-myrepo",  # Same workspace_id
    "prompt": "Add comprehensive error handling to all API endpoints"
})

# Both tools see the same files via WorkspaceService!
```

---

## Security Considerations

### Sandboxing

1. **Docker Isolation**: Claude Code runs in ephemeral containers
   - Host filesystem only accessible via explicit volume mounts
   - No access to host network except container network
   - Container removed after execution (--rm flag)

2. **Claude Code Sandbox**: Settings enforce restrictions
   - Permissive in Docker (allowedTools: ["*"])
   - Network access allowed (we're already in container)
   - OS-level sandboxing still active within container

3. **Volume Permissions**: SELinux/AppArmor contexts
   - `:Z` flag on volume mounts for SELinux
   - Workspace directories owned by appropriate user
   - No access to sensitive host paths

### API Key Management

```python
# Recommended: Pass via tool_config from secure storage
tool_config = {
    "api_key": os.getenv("ANTHROPIC_API_KEY"),  # From secure env
    "environment_variables": {
        "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL"),
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN")
    }
}

# NOT RECOMMENDED: Hardcoded in agent config
# BAD: "api_key": "sk-ant-..."
```

API keys should:
- Be injected from secure environment variables
- Never be stored in workspace files
- Be rotated regularly
- Use separate keys per environment (dev/staging/prod)

### Workspace Isolation

- User workspaces are isolated: `/workspaces/{user_id}/`
- No cross-user access
- Session workspaces cleaned up after SAM session ends
- App workspaces require explicit export for sharing

---

## Future Enhancements

### Phase 2: Advanced Features

1. **Streaming Output**: Stream Claude Code output in real-time
   - Use `--stream` flag instead of `-p`
   - Parse SSE events and forward to SAM agent
   - Better UX for long-running tasks

2. **Custom Tool Injection**: Add SAM-specific tools to Claude Code
   - Tool to call other SAM agents
   - Tool to access SAM artifact service
   - Tool to query SAM databases

3. **Collaborative Workspaces**: Multi-agent collaboration
   - Multiple agents working on same workspace
   - Locking mechanism for concurrent edits
   - Change notifications

4. **Workspace Templates**: Pre-configured starting points
   - "React App Template"
   - "FastAPI Service Template"
   - "Data Analysis Template"

### Phase 3: UI Integration

1. **Frontend Workspace Browser**: View workspace files in UI
2. **Live Preview**: Iframe preview for web apps
3. **Version Diff Viewer**: Compare workspace versions
4. **Session Replay**: Replay Claude Code session history

---

## Open Questions

1. **Container Image Management**:
   - Who builds and maintains the `claude-code-{env}:latest` images?
   - How do we handle updates to Claude Code CLI?
   - Should we version-pin the CLI?

2. **Workspace Cleanup**:
   - When to delete session workspaces?
   - Retention policy for old workspaces?
   - Archive vs. delete?

3. **Cost Management**:
   - How to track/limit Claude Code costs per user?
   - Budget alerts when approaching limits?
   - Cost attribution per workspace?

4. **Multi-user Scenarios**:
   - Can workspaces be shared between users?
   - Permissions model for workspace access?
   - Team vs. personal workspaces?

5. **Error Recovery**:
   - What if Claude Code container fails to start?
   - How to handle Docker daemon unavailability?
   - Retry logic for transient failures?

---

## Appendix A: File Locations

```
Repository Structure:
  src/solace_agent_mesh/
    common/workspace/
      base_workspace_service.py         # NEW: Abstract interface
      local_filesystem_workspace.py     # NEW: Local implementation
      nfs_workspace.py                  # NEW: NFS implementation

    agent/tools/
      claude_code/
        tool_provider.py                # ClaudeCodeToolProvider
        execute_tool.py                 # claude_code_execute
        list_workspaces_tool.py         # claude_code_list_workspaces
        ... other tools ...

  docker/
    claude-code-node/
      Dockerfile
    claude-code-python/
      Dockerfile
    claude-code-go/
      Dockerfile

  config/
    examples/
      agent-with-claude-code.yaml       # Example agent config

Runtime Structure:
  /claude-workspaces/                   # WorkspaceService storage
    {user_id}/
      sessions/{workspace_id}/
      apps/{workspace_id}/

  /claude-settings/                     # Claude Code configuration
    {user_id}/{workspace_id}/
      settings.json
      __store.db
      projects/
```

---

## Appendix B: Example Agent Configuration

```yaml
# config/examples/coding-agent.yaml

agent_name: "coding-assistant"

model:
  name: "claude-3-7-sonnet-20250219"

instruction: |
  You are a helpful coding assistant with access to Claude Code.

  When users ask you to write code, use the claude_code_execute tool
  to leverage AI-assisted development.

  Session continuity is automatic - just keep using the same workspace_id
  for related requests.

tools:
  dynamic:
    - provider: "solace_agent_mesh.agent.tools.claude_code.ClaudeCodeToolProvider"
      config:
        # API Configuration
        api_key: "${ANTHROPIC_API_KEY}"
        model: "claude-sonnet-4"
        max_iterations: 15

        # Workspace Configuration
        workspace_base: "/claude-workspaces"

        # Arbitrary Environment Variables
        environment_variables:
          ANTHROPIC_BASE_URL: "${ANTHROPIC_BASE_URL}"
          ANTHROPIC_BEDROCK_BASE_URL: "${ANTHROPIC_BEDROCK_BASE_URL}"
          GITHUB_TOKEN: "${GITHUB_TOKEN}"

        # Claude Code Settings
        settings:
          allowedTools: ["*"]  # Permissive in sandbox
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

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-05 | System | Initial design document |
| 2.0 | 2024-12-05 | System | Major revision: WorkspaceService abstraction, container mount requirement clarification, session management internal to tool, tool_config parameter changes |
