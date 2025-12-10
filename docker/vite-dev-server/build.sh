#!/bin/bash
set -e

IMAGE_NAME="vite-dev-server"
TAG="latest"

echo "Building $IMAGE_NAME:$TAG..."

# Build the image
docker build -t "$IMAGE_NAME:$TAG" .

echo "Build complete!"
echo ""
echo "Image: $IMAGE_NAME:$TAG"
echo "Size: $(docker images "$IMAGE_NAME:$TAG" --format "{{.Size}}")"
echo ""
echo "Usage example:"
echo "  docker run -d --name my-app-dev \\"
echo "    --network sam-internal \\"
echo "    -v /path/to/workspace:/workspace \\"
echo "    -p 5173:5173 \\"
echo "    $IMAGE_NAME:$TAG"
