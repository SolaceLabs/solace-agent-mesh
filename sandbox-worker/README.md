# SAM Sandbox Worker

The sandbox worker executes Python tools in a sandboxed environment using nsjail inside a container. It communicates with SAM agents via Solace broker.

This implementation supports both **Podman** and **Docker** with automatic detection.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ SAM Agent (Host)                                                │
│   └─→ SandboxedPythonExecutor                                   │
│         ├─ Pre-loads artifacts                                  │
│         ├─ Publishes invocation to Solace                       │
│         └─ Waits for response (with timeout)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ Solace Broker
┌─────────────────────────────────────────────────────────────────┐
│ Container (Podman/Docker)                                       │
│   └─→ SandboxWorker                                             │
│         ├─ Subscribes to invocation topics                      │
│         ├─ Spawns nsjail per tool invocation                    │
│         │     └─→ Python subprocess executes tool               │
│         ├─ Forwards status messages to Solace                   │
│         └─ Publishes result to Solace                           │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Using the Helper Scripts (Recommended)

The helper scripts automatically detect whether you have `podman` or `docker` installed.

```bash
# Build the container image
./build.sh

# Run the container
SAM_NAMESPACE=myorg/dev \
SOLACE_HOST=host.containers.internal:55554 \
./run.sh
```

### Manual Commands

If you prefer to run commands directly:

```bash
# Detect your container runtime
CONTAINER_CMD=$(command -v podman || command -v docker)

# Build
$CONTAINER_CMD build -t sam-sandbox-worker .

# Run
$CONTAINER_CMD run -d --privileged \
  --name sandbox-worker \
  -e SAM_NAMESPACE=myorg/dev \
  -e SOLACE_HOST=host.containers.internal:55554 \
  -e SOLACE_VPN=default \
  -e SOLACE_USERNAME=admin \
  -e SOLACE_PASSWORD=admin \
  sam-sandbox-worker
```

## Building

```bash
# Using helper script (auto-detects podman/docker)
./build.sh

# With custom tag
./build.sh my-registry/sam-sandbox-worker:v1

# Manual - Podman
podman build -t sam-sandbox-worker .

# Manual - Docker
docker build -t sam-sandbox-worker .
```

## Running

The container requires privileged mode for nsjail to work (it uses Linux namespaces).

### Basic Usage

```bash
# Using helper script
SAM_NAMESPACE=myorg/dev \
SOLACE_HOST=host.containers.internal:55554 \
./run.sh

# Manual - Podman
podman run -d --privileged \
  --name sandbox-worker \
  -e SAM_NAMESPACE=myorg/dev \
  -e SOLACE_HOST=host.containers.internal:55554 \
  -e SOLACE_VPN=default \
  -e SOLACE_USERNAME=admin \
  -e SOLACE_PASSWORD=admin \
  sam-sandbox-worker

# Manual - Docker
docker run -d --privileged \
  --name sandbox-worker \
  -e SAM_NAMESPACE=myorg/dev \
  -e SOLACE_HOST=host.containers.internal:55554 \
  -e SOLACE_VPN=default \
  -e SOLACE_USERNAME=admin \
  -e SOLACE_PASSWORD=admin \
  sam-sandbox-worker
```

### With Filesystem Artifact Service

```bash
# Using helper script
SAM_NAMESPACE=myorg/dev \
SOLACE_HOST=host.containers.internal:55554 \
ARTIFACT_SERVICE_TYPE=filesystem \
ARTIFACT_BASE_PATH=/sam/artifacts \
ARTIFACT_MOUNT=/path/to/artifacts:/sam/artifacts:rw \
./run.sh

# Manual
podman run -d --privileged \
  --name sandbox-worker \
  -v /path/to/artifacts:/sam/artifacts:rw \
  -e SAM_NAMESPACE=myorg/dev \
  -e SOLACE_HOST=host.containers.internal:55554 \
  -e SOLACE_VPN=default \
  -e SOLACE_USERNAME=admin \
  -e SOLACE_PASSWORD=admin \
  -e ARTIFACT_SERVICE_TYPE=filesystem \
  -e ARTIFACT_BASE_PATH=/sam/artifacts \
  sam-sandbox-worker
```

### With S3 Artifact Service

```bash
podman run -d --privileged \
  --name sandbox-worker \
  -e SAM_NAMESPACE=myorg/dev \
  -e SOLACE_HOST=broker.example.com:55554 \
  -e SOLACE_VPN=default \
  -e SOLACE_USERNAME=admin \
  -e SOLACE_PASSWORD=admin \
  -e ARTIFACT_SERVICE_TYPE=s3 \
  -e ARTIFACT_S3_BUCKET=my-artifacts \
  -e ARTIFACT_S3_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=... \
  -e AWS_SECRET_ACCESS_KEY=... \
  sam-sandbox-worker
```

