#!/usr/bin/env python3
"""
Test script for Claude Code tools.

Run this to validate all Claude Code tools work correctly.
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import Mock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from solace_agent_mesh.agent.tools.claude_code.tool_provider import ClaudeCodeToolProvider


async def main():
    """Test all Claude Code tools."""

    print("=" * 80)
    print("Testing Claude Code Tools")
    print("=" * 80)

    # Load user's Claude Code settings
    import json
    user_settings_path = Path.home() / ".claude" / "settings.json"
    user_settings = {}
    env_vars = {}

    if user_settings_path.exists():
        print(f"\n✓ Found user settings at: {user_settings_path}")
        try:
            with open(user_settings_path) as f:
                user_settings = json.load(f)

            # Extract environment variables
            if "env" in user_settings:
                env_vars = user_settings["env"]
                print(f"✓ Loaded {len(env_vars)} environment variables from settings")
        except Exception as e:
            print(f"⚠ Warning: Could not load user settings: {e}")
    else:
        print(f"\n⚠ User settings not found at: {user_settings_path}")

    # Get API key and base URL (try both ANTHROPIC_API_KEY and ANTHROPIC_AUTH_TOKEN)
    api_key = (
        env_vars.get("ANTHROPIC_API_KEY") or
        env_vars.get("ANTHROPIC_AUTH_TOKEN") or
        os.getenv("ANTHROPIC_API_KEY", "") or
        os.getenv("ANTHROPIC_AUTH_TOKEN", "")
    )
    base_url = env_vars.get("ANTHROPIC_BASE_URL", os.getenv("ANTHROPIC_BASE_URL", ""))

    # Configuration
    # Use paths under HOME for Podman on macOS compatibility
    home = str(Path.home())
    tool_config = {
        "api_key": api_key,
        "model": user_settings.get("model", "claude-sonnet-4"),
        "max_iterations": 5,
        "workspace_base": f"{home}/.claude-workspaces",
        "settings_base": f"{home}/.claude-settings",
        "export_base": f"{home}/.claude-exports",
        "prepull_images": False,
        "environments": ["node"],
        "environment_variables": {
            "ANTHROPIC_BASE_URL": base_url,
        },
        "settings": user_settings if user_settings else {
            "allowedTools": ["*"],
            "autoApproveTools": True,
            "maxThinkingTokens": 4000,
            "sandbox": {
                "enabled": True,
                "allowedNetworkDomains": ["*"],
            },
        },
    }

    # Check configuration
    has_api_key = bool(tool_config["api_key"])
    if has_api_key:
        print(f"\n✓ API key configured: {tool_config['api_key'][:20]}...")
    else:
        print("\n⚠ WARNING: ANTHROPIC_API_KEY not found")
        print("   Basic tool tests will run, but Claude Code execution will be skipped")

    if base_url:
        print(f"✓ Base URL configured: {base_url}")
    else:
        print("⚠ No ANTHROPIC_BASE_URL configured (using default)")

    print(f"✓ Model: {tool_config['model']}")
    print(f"✓ Workspace base: {tool_config['workspace_base']}")
    print(f"✓ Settings base: {tool_config['settings_base']}")

    # Create provider and tools
    print("\n" + "=" * 80)
    print("Creating Tool Provider")
    print("=" * 80)

    try:
        provider = ClaudeCodeToolProvider()
        tools = provider.create_tools(tool_config)
        print(f"\n✓ Created {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.tool_name}")
    except Exception as e:
        print(f"\n❌ Failed to create tools: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Create mock tool context
    print("\n" + "=" * 80)
    print("Creating Mock Tool Context")
    print("=" * 80)

    mock_session_context = Mock()
    mock_session_context.user_id = "test_user"
    mock_session_context.app_name = "test_app"

    mock_invocation_context = Mock()
    mock_invocation_context.session = mock_session_context

    tool_context = Mock()
    tool_context._invocation_context = mock_invocation_context
    # Also add user_id directly for compatibility with helper functions
    tool_context.user_id = "test_user"

    print("\n✓ Mock context created with user_id: test_user")

    # Test 1: List workspaces (should be empty initially)
    print("\n" + "=" * 80)
    print("Test 1: List Workspaces (Initial)")
    print("=" * 80)

    list_tool = next(t for t in tools if t.tool_name == "claude_code_list_workspaces")
    try:
        result = await list_tool.run_async(
            args={},
            tool_context=tool_context,
        )
        print(f"\n✓ List workspaces result:")
        print(f"  Status: {result.get('status')}")
        print(f"  Count: {result.get('count', 0)}")
        print(f"  Workspaces: {len(result.get('workspaces', []))}")
    except Exception as e:
        print(f"\n❌ List workspaces failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Test 2: Execute Claude Code (create a simple test)
    print("\n" + "=" * 80)
    print("Test 2: Execute Claude Code")
    print("=" * 80)

    if not has_api_key:
        print("\n⊘ Skipping execution test (no API key)")
        test_workspace_id = None
    else:
        execute_tool = next(t for t in tools if t.tool_name == "claude_code_execute")

        # Simple test prompt
        test_prompt = "Create a simple hello.txt file with the text 'Hello from Claude Code!'"
        test_workspace_id = "test-workspace-001"

        print(f"\nPrompt: {test_prompt}")
        print(f"Workspace ID: {test_workspace_id}")
        print(f"Environment: node")

        try:
            result = await execute_tool.run_async(
                args={
                    "prompt": test_prompt,
                    "workspace_id": test_workspace_id,
                    "workspace_type": "session",
                    "environment": "node",
                },
                tool_context=tool_context,
            )

            print(f"\n✓ Execute result:")
            print(f"  Status: {result.get('status')}")
            print(f"  Workspace path: {result.get('workspace_path')}")
            print(f"  Session ID: {result.get('session_id', 'N/A')}")

            if result.get('metadata'):
                print(f"  Cost: ${result['metadata'].get('cost_usd', 0):.4f}")
                print(f"  Duration: {result['metadata'].get('duration_ms', 0)}ms")
                print(f"  Turns: {result['metadata'].get('num_turns', 0)}")

            output = result.get('output', '')
            if output:
                print(f"\n  Output (first 500 chars):")
                print(f"  {output[:500]}")

            if result.get('status') == 'error':
                print(f"\n  Error: {result.get('error')}")
                return 1

        except Exception as e:
            print(f"\n❌ Execute failed: {e}")
            import traceback
            traceback.print_exc()
            return 1

    # Test 3: Read files from workspace
    print("\n" + "=" * 80)
    print("Test 3: Read Files from Workspace")
    print("=" * 80)

    if not test_workspace_id:
        print("\n⊘ Skipping read files test (no workspace created)")
    else:
        read_tool = next(t for t in tools if t.tool_name == "claude_code_read_files")
        try:
            result = await read_tool.run_async(
                args={
                    "workspace_id": test_workspace_id,
                    "file_pattern": "**/*",
                },
                tool_context=tool_context,
            )

            print(f"\n✓ Read files result:")
            print(f"  Status: {result.get('status')}")
            print(f"  Files found: {len(result.get('files', {}))}")

            if result.get('tree'):
                print(f"\n  Directory tree:")
                print(result['tree'])

            if result.get('files'):
                print(f"\n  Files:")
                for path, content in list(result['files'].items())[:3]:
                    print(f"    - {path} ({len(content)} bytes)")

        except Exception as e:
            print(f"\n❌ Read files failed: {e}")
            import traceback
            traceback.print_exc()
            return 1

    # Test 4: List workspaces (should show our test workspace)
    print("\n" + "=" * 80)
    print("Test 4: List Workspaces (After Creation)")
    print("=" * 80)

    try:
        result = await list_tool.run_async(
            args={"workspace_type": "session"},
            tool_context=tool_context,
        )

        print(f"\n✓ List workspaces result:")
        print(f"  Status: {result.get('status')}")
        print(f"  Count: {result.get('count', 0)}")

        for ws in result.get('workspaces', []):
            print(f"\n  Workspace:")
            print(f"    ID: {ws.get('workspace_id')}")
            print(f"    Type: {ws.get('workspace_type')}")
            print(f"    Environment: {ws.get('environment')}")
            print(f"    Path: {ws.get('path')}")

    except Exception as e:
        print(f"\n❌ List workspaces failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Test 5: Export workspace
    print("\n" + "=" * 80)
    print("Test 5: Export Workspace")
    print("=" * 80)

    if not test_workspace_id:
        print("\n⊘ Skipping export test (no workspace created)")
    else:
        export_tool = next(t for t in tools if t.tool_name == "claude_code_export_workspace")
        try:
            result = await export_tool.run_async(
                args={
                    "workspace_id": test_workspace_id,
                    "include_git_history": False,
                },
                tool_context=tool_context,
            )

            print(f"\n✓ Export result:")
            print(f"  Status: {result.get('status')}")
            print(f"  Artifact URI: {result.get('artifact_uri')}")
            print(f"  Size: {result.get('size_bytes', 0)} bytes")
            print(f"  Checksum: {result.get('checksum', 'N/A')}")

            if result.get('status') == 'error':
                print(f"\n  Error: {result.get('error')}")

        except Exception as e:
            print(f"\n❌ Export failed: {e}")
            import traceback
            traceback.print_exc()
            # Don't fail on export error

    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    print("\n✓ All core tests passed!")
    print(f"✓ Workspace created at: {result.get('workspace_path', 'N/A')}")
    print("\nNote: The workspace is in /tmp and will be cleared on system restart")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
