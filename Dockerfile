# syntax=docker/dockerfile:1.9

# ============================================================================
# Build Stage: Compile dependencies and build wheel
# ============================================================================
FROM python:3.11-slim AS builder

SHELL ["sh", "-exc"]

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

# Install build dependencies including Node.js (needed for frontend build hook)
RUN <<EOT
apt-get update -qy
apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    ca-certificates
curl -sL https://deb.nodesource.com/setup_24.x | bash -
apt-get install -y --no-install-recommends nodejs
apt-get clean
rm -rf /var/lib/apt/lists/*
EOT

# Install uv - the fast Python package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Configure uv for optimal Docker usage
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.11 \
    UV_PROJECT_ENVIRONMENT=/app

# ============================================================================
# Step 1: Install dependencies ONLY (cached until uv.lock changes)
# ============================================================================
WORKDIR /build

# Copy only the lock file first - this layer is cached unless dependencies actually change
COPY uv.lock pyproject.toml ./

# Install dependencies from lockfile (cached until uv.lock changes)
# Using cache mount ensures packages are never re-downloaded
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# ============================================================================
# Step 2: Build the project wheel (requires source code and Node.js)
# ============================================================================
# Copy source code needed for build
COPY . /build

# Build the wheel using hatch (via uv, which hatch natively supports)
# The custom build hook will run npm to build frontends
# Use cache mounts for both uv and npm
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/root/.npm \
    <<EOT
# Install hatch in the build environment
uv pip install --system hatch

# Build the wheel - this runs build_frontend.py hook (which uses npm)
hatch build -t wheel

# Now install the built wheel into /app venv
uv pip install --python /app/bin/python --no-deps dist/solace_agent_mesh-*.whl
EOT

# ============================================================================
# Runtime Stage: Minimal image with only runtime dependencies
# ============================================================================
FROM python:3.11-slim AS runtime

SHELL ["sh", "-exc"]

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PATH=/app/bin:$PATH

# Install runtime dependencies only (no build tools, no Node.js)
# Note: When using cache mounts, we should NOT clean apt cache
RUN <<EOT
apt-get update -qy
apt-get install -y --no-install-recommends \
    git \
    curl \
    ffmpeg \
    ca-certificates
rm -rf /var/lib/apt/lists/*
# Create user with specific UID for cache mount compatibility
groupadd -r -g 1000 solaceai
useradd --create-home -r -u 1000 -g solaceai solaceai
EOT

# Copy the complete /app venv from builder (includes all deps + application)
# Use --link for faster layer creation (avoid unnecessary file copies)
COPY --from=builder --link --chown=solaceai:solaceai /app /app

# Install Playwright (large dependency, but needed at runtime)
# Use cache mounts to speed up repeated builds:
# - apt cache for system dependencies  
# - playwright cache for chromium binaries
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    <<EOT
/app/bin/python -m playwright install-deps chromium
EOT

USER solaceai
RUN --mount=type=cache,target=/home/solaceai/.cache,uid=1000,gid=1000 \
    /app/bin/python -m playwright install chromium

# Copy sample SAM applications
USER root
COPY --link --chown=solaceai:solaceai preset /preset

WORKDIR /app
USER solaceai

# Verification and introspection
RUN <<EOT
python -V
python -Im site
python -Ic 'import solace_agent_mesh'
EOT

# Required environment variables
ENV CONFIG_PORTAL_HOST=0.0.0.0
ENV FASTAPI_HOST=0.0.0.0
ENV FASTAPI_PORT=8000
ENV NAMESPACE=sam/
ENV SOLACE_DEV_MODE=True

# Set the following environment variables to appropriate values before deploying
ENV SESSION_SECRET_KEY="REPLACE_WITH_SESSION_SECRET_KEY"
ENV LLM_SERVICE_ENDPOINT="REPLACE_WITH_LLM_SERVICE_ENDPOINT"
ENV LLM_SERVICE_API_KEY="REPLACE_WITH_LLM_SERVICE_API_KEY"
ENV LLM_SERVICE_PLANNING_MODEL_NAME="REPLACE_WITH_PLANNING_MODEL_NAME"
ENV LLM_SERVICE_GENERAL_MODEL_NAME="REPLACE_WITH_GENERAL_MODEL_NAME"

LABEL org.opencontainers.image.source=https://github.com/SolaceLabs/solace-agent-mesh

EXPOSE 5002 8000

# CLI entry point
ENTRYPOINT ["solace-agent-mesh"]

# Default command to run the preset agents
CMD ["run", "/preset/agents"]
