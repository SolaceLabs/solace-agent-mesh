#!/usr/bin/env python3
"""Quick test to verify instruction fix works."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent / "src"))

from solace_agent_mesh.agent.tools.claude_code.tool_provider import ClaudeCodeToolProvider

async def main():
    """Test instruction fix."""
    import os
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

    # Create tools
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

    print("=" * 80)
    print("Testing Claude Code with Prompt-Based Instructions")
    print("=" * 80)
    print("\nPrompt: Create test.txt file with content 'Success!'")
    print("Workspace: final-test")
    print()

    result = await execute_tool.run_async(
        args={
            "prompt": "Create test.txt file with content 'Success!'",
            "workspace_id": "final-test",
            "workspace_type": "session",
            "environment": "node",
        },
        tool_context=tool_context,
    )

    print(f"Status: {result.get('status')}")
    print(f"Workspace: {result.get('workspace_path')}")
    print(f"Session ID: {result.get('session_id')}")
    print()

    print("Claude Code Output:")
    print("-" * 80)
    print(result.get('output', '(empty)'))
    print("-" * 80)

    if result.get('raw_output'):
        print("\nRaw JSON Output (first 1000 chars):")
        print(result['raw_output'][:1000])

    if result.get('status') == 'error':
        print(f"\nError: {result.get('error')}")
        return 1

    # Check if file was created
    workspace_path = Path(result.get('workspace_path'))
    test_file = workspace_path / "test.txt"

    print(f"\nChecking if test.txt exists...")
    if test_file.exists():
        print(f"✓ File created successfully!")
        print(f"  Content: {test_file.read_text()}")
    else:
        print(f"✗ File was NOT created")
        print(f"  Files in workspace:")
        for f in workspace_path.iterdir():
            if not f.name.startswith('.'):
                print(f"    - {f.name}")

    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
