# Release Process

This document describes the release process for Solace Agent Mesh, including CI/CD workflows, security scanning, and publishing to PyPI and DockerHub.

## Table of Contents

- [Overview](#overview)
- [CI/CD Workflows](#cicd-workflows)
  - [Pull Request & Main Branch CI](#pull-request--main-branch-ci)
  - [Release Workflow](#release-workflow)
- [Security & Compliance Scanning](#security--compliance-scanning)
  - [FOSSA Scanning](#fossa-scanning)
  - [Security Checks](#security-checks)
- [Release Checklist](#release-checklist)
- [Emergency Releases](#emergency-releases)
- [Troubleshooting](#troubleshooting)

## Overview

Solace Agent Mesh follows a multi-stage release process:

1. **Development**: Code changes merged to `main` branch via pull requests
2. **RC Verification**: Release candidate tested in RC environment
3. **Security Scanning**: FOSSA license compliance + security checks (Prisma, SonarQube, WhiteSource)
4. **Release**: PyPI package published, Docker images pushed to DockerHub
5. **Deployment**: Release deployed to production environments

## CI/CD Workflows

### Pull Request & Main Branch CI

**Workflow**: `.github/workflows/ci.yaml`

**Triggers**:
- Pull requests to `main` branch
- Direct pushes to `main` branch

**Jobs** (run in parallel):

1. **FOSSA Scan** (`fossa_scan`)
   - Scans dependencies for license compliance and security vulnerabilities
   - Uses `sca-scan-and-guard` shareable workflow
   - Reads configuration from `.github/workflow-config.json`
   - **Policy mode**: BLOCK (fails on license policy violations)
   - **Vulnerability mode**: REPORT (reports but doesn't block)
   - Comments on PRs with scan results
   - Creates status checks for branch protection

2. **CI** (`ci`)
   - Python testing (versions 3.10, 3.11, 3.13)
   - SonarQube code quality analysis
   - WhiteSource dependency scanning
   - Node.js frontend build and testing
   - Runs in parallel with FOSSA scan

3. **Build Platform** (`build-platform`, `merge-manifest`)
   - Multiplatform Docker builds (linux/amd64, linux/arm64)
   - Pushes to Amazon ECR (only on main branch)
   - Creates multi-platform manifests
   - Updates DynamoDB release manifest
   - Triggers RC workflow for testing

**Configuration**:
- FOSSA configuration: `.github/workflow-config.json`
- FOSSA project config: `.fossa.yml`
- Required secrets: `FOSSA_API_KEY`, `SONARQUBE_TOKEN`, `WHITESOURCE_API_KEY`

### Release Workflow

**Workflow**: `.github/workflows/release.yml`

**Trigger**: Manual workflow dispatch

**Inputs**:
- `ref`: Git ref to release from (default: `main`)
- `version_bump_type`: Version bump type (`patch`, `minor`, `major`)
- `version`: Exact version to release (overrides bump type)
- `skip_docker_push`: Skip Docker push (default: `false`)
- `tag_as_latest`: Tag image as `latest` in DockerHub (default: `true`)
- `skip_security_checks`: Skip security checks (default: `false`, emergency only)
- `skip_rc_check`: Skip RC verification (default: `false`, emergency only)

**Jobs**:

```
prepare-release-metadata (validates actor if skip_security_checks=true)
  ↓
verify-rc (checks RC testing passed)
  ↓
┌─────────────────────┬────────────────────┐
│ fossa_scan          │ security-checks    │  (run in parallel)
│ (license/vuln scan) │ (Prisma, SonarQube)│
└─────────────────────┴────────────────────┘
  ↓
release (PyPI publish + git tag created)
  ↓
┌──────────────────────────┬───────────────────────────┐
│ fossa_scan_version_upload│ build_and_push_docker      │  (run in parallel)
│ (uploads tagged results  │ (DockerHub)                │
│  to FOSSA dashboard)     │                            │
└──────────────────────────┴───────────────────────────┘
```

#### 1. Prepare Release Metadata
- Finds last non-skip-ci commit
- Gets current version from `hatch`
- Constructs image tags for Prisma scanning

#### 2. Verify RC
- Checks GitHub status check: `RC / Integration Tests (Community)`
- Fallback: Verifies RC image exists in ECR
- Can be skipped with `skip_rc_check: true` input

#### 3. FOSSA Scan ⚠️ **RELEASE GATE**
- Scans the **commit SHA** resolved in `prepare-release-metadata` for license compliance
  - Note: the version tag does not exist yet at this point — it is created by `hatch-release-post` inside the `release` job downstream. The commit SHA is used to ensure FOSSA scans the exact code being released.
- Uses `sca-scan-and-guard` shareable workflow
- Configuration: `.github/workflow-config.json`
- **BLOCKS release if**:
  - License policy violations found (unapproved licenses)
  - Unlicensed dependencies detected
- **REPORTS but doesn't block**:
  - Security vulnerabilities (critical, high severity)
- Can be skipped with `skip_security_checks: true` input (**admin only** — see [Emergency Releases](#emergency-releases))

#### 4. Security Checks
- **Prisma Cloud**: Docker image vulnerability scanning
- **SonarQube**: Code quality hotspot check
- **WhiteSource**: Dependency security analysis
- **Note**: FOSSA check disabled here (`fossa_check: false`) - handled by dedicated `fossa_scan` job
- Can be skipped with `skip_security_checks: true` input

#### 5. Release to PyPI
- **Depends on**: `fossa_scan` + `security-checks` must pass
- Bumps version using `hatch`
- Builds Python package (includes frontend build)
- Publishes to PyPI using Trusted Publishing
- Creates git tag (e.g., `v1.18.0`)
- Creates GitHub release with changelog

#### 6. FOSSA Version Upload
- **Depends on**: Release to PyPI succeeds (git tag now exists)
- Re-runs FOSSA scan using the released **version tag** (e.g., `1.18.0`)
- Not a gate — runs unconditionally after a successful release
- Associates scan results with the semantic version in the FOSSA dashboard for long-term traceability
- Runs in parallel with Docker push

#### 7. Build and Push to DockerHub
- **Depends on**: Release to PyPI succeeds
- Builds Docker images for linux/amd64 and linux/arm64
- Pushes to DockerHub
- Optionally tags as `latest`
- Runs in parallel with FOSSA version upload

## Security & Compliance Scanning

### FOSSA Scanning

FOSSA scans all dependencies for:
- **License compliance**: Detects license policy violations
- **Security vulnerabilities**: Identifies known CVEs in dependencies

**Configuration File**: `.github/workflow-config.json`

```json
{
  "sca_scanning": {
    "enabled": true,
    "fossa": {
      "policy": {
        "mode": "BLOCK",
        "block_on": ["policy_conflict", "unlicensed_dependency"]
      },
      "vulnerability": {
        "mode": "REPORT",
        "block_on": ["critical", "high"]
      },
      "project_id": "SolaceLabs_solace-agent-mesh",
      "team": null,
      "labels": []
    }
  }
}
```

**Policy Modes**:
- **BLOCK**: Fails workflow if violations found (license policy only)
- **REPORT**: Reports findings but doesn't fail workflow (vulnerabilities)

**When FOSSA Runs**:

| Workflow | When | What It Scans | Blocks? |
|----------|------|---------------|---------|
| CI (PR/Push) | All PRs and main pushes | PR diff / latest commit | License violations only |
| Release (gate) | Manual release trigger | Commit SHA being released | License violations only |
| Release (upload) | After successful release | Version tag (e.g., `1.18.0`) | Never — traceability only |
| Manual (`fossa-scan.yaml`) | On demand via Actions UI | Any branch, tag, or SHA | License violations only |

**FOSSA Project Configuration**: `.fossa.yml`

```yaml
version: 3

project:
  locator: SolaceLabs_solace-agent-mesh
  id: SolaceLabs_solace-agent-mesh
  name: solace-agent-mesh
  labels:
    - solaceai
    - solacelabs
    - community
    - repository

paths:
  exclude:
    - ./.github

telemetry:
  scope: full
```

**How to View FOSSA Results**:
- FOSSA comments on PRs with scan results
- View full report: https://app.fossa.com/projects/custom+SolaceLabs_solace-agent-mesh
- Status checks appear in PR checks list

### Security Checks

**Prisma Cloud** (Docker Image Scanning):
- Scans Docker images for vulnerabilities
- Checks CVEs, malware, compliance issues
- Scans the RC image from ECR before release

**SonarQube** (Code Quality):
- Checks for security hotspots in code
- Analyzes code quality and maintainability
- Queries SonarQube API for open hotspots

**WhiteSource** (Dependency Security):
- Scans project dependencies for known vulnerabilities
- Checks for outdated or risky dependencies
- Separate from FOSSA (complementary analysis)

## Release Checklist

Before triggering a release:

- [ ] All PRs merged to `main` branch
- [ ] CI passing on `main` branch (FOSSA + tests)
- [ ] RC testing completed and passed
- [ ] RC status check shows success (or RC image exists in ECR)
- [ ] No open security hotspots in SonarQube
- [ ] FOSSA scan passes on latest commit (no license violations)
- [ ] Frontend built and tested
- [ ] Version number decided (patch/minor/major)

**To trigger a release**:

1. Go to [Actions → Release (PyPI & Docker)](https://github.com/SolaceLabs/solace-agent-mesh/actions/workflows/release.yml)
2. Click "Run workflow"
3. Select inputs:
   - **ref**: `main` (or specific branch/tag)
   - **version_bump_type**: `patch` (or `minor`/`major`)
   - **tag_as_latest**: ✅ (check if this should be the latest tag)
   - Leave other options at defaults
4. Click "Run workflow"
5. Monitor workflow progress:
   - Verify RC check passes
   - Verify FOSSA scan passes (no license violations)
   - Verify security checks pass
   - Verify PyPI publish succeeds
   - Verify DockerHub push succeeds

**After release**:

- [ ] Verify package on PyPI: https://pypi.org/project/solace-agent-mesh/
- [ ] Verify Docker image on DockerHub: https://hub.docker.com/r/solace/solace-agent-mesh
- [ ] Verify git tag created: `v{version}`
- [ ] Verify GitHub release created with changelog
- [ ] Test installation: `pip install solace-agent-mesh`
- [ ] Test Docker image: `docker pull solace/solace-agent-mesh:latest`

## Emergency Releases

In rare cases where immediate release is needed and security checks are failing:

**⚠️ WARNING**: Emergency releases bypass security gates and should only be used when:
- Critical production bug needs immediate fix
- Security checks have false positives blocking release
- Pre-approval from security team obtained

> **Admin only**: `skip_security_checks: true` can only be set by repository admins. If a non-admin triggers the release with this flag, the workflow fails immediately in `prepare-release-metadata` with a permission error.

**To perform an emergency release**:

1. Go to [Actions → Release (PyPI & Docker)](https://github.com/SolaceLabs/solace-agent-mesh/actions/workflows/release.yml)
2. Click "Run workflow"
3. Set emergency flags (**requires admin permissions**):
   - ✅ `skip_security_checks: true` (skips FOSSA + security checks)
   - ✅ `skip_rc_check: true` (skips RC verification)
4. Document the emergency release:
   - Create GitHub issue explaining why checks were skipped
   - Tag issue with `emergency-release` label
   - Follow up with proper security review post-release

**Emergency release workflow**:

```
prepare-release-metadata (admin permission verified here)
  ↓
verify-rc (SKIPPED)
  ↓
fossa_scan (SKIPPED)
security-checks (SKIPPED)
  ↓
release (PyPI publish + git tag created)
  ↓
┌──────────────────────────┬───────────────────────────┐
│ fossa_scan_version_upload│ build_and_push_docker      │
│ (always runs — records   │ (DockerHub)                │
│  version in FOSSA)       │                            │
└──────────────────────────┴───────────────────────────┘
```

> Note: `fossa_scan_version_upload` always runs after a successful release, even for emergency releases — ensuring every published version is recorded in the FOSSA dashboard.

**Post-emergency actions**:
- [ ] Create follow-up PR to address security issues
- [ ] Re-run security scans manually
- [ ] Document findings in security issue
- [ ] Plan for next regular release with full checks

## Troubleshooting

### Release Fails: FOSSA License Violation

**Error**: `FOSSA Scan / license-scan` fails with policy violations

**Cause**: Dependency uses unapproved license or has no license

**Solution**:
1. View FOSSA report: https://app.fossa.com/projects/custom+SolaceLabs_solace-agent-mesh
2. Identify the problematic dependency
3. Options:
   - Replace dependency with approved alternative
   - Request license approval from legal team
   - Add dependency to FOSSA license policy exceptions (requires approval)
4. Re-run release after fixing

### Release Fails: RC Verification

**Error**: `RC image not found in ECR`

**Cause**: RC testing not completed or failed

**Solution**:
1. Check RC workflow status: https://github.com/SolaceDev/rc-sam-community/actions
2. Wait for RC tests to complete
3. If RC tests failed, fix issues and re-run
4. If RC tests passed but image missing, verify ECR manually
5. Emergency option: Use `skip_rc_check: true` (requires justification)

### Release Fails: Prisma Cloud Scan

**Error**: Security checks fail due to Prisma Cloud vulnerabilities

**Cause**: Docker image has critical/high vulnerabilities

**Solution**:
1. Review Prisma Cloud report
2. Update base image or vulnerable dependencies
3. Rebuild Docker image
4. Re-run security checks

### FOSSA Scan Timeout

**Error**: FOSSA scan times out or hangs

**Cause**: Large number of dependencies or network issues

**Solution**:
1. Check FOSSA service status: https://status.fossa.com/
2. Re-run workflow (may be transient)
3. If persistent, contact FOSSA support

### Workflow Permission Errors

**Error**: `Resource not accessible by integration` or permission denied

**Cause**: Missing permissions in workflow

**Solution**:
1. Check workflow `permissions:` section
2. Ensure these are set:
   - `contents: write` (for git tags)
   - `pull-requests: write` (for PR comments)
   - `checks: write` (for status checks)
   - `statuses: write` (for commit status)
3. If using GitHub Apps, verify app permissions

## Additional Resources

- **FOSSA Dashboard**: https://app.fossa.com/projects/custom+SolaceLabs_solace-agent-mesh
- **PyPI Package**: https://pypi.org/project/solace-agent-mesh/
- **DockerHub**: https://hub.docker.com/r/solace/solace-agent-mesh
- **CI/CD Workflows**: `.github/workflows/`
- **Shareable Workflows**: https://github.com/SolaceDev/solace-public-workflows

For questions about the release process, contact the AI Team or create an issue in the repository.
