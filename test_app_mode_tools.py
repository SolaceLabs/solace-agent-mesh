#!/usr/bin/env python3
"""
Test script for Claude Code tools with app_mode configuration.

Tests:
1. Tool filtering based on hidden_tools config
2. Dynamic parameter schema generation
3. app_id extraction and workspace override
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from solace_agent_mesh.agent.tools.claude_code.tool_provider import ClaudeCodeToolProvider
from solace_agent_mesh.agent.tools.claude_code.context_helpers import (
    extract_app_id_from_context,
    should_hide_workspace_params,
    resolve_workspace_params,
)


def test_tool_filtering():
    """Test that tools are filtered based on hidden_tools config."""
    print("\n=== Test 1: Tool Filtering ===")

    # Test without app_mode
    provider1 = ClaudeCodeToolProvider()
    tools1 = provider1.create_tools({
        "workspace_base": "/tmp/test-workspaces",
        "settings_base": "/tmp/test-settings",
    })
    print(f"Without app_mode: {len(tools1)} tools")
    tool_names1 = [tool.tool_name for tool in tools1]
    print(f"  Tools: {tool_names1}")

    # Test with app_mode and hidden_tools
    provider2 = ClaudeCodeToolProvider()
    tools2 = provider2.create_tools({
        "workspace_base": "/tmp/test-workspaces",
        "settings_base": "/tmp/test-settings",
        "app_mode": {
            "enabled": True,
            "hidden_tools": [
                "claude_code_list_workspaces",
                "claude_code_list_sessions",
                "claude_code_import_workspace",
            ]
        }
    })
    print(f"\nWith app_mode (3 hidden): {len(tools2)} tools")
    tool_names2 = [tool.tool_name for tool in tools2]
    print(f"  Tools: {tool_names2}")

    # Verify filtering worked
    assert len(tools2) == len(tools1) - 3, "Expected 3 tools to be hidden"
    assert "claude_code_list_workspaces" not in tool_names2
    assert "claude_code_list_sessions" not in tool_names2
    assert "claude_code_import_workspace" not in tool_names2
    assert "claude_code_execute" in tool_names2
    print("\n✅ Tool filtering works correctly")


def test_parameter_schema():
    """Test that parameter schemas are dynamic based on app_mode."""
    print("\n=== Test 2: Parameter Schema ===")

    # Test without app_mode (workspace params visible)
    provider1 = ClaudeCodeToolProvider()
    tools1 = provider1.create_tools({
        "workspace_base": "/tmp/test-workspaces",
        "settings_base": "/tmp/test-settings",
    })
    execute_tool1 = [t for t in tools1 if t.tool_name == "claude_code_execute"][0]
    schema1 = execute_tool1.parameters_schema
    print(f"Without app_mode:")
    print(f"  Required params: {schema1.required}")
    print(f"  Has workspace_id: {'workspace_id' in schema1.properties}")
    print(f"  Has workspace_type: {'workspace_type' in schema1.properties}")

    # Test with app_mode (workspace params hidden)
    provider2 = ClaudeCodeToolProvider()
    tools2 = provider2.create_tools({
        "workspace_base": "/tmp/test-workspaces",
        "settings_base": "/tmp/test-settings",
        "app_mode": {
            "enabled": True,
            "hide_workspace_params": True,
        }
    })
    execute_tool2 = [t for t in tools2 if t.tool_name == "claude_code_execute"][0]
    schema2 = execute_tool2.parameters_schema
    print(f"\nWith app_mode (hide_workspace_params=True):")
    print(f"  Required params: {schema2.required}")
    print(f"  Has workspace_id: {'workspace_id' in schema2.properties}")
    print(f"  Has workspace_type: {'workspace_type' in schema2.properties}")

    # Verify schema changes
    assert "workspace_id" in schema1.required, "workspace_id should be required without app_mode"
    assert "workspace_id" in schema1.properties, "workspace_id should be in properties without app_mode"
    assert "workspace_id" not in schema2.required, "workspace_id should not be required with app_mode"
    assert "workspace_id" not in schema2.properties, "workspace_id should not be in properties with app_mode"
    print("\n✅ Parameter schema generation works correctly")


def test_context_helpers():
    """Test context helper functions."""
    print("\n=== Test 3: Context Helpers ===")

    # Test should_hide_workspace_params
    config1 = None
    config2 = {"app_mode": {"enabled": False}}
    config3 = {"app_mode": {"enabled": True, "hide_workspace_params": False}}
    config4 = {"app_mode": {"enabled": True, "hide_workspace_params": True}}

    assert not should_hide_workspace_params(config1), "No config should not hide"
    assert not should_hide_workspace_params(config2), "Disabled app_mode should not hide"
    assert not should_hide_workspace_params(config3), "hide_workspace_params=False should not hide"
    assert should_hide_workspace_params(config4), "hide_workspace_params=True should hide"
    print("✅ should_hide_workspace_params() works correctly")

    # Test extract_app_id_from_context with mock context
    class MockToolContext:
        def __init__(self, app_id=None):
            self.state = {"a2a_context": {"app_id": app_id} if app_id else {}}

    config_enabled = {"app_mode": {"enabled": True, "extract_app_id_from_context": True}}
    config_disabled = {"app_mode": {"enabled": False}}

    context_with_id = MockToolContext("test-app-123")
    context_without_id = MockToolContext(None)

    result1 = extract_app_id_from_context(context_with_id, config_enabled)
    result2 = extract_app_id_from_context(context_without_id, config_enabled)
    result3 = extract_app_id_from_context(context_with_id, config_disabled)

    assert result1 == "test-app-123", "Should extract app_id when enabled and present"
    assert result2 is None, "Should return None when app_id not in context"
    assert result3 is None, "Should return None when app_mode disabled"
    print("✅ extract_app_id_from_context() works correctly")

    # Test resolve_workspace_params
    class MockToolContext:
        def __init__(self, app_id=None):
            self.state = {"a2a_context": {"app_id": app_id} if app_id else {}}

    # Normal mode: use args
    args1 = {"workspace_id": "my-workspace", "workspace_type": "session"}
    config_normal = {}
    context1 = MockToolContext(None)
    workspace_id1, workspace_type1 = resolve_workspace_params(args1, context1, config_normal)
    assert workspace_id1 == "my-workspace", "Should use workspace_id from args"
    assert workspace_type1 == "session", "Should use workspace_type from args"

    # App mode: override with app_id
    args2 = {"workspace_id": "ignored"}  # This should be ignored
    config_app = {
        "app_mode": {
            "enabled": True,
            "extract_app_id_from_context": True,
            "fixed_workspace_type": "app"
        }
    }
    context2 = MockToolContext("my-app-456")
    workspace_id2, workspace_type2 = resolve_workspace_params(args2, context2, config_app)
    assert workspace_id2 == "my-app-456", "Should use app_id from context, not args"
    assert workspace_type2 == "app", "Should use fixed_workspace_type from config"
    print("✅ resolve_workspace_params() works correctly")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Claude Code Tools - App Mode Tests")
    print("=" * 60)

    try:
        test_tool_filtering()
        test_parameter_schema()
        test_context_helpers()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
