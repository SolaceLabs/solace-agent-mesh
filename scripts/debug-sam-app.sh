#!/bin/bash
#
# Debug script for SAM apps - extracts workspace and launches interactive container
#
# Usage: ./scripts/debug-sam-app.sh <app-prefix>
# Example: ./scripts/debug-sam-app.sh workflow
#

set -e

# Configuration
ARTIFACT_STORAGE="/tmp/samv2/sam_dev_user"
WORKSPACE_BASE="$HOME/.claude-workspaces/sam_dev_user/apps"
SETTINGS_BASE="$HOME/.claude/sam-settings/sam_dev_user"
CONTAINER_IMAGE="localhost/claude-code-sam-app:latest"
CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-podman}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check arguments
if [ -z "$1" ]; then
    echo "Usage: $0 <app-prefix>"
    echo ""
    echo "Searches for apps matching the prefix in:"
    echo "  - Artifact storage: $ARTIFACT_STORAGE"
    echo "  - Workspaces: $WORKSPACE_BASE"
    echo ""
    echo "Examples:"
    echo "  $0 workflow     # Find apps starting with 'workflow'"
    echo "  $0 todo         # Find apps starting with 'todo'"
    exit 1
fi

APP_PREFIX="$1"

# Find matching apps in artifact storage
log_info "Searching for apps matching '$APP_PREFIX'..."

ARTIFACT_MATCHES=$(find "$ARTIFACT_STORAGE" -maxdepth 1 -type d -name "${APP_PREFIX}*" 2>/dev/null | grep -v "web-session" || true)
WORKSPACE_MATCHES=$(find "$WORKSPACE_BASE" -maxdepth 1 -type d -name "${APP_PREFIX}*" 2>/dev/null || true)

echo ""
echo "=== Artifact Storage Matches ==="
if [ -n "$ARTIFACT_MATCHES" ]; then
    echo "$ARTIFACT_MATCHES" | while read -r match; do
        basename "$match"
    done
else
    echo "(none)"
fi

echo ""
echo "=== Workspace Matches ==="
if [ -n "$WORKSPACE_MATCHES" ]; then
    echo "$WORKSPACE_MATCHES" | while read -r match; do
        basename "$match"
    done
else
    echo "(none)"
fi

# Count matches
ARTIFACT_COUNT=$(echo "$ARTIFACT_MATCHES" | grep -c . 2>/dev/null || echo 0)
WORKSPACE_COUNT=$(echo "$WORKSPACE_MATCHES" | grep -c . 2>/dev/null || echo 0)

if [ "$ARTIFACT_COUNT" -eq 0 ] && [ "$WORKSPACE_COUNT" -eq 0 ]; then
    log_error "No apps found matching '$APP_PREFIX'"
    exit 1
fi

# If multiple matches, ask user to be more specific
if [ "$ARTIFACT_COUNT" -gt 1 ] || [ "$WORKSPACE_COUNT" -gt 1 ]; then
    log_warn "Multiple matches found. Please provide a more specific prefix."
    exit 1
fi

# Determine the app ID
if [ -n "$ARTIFACT_MATCHES" ]; then
    APP_ID=$(basename "$ARTIFACT_MATCHES")
elif [ -n "$WORKSPACE_MATCHES" ]; then
    APP_ID=$(basename "$WORKSPACE_MATCHES")
fi

log_success "Found app: $APP_ID"

# Define paths
ARTIFACT_PATH="$ARTIFACT_STORAGE/$APP_ID"
WORKSPACE_PATH="$WORKSPACE_BASE/$APP_ID"
SETTINGS_PATH="$SETTINGS_BASE/$APP_ID"
TARBALL_DIR="$ARTIFACT_PATH/workspace.tar.gz"

echo ""
log_info "Paths:"
echo "  Artifact: $ARTIFACT_PATH"
echo "  Workspace: $WORKSPACE_PATH"
echo "  Settings: $SETTINGS_PATH"

