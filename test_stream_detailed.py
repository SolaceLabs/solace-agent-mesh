#!/usr/bin/env python3
"""Examine the detailed structure of Claude Code streaming events."""

import asyncio
import sys
from pathlib import Path
import json

async def main():
    """Run Claude Code with stream-json and show full event structure."""

    user_settings_path = Path.home() / ".claude-settings" / "test_user" / "streaming-test" / "settings.json"

    if not user_settings_path.exists():
        print(f"Settings not found at {user_settings_path}")
        return 1

    with open(user_settings_path) as f:
        user_settings = json.load(f)

    workspace_path = Path.home() / ".claude-workspaces" / "test_user" / "sessions" / "streaming-test"
    settings_path = Path.home() / ".claude-settings" / "test_user" / "streaming-test"

    # Build podman command
    cmd = [
        "podman", "run", "--rm",
        "-v", f"{workspace_path}:/workspace:Z",
        "-v", f"{settings_path}:/home/node/.claude:Z",
    ]

    # Add env vars
    if "env" in user_settings:
        for key, value in user_settings["env"].items():
            cmd.extend(["-e", f"{key}={value}"])

    # Add image and Claude Code args
    cmd.extend([
        "claude-code-node:latest",
        "-p", "Write a file called hello.txt with 'Hello Streaming!'",
        "--output-format", "stream-json",
        "--include-partial-messages",
        "--verbose",
        "--dangerously-skip-permissions",
    ])

    print("Looking for tool use events...")
    print()

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Look for interesting events
    while True:
        line_bytes = await proc.stdout.readline()
        if not line_bytes:
            break

        line = line_bytes.decode("utf-8").strip()
        if not line:
            continue

        try:
            data = json.loads(line)
            event_type = data.get("type")

            # Show stream_event details
            if event_type == "stream_event":
                stream_data = data.get("data", {})
                stream_type = stream_data.get("type")

                # Look for tool use
                if stream_type in ["content_block_start", "content_block_delta", "content_block_stop"]:
                    print(f"\n=== {stream_type} ===")
                    print(json.dumps(stream_data, indent=2))

            # Show assistant messages
            elif event_type == "assistant":
                print(f"\n=== ASSISTANT MESSAGE ===")
                content = data.get("message", {}).get("content", [])
                for item in content:
                    if item.get("type") == "tool_use":
                        print(f"Tool: {item.get('name')}")
                        print(f"ID: {item.get('id')}")
                        print(f"Input: {json.dumps(item.get('input', {}), indent=2)}")

        except json.JSONDecodeError:
            pass

    await proc.wait()

    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
