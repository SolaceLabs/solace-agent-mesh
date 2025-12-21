#!/bin/bash

# Prescriptive Workflows - Stacked PR Creation Script
#
# This script creates the stacked PR branches for the prescriptive workflows feature.
# Each PR branch builds on the previous one, with the final branch containing all changes.
#
# Usage: ./scripts/create-workflow-prs.sh [--dry-run] [--start-from <pr-number>]
#
# Options:
#   --dry-run        Show what would be done without making changes
#   --start-from N   Start from PR N (useful for resuming after failure)

set -e  # Exit on error

# Configuration
SOURCE_BRANCH="ed/prescriptive-workflows"
FEATURE_BRANCH="feature/prescriptive-workflows"
PR_SUMMARIES_DIR="docs/plans/pr-summaries"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=false
START_FROM=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --start-from)
            START_FROM="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Helper functions
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

# Verify we're in the right repo
verify_repo() {
    if [ ! -d ".git" ]; then
        log_error "Not in a git repository"
        exit 1
    fi

    if [ ! -f "src/solace_agent_mesh/__init__.py" ]; then
        log_error "Not in the solace-agent-mesh repository root"
        exit 1
    fi

    # Verify source branch exists
    if ! git rev-parse --verify "$SOURCE_BRANCH" >/dev/null 2>&1; then
        log_error "Source branch '$SOURCE_BRANCH' does not exist"
        exit 1
    fi

    log_success "Repository verification passed"
}

# Check for uncommitted changes
check_clean_state() {
    if [ -n "$(git status --porcelain)" ]; then
        log_error "Working directory has uncommitted changes. Please commit or stash them first."
        exit 1
    fi
    log_success "Working directory is clean"
}

# Create the base feature branch
create_feature_branch() {
    log_info "Creating feature branch: $FEATURE_BRANCH"

    run_cmd git checkout main
    run_cmd git pull origin main

    # Check if feature branch already exists
    if git rev-parse --verify "$FEATURE_BRANCH" >/dev/null 2>&1; then
        log_warning "Feature branch '$FEATURE_BRANCH' already exists"
        run_cmd git checkout "$FEATURE_BRANCH"
    else
        run_cmd git checkout -b "$FEATURE_BRANCH"
        run_cmd git push -u origin "$FEATURE_BRANCH"
    fi

    log_success "Feature branch ready"
}

# Generic function to create a PR branch
create_pr_branch() {
    local pr_number="$1"
    local pr_name="$2"
    local base_branch="$3"
    local pr_title="$4"
    local commit_msg="$5"
    shift 5
    local files=("$@")

    local branch_name="pr/workflows-${pr_number}"

    log_info "=========================================="
    log_info "Creating PR $pr_number: $pr_name"
    log_info "Branch: $branch_name"
    log_info "Base: $base_branch"
    log_info "=========================================="

    # Checkout base branch
    run_cmd git checkout "$base_branch"

    # Check if PR branch already exists
    if git rev-parse --verify "$branch_name" >/dev/null 2>&1; then
        log_warning "Branch '$branch_name' already exists. Deleting and recreating..."
        run_cmd git branch -D "$branch_name"
    fi

    # Create new branch
    run_cmd git checkout -b "$branch_name"

    # Checkout files from source branch
    log_info "Checking out files from $SOURCE_BRANCH:"
    for file in "${files[@]}"; do
        log_info "  - $file"
        if [ "$DRY_RUN" = false ]; then
            git checkout "$SOURCE_BRANCH" -- "$file" 2>/dev/null || log_warning "File/path not found: $file"
        fi
    done

    # Commit changes
    run_cmd git add -A

    if [ "$DRY_RUN" = false ]; then
        # Check if there are changes to commit
        if git diff --cached --quiet; then
            log_warning "No changes to commit for $branch_name"
        else
            git commit -m "$commit_msg"
        fi
    else
        echo -e "${YELLOW}[DRY-RUN]${NC} git commit -m \"$commit_msg\""
    fi

    # Push branch
    run_cmd git push -u origin "$branch_name" --force

    # Show diff stats
    if [ "$DRY_RUN" = false ]; then
        log_info "Changes in this PR:"
        git diff --stat "$base_branch"
    fi

    log_success "Branch $branch_name created and pushed"
    echo ""
}

