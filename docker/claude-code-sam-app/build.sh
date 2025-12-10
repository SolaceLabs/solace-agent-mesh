#!/bin/bash
# Build the claude-code-sam-app Docker image
# This script must be run from the repository root

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Building SAM SDK..."
cd "$REPO_ROOT/packages/sam-sdk"
npm install
npm run build

echo "Building claude-code-sam-app Docker image..."
cd "$REPO_ROOT"

# Detect container runtime
if command -v docker &> /dev/null; then
    RUNTIME="docker"
elif command -v podman &> /dev/null; then
    RUNTIME="podman"
else
    echo "Error: Neither docker nor podman found"
    exit 1
fi

echo "Using container runtime: $RUNTIME"

# Build from repo root with correct context
$RUNTIME build \
    -f docker/claude-code-sam-app/Dockerfile \
    -t claude-code-sam-app:latest \
    .

echo "✓ Build complete! Image: claude-code-sam-app:latest"
