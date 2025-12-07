# Claude Code Tools - Developer Guide

## 1. Architecture Overview

The Claude Code tools integrate Anthropic's Claude Code CLI into SAM through a containerized execution model. The implementation consists of several key components:

- **Tool Provider**—Manages tool lifecycle and session state
- **Dynamic Tools**—Seven specialized tools for different operations
- **Container Runtime**—Docker/Podman execution with isolated environments
- **Workspace Service**—File system abstraction for workspace management
- **Streaming Parser**—Real-time status updates via NDJSON stream processing
- **Settings Generator**—Dynamic Claude Code configuration

### Component Relationships

```
ClaudeCodeToolProvider (tool_provider.py)
    ├── Session Store: {user/workspace -> session_id}
    ├── Workspace Service: LocalFilesystemWorkspaceService
    └── Creates 7 Dynamic Tools:
        ├── ClaudeCodeExecuteTool (execute_tool.py)
        ├── ClaudeCodeListWorkspacesTool (list_workspaces_tool.py)
        ├── ClaudeCodeListSessionsTool (list_sessions_tool.py)
        ├── ClaudeCodeReadFilesTool (read_files_tool.py)
        ├── ClaudeCodeCreateVersionTool (create_version_tool.py)
        ├── ClaudeCodeExportWorkspaceTool (export_workspace_tool.py)
        └── ClaudeCodeImportWorkspaceTool (import_workspace_tool.py)

Each tool shares:
    - workspace_service reference
    - cc_sessions dict (session store)
    - tool_config dict
```

### Execution Flow

1. **Tool Registration**—Framework calls <code>ClaudeCodeToolProvider.create_tools()</code>
2. **Tool Invocation**—Agent calls tool via <code>_run_async_impl()</code>
3. **Workspace Resolution**—Get or create workspace via workspace service
4. **Settings Generation**—Generate settings.json from tool_config
5. **Container Execution**—Run Claude Code CLI in Docker/Podman
6. **Stream Processing**—Parse NDJSON output for status updates (if streaming enabled)
7. **Session Tracking**—Store session_id for next invocation
8. **Result Return**—Return structured result to agent

## 2. File Organization

The Claude Code tools are located in <code>src/solace_agent_mesh/agent/tools/claude_code/</code>:

```
claude_code/
├── tool_provider.py          # DynamicToolProvider implementation
├── execute_tool.py            # Main execution tool
├── list_workspaces_tool.py    # Workspace listing
├── list_sessions_tool.py      # Session listing
├── read_files_tool.py         # File reading
├── create_version_tool.py     # Git versioning
├── export_workspace_tool.py   # Workspace export
├── import_workspace_tool.py   # Workspace import
├── utils.py                   # Container execution and helpers
└── streaming_utils.py         # NDJSON stream parsing
```

### Core Modules

**tool_provider.py**—Entry point for the tool provider. Implements <code>DynamicToolProvider</code> interface and manages shared state (session store, workspace service) across all tools.

**execute_tool.py**—Primary tool for code execution. Handles workspace initialization, settings generation, container execution, and status update publishing.

**utils.py**—Container execution logic, settings generation, CLAUDE.md generation, and environment variable management.

**streaming_utils.py**—NDJSON stream parser for real-time status updates. Filters events and publishes selected updates to SAM event mesh.

## 3. Tool Provider Implementation

### ClaudeCodeToolProvider

The provider manages tool lifecycle and shared state:

```python
class ClaudeCodeToolProvider(DynamicToolProvider):
    def __init__(self):
        super().__init__()
        self.cc_sessions: Dict[str, str] = {}  # Session store
        self.workspace_service: Optional[BaseWorkspaceService] = None
        self.settings_base: str = "/claude-settings"
        self.tool_config: Optional[Dict[str, Any]] = None
        self._initialized: bool = False
```

**Key Responsibilities:**

- Initialize workspace service from tool_config
- Maintain session store mapping {user_id/workspace_id -> session_id}
- Create and configure all seven tool instances
- Share references (workspace_service, cc_sessions) with tools

### Initialization Pattern

The provider uses a two-phase initialization:

1. **Construction**—Lightweight init, no I/O
2. **Configuration**—Called from <code>create_tools()</code> with tool_config

