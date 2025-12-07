#!/usr/bin/env python3
"""Test to see raw streaming events from Claude Code."""

import asyncio
import sys
from pathlib import Path

async def main():
    """Run Claude Code with stream-json and print raw events."""

    # Use same settings as test_streaming.py
    import json
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
        "-p", "Create a simple test.txt file with 'Hello World'",
        "--output-format", "stream-json",
        "--include-partial-messages",
        "--verbose",
        "--dangerously-skip-permissions",
    ])

    print("Running:", " ".join(cmd[:10]), "...")
    print()
    print("=" * 80)
    print("RAW STREAMING EVENTS:")
    print("=" * 80)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Print each line as it comes
    line_num = 0
    while True:
        line_bytes = await proc.stdout.readline()
        if not line_bytes:
            break

        line = line_bytes.decode("utf-8").strip()
        if line:
            line_num += 1
            # Try to parse as JSON and pretty print
            try:
                data = json.loads(line)
                event_type = data.get("type", "unknown")
                print(f"\n[{line_num}] Event: {event_type}")

                # Show relevant details based on event type
                if event_type == "content_block_start":
                    content_block = data.get("content_block", {})
                    cb_type = content_block.get("type")
                    print(f"    content_block.type: {cb_type}")
                    if cb_type == "tool_use":
                        print(f"    tool name: {content_block.get('name')}")
                        print(f"    tool id: {content_block.get('id')}")

                elif event_type == "content_block_delta":
                    delta = data.get("delta", {})
                    delta_type = delta.get("type")
                    print(f"    delta.type: {delta_type}")
                    if delta_type == "input_json_delta":
                        partial = delta.get("partial_json", "")
                        print(f"    partial_json: {partial[:100]}")
                    elif delta_type == "text_delta":
                        text = delta.get("text", "")
                        print(f"    text: {text[:100]}")

                elif event_type == "content_block_stop":
                    print(f"    index: {data.get('index')}")

            except json.JSONDecodeError:
                print(f"\n[{line_num}] Non-JSON: {line[:100]}")

    await proc.wait()
    stderr = await proc.stderr.read()

    print()
    print("=" * 80)
    print(f"Process exited with code: {proc.returncode}")
    print(f"Total events received: {line_num}")

    if stderr:
        print()
        print("STDERR:")
        print(stderr.decode())

    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
