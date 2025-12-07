#!/usr/bin/env python3
"""Test to show what commands are being constructed."""

from pathlib import Path

def build_command(prompt, session_id=None):
    """Simulate command building logic from utils.py."""

    workspace_path = "/workspace"
    settings_path = "/home/node/.claude"
    image_name = "claude-code-node:latest"
    model = "claude-sonnet-4"

    docker_cmd = [
        "podman", "run", "--rm",
        "-v", f"{workspace_path}:/workspace:Z",
        "-v", f"{settings_path}:/home/node/.claude:Z",
        "-e", "ANTHROPIC_API_KEY=test-key",
        "-e", "ANTHROPIC_BASE_URL=https://lite-llm.mymaas.net",
        image_name,
    ]

    # Prepend autonomous execution instruction
    autonomous_prompt = (
        f"TASK: {prompt}\n\n"
        "Execute this task immediately. Do not ask for permission or provide introductions. "
        "Take action, complete the task, and report the results."
    )

    # Add Claude Code CLI arguments
    docker_cmd.extend([
        "claude",
        "-p", autonomous_prompt,
        "--output-format", "json",
        "--dangerously-skip-permissions",
    ])

    # Add model
    docker_cmd.extend(["--model", model])

    # Add session resumption if provided
    if session_id:
        docker_cmd.extend(["-r", session_id])

    return docker_cmd

# Test 1: First call (no session)
print("=" * 80)
print("TURN 1: New session")
print("=" * 80)
cmd1 = build_command("Create file1.txt")
print("Command structure:")
for i, arg in enumerate(cmd1):
    if i < 10:  # Show first 10 args (container setup)
        print(f"  [{i}] {arg}")
    elif "claude" in arg or arg.startswith("-") or "TASK:" in arg or "file" in arg:
        # Show claude-related args
        if "TASK:" in arg:
            print(f"  [{i}] {arg[:80]}...")
        else:
            print(f"  [{i}] {arg}")

print()

# Test 2: Second call (with session)
print("=" * 80)
print("TURN 2: Resuming session")
print("=" * 80)
cmd2 = build_command("Create file2.txt", session_id="abc-123")
print("Command structure:")
for i, arg in enumerate(cmd2):
    if i < 10:
        print(f"  [{i}] {arg}")
    elif "claude" in arg or arg.startswith("-") or "TASK:" in arg or "file" in arg or "abc" in arg:
        if "TASK:" in arg:
            print(f"  [{i}] {arg[:80]}...")
        else:
            print(f"  [{i}] {arg}")

print()
print("=" * 80)
print("ISSUE IDENTIFIED:")
print("=" * 80)
print("When using '-r session_id' to resume, Claude Code likely ignores the")
print("positional prompt argument because it's resuming an existing conversation.")
print()
print("The prompt 'TASK: Create file2.txt...' is there, but Claude Code sees:")
print("  -r abc-123 (resume session abc-123)")
print("And ignores the prompt positional arg!")
