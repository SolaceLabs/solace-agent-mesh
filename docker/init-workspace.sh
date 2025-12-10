#!/bin/sh
# Universal workspace initialization script for Claude Code containers
# This script runs before Claude Code starts to ensure workspace is properly initialized

set -e

WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
TEMPLATE_DIR="${TEMPLATE_DIR:-}"

echo "Checking workspace initialization at $WORKSPACE_DIR..."

# Check if workspace is empty or uninitialized
# We consider it initialized if it has a .git directory or any substantial content
if [ -d "$WORKSPACE_DIR/.git" ] || [ "$(ls -A "$WORKSPACE_DIR" 2>/dev/null | wc -l)" -gt 0 ]; then
    echo "✓ Workspace already initialized"
    exit 0
fi

echo "Initializing new workspace..."

# If a template directory is provided, copy it to workspace
if [ -n "$TEMPLATE_DIR" ] && [ -d "$TEMPLATE_DIR" ]; then
    echo "Copying template from $TEMPLATE_DIR..."
    cp -r "$TEMPLATE_DIR"/* "$WORKSPACE_DIR/" 2>/dev/null || true
    cp -r "$TEMPLATE_DIR"/.[!.]* "$WORKSPACE_DIR/" 2>/dev/null || true

    # Update package.json if it exists and APP_ID/APP_NAME are provided
    if [ -f "$WORKSPACE_DIR/package.json" ] && [ -n "$APP_ID" ] && [ -n "$APP_NAME" ]; then
        echo "Updating package.json metadata..."
        # Use node to properly update JSON (node is available in all our containers)
        node -e "
const fs = require('fs');
const packageJson = JSON.parse(fs.readFileSync('$WORKSPACE_DIR/package.json', 'utf8'));
packageJson.name = '$APP_ID';
packageJson.description = 'SAM App: $APP_NAME';
fs.writeFileSync('$WORKSPACE_DIR/package.json', JSON.stringify(packageJson, null, 2) + '\n');
console.log('✓ Updated package.json');
" || echo "Warning: Failed to update package.json"
    fi

    echo "✓ Template copied successfully"
fi

# Initialize git repository if not already initialized
if [ ! -d "$WORKSPACE_DIR/.git" ]; then
    echo "Initializing git repository..."
    cd "$WORKSPACE_DIR"
    git init
    git add . 2>/dev/null || true
    git commit -m "Initial commit" 2>/dev/null || true
    echo "✓ Git repository initialized"
fi

echo "✓ Workspace initialization complete"