```python
def _initialize_sync(self, tool_config: Dict[str, Any]) -> None:
    if self._initialized:
        return

    self.tool_config = tool_config
    workspace_base = tool_config.get("workspace_base", "/claude-workspaces")
    self.workspace_service = LocalFilesystemWorkspaceService(workspace_base)
    self.settings_base = tool_config.get("settings_base", "/claude-settings")
    self._initialized = True
```

This pattern ensures:
- Idempotent initialization
- No premature I/O operations
- Configuration flexibility

### Session Management

Sessions are tracked in a dict with composite keys:

```python
session_key = f"{user_id}/{workspace_id}"
self.cc_sessions[session_key] = session_id
```

The execute tool automatically:
1. Checks for existing session on workspace_key
2. Passes session_id to container if found
3. Updates session store with new session_id from response

This provides transparent session continuity without agent involvement.

## 4. Execute Tool Deep Dive

### ClaudeCodeExecuteTool

The execute tool is the primary interface for code generation. It orchestrates:

- Workspace lifecycle (creation, initialization)
- Settings generation
- Container execution
- Status update streaming
- Session management

### Core Implementation

```python
async def _run_async_impl(
    self,
    args: dict,
    tool_context: Optional[ToolContext] = None,
    credential: Optional[str] = None,
) -> dict:
    # 1. Extract parameters
    user_id = get_user_id_from_context(tool_context)
    workspace_id = args["workspace_id"]
    workspace_type = args.get("workspace_type", "session")
    environment = args.get("environment", "node")
    prompt = args["prompt"]

    # 2. Get or create workspace
    workspace_path = await self.workspace_service.get_workspace_path(
        workspace_id, user_id, workspace_type
    )
    if not workspace_path:
        workspace_path = await self.workspace_service.create_workspace(...)
        await self._initialize_workspace(...)

    # 3. Resolve session ID
    session_key = f"{user_id}/{workspace_id}"
    resume_session_id = args.get("resume_session_id")
    session_id = resume_session_id or self.session_store.get(session_key)

    # 4. Ensure settings directory
    settings_path = get_settings_path(self.settings_base, user_id, workspace_id)
    ensure_settings_directory(settings_path, self.tool_config, workspace_id)

    # 5. Create status callback
    status_callback = self._create_status_callback(tool_context)

    # 6. Execute Claude Code
    result = await run_claude_code_headless(
        workspace_path=workspace_path,
        settings_path=settings_path,
        prompt=prompt,
        environment=environment,
        tool_config=self.tool_config,
        session_id=session_id,
        resume_session=bool(resume_session_id),
        stream=enable_streaming,
        status_callback=status_callback,
    )

    # 7. Save session ID
    if result.get("session_id"):
        self.session_store[session_key] = result["session_id"]

    # 8. Return enhanced result
    result["workspace_id"] = workspace_id
    result["workspace_path"] = str(workspace_path)
    result["workspace_type"] = workspace_type
    return result
```

### Workspace Initialization

New workspaces are initialized with git and CLAUDE.md:

```python
async def _initialize_workspace(
    self,
    workspace_path: Path,
    environment: str,
    workspace_name: str,
    workspace_description: str,
) -> None:
    # Create CLAUDE.md
    claude_md_content = generate_claude_md(
        workspace_name, workspace_description, environment
    )
    claude_md_path = workspace_path / "CLAUDE.md"
    claude_md_path.write_text(claude_md_content)

    # Initialize git repository
    await asyncio.create_subprocess_exec("git", "init", cwd=str(workspace_path))
    await asyncio.create_subprocess_exec(
        "git", "config", "user.name", "Claude Code", cwd=str(workspace_path)
    )
    await asyncio.create_subprocess_exec(
        "git", "config", "user.email", "cc@workspace", cwd=str(workspace_path)
    )
    await asyncio.create_subprocess_exec(
        "git", "add", "CLAUDE.md", cwd=str(workspace_path)
    )
    await asyncio.create_subprocess_exec(
        "git", "commit", "-m", "Initial commit: Add CLAUDE.md",
        cwd=str(workspace_path)
    )
```

This provides:
- Version control from the start
- Context for Claude Code via CLAUDE.md
- Clean initial state

## 5. Container Execution

### Container Runtime Detection

The system auto-detects Docker or Podman:

```python
def detect_container_runtime() -> str:
    global _detected_container_runtime
    if _detected_container_runtime:
        return _detected_container_runtime

    if shutil.which("docker"):
        _detected_container_runtime = "docker"
        return "docker"

    if shutil.which("podman"):
        _detected_container_runtime = "podman"
        return "podman"

    raise RuntimeError("No container runtime found")
```

