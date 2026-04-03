#!/usr/bin/env python3
"""Propagate RC commit status from source SHA to release PR SHA."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request


def log(message: str) -> None:
    print(message, flush=True)


def write_output(name: str, value: str) -> None:
    output_file = os.getenv("GITHUB_OUTPUT")
    if not output_file:
        return
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(f"{name}={value}\n")


def github_request(method: str, path: str, token: str, data: dict | None = None) -> dict:
    url = f"https://api.github.com{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "release-pr-rc-check",
    }
    payload = None
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"{method} {path} failed ({exc.code}): {body}") from exc


def get_latest_status(repo: str, commit_sha: str, context_name: str, token: str) -> dict | None:
    data = github_request("GET", f"/repos/{repo}/commits/{commit_sha}/status", token)
    statuses = data.get("statuses", [])
    for status in statuses:
        if status.get("context") == context_name:
            return status
    return None


def post_status(
    repo: str,
    target_commit_sha: str,
    state: str,
    context_name: str,
    description: str,
    target_url: str | None,
    token: str,
) -> None:
    clean_description = description.strip()
    if len(clean_description) > 140:
        clean_description = clean_description[:137] + "..."

    payload = {
        "state": state,
        "context": context_name,
        "description": clean_description or "RC status update",
    }
    if target_url:
        payload["target_url"] = target_url

    github_request(
        "POST",
        f"/repos/{repo}/statuses/{target_commit_sha}",
        token,
        data=payload,
    )


def main() -> int:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    source_commit_sha = os.getenv("SOURCE_COMMIT_SHA", "").strip()
    target_commit_sha = os.getenv("TARGET_COMMIT_SHA", "").strip()
    status_context = os.getenv("STATUS_CONTEXT", "RC / Integration Tests (Community)").strip()
    propagated_context = os.getenv(
        "PROPAGATED_CONTEXT", "RC / Integration Tests (Community) [Release PR]"
    ).strip()
    poll_interval_seconds = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
    max_attempts = int(os.getenv("MAX_ATTEMPTS", "75"))

    if not token or not repo or not source_commit_sha or not target_commit_sha:
        log("Missing required inputs: github token, repository, source SHA, or target SHA.")
        return 1

    write_output("source_commit_sha", source_commit_sha)
    write_output("target_commit_sha", target_commit_sha)
    write_output("propagated_context", propagated_context)

    for attempt in range(1, max_attempts + 1):
        status = get_latest_status(repo, source_commit_sha, status_context, token)
        if not status:
            description = (
                f"Waiting for '{status_context}' to appear on source commit "
                f"{source_commit_sha[:10]}"
            )
            post_status(
                repo,
                target_commit_sha,
                "pending",
                propagated_context,
                description,
                None,
                token,
            )
            log(f"[{attempt}/{max_attempts}] RC status not found on source commit.")
        else:
            source_state = status.get("state", "error")
            source_description = status.get("description") or f"RC status is {source_state}"
            source_target_url = status.get("target_url")

            if source_state == "pending":
                post_status(
                    repo,
                    target_commit_sha,
                    "pending",
                    propagated_context,
                    source_description,
                    source_target_url,
                    token,
                )
                log(f"[{attempt}/{max_attempts}] RC status is pending.")
            elif source_state in {"success", "failure", "error"}:
                post_status(
                    repo,
                    target_commit_sha,
                    source_state,
                    propagated_context,
                    source_description,
                    source_target_url,
                    token,
                )
                write_output("rc_state", source_state)
                log(f"RC status resolved as '{source_state}'.")
                return 0 if source_state == "success" else 1
            else:
                post_status(
                    repo,
                    target_commit_sha,
                    "pending",
                    propagated_context,
                    f"Unexpected source state '{source_state}', waiting...",
                    source_target_url,
                    token,
                )
                log(f"[{attempt}/{max_attempts}] Unexpected RC state: {source_state}")

        if attempt < max_attempts:
            time.sleep(poll_interval_seconds)

    timeout_description = (
        f"Timed out waiting for '{status_context}' on source commit {source_commit_sha[:10]}"
    )
    post_status(
        repo,
        target_commit_sha,
        "error",
        propagated_context,
        timeout_description,
        None,
        token,
    )
    write_output("rc_state", "timeout")
    log(timeout_description)
    return 1


if __name__ == "__main__":
    sys.exit(main())
