FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1

# Install system dependencies and uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    git && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js (only if frontend build is needed)
RUN curl -sL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ============================================================
# UI Build Stages - Run in parallel with separate caches
# ============================================================

# Build Config Portal UI
FROM base AS ui-config-portal
WORKDIR /build/config_portal/frontend
COPY config_portal/frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY config_portal/frontend ./
RUN npm run build

# Build WebUI
FROM base AS ui-webui
WORKDIR /build/client/webui/frontend
COPY client/webui/frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY client/webui/frontend ./
RUN npm run build

# Build Documentation
FROM base AS ui-docs
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

# Builder stage for creating wheels and runtime environment
FROM base AS builder

WORKDIR /app

# Install hatch with cache mount (before copying deps for better layer caching)
# This layer is invalidated only when base image changes, not when pyproject.toml changes
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system hatch

# Sync dependencies from lock file directly into venv (cached layer)
# This is the expensive step with 188 packages (~8s with cache, ~280MB downloads without)
# Using lock file ensures reproducible builds with exact versions
# --frozen ensures lock file isn't modified, --no-dev skips dev dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    UV_PROJECT_ENVIRONMENT=/opt/venv uv sync \
        --frozen \
        --no-dev \
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
    uv pip install --python=/opt/venv/bin/python --no-deps /app/dist/solace_agent_mesh-*.whl

# Runtime stage
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Install minimal runtime dependencies (no uv for licensing compliance)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install playwright temporarily just for browser installation (cached layer)
# This is separate from the full venv to keep this layer cached
# We'll use the playwright from the full venv at runtime
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --no-cache-dir playwright==1.55.0

# Install Playwright system dependencies (cached layer)
RUN playwright install-deps chromium

# Install Playwright browsers with cache (cached layer)
# This layer stays cached because it doesn't depend on builder stage
RUN --mount=type=cache,target=/var/cache/playwright,sharing=locked \
    PLAYWRIGHT_BROWSERS_PATH=/var/cache/playwright playwright install chromium

# Create non-root user and Playwright cache directory
RUN groupadd -r solaceai && useradd --create-home -r -g solaceai solaceai && \
    mkdir -p /var/cache/playwright && \
    chown -R solaceai:solaceai /var/cache/playwright

WORKDIR /app
RUN chown -R solaceai:solaceai /app /tmp

# Copy the pre-built virtual environment from builder
# This avoids slow pip install in runtime (UV already did it)
# Copied AFTER Playwright setup so Playwright layers stay cached
COPY --from=builder /opt/venv /opt/venv

# Set Playwright to use the cached browser location
ENV PLAYWRIGHT_BROWSERS_PATH=/var/cache/playwright

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