Caching ensures detection runs once per process.

### Container Execution Flow

The <code>run_claude_code_headless()</code> function builds and executes container commands:

```python
async def run_claude_code_headless(
    workspace_path: Path,
    settings_path: Path,
    prompt: str,
    environment: str,
    tool_config: Optional[Dict[str, Any]],
    session_id: Optional[str] = None,
    resume_session: bool = False,
    stream: bool = False,
    status_callback: Optional[callable] = None,
) -> Dict[str, Any]:
```

**Command Construction:**

1. **Base Command**—Runtime, image, user
2. **Volume Mounts**—Workspace and settings
3. **Environment Variables**—API keys, config
4. **Claude Code Arguments**—Prompt, model, session

**Volume Mounting:**

```python
docker_cmd = [
    container_runtime, "run", "--rm",
    "--user", container_user,
    "-v", f"{workspace_path}:/workspace:Z",
    "-v", f"{settings_path}:{container_home}/.claude:Z",
]
```

The <code>:Z</code> suffix enables SELinux compatibility.

**Environment Variable Injection:**

```python
env_vars = get_container_env_vars(tool_config)
for key, value in env_vars.items():
    docker_cmd.extend(["-e", f"{key}={value}"])
```

**Autonomous Prompt Wrapping:**

```python
autonomous_prompt = (
    f"TASK: {prompt}\n\n"
    "Execute this task immediately. Do not ask for permission or provide "
    "introductions. Take action, complete the task, and report the results."
)
docker_cmd.extend(["-p", autonomous_prompt])
```

This ensures Claude Code operates in autonomous mode.

### Session Resumption

Resume is controlled by <code>resume_session</code> parameter:

```python
if resume_session and session_id:
    docker_cmd.extend(["-r", session_id])
    log.info(f"Resuming Claude Code session: {session_id}")
else:
    log.info("Starting new Claude Code session")
```

**Resume Behavior:**

- **resume_session=True**—Prompt becomes "answer" to previous Claude Code question
- **resume_session=False**—New conversation, even if session_id exists

### Output Processing

The function handles two output modes:

**Streaming Mode:**

```python
if stream and status_callback:
    from .streaming_utils import process_claude_stream

    stream_result = await process_claude_stream(proc.stdout, status_callback)
    await proc.wait()
    stderr = await proc.stderr.read()

    # Synthesize JSON result from stream
    stdout_str = json.dumps({
        "type": "result",
        "subtype": "success",
        "result": stream_result.get("text", ""),
        "session_id": stream_result.get("session_id", ""),
        "tools_used": stream_result.get("tools_used", []),
    })
```

**Non-Streaming Mode:**

```python
else:
    stdout, stderr = await proc.communicate()
    stdout_str = stdout.decode()
    stderr_str = stderr.decode()
```

Both modes produce the same result structure.

## 6. Settings Generation

### Settings Architecture

Claude Code settings control:
- Tool permissions
- Sandbox configuration
- API credentials
- Behavior overrides

### Generation Logic

The <code>generate_settings_json()</code> function creates settings.json:

```python
def generate_settings_json(
    tool_config: Optional[Dict[str, Any]],
    workspace_id: str,
) -> Dict[str, Any]:
    # Base settings
    base_settings = {
        "allowedTools": ["*"],
        "autoApproveTools": True,
        "maxThinkingTokens": 4000,
        "sandbox": {
            "enabled": True,
            "allowedNetworkDomains": ["*"],
        },
    }

    # Add environment variables
    env_vars = get_container_env_vars(tool_config)
    if env_vars:
        base_settings["env"] = env_vars

    # Merge with user overrides
    if tool_config and "settings" in tool_config:
        base_settings = deep_merge(base_settings, tool_config["settings"])

    # Ensure autonomous instruction
    autonomous_instruction = (
        "\n\nIMPORTANT: You are running in headless/autonomous mode. "
        "When given a task, take immediate action without asking for confirmation."
    )
    if "instruction" in base_settings:
        base_settings["instruction"] += autonomous_instruction
    else:
        base_settings["instruction"] = "You are an autonomous AI coding assistant..."

    return base_settings
```

**Key Principles:**

