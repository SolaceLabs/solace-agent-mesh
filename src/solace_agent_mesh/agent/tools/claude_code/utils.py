"""
Utility functions for Claude Code tool execution.

Includes Docker execution, settings generation, and helper functions.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
import asyncio
import shutil

log = logging.getLogger(__name__)

# Cache for detected container runtime
_detected_container_runtime: Optional[str] = None


def detect_container_runtime() -> str:
    """
    Auto-detect available container runtime.

    Checks for docker first, then podman.

    Returns:
        "docker" or "podman"

    Raises:
        RuntimeError: If neither docker nor podman is found
    """
    global _detected_container_runtime

    # Return cached value if already detected
    if _detected_container_runtime:
        return _detected_container_runtime

    # Check for docker first
    if shutil.which("docker"):
        _detected_container_runtime = "docker"
        log.info("Auto-detected container runtime: docker")
        return "docker"

    # Check for podman
    if shutil.which("podman"):
        _detected_container_runtime = "podman"
        log.info("Auto-detected container runtime: podman")
        return "podman"

    raise RuntimeError(
        "No container runtime found. Please install Docker or Podman to use Claude Code tools."
    )


def generate_settings_json(
    tool_config: Optional[Dict[str, Any]],
    workspace_id: str,
) -> Dict[str, Any]:
    """
    Generate Claude Code settings.json from tool_config.

    Args:
        tool_config: Tool configuration dict
        workspace_id: Workspace identifier (for logging)

    Returns:
        Settings dict ready to be written to settings.json
    """
    # Base settings for headless, sandboxed execution
    base_settings = {
        "allowedTools": ["*"],  # Permissive - we're in a sandbox
        "autoApproveTools": True,  # Required for headless mode
        "maxThinkingTokens": 4000,
        "sandbox": {
            "enabled": True,
            "allowedNetworkDomains": ["*"],  # Permissive in Docker
        },
    }

    # Add environment variables section with API key and other config
    env_vars = get_container_env_vars(tool_config)
    if env_vars:
        base_settings["env"] = env_vars
        log.debug(f"Added {len(env_vars)} environment variables to settings.json")

    # Merge with tool_config overrides
    if tool_config and "settings" in tool_config:
        settings_overrides = tool_config["settings"]
        # Deep merge
        base_settings = deep_merge(base_settings, settings_overrides)

    # CRITICAL: Ensure instruction for autonomous behavior is always present
    # If user settings override the instruction, append our requirement to it
    autonomous_instruction = (
        "\n\nIMPORTANT: You are running in headless/autonomous mode. "
        "When given a task, take immediate action without asking for confirmation. "
        "Do not just acknowledge - actually complete the requested work."
    )

    if "instruction" in base_settings:
        # Append to existing instruction
        base_settings["instruction"] += autonomous_instruction
    else:
        # Use our default instruction
        base_settings["instruction"] = (
            "You are an autonomous AI coding assistant running in headless mode. "
            "When given a task, you should IMMEDIATELY take action without asking for permission. "
            "Proactively read files, write code, run commands, and verify your work. "
            "Do not just acknowledge requests - actually complete them. "
            "Use all available tools to accomplish the task fully and autonomously."
        )

    log.debug(f"Generated settings.json for workspace {workspace_id}")
    return base_settings


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.

    Args:
        base: Base dictionary
        override: Override dictionary

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def get_container_env_vars(tool_config: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """
    Build environment variables for container.

    Args:
        tool_config: Tool configuration dict

    Returns:
        Dict of environment variable name -> value
    """
    env_vars = {}

    if not tool_config:
        return env_vars

    # Add API key
    if "api_key" in tool_config:
        env_vars["ANTHROPIC_API_KEY"] = tool_config["api_key"]
    elif "ANTHROPIC_API_KEY" in os.environ:
        env_vars["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY"]

    # Add arbitrary environment variables from config
    if "environment_variables" in tool_config:
        for key, value in tool_config["environment_variables"].items():
            # Resolve ${VAR} references
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_name = value[2:-1]
                env_vars[key] = os.getenv(env_name, "")
            else:
                env_vars[key] = str(value)

    return env_vars


def get_settings_path(settings_base: str, user_id: str, workspace_id: str) -> Path:
    """
    Get the settings directory path for a workspace.

    Args:
        settings_base: Base path for settings
        user_id: User ID
        workspace_id: Workspace ID

    Returns:
        Path to settings directory
    """
    return Path(settings_base) / user_id / workspace_id


def ensure_settings_directory(
    settings_path: Path,
    tool_config: Optional[Dict[str, Any]],
    workspace_id: str,
) -> None:
    """
    Ensure settings directory exists with settings.json.

    Args:
        settings_path: Path to settings directory
        tool_config: Tool configuration
        workspace_id: Workspace ID
    """
    settings_path.mkdir(parents=True, exist_ok=True)

    # Generate and write settings.json
    settings_json = generate_settings_json(tool_config, workspace_id)
    settings_file = settings_path / "settings.json"

    # Write settings
    settings_content = json.dumps(settings_json, indent=2)
    settings_file.write_text(settings_content)

    # Log what we wrote (with API keys redacted)
    log.info(f"Wrote settings.json to {settings_file}")
    if "env" in settings_json:
        env_keys = list(settings_json["env"].keys())
        log.debug(f"Settings include env vars: {env_keys}")
        if "ANTHROPIC_API_KEY" in settings_json["env"]:
            log.info("API key is configured in settings.json env section")
        if "ANTHROPIC_AUTH_TOKEN" in settings_json["env"]:
            log.info("Auth token is configured in settings.json env section")


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
    """
    Run Claude Code in headless mode inside a Docker/Podman container.

    Args:
        workspace_path: Path to workspace directory
        settings_path: Path to settings directory
        prompt: Prompt for Claude Code
        environment: Environment name (node, python, go)
        tool_config: Tool configuration
        session_id: Optional session ID to resume

    Returns:
        Dict with:
            - status: "success" or "error"
            - output: Claude Code's response
            - session_id: Session ID for continuation
            - metadata: cost_usd, duration_ms, num_turns
            - raw_output: Full JSON from Claude Code
            - error: Error message if status == "error"
    """
    # Ensure paths exist and are directories
    log.info(f"Validating paths...")
    log.info(f"  Workspace path: {workspace_path}")
    log.info(f"  Settings path: {settings_path}")

    if not workspace_path.exists():
        log.error(f"Workspace path does not exist: {workspace_path}")
        return {
            "status": "error",
            "output": "",
            "error": f"Workspace path does not exist: {workspace_path}",
            "raw_output": "",
            "metadata": {},
        }

    if not workspace_path.is_dir():
        log.error(f"Workspace path is not a directory: {workspace_path}")
        return {
            "status": "error",
            "output": "",
            "error": f"Workspace path is not a directory: {workspace_path}",
            "raw_output": "",
            "metadata": {},
        }

    if not settings_path.exists():
        log.warning(f"Settings path does not exist, creating: {settings_path}")
        settings_path.mkdir(parents=True, exist_ok=True)

    log.info(f"Path validation complete")

    image_name = f"claude-code-{environment}:latest"

    # Use container runtime from config, or auto-detect
    if tool_config and "container_runtime" in tool_config:
        container_runtime = tool_config["container_runtime"]
    else:
        container_runtime = detect_container_runtime()

    # Determine container user and home directory based on environment
    # Each container type has its own non-root user
    container_user_map = {
        "node": {"user": "node", "home": "/home/node"},
        "python": {"user": "python", "home": "/home/python"},
        "go": {"user": "go", "home": "/home/go"},
    }

    container_info = container_user_map.get(environment, {"user": "node", "home": "/home/node"})
    container_user = container_info["user"]
    container_home = container_info["home"]

    # Convert Path objects to absolute strings for container mounting
    workspace_path_str = str(workspace_path.absolute())
    settings_path_str = str(settings_path.absolute())

    # Build container command
    docker_cmd = [
        container_runtime,
        "run",
        "--rm",  # Remove container after execution
        "--user", container_user,  # Run as non-root user (required for --dangerously-skip-permissions)
        "-v",
        f"{workspace_path_str}:/workspace:Z",  # Mount workspace
        "-v",
        f"{settings_path_str}:{container_home}/.claude:Z",  # Mount settings to user's home directory
    ]

    # Add environment variables
    env_vars = get_container_env_vars(tool_config)
    log.info(f"Setting {len(env_vars)} environment variables in container")
    for key, value in env_vars.items():
        # Don't log full API key values
        if "KEY" in key or "TOKEN" in key:
            log.debug(f"  {key}={value[:20]}..." if len(value) > 20 else f"  {key}=***")
        else:
            log.debug(f"  {key}={value}")
        docker_cmd.extend(["-e", f"{key}={value}"])

    # Add image name
    docker_cmd.append(image_name)

    # Prepend autonomous execution instruction to prompt
    # This ensures Claude Code takes immediate action instead of being conversational
    autonomous_prompt = (
        f"TASK: {prompt}\n\n"
        "Execute this task immediately. Do not ask for permission or provide introductions. "
        "Take action, complete the task, and report the results."
    )

    # Add Claude Code CLI arguments
    # Note: Don't include "claude" here because Dockerfile has ENTRYPOINT ["claude"]
    output_format = "stream-json" if stream else "json"
    docker_cmd.extend([
        "-p", autonomous_prompt,
        "--output-format", output_format,
        "--dangerously-skip-permissions",  # Required for headless autonomous execution in sandbox
    ])

    # Add streaming flags if enabled
    if stream:
        docker_cmd.append("--include-partial-messages")
        docker_cmd.append("--verbose")  # Required for stream-json with -p

    # Add model if specified
    if tool_config and "model" in tool_config:
        docker_cmd.extend(["--model", tool_config["model"]])
        log.info(f"Using model: {tool_config['model']}")

    # Note: Claude Code CLI doesn't support --max-iterations, control is via model config
    # The max_iterations parameter is kept in tool_config for future use or documentation

    # Session resumption: Only used when explicitly requested via resume_session parameter
    # When resuming, the prompt becomes the "answer" or continuation message
    # This allows LLM to answer questions from Claude Code or continue a conversation
    if resume_session and session_id:
        docker_cmd.extend(["-r", session_id])
        log.info(f"Resuming Claude Code session: {session_id}")
    else:
        if session_id and not resume_session:
            log.debug(f"Session ID available ({session_id}) but not resuming (fresh execution)")
        log.info("Starting new Claude Code session")

    log.info(f"Executing Claude Code in {environment} environment")
    log.info(f"Container runtime: {container_runtime}")
    log.info(f"Image: {image_name}")
    log.debug(f"Full command: {' '.join(docker_cmd)}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Handle streaming vs non-streaming modes
        if stream and status_callback:
            from .streaming_utils import process_claude_stream

            # Process stream and collect stderr separately
            stream_result = await process_claude_stream(proc.stdout, status_callback)
            await proc.wait()  # Wait for process to complete
            stderr = await proc.stderr.read()
            stderr_str = stderr.decode() if stderr else ""

            # For streaming, we need to construct stdout_str from stream result
            # The final JSON line will be synthesized from stream_result
            stdout_str = json.dumps({
                "type": "result",
                "subtype": "success",
                "result": stream_result.get("text", ""),
                "session_id": stream_result.get("session_id", ""),
                "tools_used": stream_result.get("tools_used", []),
            })
        else:
            # Non-streaming mode: read all at once
            stdout, stderr = await proc.communicate()
            stdout_str = stdout.decode() if stdout else ""
            stderr_str = stderr.decode() if stderr else ""

        # Log detailed execution info
        log.info(f"Container exit code: {proc.returncode}")
        if stdout_str:
            log.debug(f"Container stdout (first 500 chars): {stdout_str[:500]}")
        if stderr_str:
            log.debug(f"Container stderr (first 500 chars): {stderr_str[:500]}")

        if proc.returncode != 0:
            # Build detailed error message
            error_parts = [f"Container exited with code {proc.returncode}"]
            if stderr_str:
                error_parts.append(f"STDERR: {stderr_str}")
            if stdout_str:
                error_parts.append(f"STDOUT: {stdout_str}")

            error_msg = "\n".join(error_parts)
            log.error(f"Claude Code execution failed: {error_msg}")
            return {
                "status": "error",
                "output": "",
                "error": error_msg,
                "raw_output": stdout_str,
                "metadata": {},
            }

        # Parse JSON output
        output_str = stdout_str
        try:
            result = json.loads(output_str)

            # Claude Code CLI returns "result" field, not "output"
            output = result.get("result", result.get("output", ""))

            return {
                "status": "success",
                "output": output,
                "session_id": result.get("session_id", ""),
                "metadata": {
                    "cost_usd": result.get("total_cost_usd", result.get("cost_usd", 0.0)),
                    "duration_ms": result.get("duration_ms", 0),
                    "num_turns": result.get("num_turns", 0),
                },
                "raw_output": output_str,
            }
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse Claude Code output as JSON: {e}")
            log.error(f"Raw output (first 1000 chars): {output_str[:1000]}")
            return {
                "status": "error",
                "output": output_str,
                "error": f"Failed to parse JSON output: {e}\nRaw output: {output_str[:500]}",
                "raw_output": output_str,
                "metadata": {},
            }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log.error(f"Failed to execute Claude Code container: {e}")
        log.error(f"Traceback: {tb}")
        log.error(f"Command that failed: {' '.join(docker_cmd)}")
        return {
            "status": "error",
            "output": "",
            "error": f"{type(e).__name__}: {e}\nCommand: {' '.join(docker_cmd)}\n{tb}",
            "raw_output": "",
            "metadata": {},
        }


def generate_claude_md(
    workspace_name: str,
    workspace_description: str,
    environment: str,
) -> str:
    """
    Generate CLAUDE.md content for a workspace.

    Args:
        workspace_name: Display name for workspace
        workspace_description: Description of workspace
        environment: Environment name (node, python, go)

    Returns:
        CLAUDE.md content
    """
    env_info = {
        "node": {
            "name": "Node.js",
            "build": "npm install && npm run build",
            "test": "npm test",
        },
        "python": {
            "name": "Python",
            "build": "pip install -r requirements.txt",
            "test": "pytest",
        },
        "go": {
            "name": "Go",
            "build": "go build ./...",
            "test": "go test ./...",
        },
    }

    env_data = env_info.get(environment, {"name": environment, "build": "", "test": ""})

    return f"""# {workspace_name}

{workspace_description}

## 🤖 AUTONOMOUS MODE

**CRITICAL:** You are running in headless autonomous mode. When given a task:
1. **IMMEDIATELY take action** - Do not ask for confirmation
2. **Complete the task fully** - Do not just acknowledge the request
3. **Use all available tools** - Read files, write code, run commands, test, verify
4. **Do not be conversational** - Go straight to executing the task

## Environment
This is a {env_data['name']} development workspace.

## Instructions
- Follow best practices for {env_data['name']} development
- Run tests after making changes
- Keep dependencies up to date
- Commit changes to git after successful modifications

## Build Commands
{env_data['build']}

## Testing
{env_data['test']}

## Project Structure
(Auto-generated tree will appear here after files are created)
"""
