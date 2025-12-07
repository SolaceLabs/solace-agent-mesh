#!/usr/bin/env python3
"""Test streaming functionality."""

import asyncio
import sys
import logging
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent / "src"))

# Enable logging to see status updates
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from solace_agent_mesh.agent.tools.claude_code.tool_provider import ClaudeCodeToolProvider


async def main():
    import json

    # Load settings
    user_settings_path = Path.home() / ".claude" / "settings.json"
    user_settings = {}
    env_vars = {}

    if user_settings_path.exists():
        with open(user_settings_path) as f:
            user_settings = json.load(f)
        if "env" in user_settings:
            env_vars = user_settings["env"]

    api_key = env_vars.get("ANTHROPIC_AUTH_TOKEN", "")
    base_url = env_vars.get("ANTHROPIC_BASE_URL", "")

    home = str(Path.home())
    tool_config = {
        "api_key": api_key,
        "model": user_settings.get("model", "claude-sonnet-4"),
        "workspace_base": f"{home}/.claude-workspaces",
        "settings_base": f"{home}/.claude-settings",
        "environment_variables": {
            "ANTHROPIC_BASE_URL": base_url,
        },
        "settings": user_settings if user_settings else {},
    }

    provider = ClaudeCodeToolProvider()
    tools = provider.create_tools(tool_config)
    execute_tool = next(t for t in tools if t.tool_name == "claude_code_execute")

    # Mock context
    mock_session_context = Mock()
    mock_session_context.user_id = "test_user"
    mock_session_context.app_name = "test_app"

    mock_invocation_context = Mock()
    mock_invocation_context.session = mock_session_context

    tool_context = Mock()
    tool_context._invocation_context = mock_invocation_context
    tool_context.user_id = "test_user"

    workspace_id = "streaming-test"

    print("=" * 80)
    print("TEST: Streaming Mode")
    print("=" * 80)
    print("Prompt: Create a simple Node.js hello world app with package.json")
    print("Watch for [Status Update] messages in the logs...")
    print()

    result = await execute_tool.run_async(
        args={
            "prompt": "Create a simple Node.js hello world app with package.json and app.js",
            "workspace_id": workspace_id,
            "workspace_type": "session",
            "environment": "node",
            # Streaming is now enabled by default via tool_config
        },
        tool_context=tool_context,
    )

    print()
    print("=" * 80)
    print("Execution Complete")
    print("=" * 80)
    print(f"Status: {result.get('status')}")
    print(f"Session ID: {result.get('session_id')}")
    print(f"Workspace: {result.get('workspace_path')}")
    print()
    print(f"Output: {result.get('output')[:300]}...")
    print()

    # Check workspace files
    workspace_path = Path(result.get("workspace_path"))
    print("=" * 80)
    print("Files created:")
    print("=" * 80)
    for f in sorted(workspace_path.iterdir()):
        if not f.name.startswith(".") and f.is_file():
            size = f.stat().st_size
            print(f"  {f.name} ({size} bytes)")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
