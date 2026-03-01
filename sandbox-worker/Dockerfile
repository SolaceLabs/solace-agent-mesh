# SAM Sandbox Worker Container
# This container runs Python tools in a sandboxed environment using bubblewrap (bwrap).
# Works with both Podman and Docker.
#
# Quick start (using helper scripts):
#   ./build.sh
#   SAM_NAMESPACE=myorg/dev SOLACE_HOST=host.containers.internal:55554 ./run.sh
#
# Manual build (podman or docker):
#   podman build -t sam-sandbox-worker .
#   docker build -t sam-sandbox-worker .
#
# Manual run:
#   podman run -d --name sandbox-worker \
#     -e SAM_NAMESPACE=myorg/dev \
#     -e SOLACE_HOST=host.containers.internal:55554 \
#     -e SOLACE_VPN=default \
#     -e SOLACE_USERNAME=admin \
#     -e SOLACE_PASSWORD=admin \
#     sam-sandbox-worker
#
# Note: With Kubernetes 1.33+ user namespaces (hostUsers: false, procMount: Unmasked),
# bwrap only needs the SETFCAP capability instead of --privileged.

FROM python:3.11-slim-bookworm

# Install system dependencies including bubblewrap for sandboxing
RUN apt-get update && apt-get install -y --no-install-recommends \
    bubblewrap \
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create sandbox directories and non-root user
RUN mkdir -p /sandbox/work \
    && mkdir -p /app \
    && mkdir -p /tools/python /tools/wheels \
    && useradd -r -s /usr/sbin/nologin sandbox

# Install SAM and dependencies
WORKDIR /app

# Copy SAM source from parent directory and install
# Note: Build context must be the parent directory (solace-agent-mesh/)
COPY pyproject.toml /app/sam-src/
COPY src/ /app/sam-src/src/
COPY README.md /app/sam-src/
COPY .github/helper_scripts/ /app/sam-src/.github/helper_scripts/
# Copy additional files required by hatch build (force-include entries)
COPY cli/ /app/sam-src/cli/
COPY templates/ /app/sam-src/templates/
COPY evaluation/ /app/sam-src/evaluation/
COPY config_portal/backend/ /app/sam-src/config_portal/backend/
COPY config_portal/__init__.py /app/sam-src/config_portal/__init__.py
COPY LICENSE /app/sam-src/LICENSE

# Create dummy static asset directories (sandbox worker doesn't need UI)
RUN mkdir -p /app/sam-src/config_portal/frontend/static \
    && mkdir -p /app/sam-src/client/webui/frontend/static \
    && mkdir -p /app/sam-src/docs/build

# Install SAM from local source (skip UI build - not needed for sandbox worker)
ENV SAM_SKIP_UI_BUILD=true
RUN pip install --no-cache-dir /app/sam-src/

# Install additional sandbox worker dependencies
COPY sandbox-worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt || true

# Remove curl (only needed during build) to reduce attack surface
RUN apt-get update && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy the entrypoint
COPY sandbox-worker/entrypoint.py /app/entrypoint.py

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default configuration via environment
ENV SAM_NAMESPACE=""
ENV SAM_WORKER_ID="sandbox-worker-001"
ENV SOLACE_HOST=""
ENV SOLACE_VPN=""
ENV SOLACE_USERNAME=""
ENV SOLACE_PASSWORD=""

# Health check — uses the built-in HTTP health server
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/healthz')" || exit 1

# The container process runs as root because bwrap requires CAP_SYS_ADMIN
# for namespace creation. Sandboxed tool code is isolated via bwrap's
# --unshare-user (mapped to nobody/65534), so tools cannot escalate.
# When K8s user namespaces (hostUsers: false) are available, the pod can
# run as non-root and bwrap still works — see README for details.

# Run the sandbox worker
ENTRYPOINT ["python", "/app/entrypoint.py"]
