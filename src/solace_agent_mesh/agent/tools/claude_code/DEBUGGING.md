# Debugging Claude Code Tools

## Enhanced Logging (2025-12-06)

The Claude Code tools now include comprehensive logging to help diagnose issues. When an error occurs, you'll see detailed information about what went wrong.

## Log Levels

Set your log level to `DEBUG` to see all diagnostic information:

```yaml
log:
  stdout_log_level: DEBUG  # or INFO for less verbose output
  log_file_level: DEBUG
  log_file: coding-agent.log
```

## What Gets Logged

### 1. Path Validation
```
INFO  | Validating paths...
INFO  |   Workspace path: /Users/user/.claude-workspaces/user123/sessions/my-project
INFO  |   Settings path: /Users/user/.claude-settings/user123/my-project
INFO  | Path validation complete
```

**Common Issues:**
- **Workspace path does not exist**: The workspace hasn't been created yet, or the path is incorrect
- **Workspace path is not a directory**: A file exists at the workspace path instead of a directory

### 2. Container Configuration
```
INFO  | Container runtime: podman
INFO  | Image: claude-code-node:latest
INFO  | Setting 2 environment variables in container
DEBUG |   ANTHROPIC_API_KEY=sk-l0C4g8drKHs5uGpFA...
DEBUG |   ANTHROPIC_BASE_URL=https://lite-llm.mymaas.net
```

**Common Issues:**
- **Container runtime detection failed**: Neither docker nor podman is installed or in PATH
- **Image not found**: Run `docker/build-all.sh` to build the container images

### 3. Claude Code Execution
```
INFO  | Using model: claude-sonnet-4
INFO  | Starting new session
INFO  | Executing Claude Code in node environment
DEBUG | Full command: podman run --rm -v /Users/user/.claude-workspaces/user123/sessions/my-project:/workspace:Z -v /Users/user/.claude-settings/user123/my-project:/root/.claude:Z -e ANTHROPIC_API_KEY=sk-... -e ANTHROPIC_BASE_URL=https://lite-llm.mymaas.net claude-code-node:latest claude -p "Create a simple hello.txt file" --output-format json --model claude-sonnet-4
```

**Common Issues:**
- **Permission denied on volume mount**: Directory permissions issue or SELinux context problem
- **Image pull error**: Container image doesn't exist locally
- **Network error**: API endpoint not reachable

### 4. Execution Results
```
INFO  | Container exit code: 0
DEBUG | Container stdout (first 500 chars): {"output":"I created hello.txt with the content 'Hello from Claude Code!'","session_id":"abc123"...}
```

**On Error (exit code != 0):**
```
INFO  | Container exit code: 125
DEBUG | Container stderr (first 500 chars): Error: unable to find image 'claude-code-node:latest' locally
ERROR | Claude Code execution failed: Container exited with code 125
STDERR: Error: unable to find image 'claude-code-node:latest' locally
```

### 5. Exception Handling
If an exception occurs during execution:
```
ERROR | Failed to execute Claude Code container: [Errno 2] No such file or directory: 'podman'
ERROR | Traceback: ...
ERROR | Command that failed: podman run --rm -v ...
```

## Common Error Patterns

### "Unknown error"
**Before Enhancement:**
```
ERROR | Claude Code execution failed: Unknown error
```

**After Enhancement:**
```
ERROR | Claude Code execution failed: Container exited with code 125
STDERR: Error: unable to find image 'claude-code-node:latest' locally
```

**Solution:** Build container images with `cd docker && ./build-all.sh`

### API Key Issues

**Issue: "Invalid API key · Please run /login"**
```
ERROR | Claude Code execution failed: Container exited with code 1
STDERR: Invalid API key · Please run /login
```

**Root cause:** API key not properly configured in settings.json

**Solution:** The tools now automatically include the API key in the settings.json `env` section (fixed 2025-12-06). Ensure your tool_config has `api_key` set:
```yaml
tools:
  - tool_type: python
    component_module: "solace_agent_mesh.agent.tools.claude_code.tool_provider"
    class_name: "ClaudeCodeToolProvider"
    tool_config:
      api_key: "${ANTHROPIC_API_KEY}"
```

