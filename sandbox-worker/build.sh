#!/bin/bash
# Build the SAM Sandbox Worker container image.
# Automatically detects podman or docker.
#
# Usage:
#   ./build.sh                    # Build with default tag
#   ./build.sh my-registry/sam-sandbox-worker:v1  # Build with custom tag

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/container-runtime.sh"

# Default image name
IMAGE_NAME="${1:-sam-sandbox-worker}"

echo "Building SAM Sandbox Worker image..."
echo "Container runtime: $CONTAINER_CMD"
echo "Image name: $IMAGE_NAME"
echo ""

# Build context is the parent directory (solace-agent-mesh/) to include SAM source
# Dockerfile path is relative to the build context
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
$CONTAINER_CMD build -t "$IMAGE_NAME" -f "$SCRIPT_DIR/Dockerfile" "$REPO_ROOT"

echo ""
echo "Build complete!"
echo "Run with: $CONTAINER_CMD run -d --privileged --name sandbox-worker \\"
echo "  -e SAM_NAMESPACE=myorg/dev \\"
echo "  -e SOLACE_HOST=host.containers.internal:55554 \\"
echo "  -e SOLACE_VPN=default \\"
echo "  -e SOLACE_USERNAME=admin \\"
echo "  -e SOLACE_PASSWORD=admin \\"
echo "  $IMAGE_NAME"
