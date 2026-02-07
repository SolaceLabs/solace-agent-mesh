# SAM Sandbox Worker Container
# This container runs Python tools in a sandboxed environment using nsjail.
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
#   podman run -d --privileged --name sandbox-worker \
#     -e SAM_NAMESPACE=myorg/dev \
#     -e SOLACE_HOST=host.containers.internal:55554 \
#     -e SOLACE_VPN=default \
#     -e SOLACE_USERNAME=admin \
#     -e SOLACE_PASSWORD=admin \
#     sam-sandbox-worker

FROM python:3.11-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # nsjail build dependencies
    build-essential \
    git \
    autoconf \
    bison \
    flex \
    pkg-config \
    libnl-3-dev \
    libnl-route-3-dev \
    libprotobuf-dev \
    protobuf-compiler \
    # Runtime dependencies
    libcap2 \
    libcap-dev \
    libnl-3-200 \
    libnl-route-3-200 \
    libprotobuf32 \
    # Useful tools
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Build and install nsjail from source
RUN git clone https://github.com/google/nsjail.git /tmp/nsjail \
    && cd /tmp/nsjail \
    && make \
    && cp nsjail /usr/bin/nsjail \
    && chmod +x /usr/bin/nsjail \
    && rm -rf /tmp/nsjail

# Create sandbox directories
RUN mkdir -p /sandbox/work \
    && mkdir -p /etc/nsjail \
    && mkdir -p /app

# Copy nsjail configuration profiles
COPY sandbox-worker/nsjail-configs/*.cfg /etc/nsjail/

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

# Health check - verifies worker is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python.*entrypoint" || exit 1

# Run the sandbox worker
ENTRYPOINT ["python", "/app/entrypoint.py"]