## Configuration

All configuration is via environment variables:

### Required

| Variable | Description |
|----------|-------------|
| `SAM_NAMESPACE` | SAM namespace (e.g., `myorg/dev`) |
| `SOLACE_HOST` | Solace broker host:port |

### Optional - Broker

| Variable | Default | Description |
|----------|---------|-------------|
| `SOLACE_VPN` | `default` | Solace VPN name |
| `SOLACE_USERNAME` | `admin` | Solace username |
| `SOLACE_PASSWORD` | `admin` | Solace password |
| `SOLACE_TRUST_STORE_PATH` | - | Path to TLS trust store |
| `SOLACE_CLIENT_CERT_PATH` | - | Path to client certificate |
| `SOLACE_CLIENT_KEY_PATH` | - | Path to client key |
| `SOLACE_RECONNECT_RETRIES` | `10` | Number of reconnect attempts |
| `SOLACE_RECONNECT_DELAY_MS` | `3000` | Delay between reconnects (ms) |

### Optional - Worker

| Variable | Default | Description |
|----------|---------|-------------|
| `SAM_WORKER_ID` | `sandbox-worker-001` | Unique worker identifier |
| `DEFAULT_TIMEOUT_SECONDS` | `300` | Default tool timeout |

### Optional - nsjail

| Variable | Default | Description |
|----------|---------|-------------|
| `NSJAIL_BIN` | `/usr/bin/nsjail` | Path to nsjail binary |
| `NSJAIL_CONFIG_DIR` | `/etc/nsjail` | Path to nsjail configs |
| `NSJAIL_PYTHON_BIN` | `/usr/bin/python3` | Python binary inside sandbox |
| `NSJAIL_WORK_DIR` | `/sandbox/work` | Work directory for executions |
| `NSJAIL_DEFAULT_PROFILE` | `standard` | Default nsjail profile |
| `NSJAIL_MAX_CONCURRENT` | `4` | Max concurrent executions |

### Optional - Artifacts

| Variable | Default | Description |
|----------|---------|-------------|
| `ARTIFACT_SERVICE_TYPE` | `memory` | Type: `memory`, `filesystem`, `s3`, `gcs` |
| `ARTIFACT_BASE_PATH` | `/sam/artifacts` | Base path for filesystem |
| `ARTIFACT_S3_BUCKET` | - | S3 bucket name |
| `ARTIFACT_S3_REGION` | `us-east-1` | S3 region |
| `ARTIFACT_GCS_BUCKET` | - | GCS bucket name |

## nsjail Profiles

Three security profiles are available:

### restrictive

- No network access
- 512MB memory limit
- 60 second timeout
- 1 CPU
- Minimal syscalls

### standard (default)

- Network access enabled
- 1GB memory limit
- 300 second timeout
- 2 CPUs
- Common syscalls allowed

### permissive

- Network access enabled
- 4GB memory limit
- 600 second timeout
- 4 CPUs
- Most syscalls allowed

## Installing Tool Dependencies

To add Python packages that tools can use, extend the Dockerfile:

```dockerfile
FROM sam-sandbox-worker

# Install additional packages
RUN pip install pandas numpy requests
```

Or mount packages at runtime:

```bash
podman run -d --privileged \
  -v /path/to/local/packages:/usr/local/lib/python3.11/site-packages:ro \
  ...
```

## Debugging

View container logs:

```bash
# Using helper script detection
source container-runtime.sh
$CONTAINER_CMD logs -f sandbox-worker

# Or directly
podman logs -f sandbox-worker
docker logs -f sandbox-worker
```

Shell into the container:

```bash
podman exec -it sandbox-worker /bin/bash
docker exec -it sandbox-worker /bin/bash
```

Test nsjail manually:

```bash
podman exec -it sandbox-worker \
  nsjail --config /etc/nsjail/standard.cfg -- \
  /usr/bin/python3 -c "print('hello from sandbox')"
```

## Helper Scripts

| Script | Description |
|--------|-------------|
| `container-runtime.sh` | Detects podman/docker, exports `$CONTAINER_CMD` |
| `build.sh` | Builds the container image |
| `run.sh` | Runs the container with environment variables |

### Using container-runtime.sh in Your Scripts

```bash
#!/bin/bash
source /path/to/container-runtime.sh

# Now use $CONTAINER_CMD
$CONTAINER_CMD ps
$CONTAINER_CMD images

# Or use helper functions
container_build -t my-image .
container_run -d my-image
container_logs my-container
container_stop my-container
```

## Podman vs Docker Notes

- Both runtimes are fully supported
- The scripts auto-detect which is available (preferring podman)
- `host.containers.internal` works for both to access host network
- `--privileged` is required for nsjail namespaces in both runtimes
- Rootless podman may require additional configuration for nsjail
