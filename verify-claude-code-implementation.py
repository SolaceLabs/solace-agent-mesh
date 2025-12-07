#!/usr/bin/env python3
"""
Verification script for Claude Code implementation.

This script verifies that all modules can be imported and basic
structure is correct.
"""

import sys
from pathlib import Path

print("Verifying Claude Code implementation...")
print("=" * 60)

# Test imports
tests = []

# 1. WorkspaceService imports
try:
    from src.solace_agent_mesh.common.workspace import (
        BaseWorkspaceService,
        LocalFilesystemWorkspaceService,
    )
    tests.append(("WorkspaceService imports", True, None))
    print("✅ WorkspaceService imports successful")
except Exception as e:
    tests.append(("WorkspaceService imports", False, str(e)))
    print(f"❌ WorkspaceService imports failed: {e}")

# 2. Claude Code tool provider import
try:
    from src.solace_agent_mesh.agent.tools.claude_code import (
        ClaudeCodeToolProvider,
    )
    tests.append(("ClaudeCodeToolProvider import", True, None))
    print("✅ ClaudeCodeToolProvider import successful")
except Exception as e:
    tests.append(("ClaudeCodeToolProvider import", False, str(e)))
    print(f"❌ ClaudeCodeToolProvider import failed: {e}")

# 3. Individual tool imports
try:
    from src.solace_agent_mesh.agent.tools.claude_code import (
        ClaudeCodeExecuteTool,
        ClaudeCodeListWorkspacesTool,
        ClaudeCodeReadFilesTool,
        ClaudeCodeCreateVersionTool,
        ClaudeCodeExportWorkspaceTool,
        ClaudeCodeImportWorkspaceTool,
    )
    tests.append(("Individual tool imports", True, None))
    print("✅ All tool imports successful")
except Exception as e:
    tests.append(("Individual tool imports", False, str(e)))
    print(f"❌ Tool imports failed: {e}")

# 4. Check Docker images exist
print("\nChecking Docker images...")
import subprocess
try:
    for env in ["node", "python", "go"]:
        image_name = f"claude-code-{env}:latest"
        result = subprocess.run(
            ["docker", "images", "-q", image_name],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            print(f"✅ Docker image exists: {image_name}")
        else:
            print(f"⚠️  Docker image not built: {image_name}")
            print(f"   Run: cd docker && ./build-all.sh")
except FileNotFoundError:
    print("⚠️  Docker not found - skipping image check")

# 5. Check directory structure
print("\nChecking file structure...")
files_to_check = [
    "src/solace_agent_mesh/common/workspace/base_workspace_service.py",
    "src/solace_agent_mesh/common/workspace/local_filesystem_workspace.py",
    "src/solace_agent_mesh/agent/tools/claude_code/tool_provider.py",
    "src/solace_agent_mesh/agent/tools/claude_code/execute_tool.py",
    "src/solace_agent_mesh/agent/tools/claude_code/utils.py",
    "docker/claude-code-node/Dockerfile",
    "docker/claude-code-python/Dockerfile",
    "docker/claude-code-go/Dockerfile",
    "config/examples/coding-agent.yaml",
    "docs/claude-code-tool-design.md",
]

for file in files_to_check:
    path = Path(file)
    if path.exists():
        print(f"✅ {file}")
    else:
        print(f"❌ Missing: {file}")

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

passed = sum(1 for t in tests if t[1])
total = len(tests)

print(f"\nTests passed: {passed}/{total}")

if passed == total:
    print("\n✅ All verification tests passed!")
    print("\nNext steps:")
    print("1. Build Docker images: cd docker && ./build-all.sh")
    print("2. Create workspace directories:")
    print("   sudo mkdir -p /claude-workspaces /claude-settings")
    print("   sudo chown -R $USER:$USER /claude-workspaces /claude-settings")
    print("3. Configure your agent using config/examples/coding-agent.yaml")
    sys.exit(0)
else:
    print("\n❌ Some verification tests failed")
    for name, passed, error in tests:
        if not passed:
            print(f"  - {name}: {error}")
    sys.exit(1)
