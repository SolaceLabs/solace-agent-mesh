#!/bin/bash
# Container Runtime Detection Script
# Detects whether to use podman or docker and provides a unified interface.
#
# Usage:
#   source container-runtime.sh
#   $CONTAINER_CMD build -t my-image .
#   $CONTAINER_CMD run my-image
#
# Or use the helper functions:
#   container_build -t my-image .
#   container_run my-image

set -e

# Detect container runtime
detect_container_runtime() {
    if command -v podman &> /dev/null; then
        echo "podman"
    elif command -v docker &> /dev/null; then
        echo "docker"
    else
        echo ""
    fi
}

# Export the detected runtime
CONTAINER_CMD=$(detect_container_runtime)

if [ -z "$CONTAINER_CMD" ]; then
    echo "Error: Neither podman nor docker found in PATH" >&2
    echo "Please install podman or docker to use sandbox workers" >&2
    exit 1
fi

export CONTAINER_CMD

# Helper function for building images
container_build() {
    $CONTAINER_CMD build "$@"
}

# Helper function for running containers
container_run() {
    $CONTAINER_CMD run "$@"
}

# Helper function for executing commands in running containers
container_exec() {
    $CONTAINER_CMD exec "$@"
}

# Helper function for viewing logs
container_logs() {
    $CONTAINER_CMD logs "$@"
}

# Helper function for stopping containers
container_stop() {
    $CONTAINER_CMD stop "$@"
}

# Helper function for removing containers
container_rm() {
    $CONTAINER_CMD rm "$@"
}

# Export functions for use in scripts that source this file
export -f container_build
export -f container_run
export -f container_exec
export -f container_logs
export -f container_stop
export -f container_rm

# If run directly (not sourced), print info
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "Detected container runtime: $CONTAINER_CMD"
    echo "Version: $($CONTAINER_CMD --version)"
    echo ""
    echo "To use in your scripts:"
    echo "  source $(basename "$0")"
    echo "  \$CONTAINER_CMD build -t my-image ."
    echo "  \$CONTAINER_CMD run my-image"
fi