- Permissive defaults (we're in a sandbox)
- Environment variables in settings.json (not container env)
- Deep merge preserves user customizations
- Autonomous instruction always appended

### Environment Variable Resolution

Environment variables support <code>${VAR}</code> references:

```python
def get_container_env_vars(tool_config: Optional[Dict[str, Any]]) -> Dict[str, str]:
    env_vars = {}

    # Add API key
    if "api_key" in tool_config:
        env_vars["ANTHROPIC_API_KEY"] = tool_config["api_key"]

    # Add arbitrary variables
    if "environment_variables" in tool_config:
        for key, value in tool_config["environment_variables"].items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_name = value[2:-1]
                env_vars[key] = os.getenv(env_name, "")
            else:
                env_vars[key] = str(value)

    return env_vars
```

This enables configuration like:

```yaml
environment_variables:
  ANTHROPIC_BASE_URL: "${CUSTOM_API_URL}"
  NPM_TOKEN: "static-value"
```

## 7. Streaming Implementation

### NDJSON Stream Processing

Claude Code CLI outputs NDJSON (newline-delimited JSON) when <code>--output-format stream-json</code> is used.

The <code>streaming_utils.py</code> module processes this stream:

```python
async def process_claude_stream(
    stdout: asyncio.StreamReader,
    status_callback: callable,
) -> Dict[str, Any]:
    result_text = ""
    session_id = ""
    tools_used = []

    while True:
        line = await stdout.readline()
        if not line:
            break

        try:
            event = json.loads(line.decode())
            event_type = event.get("type")

            # Track session ID
            if "session_id" in event:
                session_id = event["session_id"]

            # Handle different event types
            if event_type == "tool_use":
                tools_used.append(event.get("tool_name"))
                status_callback("tool_use", {
                    "message": f"Using tool: {event.get('tool_name')}"
                })
            elif event_type == "text":
                result_text += event.get("text", "")
            elif event_type == "file_edit":
                status_callback("file_edit", {
                    "message": f"Editing file: {event.get('file_path')}"
                })
            # ... more event types
        except json.JSONDecodeError:
            continue

    return {
        "text": result_text,
        "session_id": session_id,
        "tools_used": tools_used,
    }
```

### Event Filtering

Not all events are published as status updates. The parser selectively reports:

- Tool usage (Bash, Read, Write, Edit)
- File operations
- Build/test execution
- Errors

Events like <code>thinking</code> and <code>partial_message</code> are filtered out to reduce noise.

### Status Update Publishing

The execute tool creates a status callback that publishes to SAM:

```python
def status_callback_impl(event_type: str, event_data: dict):
    message = event_data.get('message', '')
    prefixed_message = f"Coding tool: {message}"

    if a2a_context and host_component:
        progress_data = AgentProgressUpdateData(status_text=prefixed_message)
        success = host_component.publish_data_signal_from_thread(
            a2a_context=a2a_context,
            signal_data=progress_data,
            skip_buffer_flush=False,
            log_identifier="[ClaudeCode]",
        )
```

The <code>publish_data_signal_from_thread()</code> method is used because streaming runs in async context but needs to publish on SAM's event loop.

## 8. SAM Integration

### Host Component Access

The tool accesses the SAM host component via tool_context:

```python
from ...utils.context_helpers import get_host_component_from_tool_context

host_component = get_host_component_from_tool_context(tool_context)
```

The helper safely traverses:

```python
tool_context._invocation_context.agent.host_component
```

### A2A Context

The A2A context is retrieved from tool_context state:

```python
a2a_context = tool_context.state.get("a2a_context")
```

This context provides:
- <code>logical_task_id</code>—Task identifier for status updates
- <code>contextId</code>—Conversation context identifier

### Cross-Thread Publishing

Status updates are published from async context to SAM's event loop:

```python
host_component.publish_data_signal_from_thread(
    a2a_context=a2a_context,
    signal_data=progress_data,
    skip_buffer_flush=False,
    log_identifier="[ClaudeCode]",
)
```

The <code>publish_data_signal_from_thread()</code> method:
1. Creates data signal event from <code>AgentProgressUpdateData</code>
2. Schedules publish on SAM's async loop via <code>asyncio.run_coroutine_threadsafe()</code>
3. Returns immediately without blocking caller

This enables real-time updates during long-running code generation.

## 9. Workspace Service Integration

### BaseWorkspaceService

The tools use <code>BaseWorkspaceService</code> interface for workspace operations:

```python
class BaseWorkspaceService(ABC):
    @abstractmethod
    async def get_workspace_path(
        self, workspace_id: str, user_id: str, workspace_type: str
    ) -> Optional[Path]:
        pass

    @abstractmethod
    async def create_workspace(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        pass

    @abstractmethod
    async def list_workspaces(
        self, user_id: str, workspace_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        pass
```

### LocalFilesystemWorkspaceService

The current implementation uses local filesystem:

```python
class LocalFilesystemWorkspaceService(BaseWorkspaceService):
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
```

**Directory Structure:**

```
{base_path}/
├── {user_id}/
│   ├── sessions/
│   │   └── {workspace_id}/
│   └── apps/
│       └── {workspace_id}/
```

**Metadata Storage:**

Workspace metadata is stored in <code>.workspace_metadata.json</code>:

```json
{
  "workspace_id": "my-app",
  "workspace_type": "app",
  "created_at": "2024-12-06T10:30:00Z",
  "metadata": {
    "environment": "node",
    "name": "My App",
    "description": "A sample application"
  }
}
```

### Extending Workspace Service

To use a different storage backend (S3, database, etc.):

1. Implement <code>BaseWorkspaceService</code> interface
2. Update <code>ClaudeCodeToolProvider._initialize_sync()</code>:
   ```python
   self.workspace_service = YourCustomWorkspaceService(...)
   ```
3. Ensure implementation is thread-safe and async-compatible

## 10. Docker Container Images

### Container Architecture

Each environment has a dedicated Dockerfile:

- <code>docker/claude-code-node/Dockerfile</code>—Node.js 20 on Debian slim
- <code>docker/claude-code-python/Dockerfile</code>—Python 3.11 on Debian slim
- <code>docker/claude-code-go/Dockerfile</code>—Go 1.21 on Alpine

### Common Container Pattern

All containers follow this pattern:

```dockerfile
FROM <base-image>

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ripgrep \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (if needed for Claude Code CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Create non-root user
RUN useradd -m -s /bin/bash <username>

# Create directories
RUN mkdir -p /workspace /home/<username>/.claude && \
    chown -R <username>:<username> /workspace /home/<username>/.claude

# Switch to non-root user
USER <username>
WORKDIR /workspace

# Configure git
RUN git config --global user.name "Claude Code" && \
    git config --global user.email "cc@workspace" && \
    git config --global init.defaultBranch main

ENTRYPOINT ["claude"]
```

### Non-Root User Requirement

Containers run as non-root users because:
- Claude Code CLI requires <code>--dangerously-skip-permissions</code> for headless mode
- This flag only works with non-root users
- Security best practice for containerized execution

### procps Package

The <code>procps</code> package (or <code>procps-ng</code> on Alpine) is required because:
- Claude Code CLI uses <code>ps</code> command internally for process management
- Without it, container execution fails with "spawn ps ENOENT"

## 11. Extension Patterns

### Adding New Tools

To add a new Claude Code tool:

1. Create tool file in <code>claude_code/</code>:
   ```python
   from ..dynamic_tool import DynamicTool

   class ClaudeCodeNewTool(DynamicTool):
       def __init__(self, workspace_service, tool_config):
           super().__init__(tool_config)
           self.workspace_service = workspace_service

       @property
       def tool_name(self) -> str:
           return "claude_code_new_operation"

       @property
       def tool_description(self) -> str:
           return "Description for LLM"

       @property
       def parameters_schema(self) -> adk_types.Schema:
           return adk_types.Schema(...)

       async def _run_async_impl(self, args, tool_context, credential):
           # Implementation
           pass
   ```

2. Add to <code>tool_provider.py</code>:
   ```python
   from .new_tool import ClaudeCodeNewTool

   def create_tools(self, tool_config):
       return [
           # ... existing tools
           ClaudeCodeNewTool(
               self.workspace_service,
               self.tool_config,
           ),
       ]
   ```

### Custom Container Images

To use custom container images:

1. Create new Dockerfile with required tools
2. Build and tag image:
   ```bash
   docker build -t claude-code-custom:latest .
   ```
3. Update <code>utils.py</code> to recognize new environment:
   ```python
   container_user_map = {
       "custom": {"user": "customuser", "home": "/home/customuser"},
   }
   ```

### Settings Customization

To add new settings options:

1. Update <code>generate_settings_json()</code> in <code>utils.py</code>
2. Document new options in tool_config
3. Test with Claude Code CLI to verify behavior

### Streaming Event Handling

To handle new Claude Code event types:

1. Update <code>process_claude_stream()</code> in <code>streaming_utils.py</code>
2. Add event type handlers:
   ```python
   elif event_type == "new_event_type":
       status_callback("new_event", {
           "message": f"New event: {event.get('data')}"
       })
   ```

## 12. Testing and Debugging

### Test File Structure

Tests are located in <code>tests/integration/test_claude_code_tools.py</code>:

```python
import asyncio
from unittest.mock import Mock
from solace_agent_mesh.agent.tools.claude_code.tool_provider import (
    ClaudeCodeToolProvider
)

async def test_execute_tool():
    # Setup
    tool_config = {
        "api_key": "test-key",
        "workspace_base": "/tmp/workspaces",
        "settings_base": "/tmp/settings",
    }

    provider = ClaudeCodeToolProvider()
    tools = provider.create_tools(tool_config)
    execute_tool = next(t for t in tools if t.tool_name == "claude_code_execute")

    # Create mock context
    mock_context = Mock()
    mock_context.user_id = "test_user"

    # Execute
    result = await execute_tool.run_async(
        args={
            "prompt": "Create a simple hello.txt file",
            "workspace_id": "test-workspace",
            "environment": "node",
        },
        tool_context=mock_context,
    )

    # Assertions
    assert result["status"] == "success"
    assert "session_id" in result
```

### Debug Logging

Enable debug logging to trace execution:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Key log points:
- Container command construction
- Session ID resolution
- Settings generation
- Stream event processing

### Common Issues

**Issue: Container not found**
- Verify images are built: <code>docker images | grep claude-code</code>
- Check image names match: <code>claude-code-{environment}:latest</code>

**Issue: Permission denied in workspace**
- Verify workspace paths are writable
- Check SELinux contexts on volume mounts

**Issue: Session not resuming**
- Check session store contents: <code>provider.cc_sessions</code>
- Verify <code>resume_session_id</code> parameter is set

**Issue: Streaming not working**
- Verify <code>enable_streaming: true</code> in tool_config
- Check <code>status_callback</code> is created
- Ensure A2A context is available in tool_context

## 13. Performance Considerations

### Container Startup Time

Container startup adds 2-5 seconds per invocation. To optimize:
- Use persistent workspaces for multi-turn tasks
- Consider container reuse (requires architectural changes)
- Pre-pull images in deployment

### Workspace Storage

Workspaces accumulate over time. Implement cleanup:
- Auto-delete session workspaces after timeout
- Archive old app workspaces
- Monitor disk usage

### Session Store Memory

The session store is in-memory and grows unbounded. For production:
- Implement LRU eviction
- Persist to Redis or database
- Add TTL for session entries

### Streaming Overhead

Streaming adds parsing overhead but provides UX value. For high-throughput scenarios:
- Disable streaming: <code>enable_streaming: false</code>
- Batch operations where possible
- Use non-streaming mode for automated workflows

## 14. Security Considerations

### Container Isolation

Containers provide process isolation but share:
- Host kernel
- Container runtime

For multi-tenant deployments:
- Use separate container runtimes per tenant
- Implement resource limits (CPU, memory, disk)
- Network isolation via container networks

### Workspace Access Control

The current implementation provides user-level isolation via directory structure. For stronger isolation:
- Implement access control in workspace service
- Use encrypted filesystems
- Add audit logging for workspace operations

### API Key Management

API keys are passed via environment variables in settings.json. Best practices:
- Use secrets management (Vault, AWS Secrets Manager)
- Rotate keys regularly
- Monitor API usage for anomalies

### Code Execution Risks

Claude Code generates and executes code. Mitigate risks:
- Containers run as non-root
- Network access is controllable via <code>allowedNetworkDomains</code>
- File system is limited to workspace directory
- Review generated code before deployment

## 15. Future Enhancements

### Planned Improvements

- **Container Pooling**—Reuse containers for faster execution
- **Workspace Templates**—Pre-configured workspaces for common frameworks
- **Parallel Execution**—Run multiple Claude Code instances concurrently
- **Enhanced Versioning**—Git tag management and branch support
- **Artifact Publishing**—Direct integration with artifact services
- **Cost Tracking**—Per-workspace cost accounting and budgets

### Extension Points

- **Custom Workspace Backends**—Implement <code>BaseWorkspaceService</code> for S3, GCS, etc.
- **Alternative Runtimes**—Kubernetes pods, AWS Fargate, etc.
- **Enhanced Streaming**—WebSocket forwarding for real-time UI updates
- **Tool Plugins**—Allow custom tools to be injected into Claude Code
