#!/usr/bin/env python3
"""Test resume/continue conversation functionality."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent / "src"))

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
    list_sessions_tool = next(t for t in tools if t.tool_name == "claude_code_list_sessions")

    # Mock context
    mock_session_context = Mock()
    mock_session_context.user_id = "test_user"
    mock_session_context.app_name = "test_app"

    mock_invocation_context = Mock()
    mock_invocation_context.session = mock_session_context

    tool_context = Mock()
    tool_context._invocation_context = mock_invocation_context
    tool_context.user_id = "test_user"

    workspace_id = "resume-test"

    print("=" * 80)
    print("TEST 1: Initial execution (create session)")
    print("=" * 80)

    result1 = await execute_tool.run_async(
        args={
            "prompt": "Create hello.txt with the text: Hello World!",
            "workspace_id": workspace_id,
            "workspace_type": "session",
            "environment": "node",
        },
        tool_context=tool_context,
    )

    print(f"Status: {result1.get('status')}")
    print(f"Session ID: {result1.get('session_id')}")
    print(f"Output: {result1.get('output')[:200]}...")
    session_id = result1.get("session_id")
    print()

    print("=" * 80)
    print("TEST 2: List sessions")
    print("=" * 80)

    sessions_result = await list_sessions_tool.run_async(
        args={},
        tool_context=tool_context,
    )

    print(f"Status: {sessions_result.get('status')}")
    print(f"Count: {sessions_result.get('count')}")
    print(f"Message: {sessions_result.get('message')}")
    for session in sessions_result.get("sessions", []):
        print(f"  - Workspace: {session['workspace_id']}, Session: {session['session_id']}")
    print()

    print("=" * 80)
    print("TEST 3: Resume session with explicit session_id")
    print("=" * 80)

    result2 = await execute_tool.run_async(
        args={
            "prompt": "Now create goodbye.txt with the text: Goodbye World!",
            "workspace_id": workspace_id,
            "workspace_type": "session",
            "environment": "node",
            "resume_session_id": session_id,
        },
        tool_context=tool_context,
    )

    print(f"Status: {result2.get('status')}")
    print(f"Session ID: {result2.get('session_id')}")
    print(f"Output: {result2.get('output')}")
    print()

    # Check workspace files
    workspace_path = Path(result2.get("workspace_path"))
    print("=" * 80)
    print("Files in workspace:")
    print("=" * 80)
    for f in sorted(workspace_path.iterdir()):
        if not f.name.startswith(".") and f.is_file():
            content = f.read_text().strip()
            print(f"  {f.name}: {content}")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
