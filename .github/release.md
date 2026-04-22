# Release Workflow

This document describes how releases are automated in `solace-agent-mesh` using
Release Please, CI-driven release readiness checks, and the publish pipeline.

## Overview

```
Push to main
  ├── CI: tests, SonarQube, FOSSA (PRs only), Docker build
  └── Release Please (independent, does not wait for CI)
        ├── Creates/updates release-please PR (if releasable commits exist)
        └── Creates GitHub Release (if release-please PR was just merged)
              └── Post-process: build & attach assets
                    └── Publish: PyPI + DockerHub

Release-please PR (opened by Release Please)
  └── CI (triggered by PR event, detects release-please context)
        ├── Tests + SonarQube
        ├── Docker build + push to ECR
        ├── Release Readiness (FOSSA, Prisma, SonarQube Hotspots, Guardian)
        ├── RC Gate (integration tests, dispatched after readiness passes)
        └── Propagate statuses to PR for branch protection
```

## Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yaml` | Push to `main`, PRs | Tests, FOSSA scan (PRs), Docker build; on release-please PRs also runs release readiness + RC gate |
| `release-please.yaml` | Push to `main` | Independently creates/updates release-please PRs and creates GitHub Releases |
| `publish.yaml` | `workflow_dispatch` | Publishes to PyPI and promotes Docker image to DockerHub |
| `release-readiness-check.yaml` | Called by CI and publish | Runs security/compliance gates (FOSSA, Prisma, SonarQube, Guardian) |
| `build-push-image.yaml` | Called by CI | Reusable multi-platform Docker build with ECR push and caching |
| `fossa-scan.yaml` | Manual dispatch | Ad-hoc FOSSA scan (wraps `sca-scan-and-guard.yaml`) |

## Release Please

