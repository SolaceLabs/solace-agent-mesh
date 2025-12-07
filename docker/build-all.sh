#!/bin/bash
# Build all Claude Code environment images

set -e

# Auto-detect container runtime
if command -v docker &> /dev/null; then
    CONTAINER_RUNTIME="docker"
    echo "Detected container runtime: docker"
elif command -v podman &> /dev/null; then
    CONTAINER_RUNTIME="podman"
    echo "Detected container runtime: podman"
else
    echo "Error: Neither docker nor podman found. Please install Docker or Podman."
    exit 1
fi

echo "Building Claude Code container images..."

# Build Node environment
echo "Building claude-code-node:latest..."
$CONTAINER_RUNTIME build -t claude-code-node:latest ./claude-code-node/

# Build Python environment
echo "Building claude-code-python:latest..."
$CONTAINER_RUNTIME build -t claude-code-python:latest ./claude-code-python/

# Build Go environment
echo "Building claude-code-go:latest..."
$CONTAINER_RUNTIME build -t claude-code-go:latest ./claude-code-go/

echo "All images built successfully!"
echo ""
echo "Available images:"
$CONTAINER_RUNTIME images | grep claude-code