# Create GitHub PR
create_github_pr() {
    local pr_number="$1"
    local base_branch="$2"
    local pr_title="$3"
    local summary_file="$4"

    local branch_name="pr/workflows-${pr_number}"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} gh pr create --base $base_branch --head $branch_name --title \"$pr_title\""
        return
    fi

    # Check if PR already exists
    existing_pr=$(gh pr list --head "$branch_name" --json number --jq '.[0].number' 2>/dev/null || echo "")

    if [ -n "$existing_pr" ]; then
        log_warning "PR already exists for $branch_name: #$existing_pr"
        return
    fi

    # Read PR body from summary file if it exists
    local pr_body=""
    if [ -f "$summary_file" ]; then
        pr_body=$(cat "$summary_file")
    else
        pr_body="See PR summary in $summary_file"
    fi

    log_info "Creating GitHub PR..."
    gh pr create \
        --base "$base_branch" \
        --head "$branch_name" \
        --title "$pr_title" \
        --body "$pr_body" \
        --draft

    log_success "GitHub PR created"
}

# ============================================================================
# PR Definitions
# ============================================================================

create_pr_1() {
    create_pr_branch "1-foundation" "Foundation" "$FEATURE_BRANCH" \
        "PR 1: Foundation - Data Models & Constants" \
        "feat(workflows): Add foundation data models and constants

Adds the foundational data models and utilities required by the
Prescriptive Workflows feature:
- StructuredInvocationRequest/Result data parts
- WorkflowExecution* data parts for visualization
- Extension URI constants
- Agent card schema utilities

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>" \
        "src/solace_agent_mesh/common/data_parts.py" \
        "src/solace_agent_mesh/common/constants.py" \
        "src/solace_agent_mesh/common/a2a/types.py" \
        "src/solace_agent_mesh/common/a2a/__init__.py" \
        "src/solace_agent_mesh/common/agent_card_utils.py"

    create_github_pr "1-foundation" "$FEATURE_BRANCH" \
        "PR 1: Foundation - Data Models & Constants" \
        "$PR_SUMMARIES_DIR/PR_1_SUMMARY.md"
}

create_pr_2() {
    create_pr_branch "2-models" "Workflow Models" "pr/workflows-1-foundation" \
        "PR 2: Workflow Definition Models" \
        "feat(workflows): Add workflow definition Pydantic models

Adds the Pydantic models that define the YAML schema for workflow
definitions with Argo Workflows-compatible syntax:
- Node types: AgentNode, ConditionalNode, SwitchNode, LoopNode, MapNode
- WorkflowDefinition with DAG validation
- RetryStrategy and ExitHandler models

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>" \
        "src/solace_agent_mesh/workflow/app.py" \
        "src/solace_agent_mesh/workflow/__init__.py"

    create_github_pr "2-models" "pr/workflows-1-foundation" \
        "PR 2: Workflow Definition Models" \
        "$PR_SUMMARIES_DIR/PR_2_SUMMARY.md"
}

create_pr_3() {
    create_pr_branch "3-agent-support" "Structured Invocation" "pr/workflows-2-models" \
        "PR 3: Structured Invocation Support" \
        "feat(workflows): Add structured invocation support for agents

Enables agents to be invoked with schema-validated input/output:
- StructuredInvocationHandler for schema validation and retry
- Integration with SamAgentComponent
- Result embed pattern for structured output

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>" \
        "src/solace_agent_mesh/agent/sac/structured_invocation/" \
        "src/solace_agent_mesh/agent/sac/component.py" \
        "src/solace_agent_mesh/agent/sac/app.py"

    create_github_pr "3-agent-support" "pr/workflows-2-models" \
        "PR 3: Structured Invocation Support" \
        "$PR_SUMMARIES_DIR/PR_3_SUMMARY.md"
}

