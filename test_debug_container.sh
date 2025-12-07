#!/bin/bash

# Clean up workspace
rm -rf /Users/edfunnekotter/.claude-workspaces/test_user/sessions/debug-prompt-test
rm -rf /Users/edfunnekotter/.claude-settings/test_user/sessions/debug-prompt-test

# Create minimal workspace
mkdir -p /Users/edfunnekotter/.claude-workspaces/test_user/sessions/debug-prompt-test
mkdir -p /Users/edfunnekotter/.claude-settings/test_user/debug-prompt-test

# Create minimal settings.json
cat > /Users/edfunnekotter/.claude-settings/test_user/debug-prompt-test/settings.json <<'EOF'
{
  "allowedTools": ["*"],
  "autoApproveTools": true,
  "env": {
    "ANTHROPIC_API_KEY": "sk-l0C4g8drKHs5uGpFA4RRcg",
    "ANTHROPIC_BASE_URL": "https://lite-llm.mymaas.net"
  }
}
EOF

# Test prompt with autonomous instructions prepended
PROMPT="TASK: Create test.txt file with content 'Success!'

Execute this task immediately. Do not ask for permission or provide introductions. Take action, complete the task, and report the results."

echo "Running with prompt:"
echo "---"
echo "$PROMPT"
echo "---"
echo

podman run --rm \
  -v "/Users/edfunnekotter/.claude-workspaces/test_user/sessions/debug-prompt-test:/workspace:Z" \
  -v "/Users/edfunnekotter/.claude-settings/test_user/debug-prompt-test:/home/node/.claude:Z" \
  claude-code-node:debug \
  -p "$PROMPT" \
  --output-format json \
  --dangerously-skip-permissions \
  2>&1 | tail -100

echo
echo "Checking workspace files:"
ls -la /Users/edfunnekotter/.claude-workspaces/test_user/sessions/debug-prompt-test/
