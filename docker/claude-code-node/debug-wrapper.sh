#!/bin/bash
# Debug wrapper for Claude Code CLI

echo "==================== CLAUDE CODE DEBUG WRAPPER ====================" >&2
echo "Time: $(date)" >&2
echo "" >&2

echo "--- Working Directory ---" >&2
pwd >&2
echo "" >&2

echo "--- Command Line Arguments ---" >&2
echo "Number of args: $#" >&2
for i in "$@"; do
    echo "  Arg: '$i'" >&2
done
echo "" >&2

echo "--- Environment Variables ---" >&2
env | grep -E "ANTHROPIC|CLAUDE" | sort >&2
echo "" >&2

echo "--- Settings Directory ---" >&2
ls -la /root/.claude/ >&2
echo "" >&2

echo "--- Settings.json Content ---" >&2
if [ -f /root/.claude/settings.json ]; then
    cat /root/.claude/settings.json >&2
else
    echo "settings.json NOT FOUND" >&2
fi
echo "" >&2

echo "--- Workspace Directory ---" >&2
ls -la /workspace/ >&2
echo "" >&2

echo "--- CLAUDE.md Content ---" >&2
if [ -f /workspace/CLAUDE.md ]; then
    head -20 /workspace/CLAUDE.md >&2
else
    echo "CLAUDE.md NOT FOUND" >&2
fi
echo "" >&2

echo "--- Executing: claude $@ ---" >&2
echo "===================================================================" >&2
echo "" >&2

# Execute the actual Claude Code command
exec claude "$@"
