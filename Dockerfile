# ============================================================
# UI Build Stages - Run in parallel with separate caches
# ============================================================
# These stages use registry cache with mode=max, which means:
# - Each stage is cached independently in the registry
# - Only stages with changed dependencies will rebuild
# - Cache mounts persist across builds for faster npm installs
# - Changes to docs/ won't invalidate config_portal or webui caches
# ============================================================

# Build Config Portal UI
FROM node:20-trixie-slim AS ui-config-portal
WORKDIR /build/config_portal/frontend
COPY config_portal/frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY config_portal/frontend ./
RUN npm run build

# Build WebUI
FROM node:20-trixie-slim AS ui-webui
WORKDIR /build/client/webui/frontend
COPY client/webui/frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY client/webui/frontend ./
RUN npm run build

# Build Documentation
FROM node:20-trixie-slim AS ui-docs
WORKDIR /build/docs
COPY docs/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY docs ./
COPY README.md ../README.md
COPY cli/__init__.py ../cli/__init__.py
RUN npm run build

# ============================================================
# Python Build Stage
# ============================================================
# This stage uses registry cache with mode=max for optimal caching:
# - uv cache mount (/root/.cache/uv) speeds up package downloads
# - Lock file changes only rebuild dependency installation layer
# - Source code changes only rebuild the wheel build layer
# - Independent from UI build stages - Python changes don't rebuild UI
# ============================================================
FROM python:3.11-slim AS builder

# Install system dependencies and uv
# Upgrade pip to >=25.3 to fix CVE-2025-8869
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg=7:7.1.3-0+deb13u1  \
    git && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m venv /opt/venv && \
    /opt/venv/bin/python -m pip install --upgrade "pip>=25.3" && \
    curl -sL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    uv pip install --system hatch

WORKDIR /app

ENV VIRTUAL_ENV=/opt/venv
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1

# Sync dependencies from lock file directly into venv (cached layer)
# This is the expensive step with 188 packages (~8s with cache, ~280MB downloads without)
# Using lock file ensures reproducible builds with exact versions
# --frozen ensures lock file isn't modified, --no-dev skips dev dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync \
        --frozen \
        --no-dev \
        --active \
        --no-install-project

# Copy Python source code and essential files (skip UI source code)
COPY src ./src
COPY cli ./cli
COPY evaluation ./evaluation
COPY templates ./templates
COPY config_portal/__init__.py ./config_portal/__init__.py
COPY config_portal/backend ./config_portal/backend
COPY .github/helper_scripts ./.github/helper_scripts

# Copy pre-built UI static assets from UI build stages
COPY --from=ui-config-portal /build/config_portal/frontend/static ./config_portal/frontend/static
COPY --from=ui-webui /build/client/webui/frontend/static ./client/webui/frontend/static
COPY --from=ui-docs /build/docs/build ./docs/build

COPY LICENSE ./LICENSE
COPY README.md ./README.md
COPY pyproject.toml ./pyproject.toml

# Build the project wheel with cache mount
# Set SAM_SKIP_UI_BUILD to skip npm builds since we already have static assets
RUN --mount=type=cache,target=/root/.cache/uv \
    SAM_SKIP_UI_BUILD=true hatch build -t wheel

# Install only the wheel package (not dependencies, they're already installed)
# This is fast since all deps are already in the venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install /app/dist/solace_agent_mesh-*.whl

# Runtime stage
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Install minimal runtime dependencies (no uv for licensing compliance)
# Upgrade system pip to >=25.3 to fix CVE-2025-8869
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ffmpeg=7:7.1.3-0+deb13u1 \
    git && \
    python3 -m pip install --upgrade "pip>=25.3" && \
    curl -sL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


# Install playwright temporarily just for browser installation (cached layer)
# This is separate from the full venv to keep this layer cached
# We'll use the playwright from the full venv at runtime
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/playwright \
    python3 -m pip install playwright && \
    playwright install-deps chromium && \
    playwright install chromium

# Create non-root user and Playwright cache directory
RUN groupadd -r solaceai && useradd --create-home -r -g solaceai solaceai && \
    mkdir -p /var/cache/playwright && \
    chown -R solaceai:solaceai /var/cache/playwright

WORKDIR /app
RUN chown -R solaceai:solaceai /app

# Copy the pre-built virtual environment from builder
# This avoids slow pip install in runtime (UV already did it)
# Copied AFTER Playwright setup so Playwright layers stay cached
COPY --from=builder /opt/venv /opt/venv

COPY preset /preset

USER solaceai
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