create_pr_4() {
    create_pr_branch "4-workflow-tool" "Workflow Tool" "pr/workflows-3-agent-support" \
        "PR 4: Workflow Tool for Agents" \
        "feat(workflows): Add workflow tool for agent invocation

Adds ADK Tool that allows agents to invoke workflows:
- Dynamic tool generation from workflow schema
- Dual-mode invocation (parameters or artifact)
- Long-running execution with polling

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>" \
        "src/solace_agent_mesh/agent/tools/workflow_tool.py"

    create_github_pr "4-workflow-tool" "pr/workflows-3-agent-support" \
        "PR 4: Workflow Tool for Agents" \
        "$PR_SUMMARIES_DIR/PR_4_SUMMARY.md"
}

create_pr_5a() {
    create_pr_branch "5a-orchestrator" "Orchestrator Component" "pr/workflows-4-workflow-tool" \
        "PR 5a: Workflow Runtime - Orchestrator Component" \
        "feat(workflows): Add workflow orchestrator component

Adds the WorkflowExecutorComponent that coordinates execution:
- Component lifecycle and message routing
- Agent card generation with schemas
- Event publishing for visualization
- A2A protocol message handlers

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>" \
        "src/solace_agent_mesh/workflow/component.py" \
        "src/solace_agent_mesh/workflow/protocol/"

    create_github_pr "5a-orchestrator" "pr/workflows-4-workflow-tool" \
        "PR 5a: Workflow Runtime - Orchestrator Component" \
        "$PR_SUMMARIES_DIR/PR_5a_SUMMARY.md"
}

create_pr_5b() {
    create_pr_branch "5b-dag-core" "DAG Executor Core" "pr/workflows-5a-orchestrator" \
        "PR 5b: Workflow Runtime - DAG Executor Core" \
        "feat(workflows): Add DAG executor core logic

Adds the core DAG execution engine:
- Dependency graph building and validation
- Node execution dispatch
- Template resolution for data flow
- Conditional expression evaluation
- Execution context management

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>" \
        "src/solace_agent_mesh/workflow/dag_executor.py" \
        "src/solace_agent_mesh/workflow/workflow_execution_context.py" \
        "src/solace_agent_mesh/workflow/flow_control/" \
        "src/solace_agent_mesh/workflow/utils.py"

    create_github_pr "5b-dag-core" "pr/workflows-5a-orchestrator" \
        "PR 5b: Workflow Runtime - DAG Executor Core" \
        "$PR_SUMMARIES_DIR/PR_5b_SUMMARY.md"
}

create_pr_5c() {
    create_pr_branch "5c-advanced-nodes" "Advanced Nodes" "pr/workflows-5b-dag-core" \
        "PR 5c: Workflow Runtime - Advanced Node Types" \
        "feat(workflows): Add agent caller for A2A invocation

Adds the AgentCaller for invoking agents via A2A:
- Input template resolution
- A2A message construction
- Artifact creation for input data

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>" \
        "src/solace_agent_mesh/workflow/agent_caller.py"

    create_github_pr "5c-advanced-nodes" "pr/workflows-5b-dag-core" \
        "PR 5c: Workflow Runtime - Advanced Node Types" \
        "$PR_SUMMARIES_DIR/PR_5c_SUMMARY.md"
}

