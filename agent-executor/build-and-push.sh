#!/bin/bash
# Build and push SAM Agent Executor image to GCR.
#
# Usage:
#   ./build-and-push.sh              # Build + push with tag "latest"
#   ./build-and-push.sh v0.1.0       # Build + push with custom tag
#   BUILD_ONLY=1 ./build-and-push.sh # Build only, don't push

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

TAG="${1:-latest}"
GCR_REGISTRY="gcr.io/stellar-arcadia-205014"
IMAGE_NAME="sam-agent-executor"
FULL_IMAGE="${GCR_REGISTRY}/${IMAGE_NAME}:${TAG}"
LOCAL_IMAGE="${IMAGE_NAME}:${TAG}"

echo "=== SAM Agent Executor Build ==="
echo "Registry: ${GCR_REGISTRY}"
echo "Image:    ${FULL_IMAGE}"
echo ""

# Build
echo "Building image..."
docker build -t "$LOCAL_IMAGE" -t "$FULL_IMAGE" -f "$SCRIPT_DIR/Dockerfile" "$REPO_ROOT"
echo "Build complete: ${FULL_IMAGE}"

if [ "${BUILD_ONLY:-}" = "1" ]; then
    echo "BUILD_ONLY=1, skipping push"
    exit 0
fi

# Authenticate with GCR
echo ""
echo "Authenticating with GCR..."
gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin gcr.io/stellar-arcadia-205014

# Push
echo ""
echo "Pushing ${FULL_IMAGE}..."
docker push "$FULL_IMAGE"

echo ""
echo "=== Done ==="
echo "Image pushed: ${FULL_IMAGE}"
echo ""
echo "To use in Helm:"
echo "  --set samDeployment.agentExecutor.enabled=true"
echo "  --set samDeployment.agentExecutor.image.repository=${GCR_REGISTRY}/${IMAGE_NAME}"
echo "  --set samDeployment.agentExecutor.image.tag=${TAG}"
