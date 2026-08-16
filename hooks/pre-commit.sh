#!/bin/sh

set -e

ROOT_DIR=$(git rev-parse --show-toplevel)

# Check if any frontend files are staged
if git diff --cached --name-only --diff-filter=ACM | grep -q '^client/webui/frontend/'; then
  echo "Frontend changes detected, running frontend pre-commit hook..."

  cd "$ROOT_DIR/client/webui/frontend" || exit 1

  npm run precommit

  echo "Frontend pre-commit hook completed successfully"
fi

exit 0