# Find latest tarball version
if [ -d "$TARBALL_DIR" ]; then
    LATEST_VERSION=$(ls "$TARBALL_DIR" | grep -E '^[0-9]+$' | sort -n | tail -1)
    if [ -n "$LATEST_VERSION" ]; then
        log_success "Latest tarball version: $LATEST_VERSION"
        TARBALL_PATH="$TARBALL_DIR/$LATEST_VERSION"
    else
        log_warn "No tarball versions found"
        TARBALL_PATH=""
    fi
else
    log_warn "No tarball directory found at $TARBALL_DIR"
    TARBALL_PATH=""
fi

# Create workspace directory if needed
if [ ! -d "$WORKSPACE_PATH" ]; then
    log_info "Creating workspace directory..."
    mkdir -p "$WORKSPACE_PATH"
fi

# Extract tarball if available
if [ -n "$TARBALL_PATH" ] && [ -f "$TARBALL_PATH" ]; then
    echo ""
    read -p "Extract tarball version $LATEST_VERSION to workspace? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Extracting tarball to workspace..."
        # Clear workspace first (except node_modules to save time)
        find "$WORKSPACE_PATH" -mindepth 1 -maxdepth 1 ! -name 'node_modules' -exec rm -rf {} \;
        tar -xzf "$TARBALL_PATH" -C "$WORKSPACE_PATH"
        log_success "Tarball extracted"
    fi
fi

# Create settings directory if needed
if [ ! -d "$SETTINGS_PATH" ]; then
    log_info "Creating settings directory..."
    mkdir -p "$SETTINGS_PATH"
fi

# Create basic settings.json if it doesn't exist
SETTINGS_JSON="$SETTINGS_PATH/settings.json"
if [ ! -f "$SETTINGS_JSON" ]; then
    log_info "Creating default settings.json..."
    cat > "$SETTINGS_JSON" << 'EOF'
{
  "allowedTools": ["*"],
  "autoApproveTools": true,
  "maxThinkingTokens": 4000,
  "sandbox": {
    "enabled": true,
    "allowedNetworkDomains": ["*"]
  }
}
EOF
fi

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    log_warn "ANTHROPIC_API_KEY not set. Claude Code won't work without it."
    log_info "Set it with: export ANTHROPIC_API_KEY=your-key"
fi

echo ""
log_info "Workspace contents:"
ls -la "$WORKSPACE_PATH" | head -20

echo ""
log_info "Launching interactive container..."
echo ""
echo "Container mounts:"
echo "  /workspace <- $WORKSPACE_PATH"
echo "  /home/node/.claude <- $SETTINGS_PATH"
echo ""
echo "You are now inside the container as the 'node' user."
echo "The workspace is at /workspace"
echo ""
echo "Useful commands:"
echo "  ls /template/node_modules/@sam/       # Check if SDK is in template"
echo "  ls /workspace/node_modules/@sam/      # Check if SDK is in workspace"
echo "  npm ls @sam/sdk                       # Check npm sees the SDK"
echo "  cat /workspace/package.json           # View package.json"
echo "  npm run build                         # Try building the app"
echo ""
echo "To copy SDK from template to workspace:"
echo "  cp -r /template/node_modules/@sam /workspace/node_modules/"
echo ""
echo "Type 'exit' to leave the container."
echo ""

# Build the docker/podman command
CMD=(
    "$CONTAINER_RUNTIME"
    "run"
    "--rm"
    "-it"
    "--user" "node"
    "-v" "$WORKSPACE_PATH:/workspace:Z"
    "-v" "$SETTINGS_PATH:/home/node/.claude:Z"
    "-w" "/workspace"
)

# Add API key if available
if [ -n "$ANTHROPIC_API_KEY" ]; then
    CMD+=("-e" "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY")
fi

# Override entrypoint to get a shell
CMD+=("--entrypoint" "/bin/sh")
CMD+=("$CONTAINER_IMAGE")

# Run the container
"${CMD[@]}"

log_success "Container exited"