create_pr_6() {
    create_pr_branch "6-integration" "Integration & Tests" "pr/workflows-5c-advanced-nodes" \
        "PR 6: Integration, Examples & Tests" \
        "feat(workflows): Add integration, examples, and tests

Adds backend integration and comprehensive test coverage:
- Gateway workflow event forwarding
- Example workflows (all_node_types, jira_bug_triage)
- Unit tests for pure functions (~1,770 lines)
- Integration tests for error scenarios (~2,000 lines)
- Declarative test workflows (8 YAML files)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>" \
        "src/solace_agent_mesh/gateway/http_sse/" \
        "examples/agents/all_node_types_workflow.yaml" \
        "examples/agents/jira_bug_triage_workflow.yaml" \
        "examples/agents/new_node_types_test.yaml" \
        "tests/unit/workflow/" \
        "tests/integration/scenarios_programmatic/test_workflow_errors.py" \
        "tests/integration/scenarios_declarative/test_data/workflows/"

    create_github_pr "6-integration" "pr/workflows-5c-advanced-nodes" \
        "PR 6: Integration, Examples & Tests" \
        "$PR_SUMMARIES_DIR/PR_6_SUMMARY.md"
}

create_pr_7() {
    create_pr_branch "7-frontend" "Frontend Visualization" "pr/workflows-6-integration" \
        "PR 7: Frontend - Visualization" \
        "feat(workflows): Add frontend workflow visualization

Adds all frontend changes for workflow visualization:
- Layout engine for positioning nodes
- FlowChart components (panel, renderer, edges)
- Node components for all node types
- NodeDetailsCard sidebar
- Task visualizer processor
- Provider updates

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>" \
        "client/webui/frontend/src/lib/components/activities/" \
        "client/webui/frontend/src/lib/providers/" \
        "client/webui/frontend/src/lib/types/activities.ts"

    create_github_pr "7-frontend" "pr/workflows-6-integration" \
        "PR 7: Frontend - Visualization" \
        "$PR_SUMMARIES_DIR/PR_7_SUMMARY.md"
}

# ============================================================================
# Main execution
# ============================================================================

main() {
    echo ""
    echo "=========================================="
    echo "Prescriptive Workflows - Stacked PR Creator"
    echo "=========================================="
    echo ""

    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN MODE - No changes will be made"
        echo ""
    fi

    # Verify prerequisites
    verify_repo
    check_clean_state

    # Create feature branch (always do this)
    if [ "$START_FROM" -le 0 ]; then
        create_feature_branch
    fi

    # Create PRs based on start point
    [ "$START_FROM" -le 1 ] && create_pr_1
    [ "$START_FROM" -le 2 ] && create_pr_2
    [ "$START_FROM" -le 3 ] && create_pr_3
    [ "$START_FROM" -le 4 ] && create_pr_4
    [ "$START_FROM" -le 5 ] && create_pr_5a
    [ "$START_FROM" -le 5 ] && create_pr_5b
    [ "$START_FROM" -le 5 ] && create_pr_5c
    [ "$START_FROM" -le 6 ] && create_pr_6
    [ "$START_FROM" -le 7 ] && create_pr_7

    echo ""
    echo "=========================================="
    log_success "All PR branches created!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Review each PR on GitHub"
    echo "2. Merge PRs in order (1 → 2 → 3 → ... → 7)"
    echo "3. After all PRs merge to feature branch, create final PR to main"
    echo ""
    echo "Branch structure:"
    echo "  main"
    echo "    └── feature/prescriptive-workflows"
    echo "          └── pr/workflows-1-foundation"
    echo "                └── pr/workflows-2-models"
    echo "                      └── pr/workflows-3-agent-support"
    echo "                            └── pr/workflows-4-workflow-tool"
    echo "                                  └── pr/workflows-5a-orchestrator"
    echo "                                        └── pr/workflows-5b-dag-core"
    echo "                                              └── pr/workflows-5c-advanced-nodes"
    echo "                                                    └── pr/workflows-6-integration"
    echo "                                                          └── pr/workflows-7-frontend"
    echo ""

    # Return to source branch
    run_cmd git checkout "$SOURCE_BRANCH"
}

# Run main
main
