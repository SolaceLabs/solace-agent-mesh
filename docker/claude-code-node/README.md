# Claude Code Node.js Environment

Docker image for running Claude Code in a Node.js development environment.

## Building the Image

```bash
# Using auto-detection script (recommended)
cd .. && ./build-all.sh

# Or manually with Docker
docker build -t claude-code-node:latest .

# Or manually with Podman
podman build -t claude-code-node:latest .
```

## What's Included

- Node.js 20 (slim)
- Claude Code CLI
- git
- ripgrep (for fast code searching)

## Usage

This image is used automatically by the Claude Code SAM tool when `environment: "node"` is specified.

Manual usage example:

```bash
# With Docker
docker run --rm \
  -v /path/to/workspace:/workspace:Z \
  -v /path/to/settings:/root/.claude:Z \
  -e ANTHROPIC_API_KEY=your_key \
  claude-code-node:latest \
  claude -p "Create a REST API with Express"

# With Podman
podman run --rm \
  -v /path/to/workspace:/workspace:Z \
  -v /path/to/settings:/root/.claude:Z \
  -e ANTHROPIC_API_KEY=your_key \
  claude-code-node:latest \
  claude -p "Create a REST API with Express"
```
