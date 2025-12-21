#!/bin/bash

# Prescriptive Workflows - PR and Branch Cleanup Script
#
# This script removes the stacked PR branches and closes the associated PRs.
# Run with --dry-run first to see what will happen.
#
# Usage: ./scripts/cleanup-workflow-prs.sh [--dry-run] [--keep-feature-branch]
#
# Options:
#   --dry-run              Show what would be done without making changes
#   --keep-feature-branch  Don't delete feature/prescriptive-workflows branch

set -e

# Configuration
FEATURE_BRANCH="feature/prescriptive-workflows"
PR_BRANCHES=(
    "pr/workflows-1-foundation"
    "pr/workflows-2-models"
    "pr/workflows-3-agent-support"
    "pr/workflows-4-workflow-tool"
    "pr/workflows-5a-orchestrator"
    "pr/workflows-5b-dag-core"
    "pr/workflows-5c-advanced-nodes"
    "pr/workflows-6-integration"
    "pr/workflows-7-frontend"
)
PR_NUMBERS=(697 698 699 700 701 702 703 704 705)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
DRY_RUN=false
KEEP_FEATURE_BRANCH=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --keep-feature-branch)
            KEEP_FEATURE_BRANCH=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $*"
    else
        log_info "Running: $*"
        "$@"
    fi
}

echo ""
echo "=========================================="
echo "Prescriptive Workflows - Cleanup Script"
echo "=========================================="
echo ""

if [ "$DRY_RUN" = true ]; then
    log_warning "DRY RUN MODE - No changes will be made"
    echo ""
fi

# Summary of what will be done
echo "This script will:"
echo ""
echo "1. Close these GitHub PRs:"
for pr in "${PR_NUMBERS[@]}"; do
    echo "   - PR #$pr"
done
echo ""
echo "2. Delete these remote branches:"
for branch in "${PR_BRANCHES[@]}"; do
    echo "   - origin/$branch"
done
if [ "$KEEP_FEATURE_BRANCH" = false ]; then
    echo "   - origin/$FEATURE_BRANCH"
fi
echo ""
echo "3. Delete these local branches (if they exist):"
for branch in "${PR_BRANCHES[@]}"; do
    echo "   - $branch"
done
if [ "$KEEP_FEATURE_BRANCH" = false ]; then
    echo "   - $FEATURE_BRANCH"
fi
echo ""

if [ "$DRY_RUN" = false ]; then
    echo -e "${RED}WARNING: This will permanently delete branches and close PRs!${NC}"
    echo ""
    read -p "Are you sure you want to proceed? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Aborted."
        exit 0
    fi
    echo ""
fi

# Ensure we're on a safe branch before deleting
current_branch=$(git branch --show-current)
if [[ " ${PR_BRANCHES[*]} " =~ " ${current_branch} " ]] || [ "$current_branch" = "$FEATURE_BRANCH" ]; then
    log_info "Currently on a branch that will be deleted. Switching to main..."
    run_cmd git checkout main
fi

# Step 1: Close PRs
log_info "=========================================="
log_info "Step 1: Closing GitHub PRs"
log_info "=========================================="
for pr in "${PR_NUMBERS[@]}"; do
    log_info "Closing PR #$pr..."
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} gh pr close $pr --comment \"Closing to recreate with complete changes.\""
    else
        gh pr close "$pr" --comment "Closing to recreate with complete changes." 2>/dev/null || log_warning "PR #$pr may already be closed"
    fi
done
echo ""

# Step 2: Delete remote branches
log_info "=========================================="
log_info "Step 2: Deleting remote branches"
log_info "=========================================="
for branch in "${PR_BRANCHES[@]}"; do
    log_info "Deleting origin/$branch..."
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} git push origin --delete $branch"
    else
        git push origin --delete "$branch" 2>/dev/null || log_warning "Remote branch $branch may not exist"
    fi
done

if [ "$KEEP_FEATURE_BRANCH" = false ]; then
    log_info "Deleting origin/$FEATURE_BRANCH..."
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} git push origin --delete $FEATURE_BRANCH"
    else
        git push origin --delete "$FEATURE_BRANCH" 2>/dev/null || log_warning "Remote branch $FEATURE_BRANCH may not exist"
    fi
fi
echo ""

# Step 3: Delete local branches
log_info "=========================================="
log_info "Step 3: Deleting local branches"
log_info "=========================================="
for branch in "${PR_BRANCHES[@]}"; do
    if git rev-parse --verify "$branch" >/dev/null 2>&1; then
        log_info "Deleting local branch $branch..."
        run_cmd git branch -D "$branch"
    else
        log_info "Local branch $branch does not exist, skipping"
    fi
done

if [ "$KEEP_FEATURE_BRANCH" = false ]; then
    if git rev-parse --verify "$FEATURE_BRANCH" >/dev/null 2>&1; then
        log_info "Deleting local branch $FEATURE_BRANCH..."
        run_cmd git branch -D "$FEATURE_BRANCH"
    else
        log_info "Local branch $FEATURE_BRANCH does not exist, skipping"
    fi
fi
echo ""

# Done
echo "=========================================="
log_success "Cleanup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Update scripts/create-workflow-prs.sh to include all changes"
echo "2. Run: ./scripts/create-workflow-prs.sh"
echo ""
