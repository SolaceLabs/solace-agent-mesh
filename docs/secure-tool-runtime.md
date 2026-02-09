# Secure Tool Runtime

The **Secure Tool Runtime (STR)** is SAM's execution environment for running tools in isolated containers. It enables agents to invoke arbitrary Python tools with process-level sandboxing, shared artifact access, and horizontal scalability — all through Solace event-driven messaging.

This document describes the current design as implemented. It is intended for architects, product owners, and engineers evaluating the system for production deployment.

## Table of Contents

1. [Introduction](#1-introduction)
2. [Architecture Overview](#2-architecture-overview)
3. [Container](#3-container)
4. [Broker Connectivity](#4-broker-connectivity)
5. [Topic Structure and Messaging Protocol](#5-topic-structure-and-messaging-protocol)
6. [Tool Manifest](#6-tool-manifest)
7. [Tool Invocation Lifecycle](#7-tool-invocation-lifecycle)
8. [Artifact Handling](#8-artifact-handling)
9. [Security Model](#9-security-model)
10. [Production Deployment](#10-production-deployment)
11. [Dev Mode](#11-dev-mode)
12. [Configuration Reference](#12-configuration-reference)
13. [Appendix](#13-appendix)

---

## 1. Introduction

### Problem

SAM agents need to execute tools — Python functions that perform actions like querying databases, processing files, or calling external APIs. Running these tools directly inside the agent process creates several problems:

- **Security**: A malicious or buggy tool can access the agent's memory, credentials, and broker connection.
- **Isolation**: Resource-hungry tools (CPU, memory) can starve the agent and other tools.
- **Dependency conflicts**: Tools may require conflicting Python packages or system libraries.
- **Multi-tenancy**: In a shared environment, tools from different tenants must not interfere with each other.

### Solution

The Secure Tool Runtime runs tools in a separate container, with each tool execution isolated in its own [bubblewrap (bwrap)](https://github.com/containers/bubblewrap) sandbox. Agents communicate with the STR through Solace broker topics — they never need to know where or how tools execute.

### Design Goals

- **Process isolation**: Each tool execution runs in its own bubblewrap sandbox with configurable resource limits.
- **Scalability**: Multiple STR instances can serve the same tools. The Solace broker handles load distribution.
- **Simplicity for tool authors**: Tools are plain Python functions that receive arguments and a context object. No broker, networking, or serialization code required.
- **Shared artifact access**: Both agents and the STR access the same artifact store (filesystem, S3, or GCS). Artifact content never flows through the broker.

---

## 2. Architecture Overview

### Component Diagram

```
┌──────────────┐         ┌──────────────────┐         ┌──────────────────────────────────┐
│   SAM Agent  │         │  Solace Broker   │         │   Secure Tool Runtime Container  │
│              │         │                  │         │                                  │
│  ┌─────────┐ │ publish │                  │ consume │  ┌──────────────────────┐        │
│  │SamRemote│─┼────────►│  invoke/{tool}   │────────►│  │SandboxWorkerComponent│        │
│  │Executor │ │         │                  │         │  └─────────┬────────────┘        │
│  └────┬────┘ │         │                  │         │            │                     │
│       │      │◄────────│  response/{agent}│◄────────│  ┌─────────▼──────────┐          │
│       │      │  consume│                  │  publish│  │   SandboxRunner    │          │
│       │      │         │  status/{agent}  │         │  └─────────┬──────────┘          │
│       │      │         └──────────────────┘         │            │                     │
│       │      │                                      │  ┌─────────▼──────────┐          │
│       │      │                                      │  │      bwrap         │          │
│       │      │                                      │  │  ┌──────────────┐  │          │
│       │      │                                      │  │  │  tool_runner │  │          │
│       │      │                                      │  │  │  ┌────────┐  │  │          │
│       │      │                                      │  │  │  │  Tool  │  │  │          │
│       │      │                                      │  │  │  └────────┘  │  │          │
│       │      │                                      │  │  └──────────────┘  │          │
│       │      │                                      │  └────────────────────┘          │
└───────┬──────┘                                      └────────────┬─────────────────────┘
        │                                                          │
        │             ┌─────────────────────┐                      │
        └─────────────┤  Artifact Service   ├──────────────────────┘
          load/save   │  (filesystem/S3/GCS)│          load/save
                      └─────────────────────┘
```

### Components

| Component | Location | Role |
|-----------|----------|------|
| **SamRemoteExecutor** | Agent process | Publishes invocation requests, waits for responses, handles retries |
| **SandboxWorkerApp** | STR container | Configures broker connections, subscriptions, and flow |
| **SandboxWorkerComponent** | STR container | Receives requests, resolves tools from manifest, orchestrates execution |
| **SandboxRunner** | STR container | Manages bwrap subprocesses, artifact pre-loading, result collection |
| **tool_runner** | Inside bwrap | Imports and calls the tool function with a context facade |
| **SandboxToolContextFacade** | Inside bwrap | Provides tools with status updates, artifact I/O, and configuration |

### Agent-Side (Brief)

Agents declare remote tools in their YAML configuration:

```yaml
tools:
  - tool_type: sam_remote
    tool_name: "process_file"
    tool_description: "Process a file and produce a summary"
    timeout_seconds: 30
    parameters:
      input_file:
        type: artifact
        description: "The file to process"
```

When the agent's LLM decides to call `process_file`, the `SamRemoteExecutor` handles all broker communication. The agent does not need to know the STR's location, container ID, or internal implementation.

---

## 3. Container

### Base Image and Build

The STR is built from `python:3.11-slim-bookworm`. Bubblewrap is installed from the Debian package repository:

```dockerfile
FROM python:3.11-slim-bookworm

# Install bubblewrap for sandboxing
RUN apt-get update && apt-get install -y --no-install-recommends bubblewrap procps curl

# Install SAM (without UI)
ENV SAM_SKIP_UI_BUILD=true
RUN pip install /app/sam-src/
```

The build context is the SAM repository root so that SAM source is available for installation. Unlike the previous nsjail-based approach, bwrap does not need to be compiled from source — it is a standard Debian package.

### Directory Structure

```
/app/
  entrypoint.py           # Container startup script

/tools/
  manifest.yaml           # Tool definitions (mounted at runtime)
  python/                 # Tool source code (mounted at runtime)
    my_tool.py

/sandbox/work/            # Per-execution work directories (ephemeral)
  {task_id}/
    input/                # Preloaded artifacts
    output/               # Tool-created artifacts
    runner_args.json      # Invocation parameters
    result.json           # Tool output
    status.pipe           # Named pipe for status messages

/usr/bin/bwrap            # bubblewrap binary (from Debian package)
```

Sandbox profiles (restrictive, standard, permissive) are defined as Python dicts in `sandbox_runner.py` rather than external configuration files.

### Startup Sequence

1. `entrypoint.py` reads configuration from environment variables
2. Builds broker config (dev or production mode)
3. Creates `SandboxWorkerApp` which:
   - Loads the tool manifest
   - Generates per-tool broker subscriptions
   - Initializes the artifact service
   - Initializes the `SandboxRunner`
4. Connects to the broker
5. Begins consuming messages

### Health Check

The Dockerfile includes a process-based health check:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python.*entrypoint" || exit 1
```

### Container Privileges

Bubblewrap uses Linux namespaces for process isolation. The bwrap command uses `--ro-bind / /` to bind-mount the entire root filesystem read-only (instead of `--proc /proc` or `--dev /dev` which require elevated privileges), so the container only needs `CAP_SYS_ADMIN` for namespace creation — `--privileged` is **not required**.

On Docker/Podman: `--cap-add=SYS_ADMIN`

On Kubernetes 1.33+ with user namespaces (`hostUsers: false`, `procMount: Unmasked`), even `SYS_ADMIN` can be dropped — bwrap only needs `SETFCAP`.

See [Section 9.1](#91-process-isolation-bubblewrap) and [Section 10.1](#101-kubernetes-deployment) for a detailed discussion of privilege requirements.

---

## 4. Broker Connectivity

### Production Mode (Solace PubSub+)

In production, the STR connects directly to a Solace PubSub+ broker:

```bash
SOLACE_HOST=broker.example.com:55555
SOLACE_VPN=production
SOLACE_USERNAME=str-service-account
SOLACE_PASSWORD=<secret>
```

**Queue naming**: `{namespace}/q/sandbox/{worker_id}`

Each STR instance gets its own queue based on its `worker_id`. Multiple instances with different `worker_id` values can serve the same tools — the broker distributes messages across subscribers.

**TLS support**: Optional client certificates for mTLS:

```bash
SOLACE_TRUST_STORE_PATH=/certs/ca.pem
SOLACE_CLIENT_CERT_PATH=/certs/client.pem
SOLACE_CLIENT_KEY_PATH=/certs/client-key.pem
```

**Reconnection**: Configurable retry count and delay:

```bash
SOLACE_RECONNECT_RETRIES=10     # default
SOLACE_RECONNECT_DELAY_MS=3000  # default
```

### Dev Mode (NetworkDevBroker)

For local development, the STR connects to SAM's in-process DevBroker over TCP:

```bash
DEV_BROKER_HOST=host.containers.internal
DEV_BROKER_PORT=55554
```

The DevBroker is a lightweight in-memory message router. It supports topic-based pub/sub but does not provide persistence, guaranteed delivery, or access control.

**Infinite retry**: In dev mode, `CONNECT_RETRIES` defaults to `0` (infinite) so the container keeps trying to connect as the developer starts and stops SAM.

### Connection Lifecycle

1. **Initial connection**: Retry with configurable delay until broker is available
2. **Subscription setup**: Subscribe to one topic per tool from the manifest, plus the discovery topic
3. **Message processing**: Consume invocation requests, publish responses and status updates
4. **Disconnection**: If the broker connection is lost, the container currently does not auto-reconnect (known limitation for dev mode)
5. **Graceful shutdown**: SIGTERM/SIGINT triggers `app.stop()` and clean exit

---

## 5. Topic Structure and Messaging Protocol

### Topic Hierarchy

All topics are namespaced under `{namespace}/a2a/v1/sam_remote_tool/`:

| Purpose | Topic Pattern | Example |
|---------|--------------|---------|
| **Invoke** (per tool) | `{ns}/a2a/v1/sam_remote_tool/invoke/{tool_name}` | `prod/a2a/v1/sam_remote_tool/invoke/process_file` |
| **Response** (per request) | `{ns}/a2a/v1/sam_remote_tool/response/{agent}/{corr_id}` | `prod/a2a/v1/sam_remote_tool/response/MyAgent/abc-123` |
| **Status** (per request) | `{ns}/a2a/v1/sam_remote_tool/status/{agent}/{corr_id}` | `prod/a2a/v1/sam_remote_tool/status/MyAgent/abc-123` |

**Design rationale**:
- **Tool name in invoke topic**: The STR subscribes per tool, so only tools declared in its manifest are received.
- **Agent name in response/status topics**: Agents subscribe with a wildcard (`{ns}/.../response/{agent}/>`) to receive all their responses.
- **Correlation ID in response/status topics**: Enables the agent to match responses to pending requests.

### Message Format

Messages follow JSON-RPC 2.0:

**Request** (published to invoke topic):

```json
{
  "jsonrpc": "2.0",
  "id": "e524ecb5-9497-4b1e-9072-11f90437d923",
  "method": "sam_remote_tool/invoke",
  "params": {
    "task_id": "e524ecb5-9497-4b1e-9072-11f90437d923",
    "tool_name": "process_file",
    "args": { "input_file": "data.csv" },
    "tool_config": {},
    "app_name": "MyAgent",
    "user_id": "user-42",
    "session_id": "web-session-abc123",
    "preloaded_artifacts": {},
    "artifact_references": {
      "input_file": { "filename": "data.csv", "version": 0 }
    },
    "timeout_seconds": 30,
    "sandbox_profile": "standard"
  }
}
```

**User properties** on the request message:

| Property | Value | Purpose |
|----------|-------|---------|
| `replyTo` | Response topic | Where to publish the result |
| `statusTo` | Status topic | Where to publish progress updates |
| `clientId` | Agent name | Identifies the requesting agent |
| `userId` | User ID | Identifies the end user |

**Success response** (published to `replyTo`):

```json
{
  "jsonrpc": "2.0",
  "id": "e524ecb5-9497-4b1e-9072-11f90437d923",
  "result": {
    "tool_result": { "status": "success", "word_count": 42 },
    "execution_time_ms": 150,
    "timed_out": false,
    "created_artifacts": [
      { "filename": "summary.txt", "version": 0, "mime_type": "text/plain", "size_bytes": 256 }
    ]
  }
}
```

**Error response**:

```json
{
  "jsonrpc": "2.0",
  "id": "e524ecb5-9497-4b1e-9072-11f90437d923",
  "error": {
    "code": "EXECUTION_ERROR",
    "message": "Tool raised ValueError: invalid input format"
  }
}
```

**Status notification** (published to `statusTo` during execution — JSON-RPC 2.0 notification, no `id`):

```json
{
  "jsonrpc": "2.0",
  "method": "sam_remote_tool/status",
  "params": {
    "task_id": "e524ecb5-9497-4b1e-9072-11f90437d923",
    "status_text": "Processing row 500 of 1000...",
    "timestamp": "2025-02-09T12:34:56.789Z"
  }
}
```

### Error Codes

| Code | Meaning | Retryable? |
|------|---------|------------|
| `SANDBOX_TIMEOUT` | Execution exceeded time limit | No |
| `SANDBOX_FAILED` | Sandbox (bwrap) process exited with error | No |
| `TOOL_NOT_AVAILABLE` | Tool not in manifest (stale subscription) | **Yes** (agent retries once) |
| `TOOL_NOT_FOUND` | Tool name not recognized | No |
| `IMPORT_ERROR` | Python module import failed | No |
| `EXECUTION_ERROR` | Tool raised an exception | No |
| `TOOL_ERROR` | Tool returned an error result | No |
| `ARTIFACT_ERROR` | Artifact loading or saving failed | No |
| `INVALID_REQUEST` | Request validation failed | No |
| `INTERNAL_ERROR` | Worker internal error | No |

---

## 6. Tool Manifest

### Format

The tool manifest is a YAML file that declares what tools the STR instance supports. Default location: `/tools/manifest.yaml`.

```yaml
version: 1

tools:
  echo_tool:
    runtime: python
    module: example_tools
    function: echo_tool
    description: "Echo back a message"

  execute_python:
    runtime: python
    module: example_tools
    function: execute_python
    timeout_seconds: 60
    sandbox_profile: restrictive

  data_processor:
    runtime: python
    package: sam-tool-data-processor
    version: ">=1.0,<2.0"
    module: sam_tool_data_processor
    function: process_data
    description: "Process data files"
    timeout_seconds: 600
    sandbox_profile: permissive
```

### Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `runtime` | No | `python` | Execution runtime (currently only `python`) |
| `module` | Yes | — | Python import path for the tool module |
| `function` | Yes | — | Function name to call |
| `package` | No | — | pip package name; auto-installed if missing |
| `version` | No | — | Version constraint for `package` (e.g., `">=1.0"`) |
| `description` | No | — | Human-readable description |
| `timeout_seconds` | No | 300 | Overrides default execution timeout |
| `sandbox_profile` | No | `standard` | Sandbox profile (`restrictive`, `standard`, `permissive`) |

### Manifest-Driven Subscriptions

On startup, the STR subscribes to one invoke topic per tool in the manifest:

```
ed_test/a2a/v1/sam_remote_tool/invoke/echo_tool
ed_test/a2a/v1/sam_remote_tool/invoke/execute_python
ed_test/a2a/v1/sam_remote_tool/invoke/data_processor
```

### Dynamic Reload

A background thread polls the manifest file's modification time every 2 seconds. When a change is detected, subscriptions are synchronized before any new requests arrive:

- **Tool added**: Subscribe to the new tool's invoke topic
- **Tool removed**: Unsubscribe from the removed tool's topic

Because subscription changes happen in the background rather than on the request path, incoming requests are not delayed by manifest reloads.

If a request arrives for a tool that was recently removed (stale subscription — race between poll and message delivery), the STR:
1. Unsubscribes from that tool's topic
2. Returns a `TOOL_NOT_AVAILABLE` error
3. The agent retries once after a 1-second delay (handles tool migration between STR instances)

### Package Auto-Installation

When a tool's manifest entry includes a `package` field, the STR checks if the package is importable on startup. If not, it runs:

```bash
uv pip install {package}{version_constraint}
```

Falls back to `pip install` if `uv` is not available. This allows tool manifests to declare dependencies that are automatically resolved at startup.

---

## 7. Tool Invocation Lifecycle

### End-to-End Flow

```
Agent                          Broker                         STR
  │                              │                              │
  │  1. Publish request          │                              │
  │─────────────────────────────►│                              │
  │                              │  2. Deliver to subscriber    │
  │                              │─────────────────────────────►│
  │                              │                              │ 3. Parse request
  │                              │                              │ 4. Resolve tool from manifest
  │                              │                              │ 5. Create work directory
  │                              │                              │ 6. Preload artifacts
  │                              │                              │ 7. Spawn bwrap
  │                              │                              │    ┌──────────────┐
  │                              │                              │    │  tool_runner  │
  │                              │  8. Status update            │    │  imports tool │
  │                              │◄─────────────────────────────│    │  calls func() │
  │  8. Status forwarded         │                              │    │              │
  │◄─────────────────────────────│                              │    └──────────────┘
  │                              │                              │ 9. Read result.json
  │                              │                              │ 10. Collect output artifacts
  │                              │ 11. Publish response         │
  │                              │◄─────────────────────────────│ 12. Clean up work directory
  │ 11. Response delivered       │                              │
  │◄─────────────────────────────│                              │
  │                              │                              │
```

**Detailed steps:**

1. **Agent publishes request** to `{ns}/a2a/v1/sam_remote_tool/invoke/{tool_name}` with `replyTo` and `statusTo` in user properties.

2. **STR receives the message** via its tool-specific subscription.

3. **Parse and validate** the `SandboxToolInvocationRequest` from the message payload.

4. **Resolve tool from manifest**: Look up `tool_name` to get `module`, `function`, and any overrides. If the tool is not found (stale subscription), return `TOOL_NOT_AVAILABLE` and unsubscribe.

5. **Create work directory**:
   ```
   /sandbox/work/{task_id}/
     input/          output/          runner_args.json
     status.pipe     result.json
   ```

6. **Preload artifacts** into `input/`:
   - **Artifact references**: Load from the shared artifact service using `app_name`, `user_id`, `session_id`
   - **Preloaded artifacts**: Write base64-decoded content directly

7. **Spawn bwrap process**:
   ```bash
   bwrap --die-with-parent --new-session --unshare-pid --unshare-ipc --unshare-uts \
     [--unshare-net]                          # restrictive profile only
     [--clearenv]                             # restrictive profile only
     --ro-bind / /                            # entire root filesystem read-only
     --tmpfs /tmp                             # writable tmp
     --bind {work_dir} {work_dir}             # writable work directory
     [--tmpfs /var]                           # writable var (permissive only)
     --setenv PYTHONPATH {tools_dir} --chdir {work_dir} \
     -- python -m solace_agent_mesh.sandbox.tool_runner {runner_args.json}
   ```
   The `--ro-bind / /` approach avoids `--proc /proc` and `--dev /dev` mounts that require elevated privileges beyond `CAP_SYS_ADMIN`. Resource limits (memory, CPU time, file size, open files) are enforced via `resource.setrlimit()` in a `preexec_fn` that runs before exec — since bwrap does not provide built-in resource control.

8. **Status updates**: The tool writes status messages to a named pipe (`status.pipe`). A background thread reads the pipe and publishes `SandboxStatusUpdate` messages to the `statusTo` topic.

9. **Read result**: After the bwrap process exits, the STR reads `result.json` from the work directory.

10. **Collect output artifacts**: Files in `output/` are saved to the artifact service and returned as `CreatedArtifact` metadata.

11. **Publish response** to the `replyTo` topic with the result or error.

12. **Clean up**: Delete the work directory.

### Timeout Handling

Three timeout layers provide defense in depth:

| Layer | Timeout | Purpose |
|-------|---------|---------|
| **setrlimit (RLIMIT_CPU)** | Profile's `rlimit_cpu_sec` | Hard kernel-enforced CPU time limit. SIGKILL on exceed. |
| **STR (SandboxRunner)** | `timeout_seconds + 5s` | Wall-clock timeout via `asyncio.wait_for()`. |
| **Agent (SamRemoteExecutor)** | `timeout_seconds + 10s` | Catches cases where the response is never published. |

If the tool times out, the response includes `timed_out: true` and error code `SANDBOX_TIMEOUT`.

### Concurrency Control

The `SandboxRunner` uses a semaphore to limit concurrent executions (default: 4, configurable via `SANDBOX_MAX_CONCURRENT`). Requests that exceed the limit wait until a slot becomes available.

---

## 8. Artifact Handling

### Design Principle

**Artifact content travels through shared storage, not through the broker.**

When an agent invokes a tool that takes an artifact parameter (e.g., a file upload), the artifact content is not serialized into the broker message. Instead:

1. The agent saves the artifact to the shared artifact service
2. The agent sends only a **reference** (filename + version) in the request
3. The STR loads the artifact from the same artifact service

This keeps broker messages small and avoids serialization overhead for large files.

### Flow

```
Agent                         Artifact Service                STR (inside bwrap)
  │                                 │                              │
  │  1. Save artifact               │                              │
  │────────────────────────────────►│                              │
  │                                 │                              │
  │  2. Send reference via broker   │                              │
  │─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─►│
  │                                 │                              │
  │                                 │  3. Load artifact            │
  │                                 │◄─────────────────────────────│
  │                                 │                              │
  │                                 │  4. File in input/ dir       │
  │                                 │─────────────────────────────►│
  │                                 │                              │ 5. Tool reads file
  │                                 │                              │ 6. Tool writes output
  │                                 │  7. Save output artifact     │
  │                                 │◄─────────────────────────────│
  │                                 │                              │
```

### Artifact Service Backends

| Backend | Config | Use Case |
|---------|--------|----------|
| **memory** | `ARTIFACT_SERVICE_TYPE=memory` | Testing only; artifacts lost on restart |
| **filesystem** | `ARTIFACT_SERVICE_TYPE=filesystem` | Single-node or shared filesystem (NFS, PVC) |
| **S3** | `ARTIFACT_SERVICE_TYPE=s3` | Cloud-native, multi-node deployments |
| **GCS** | `ARTIFACT_SERVICE_TYPE=gcs` | Google Cloud deployments |

### Storage Layout (Filesystem)

```
{base_path}/
  {scoped_app_name}/
    {user_id}/
      {session_id}/
        {filename}/
          0           # Version 0 data
          0.meta      # Version 0 metadata (JSON)
          1           # Version 1 data
          1.meta
      user/           # User-scoped artifacts (available across sessions)
        {filename}/
          ...
```

### Scoping

The `ScopedArtifactServiceWrapper` enforces artifact isolation:

- **Namespace scope** (default): `scoped_app_name` = `component.namespace`. All agents and STR instances in the same namespace share artifacts.
- **App scope**: `scoped_app_name` = `app_name`. Each agent has its own artifact partition.

Both the agent and the STR must use the **same namespace value** for artifact paths to align. The wrapper applies `os.path.basename()` to all path components to prevent directory traversal.

### Preloaded vs. Referenced Artifacts

| Mechanism | When Used | How It Works |
|-----------|-----------|--------------|
| **ArtifactReference** | Production (default) | Only filename + version sent in request. STR loads from shared store. |
| **PreloadedArtifact** | Testing, or when shared storage is unavailable | Base64-encoded content sent in the broker message. |

### Output Artifacts

Tools create output artifacts by writing files to the `output/` directory via `ctx.save_artifact()`. After execution:

1. The STR scans the `output/` directory
2. Each file is saved to the artifact service (scoped by `app_name`, `user_id`, `session_id`)
3. Metadata (`CreatedArtifact`) is included in the response

---

## 9. Security Model

### 9.1 Process Isolation (bubblewrap)

Each tool execution runs inside a [bubblewrap (bwrap)](https://github.com/containers/bubblewrap) sandbox — a lightweight Linux namespace-based isolation tool used by Flatpak. Bwrap creates a new PID, mount, IPC, UTS, and (optionally) network namespace for each execution. Resource limits (memory, CPU time, file size, open files) are enforced via `resource.setrlimit()` in a `preexec_fn`.

Three security profiles are available:

| Property | Restrictive | Standard | Permissive |
|----------|:-----------:|:--------:|:----------:|
| **Virtual memory** | 512 MB | 1 GB | 4 GB |
| **CPU time** | 60s | 300s (5 min) | 600s (10 min) |
| **Max CPUs** | 1 | 2 | 4 |
| **Max file size** | 64 MB | 256 MB | 1 GB |
| **Open files** | 128 | 512 | 1024 |
| **Network** | **Isolated** | Host | Host |
| **Environment vars** | Allowlist only | Inherited | Inherited |
| **DNS resolution** | No | Yes | Yes |
| **HTTPS (SSL certs)** | No | Yes | Yes |
| **Filesystem access** | Minimal | Standard | Extensive |

**When to use each profile:**

- **Restrictive**: Untrusted code execution, pure computation, no external dependencies. Example: `execute_python` for user-submitted code.
- **Standard**: Most tools. Needs network for API calls, DNS for hostname resolution, SSL certs for HTTPS.
- **Permissive**: Trusted tools that need extensive system access. Example: tools that read system configuration or run subprocesses.

### 9.2 Filesystem Isolation

All sandbox profiles use `--ro-bind / /` as the base filesystem mount, which makes the entire container filesystem visible read-only inside the bwrap sandbox. Writable areas are layered on top:

**Read-only** (tools cannot modify):
- Everything inherited from `--ro-bind / /` — system libraries, Python installation, `/proc`, `/dev`, `/etc`, tool source code
- This approach avoids `--proc` and `--dev` mounts that require elevated container privileges

**Read-write** (isolated per execution):
- `/sandbox/work/{task_id}/` — Work directory with `input/`, `output/`, and temp files
- `/tmp` — tmpfs (memory-backed, not persisted to disk)
- `/var` — tmpfs (permissive profile only, for logs and runtime)

**Isolation boundaries**:
- **PID namespace** (`--unshare-pid`): Tools cannot see or signal processes outside the sandbox
- **IPC namespace** (`--unshare-ipc`): No shared memory or semaphore access
- **Network namespace** (`--unshare-net`, restrictive only): No network interfaces
- **Environment** (`--clearenv`, restrictive only): Only explicitly set variables are visible

**Per-execution lifecycle**: The work directory is created before execution and deleted immediately after. No state persists between tool executions.

### 9.3 Multi-Tenancy and Data Isolation

Artifact access is scoped by three levels:

```
{base_path}/{namespace}/{user_id}/{session_id}/{filename}/{version}
```

- **Namespace**: Partitions data between organizational tenants
- **User**: Partitions data between users within a tenant
- **Session**: Partitions data between conversations/tasks for a user

Path traversal is prevented by applying `os.path.basename()` to all path components before constructing file paths.

**Current trust model**: The STR trusts the `user_id` and `session_id` values provided in the invocation request. There is no independent verification that the requesting agent is authorized to access artifacts for a given user or session. See [Section 9.6](#96-current-limitations-and-gaps).

### 9.4 Network Security

- **Restrictive profile**: Full network isolation via `--unshare-net`. The tool runs in its own empty network namespace with no interfaces. No outbound connections possible.
- **Standard/Permissive profiles**: Inherit the host network namespace. Tools can make outbound HTTP/HTTPS calls (needed for API tools).
- **Broker authentication**: Production mode supports username/password and optional mTLS.

### 9.5 Tool Code Trust

Tools are loaded from the `/tools/python` directory, which is mounted into the container at runtime. The trust boundary is:

- Whoever controls the container image controls the system libraries
- Whoever controls the `/tools/` mount controls the tool code
- The manifest file at `/tools/manifest.yaml` determines which tools are available

There is currently **no code signing or hash verification**. If the manifest or tool source files are tampered with, the STR will execute the modified code.

### 9.6 Current Limitations and Gaps

The following are known gaps in the current implementation. They are listed here for architectural review.

| Gap | Risk | Mitigation Path |
|-----|------|-----------------|
| **Container privilege requirements** | Bwrap needs `CAP_SYS_ADMIN` for namespace creation on Docker/Podman | Use K8s 1.33+ `hostUsers: false` + `procMount: Unmasked` to drop to `SETFCAP` only (see [Section 10.1](#101-kubernetes-deployment)) |
| **No request signing** | A compromised or rogue broker subscriber could forge invocation requests with arbitrary `user_id`/`session_id` | Add HMAC-SHA256 signature over request payload using shared secret |
| **No per-user rate limiting** | A single user could monopolize STR resources | Track invocations per `user_id` per time window; reject above threshold |
| **No artifact access audit trail** | No record of which user accessed which artifacts | Append-only audit log of artifact operations |
| **Environment variable leakage** | Standard/permissive profiles inherit all container env vars, potentially exposing secrets | Use restrictive profile for untrusted tools; inject secrets via `tool_config` instead of env vars |
| **No payload size limits** | Oversized request payloads could exhaust memory | Add `max_payload_size` validation in executor |
| **No tool code verification** | Modified tool source executes without detection | Store code hashes in manifest; verify before loading |
| **No auto-reconnect (dev mode)** | NetworkDevBroker does not reconnect after connection loss | Add reconnection logic to NetworkDevBroker |

---

## 10. Production Deployment

### 10.1 Kubernetes Deployment

#### Container Privileges

Bubblewrap requires the ability to create Linux namespaces. Kubernetes 1.33+ introduced user namespace support that dramatically simplifies this.

**Option A: Kubernetes 1.33+ user namespaces (recommended)**

```yaml
spec:
  hostUsers: false
  containers:
  - name: sandbox-worker
    securityContext:
      procMount: Unmasked
      capabilities:
        add:
          - SETFCAP          # only capability needed
```

With `hostUsers: false`, the container runs in its own user namespace. Bwrap can then create child namespaces (PID, mount, IPC, UTS, net) without any elevated host capabilities. The `procMount: Unmasked` setting allows bwrap to mount `/proc` inside its namespace.

This is the most secure option — even a container escape results in an unprivileged host user.

**Option B: Minimal capabilities (older Kubernetes)**

```yaml
securityContext:
  capabilities:
    add:
      - SYS_ADMIN      # namespace creation
      - NET_ADMIN       # network namespace (restrictive profile)
      - SYS_CHROOT
```

Combined with a custom seccomp profile that allows namespace syscalls (`clone`, `unshare`, `mount`) but blocks dangerous ones (`bpf`, `perf_event_open`).

**Option C: `--privileged` (development only)**

```yaml
securityContext:
  privileged: true
```

Grants all Linux capabilities. Only for local development. Not recommended for any environment accessible to untrusted users.

#### Artifact Storage

| Environment | Recommended Backend | Notes |
|-------------|-------------------|-------|
| Single node | Filesystem with hostPath | Simple but not scalable |
| Multi-node cluster | S3 or GCS | Cloud-native, no shared filesystem needed |
| On-premise cluster | Filesystem with NFS/PVC | Shared storage across nodes |

The artifact service must be accessible to both agent pods and STR pods with consistent path/bucket configuration.

#### Pod Resources

Consider that the STR pod's resource limits must account for multiple concurrent bwrap processes:

```yaml
resources:
  requests:
    cpu: "2"
    memory: "4Gi"
  limits:
    cpu: "4"
    memory: "8Gi"
```

These are in addition to the per-execution `setrlimit()` limits. A standard profile tool using 1 GB RAM inside bwrap, with 4 concurrent executions, requires at least 4 GB for tool processes plus overhead for the STR itself.

### 10.2 SaaS / Multi-Tenant Considerations

- **Namespace isolation**: Use separate SAM namespaces per tenant. Each namespace has its own topic prefix, artifact partition, and can have dedicated STR instances.
- **Broker access control**: Solace ACLs can restrict which topics each client can publish/subscribe to, preventing cross-tenant message access.
- **Noisy neighbor prevention**: `setrlimit()` resource limits (CPU, memory, file size) prevent a single tool execution from affecting others. The `max_concurrent_executions` semaphore limits total load per STR instance.
- **Secret management**: Tool-specific secrets (API keys, credentials) should be injected via `tool_config` in the invocation request, not via container environment variables. In Kubernetes, use Secrets or Vault integration.

### 10.3 Scaling

**Horizontal scaling**: Deploy multiple STR pods. Since each pod subscribes to the same tool topics, the Solace broker distributes invocations across pods using exclusive queue subscriptions.

**Tool-specific instances**: Different STR instances can serve different tool sets by mounting different manifests. For example:
- General-purpose STR instances with standard tools
- GPU-enabled instances for ML tools (with permissive profile and GPU passthrough)
- High-memory instances for data processing tools

**Key scaling parameters**:

| Parameter | Default | Effect |
|-----------|---------|--------|
| Number of STR pods | 1 | Horizontal throughput |
| `SANDBOX_MAX_CONCURRENT` | 4 | Concurrent executions per pod |
| Sandbox profile | standard | Resource limits per execution |

### 10.4 Monitoring and Observability

**Logs**: The STR uses Python structured logging to stdout. Key events:
- Tool invocation received (tool name, task ID)
- Execution started/completed (execution time, artifact count)
- Errors (with error codes and details)
- Manifest changes (tools added/removed)

**Metrics to track**:
- Invocations per second (per tool)
- Execution time distribution (p50, p95, p99)
- Timeout rate
- Error rate by code
- Concurrent execution count vs. limit
- Artifact service latency

**Health check**: Process-based health check is included in the Dockerfile. For Kubernetes, add liveness and readiness probes:

```yaml
livenessProbe:
  exec:
    command: ["pgrep", "-f", "python.*entrypoint"]
  periodSeconds: 30
readyinessProbe:
  # Could check broker connection status
  exec:
    command: ["pgrep", "-f", "python.*entrypoint"]
  periodSeconds: 10
```

---

## 11. Dev Mode

### Overview

Dev mode enables rapid iteration without a production Solace broker. The STR container connects over TCP to SAM's in-process DevBroker, which provides lightweight topic-based messaging.

### Setup

1. **Start SAM** with `SOLACE_DEV_MODE=true` (enables the DevBroker network server)

2. **Start the STR container**:
   ```bash
   podman run --rm --cap-add=SYS_ADMIN \
     --name sam-sandbox-worker \
     -e SAM_NAMESPACE=ed_test/ \
     -e DEV_BROKER_HOST=host.containers.internal \
     -e DEV_BROKER_PORT=55554 \
     -e ARTIFACT_SERVICE_TYPE=filesystem \
     -e ARTIFACT_BASE_PATH=/tmp/samv2 \
     -v /path/to/tools/manifest.yaml:/tools/manifest.yaml:ro \
     -v /path/to/tools/python:/tools/python:ro \
     -v /tmp/samv2:/tmp/samv2 \
     localhost/sam-sandbox-worker:latest
   ```

### Source Mounting for Rapid Iteration

During development, mount SAM and SAC source directly into the container to avoid rebuilding the image:

```bash
-v ./src/solace_agent_mesh:/usr/local/lib/python3.11/site-packages/solace_agent_mesh:ro
-v ../solace-ai-connector/src/solace_ai_connector:/usr/local/lib/python3.11/site-packages/solace_ai_connector:ro
-v ./sandbox-worker/entrypoint.py:/app/entrypoint.py:ro
```

Note: The container uses Python 3.11; the host may use a different version.

### Isolated Testing with sandbox_test.py

The `examples/sandbox/sandbox_test.py` script provides a standalone test harness that creates its own DevBroker, connects to the STR, and sends invocations directly — without running the full SAM system:

```bash
# Simple echo test
python sandbox_test.py --wait-for-worker invoke --tool echo_tool --args '{"message": "hello"}'

# Artifact test
python sandbox_test.py --wait-for-worker invoke \
  --tool process_file \
  --args '{"input_file": "test_input.txt"}' \
  --artifact input_file=tools/test_input.txt
```

### Common Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Container never receives messages | Namespace mismatch between SAM and container | Ensure `SAM_NAMESPACE` matches exactly (including trailing slash if present) |
| Artifact not found | Namespace mismatch causes different filesystem paths | Same fix — namespaces must match character-for-character |
| Broken pipe errors after SAM restart | NetworkDevBroker does not auto-reconnect | Restart the container after restarting SAM |
| Port conflict | Previous test still holds the DevBroker port | Wait a few seconds or use a different port |
| `session_id: "unknown"` in requests | Agent-side context extraction failed | Ensure `get_original_session_id()` is used (reads `invocation_context.session.id`) |

---

## 12. Configuration Reference

### Environment Variables

#### Required

| Variable | Description |
|----------|-------------|
| `SAM_NAMESPACE` | SAM namespace for topic routing and artifact scoping. Must match the agent's namespace exactly. |

#### Broker — Dev Mode

| Variable | Default | Description |
|----------|---------|-------------|
| `DEV_BROKER_HOST` | — | Hostname of SAM's DevBroker (enables dev mode when set) |
| `DEV_BROKER_PORT` | `55555` | DevBroker TCP port |
| `CONNECT_RETRIES` | `0` | Max connection attempts (`0` = infinite) |
| `CONNECT_RETRY_DELAY_MS` | `3000` | Delay between connection attempts |

#### Broker — Production Mode

| Variable | Default | Description |
|----------|---------|-------------|
| `SOLACE_HOST` | — | Solace broker `host:port` (required in production) |
| `SOLACE_VPN` | `default` | Solace VPN name |
| `SOLACE_USERNAME` | `admin` | Broker username |
| `SOLACE_PASSWORD` | `admin` | Broker password |
| `SOLACE_TRUST_STORE_PATH` | — | TLS CA certificate path |
| `SOLACE_CLIENT_CERT_PATH` | — | mTLS client certificate path |
| `SOLACE_CLIENT_KEY_PATH` | — | mTLS client key path |
| `SOLACE_RECONNECT_RETRIES` | `10` | Reconnection attempts |
| `SOLACE_RECONNECT_DELAY_MS` | `3000` | Delay between reconnection attempts |

#### Worker Identity

| Variable | Default | Description |
|----------|---------|-------------|
| `SAM_WORKER_ID` | `sandbox-worker-001` | Unique identifier for this STR instance |

#### Tool Manifest

| Variable | Default | Description |
|----------|---------|-------------|
| `MANIFEST_PATH` | `/tools/manifest.yaml` | Path to the tool manifest file |
| `TOOLS_PYTHON_DIR` | `/tools/python` | Directory containing tool Python modules |
| `DEFAULT_TIMEOUT_SECONDS` | `300` | Default tool execution timeout |

#### Sandbox (bubblewrap)

| Variable | Default | Description |
|----------|---------|-------------|
| `SANDBOX_BWRAP_BIN` | `/usr/bin/bwrap` | Path to bubblewrap binary |
| `SANDBOX_PYTHON_BIN` | `/usr/bin/python3` | Python binary for tool execution |
| `SANDBOX_WORK_DIR` | `/sandbox/work` | Base directory for per-execution work dirs |
| `SANDBOX_DEFAULT_PROFILE` | `standard` | Default sandbox profile (restrictive, standard, permissive) |
| `SANDBOX_MAX_CONCURRENT` | `4` | Maximum concurrent tool executions |

#### Artifact Service

| Variable | Default | Description |
|----------|---------|-------------|
| `ARTIFACT_SERVICE_TYPE` | `memory` | Backend: `memory`, `filesystem`, `s3`, `gcs` |
| `ARTIFACT_BASE_PATH` | `/sam/artifacts` | Base path (filesystem backend) |
| `ARTIFACT_S3_BUCKET` | — | S3 bucket name (required for s3 backend) |
| `ARTIFACT_S3_REGION` | `us-east-1` | S3 region |
| `ARTIFACT_GCS_BUCKET` | — | GCS bucket name (required for gcs backend) |

### Manifest YAML Schema

```yaml
version: 1                      # Schema version (required)

tools:
  {tool_name}:                   # Unique tool identifier
    runtime: python              # Runtime (default: python)
    module: {import_path}        # Python import path (required)
    function: {function_name}    # Function to call (required)
    package: {pip_package}       # Auto-install if missing
    version: "{constraint}"      # Version constraint for package
    description: "{text}"        # Human-readable description
    timeout_seconds: 300         # Execution timeout override
    sandbox_profile: standard    # Sandbox profile override
```

---

## 13. Appendix

### A. Sequence Diagram — Successful Invocation

```
Agent           Executor        Broker          STR             bwrap           ArtifactSvc
  │                │               │              │                │                │
  │ call tool      │               │              │                │                │
  │───────────────►│               │              │                │                │
  │                │ gen corr_id   │              │                │                │
  │                │ extract refs  │              │                │                │
  │                │──publish─────►│              │                │                │
  │                │               │──deliver────►│                │                │
  │                │               │              │ resolve tool   │                │
  │                │               │              │ setup work dir │                │
  │                │               │              │────load artifact───────────────►│
  │                │               │              │◄───artifact data────────────────│
  │                │               │              │──spawn────────►│                │
  │                │               │              │                │ import module  │
  │                │               │              │                │ call func()    │
  │                │  status       │◄──status─────│◄──pipe─────────│                │
  │◄──status───────│               │              │                │ write result   │
  │                │               │              │◄──exit─────────│                │
  │                │               │              │ read result    │                │
  │                │               │              │ collect output │                │
  │                │               │              │────save artifact───────────────►│
  │                │               │◄──response───│                │                │
  │                │◄──response────│              │ cleanup        │                │
  │◄──result───────│               │              │                │                │
```

### B. Example Tool Implementation

```python
"""Example tool that runs inside the Secure Tool Runtime."""

from typing import Any, Dict


def process_file(ctx: Any, input_file: str) -> Dict[str, Any]:
    """
    Process an input artifact and produce a summary.

    Args:
        ctx: SandboxToolContextFacade — provides status, artifacts, config
        input_file: Filename of the input artifact
    """
    # Send a status update to the user
    ctx.send_status("Loading input file...")

    # Load the artifact content (reads from /sandbox/work/{task_id}/input/)
    content = ctx.load_artifact_text("input_file")
    if content is None:
        return {"status": "error", "error": "Could not load input artifact"}

    ctx.send_status("Analyzing content...")

    # Process the content
    lines = content.split("\n")
    words = content.split()

    # Create an output artifact
    summary = f"Lines: {len(lines)}\nWords: {len(words)}\nChars: {len(content)}"
    ctx.save_artifact("summary.txt", summary.encode("utf-8"))

    return {
        "status": "success",
        "statistics": {
            "line_count": len(lines),
            "word_count": len(words),
            "char_count": len(content),
        },
        "output_artifact": "summary.txt",
    }
```

### C. SandboxToolContextFacade API

| Method | Description |
|--------|-------------|
| `send_status(message: str) -> bool` | Send a status update to the user (via named pipe) |
| `load_artifact(param_name: str) -> Optional[bytes]` | Load a preloaded artifact as bytes |
| `load_artifact_text(param_name: str) -> Optional[str]` | Load a preloaded artifact as text |
| `save_artifact(filename: str, content: bytes)` | Save an output artifact |
| `save_artifact_text(filename: str, content: str)` | Save a text output artifact |
| `list_artifacts() -> Dict[str, str]` | List available input artifacts |
| `list_output_artifacts() -> list[str]` | List created output artifacts |
| `get_config(key: str, default=None) -> Any` | Get tool configuration value |
| `user_id: str` | User ID from the invocation context |
| `session_id: str` | Session ID from the invocation context |

### D. Error Code Reference

| Code | Constant | Description |
|------|----------|-------------|
| `SANDBOX_TIMEOUT` | `SandboxErrorCodes.TIMEOUT` | Execution exceeded the configured time limit |
| `SANDBOX_FAILED` | `SandboxErrorCodes.SANDBOX_FAILED` | Sandbox (bwrap) process exited with a non-zero code |
| `TOOL_NOT_FOUND` | `SandboxErrorCodes.TOOL_NOT_FOUND` | Tool name not recognized |
| `TOOL_NOT_AVAILABLE` | `SandboxErrorCodes.TOOL_NOT_AVAILABLE` | Tool removed from manifest (retryable) |
| `IMPORT_ERROR` | `SandboxErrorCodes.IMPORT_ERROR` | Python module import failed |
| `EXECUTION_ERROR` | `SandboxErrorCodes.EXECUTION_ERROR` | Tool raised an unhandled exception |
| `TOOL_ERROR` | `SandboxErrorCodes.TOOL_ERROR` | Tool returned an error result |
| `ARTIFACT_ERROR` | `SandboxErrorCodes.ARTIFACT_ERROR` | Artifact loading or saving failed |
| `INVALID_REQUEST` | `SandboxErrorCodes.INVALID_REQUEST` | Request failed validation |
| `INTERNAL_ERROR` | `SandboxErrorCodes.INTERNAL_ERROR` | Unexpected worker internal error |
q