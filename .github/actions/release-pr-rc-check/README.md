# Release PR RC Check Action

This action propagates RC status from a source commit (typically `main` head SHA)
to a release-please PR commit, while polling until the source RC status resolves.

## What it does

1. Reads a status context from `source_commit_sha` (default context:
   `RC / Integration Tests (Community)`).
2. Writes a pending status to `target_commit_sha` using `propagated_context` while
   the source status is missing or pending.
3. Continues polling until the source status resolves to `success`, `failure`, or
   `error`.
4. Publishes the same final state onto `target_commit_sha`.
5. Exits with failure for non-success final states or timeout.

## Inputs

- `github_token` (required): token with status read/write permissions.
- `source_commit_sha` (required): SHA to monitor for RC status.
- `target_commit_sha` (required): SHA to publish propagated status to.
- `status_context` (optional): source context to monitor.
  - default: `RC / Integration Tests (Community)`
- `propagated_context` (optional): context name to publish on target SHA.
  - default: `RC / Integration Tests (Community) [Release PR]`
- `poll_interval_seconds` (optional): polling interval in seconds.
  - default: `60`
- `max_attempts` (optional): max polling attempts before timeout.
  - default: `75`

## Outputs

- `rc_state`: final state from source (`success|failure|error|timeout`)
- `propagated_context`: context published on target SHA
- `source_commit_sha`: source SHA monitored
- `target_commit_sha`: target SHA updated

## Example

```yaml
- name: Propagate RC status from main commit to release PR commit
  uses: ./.github/actions/release-pr-rc-check
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    source_commit_sha: ${{ github.event.pull_request.base.sha }}
    target_commit_sha: ${{ github.event.pull_request.head.sha }}
    status_context: RC / Integration Tests (Community)
    propagated_context: RC / Integration Tests (Community) [Release PR]
    poll_interval_seconds: "60"
    max_attempts: "75"
```
