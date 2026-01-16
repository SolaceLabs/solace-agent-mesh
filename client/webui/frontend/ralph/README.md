# Ralph Wiggum Setup for Solace Agent Mesh UI

This directory contains the Ralph Wiggum autonomous development setup for this project.

## Quick Start

### 1. Create a Feature Spec

Create a file in `specs/` describing what you want to build:

```bash
nano specs/project-sharing.md
```

### 2. Run Planning Mode

Generate the implementation plan:

```bash
cd ralph
./loop.sh plan 1
```

This creates `IMPLEMENTATION_PLAN.md` with prioritized tasks.

### 3. Review the Plan

```bash
cat IMPLEMENTATION_PLAN.md
```

### 4. Run Build Mode

Execute the plan:

```bash
# Run 5 iterations
./loop.sh build 5

# Or unlimited
./loop.sh build
```

## How It Works

- **loop.sh** - Orchestrates the Ralph loop
- **PROMPT_plan.md** - Instructions for planning phase
- **PROMPT_build.md** - Instructions for build phase
- **AGENTS.md** - Operational learnings (stays lean)
- **specs/** - Your feature specifications
- **IMPLEMENTATION_PLAN.md** - Generated task list (tasks are REMOVED when complete)

## Task Completion

Tasks are marked complete by **REMOVING** them from `IMPLEMENTATION_PLAN.md`, not by checking them off.

## Backpressure

Each iteration runs:

```bash
npm run build-package && npm run lint
```

Tests must pass before a task is considered complete.

## Directory Structure

```
ralph/                      # Ralph setup (this directory)
├── loop.sh                 # Main script
├── PROMPT_plan.md          # Planning instructions
├── PROMPT_build.md         # Build instructions
├── AGENTS.md               # Operational knowledge
├── specs/                  # Feature specifications
│   └── your-feature.md
└── IMPLEMENTATION_PLAN.md  # Generated task list

../                         # Project root
├── src/                    # Implementation code
├── package.json
└── ...
```

## Tips

- Keep specs focused on one feature per file
- Let Ralph explore before assuming code is missing
- Plans are disposable - regenerate if off track
- Monitor progress: `watch -n 2 cat IMPLEMENTATION_PLAN.md`