[Release Please](https://github.com/googleapis/release-please) automates
versioning and changelog generation from
[Conventional Commits](https://www.conventionalcommits.org/).

### How it works

Release Please runs as a **standalone workflow** (`release-please.yaml`) on every
push to `main`. It does **not** wait for CI checks and does **not** consume CI
results. On each push it does one of two things:

- **No release-please PR was merged** &mdash; Creates or updates a release-please
  PR with a version bump and `CHANGELOG.md` update. The PR accumulates all
  releasable commits since the last release.
- **A release-please PR was just merged** &mdash; Creates a GitHub Release with a
  tag, triggering the post-process and publish pipeline.

Release readiness verification happens separately, driven by CI on the
release-please PR itself (see [CI on release-please PRs](#on-release-please-prs)).

### Configuration

| File | Purpose |
|------|---------|
| `release-please-config.json` | Release type (`python`), changelog sections, PR title pattern, extra files to version-bump |
| `.release-please-manifest.json` | Tracks the current released version per package |

### Version bumping rules

Release Please reads commit messages since the last release:

| Commit prefix | Version bump |
|---------------|-------------|
| `feat:` | Minor (`0.x.0`) |
| `fix:` | Patch (`0.0.x`) |
| `feat!:` or `BREAKING CHANGE` | Major (`x.0.0`) &mdash; while pre-1.0, bumps minor instead |

## CI Pipeline (`ci.yaml`)

CI runs on every push to `main` and every PR. The first thing it does is detect
the execution context (`detect-context` job) to determine the flow:

### On regular PRs

```
detect-context
  ├── fossa_pr_scan (diff mode, PR comment, status check)
  ├── test-and-sonarqube
  ├── build-and-push (build only, no ECR push)
  └── ci-status (gate)
```

- FOSSA runs in **diff mode**, showing only new licensing/vulnerability
  violations and posting a PR comment with a status check.
- Docker images are built but not pushed to ECR.
- Prisma container scan runs on the locally-built image.

### On push to main

```
detect-context
  ├── test-and-sonarqube
  ├── build-and-push (build + push to ECR + multi-arch manifest + DynamoDB update)
  └── ci-status (gate)
```

- Tests and SonarQube analysis run.
- Docker images are built, pushed to ECR, and a multi-arch manifest is created.
- FOSSA does **not** run on push (it runs on PRs and inside release readiness).
- Release Please runs independently in its own workflow &mdash; CI does not call it.

### On release-please PRs

When CI detects a release-please PR (branch name contains `release-please`), it
runs the full release readiness pipeline instead of the regular PR flow:

```
detect-context
  ├── test-and-sonarqube
  ├── build-and-push (build + push to ECR for scanning)
  ├── release-readiness (FOSSA, Prisma, SonarQube Hotspots, Guardian)
  │     └── rc-gate (dispatch RC workflow and wait)
  └── propagate-release-statuses
        └── Commit statuses written to PR head + base SHAs
              └── ci-status (gate)
```

- Docker images are pushed to ECR so Prisma can scan them.
- Release readiness runs the full security/compliance suite.
- After readiness passes, the RC gate dispatches integration tests in
  `rc-sam-community` and waits for completion (up to 2 hours).
- All results (FOSSA, Prisma, SonarQube, Guardian, RC) are propagated as
  **GitHub commit statuses** on the PR, making them visible in the PR UI and
  available for branch protection rules.

## Release Readiness Check (`release-readiness-check.yaml`)

A reusable workflow that evaluates whether a commit is safe to release. It runs
the following security and compliance gates:

| Gate | What it checks |
|------|---------------|
| **FOSSA Scan** | Open-source licensing compliance and known vulnerabilities |
| **Prisma Scan** | Container image vulnerability scanning |
| **SonarQube Hotspots** | Security hotspot review status |
| **Guardian Gate** | Unified vulnerability gate across FOSSA and Prisma findings |

The RC gate is **not** part of this workflow. It runs as a separate job in
`ci.yaml` after release readiness completes, keeping concerns separated.

### Operating modes

The workflow supports two modes controlled by `check_only`:

- **`check_only: false`** (default) &mdash; Runs fresh FOSSA and Prisma scans
  and synchronizes the Guardian database. Used during CI on release-please PRs.
- **`check_only: true`** &mdash; Skips FOSSA/Prisma scans (assumes they already
  ran) and only checks the Guardian gate against existing data. Used during
  publish to avoid redundant scans.

### Skip security checks

When `skip_security_checks: true` is passed, the workflow verifies that the
triggering GitHub actor has **admin** permission on the repository. If confirmed:

- Failing security gates (FOSSA, Prisma, SonarQube, Guardian) emit warnings
  instead of errors and do not cause the workflow to fail.

If the actor is not an admin, the bypass is denied and all gates are enforced
normally.

### Where it runs

| Caller | Mode | When |
|--------|------|------|
| `ci.yaml` (release-please PR) | `check_only: false` | When CI detects a release-please PR |
| `publish.yaml` | `check_only: true` | Before publishing to PyPI/DockerHub |

### Status propagation

After the release readiness check and RC gate complete on a release-please PR,
`ci.yaml` propagates results as GitHub commit statuses to both the PR head and
base SHAs:

- `FOSSA / Release Readiness`
- `Prisma / Release Readiness`
- `SonarQube Hotspots / Release Readiness`
- `Guardian / Release Readiness`
- `RC / Integration Tests (Community)`

These statuses are visible on the PR and can be used in branch protection rules
to gate merging.

## FOSSA Scan

CI calls the shared `SolaceDev/solace-public-workflows/.github/workflows/sca-scan-and-guard.yaml`
reusable workflow. It auto-detects the calling context:

| Context | Diff mode | PR comment | Status check |
|---------|-----------|------------|-------------|
| **Regular PR** | Yes (new violations only) | Yes | Yes |
| **Release readiness** | No (full scan at release revision) | No | No |
| **Manual** (`fossa-scan.yaml`) | No (full scan) | No | No |

### What the scan checks

- **Licensing** &mdash; Policy conflicts (e.g., copyleft in a permissive project).
- **Vulnerability** &mdash; Known CVEs in dependencies.

## Publish Pipeline (`publish.yaml`)

Triggered by `workflow_dispatch` (usually from `release-please.yaml` after a
release is created). Accepts a version string and performs:

1. **Resolve release** &mdash; Finds the GitHub Release by tag, resolves the commit
   SHA and Docker image tag.
2. **Release readiness check** &mdash; Runs in `check_only` mode to verify all
   security gates passed before publishing.
3. **PyPI publish** &mdash; Downloads `.whl` and `.tar.gz` artifacts from the
   GitHub Release and publishes to PyPI using trusted publishing.
4. **DockerHub promotion** &mdash; Copies the multi-arch image from ECR to
   `solace/solace-agent-mesh` on DockerHub using skopeo.

### Manual publish with security bypass

To publish when security checks are failing (e.g., a known false positive):

```
gh workflow run publish.yaml \
  -f version=1.19.0 \
  -f skip_security_checks=true
```

Only repository admins can use this bypass.

## End-to-End Release Flow

```
 1. Developer merges feature PR to main
 2. CI runs on main: tests, SonarQube, Docker build + push to ECR
 3. Release Please (independent) creates/updates release-please PR
 4. CI runs on release-please PR:
    a. Tests + SonarQube
    b. Docker build + push to ECR
    c. Release readiness: FOSSA, Prisma, SonarQube Hotspots, Guardian
    d. RC gate: dispatches and waits for integration tests
    e. Statuses propagated to PR for branch protection
 5. Reviewer approves and merges the release-please PR
 6. release-please.yaml creates a GitHub Release + tag
 7. release-post-process.yml builds and attaches Python artifacts
 8. publish.yaml is dispatched:
    a. Verifies release readiness (check-only)
    b. Publishes to PyPI
    c. Promotes Docker image to DockerHub
 9. release-please.yaml verifies publish succeeded
```

## Troubleshooting

### Release readiness failing on the release-please PR

Check the individual gates in the workflow run summary. Each gate (FOSSA, Prisma,
SonarQube, Guardian) reports its status. If a gate is failing due to a known
issue, an admin can use `skip_security_checks` on the publish workflow to proceed
with publishing despite the failure.

### RC gate timing out

The RC gate waits up to 2 hours for the integration test workflow in
`rc-sam-community` to complete. If it times out, check the dispatched RC workflow
run for stuck jobs or infrastructure issues.

### Publish workflow failing after release

The `trigger-publish` job in `release-please.yaml` explicitly checks the publish
workflow's conclusion. If it reports `startup_failure` or `failure`, the job fails.
Check the dispatched publish workflow run for details.

### Commit statuses not appearing on the release-please PR

The `propagate-release-statuses` job runs with `if: always()` so it executes even
if the RC gate fails. However, it requires the `detect-context` job to have
resolved the PR SHAs. If statuses are missing, check that `detect-context`
succeeded and that the PR head/base SHAs were resolved correctly.