**Issue: "ANTHROPIC_API_KEY environment variable not set"**
```
ERROR | Claude Code execution failed: Container exited with code 1
STDERR: Error: ANTHROPIC_API_KEY environment variable not set
```

**Solution:** Set `api_key` in tool_config or export `ANTHROPIC_API_KEY` environment variable

### Path Mounting Issues (Podman on macOS)
```
ERROR | Claude Code execution failed: Container exited with code 125
STDERR: Error: statfs /tmp/workspace: no such file or directory
```

**Solution:** Use paths under `$HOME` instead of `/tmp`:
```yaml
workspace_base: "${HOME}/.claude-workspaces"
settings_base: "${HOME}/.claude-settings"
```

### JSON Parse Errors
```
ERROR | Failed to parse Claude Code output as JSON: Expecting value: line 1 column 1 (char 0)
ERROR | Raw output (first 1000 chars): Error: Unable to connect to API
```

**Solution:** Check network connectivity and API endpoint configuration

## Debugging Workflow

1. **Enable DEBUG logging** in your agent config
2. **Run your agent** and reproduce the error
3. **Check the log file** specified in `log.log_file`
4. **Look for the error sequence:**
   - Path validation messages
   - Container runtime and image
   - Environment variables being set
   - Container exit code
   - stdout/stderr output
   - Any exceptions with stack traces

5. **Match against common patterns above**

## Example Debug Session

```
2025-12-06 09:39:45,800 | INFO  | solace_agent_mesh.agent.tools.claude_code.utils | Validating paths...
2025-12-06 09:39:45,800 | INFO  | solace_agent_mesh.agent.tools.claude_code.utils |   Workspace path: /home/user/.claude-workspaces/user123/sessions/test
2025-12-06 09:39:45,800 | INFO  | solace_agent_mesh.agent.tools.claude_code.utils |   Settings path: /home/user/.claude-settings/user123/test
2025-12-06 09:39:45,800 | INFO  | solace_agent_mesh.agent.tools.claude_code.utils | Path validation complete
2025-12-06 09:39:45,801 | INFO  | solace_agent_mesh.agent.tools.claude_code.utils | Container runtime: docker
2025-12-06 09:39:45,801 | INFO  | solace_agent_mesh.agent.tools.claude_code.utils | Image: claude-code-node:latest
2025-12-06 09:39:45,801 | INFO  | solace_agent_mesh.agent.tools.claude_code.utils | Setting 2 environment variables in container
2025-12-06 09:39:45,801 | DEBUG | solace_agent_mesh.agent.tools.claude_code.utils |   ANTHROPIC_API_KEY=sk-l0C4g8drKHs5uGpFA...
2025-12-06 09:39:45,801 | DEBUG | solace_agent_mesh.agent.tools.claude_code.utils |   ANTHROPIC_BASE_URL=https://lite-llm.mymaas.net
2025-12-06 09:39:45,801 | INFO  | solace_agent_mesh.agent.tools.claude_code.utils | Using model: claude-sonnet-4
2025-12-06 09:39:45,801 | INFO  | solace_agent_mesh.agent.tools.claude_code.utils | Starting new session
2025-12-06 09:39:45,801 | INFO  | solace_agent_mesh.agent.tools.claude_code.utils | Executing Claude Code in node environment
2025-12-06 09:39:45,801 | DEBUG | solace_agent_mesh.agent.tools.claude_code.utils | Full command: docker run --rm -v ...
2025-12-06 09:39:50,920 | INFO  | solace_agent_mesh.agent.tools.claude_code.utils | Container exit code: 0
2025-12-06 09:39:50,921 | DEBUG | solace_agent_mesh.agent.tools.claude_code.utils | Container stdout (first 500 chars): {"output":"I created a file called hello.txt...","session_id":"abc123","cost_usd":0.0,"duration_ms":4127,"num_turns":1}
```

## Reporting Issues

When reporting issues, please include:
1. The full error message from the log
2. The "Full command:" line showing the exact container command
3. Your agent configuration (with API keys redacted)
4. Container runtime and version: `docker --version` or `podman --version`
5. Output of: `docker images | grep claude-code` or `podman images | grep claude-code`
