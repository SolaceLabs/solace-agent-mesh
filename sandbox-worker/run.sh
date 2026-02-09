#!/bin/bash
# Run the SAM Sandbox Worker container.
# Automatically detects podman or docker.
#
# Usage:
#   ./run.sh                      # Run with environment variables
#   SAM_NAMESPACE=myorg/dev SOLACE_HOST=broker:55554 ./run.sh
#
# Required environment variables:
#   SAM_NAMESPACE   - SAM namespace (e.g., myorg/dev)
#   SOLACE_HOST     - Solace broker host:port
#
# Optional environment variables:
#   SOLACE_VPN        - Solace VPN name (default: default)
#   SOLACE_USERNAME   - Solace username (default: admin)
#   SOLACE_PASSWORD   - Solace password (default: admin)
#   SAM_WORKER_ID     - Worker ID (default: sandbox-worker-001)
#   CONTAINER_NAME    - Container name (default: sandbox-worker)
#   IMAGE_NAME        - Image name (default: sam-sandbox-worker)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/container-runtime.sh"

# Check required variables
if [ -z "$SAM_NAMESPACE" ]; then
    echo "Error: SAM_NAMESPACE environment variable is required"
    echo "Example: SAM_NAMESPACE=myorg/dev ./run.sh"
    exit 1
fi

if [ -z "$SOLACE_HOST" ]; then
    echo "Error: SOLACE_HOST environment variable is required"
    echo "Example: SOLACE_HOST=broker:55554 ./run.sh"
    exit 1
fi

# Defaults
SOLACE_VPN="${SOLACE_VPN:-default}"
SOLACE_USERNAME="${SOLACE_USERNAME:-admin}"
SOLACE_PASSWORD="${SOLACE_PASSWORD:-admin}"
SAM_WORKER_ID="${SAM_WORKER_ID:-sandbox-worker-001}"
CONTAINER_NAME="${CONTAINER_NAME:-sandbox-worker}"
IMAGE_NAME="${IMAGE_NAME:-sam-sandbox-worker}"

echo "Starting SAM Sandbox Worker..."
echo "Container runtime: $CONTAINER_CMD"
echo "Namespace: $SAM_NAMESPACE"
echo "Broker: $SOLACE_HOST"
echo "Worker ID: $SAM_WORKER_ID"
echo ""

# Stop and remove existing container if running
if $CONTAINER_CMD ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Stopping existing container..."
    $CONTAINER_CMD stop "$CONTAINER_NAME" 2>/dev/null || true
    $CONTAINER_CMD rm "$CONTAINER_NAME" 2>/dev/null || true
fi

# Build environment arguments
ENV_ARGS=(
    -e "SAM_NAMESPACE=$SAM_NAMESPACE"
    -e "SOLACE_HOST=$SOLACE_HOST"
    -e "SOLACE_VPN=$SOLACE_VPN"
    -e "SOLACE_USERNAME=$SOLACE_USERNAME"
    -e "SOLACE_PASSWORD=$SOLACE_PASSWORD"
    -e "SAM_WORKER_ID=$SAM_WORKER_ID"
)

# Add optional artifact service config
if [ -n "$ARTIFACT_SERVICE_TYPE" ]; then
    ENV_ARGS+=(-e "ARTIFACT_SERVICE_TYPE=$ARTIFACT_SERVICE_TYPE")
fi
if [ -n "$ARTIFACT_BASE_PATH" ]; then
    ENV_ARGS+=(-e "ARTIFACT_BASE_PATH=$ARTIFACT_BASE_PATH")
fi
if [ -n "$ARTIFACT_S3_BUCKET" ]; then
    ENV_ARGS+=(-e "ARTIFACT_S3_BUCKET=$ARTIFACT_S3_BUCKET")
fi
if [ -n "$ARTIFACT_S3_REGION" ]; then
    ENV_ARGS+=(-e "ARTIFACT_S3_REGION=$ARTIFACT_S3_REGION")
fi

# Add volume mounts if specified
VOLUME_ARGS=()
if [ -n "$ARTIFACT_MOUNT" ]; then
    VOLUME_ARGS+=(-v "$ARTIFACT_MOUNT")
fi

# Run the container
# CAP_SYS_ADMIN is required for bubblewrap to create user namespaces.
# The bwrap command uses --ro-bind / / (no --proc or --dev mounts),
# so --privileged is NOT needed.
$CONTAINER_CMD run -d --cap-add=SYS_ADMIN \
    --name "$CONTAINER_NAME" \
    "${ENV_ARGS[@]}" \
    "${VOLUME_ARGS[@]}" \
    "$IMAGE_NAME"

echo ""
echo "Container started!"
echo "View logs: $CONTAINER_CMD logs -f $CONTAINER_NAME"
echo "Stop: $CONTAINER_CMD stop $CONTAINER_NAME"
echo "Shell: $CONTAINER_CMD exec -it $CONTAINER_NAME /bin/bash"
