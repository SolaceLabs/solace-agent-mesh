#!/bin/bash
# Build and version script for SAM apps
# Usage: build_and_version.sh [major|minor|patch]
# Default: patch
#
# This script:
# 1. Reads current version from VERSION file
# 2. Increments version based on argument (semver)
# 3. Runs npm run build
# 4. On success: commits, tags, and updates VERSION file
# 5. On failure: exits without committing

set -e  # Exit on error

# Parse increment type (default to patch)
INCREMENT_TYPE="${1:-patch}"

if [[ ! "$INCREMENT_TYPE" =~ ^(major|minor|patch)$ ]]; then
    echo "Error: Invalid increment type '$INCREMENT_TYPE'. Must be major, minor, or patch." >&2
    exit 1
fi

# Working directory (mounted at /workspace in container)
WORKSPACE="${WORKSPACE_DIR:-/workspace}"
cd "$WORKSPACE"

# Version file path
VERSION_FILE="$WORKSPACE/VERSION"

# Function to read current version
read_version() {
    if [[ -f "$VERSION_FILE" ]]; then
        # Parse JSON version file
        VERSION=$(node -e "console.log(JSON.parse(require('fs').readFileSync('$VERSION_FILE', 'utf8')).version)")
        echo "$VERSION"
    else
        # Start at 0.0.0 if no version file exists
        echo "0.0.0"
    fi
}

# Function to increment version
increment_version() {
    local version=$1
    local increment=$2

    # Split version into major.minor.patch
    IFS='.' read -r major minor patch <<< "$version"

    case "$increment" in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        patch)
            patch=$((patch + 1))
            ;;
    esac

    echo "$major.$minor.$patch"
}

# Read current version
CURRENT_VERSION=$(read_version)
echo "Current version: $CURRENT_VERSION"

# Calculate new version
NEW_VERSION=$(increment_version "$CURRENT_VERSION" "$INCREMENT_TYPE")
echo "New version: $NEW_VERSION (increment: $INCREMENT_TYPE)"

# Run npm build
echo ""
echo "Building application..."
echo "Running: npm run build"
echo ""

if npm run build; then
    echo ""
    echo "✓ Build successful"
else
    echo "" >&2
    echo "✗ Build failed - aborting versioning" >&2
    exit 1
fi

# Get git commit hash
COMMIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Get timestamp (milliseconds since epoch)
TIMESTAMP=$(date +%s)000

# Write VERSION file
echo "Writing VERSION file..."
cat > "$VERSION_FILE" <<EOF
{
  "version": "$NEW_VERSION",
  "timestamp": $TIMESTAMP,
  "commit": "$COMMIT_HASH",
  "increment": "$INCREMENT_TYPE"
}
EOF

# Git commit and tag
echo "Creating git commit and tag..."

# Configure git if not already configured
git config user.name "Claude Code" 2>/dev/null || true
git config user.email "cc@workspace" 2>/dev/null || true

# Add all changes
git add .

# Commit with version message
git commit -m "Release v$NEW_VERSION" || {
    echo "Warning: No changes to commit (build output already committed?)" >&2
}

# Create git tag
git tag "v$NEW_VERSION" 2>/dev/null || {
    echo "Warning: Tag v$NEW_VERSION already exists, skipping tag creation" >&2
}

echo ""
echo "✓ Version $NEW_VERSION created successfully"
echo "  - Commit: $COMMIT_HASH"
echo "  - Tag: v$NEW_VERSION"
echo "  - Timestamp: $TIMESTAMP"

exit 0
