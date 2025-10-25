FROM python:3.11-slim AS base

# Capture build platform information
ARG TARGETARCH
ARG TARGETPLATFORM

ENV PYTHONUNBUFFERED=1

# Install system dependencies and uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    ffmpeg && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js (only if frontend build is needed)
RUN curl -sL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Builder stage for creating wheels
FROM base AS builder

WORKDIR /app

# Install hatch with cache mount (before copying deps for better layer caching)
# This layer is invalidated only when base image changes, not when pyproject.toml changes
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-build-${TARGETARCH} \
    uv pip install --system hatch

# Copy dependency files for metadata
COPY pyproject.toml README.md ./

# Copy remaining source code
COPY . .

# Build the project wheel with cache mount
# uv caches downloaded packages, no need for separate pip wheel step
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-build-${TARGETARCH} \
    --mount=type=cache,target=/root/.npm,id=npm-${TARGETARCH} \
    hatch build -t wheel

# Runtime stage
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1

# Install minimal runtime dependencies (no uv for licensing compliance)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install Playwright early (large download, rarely changes)
RUN python -m pip install --no-cache-dir playwright && \
    playwright install-deps chromium

# Create non-root user
RUN groupadd -r solaceai && useradd --create-home -r -g solaceai solaceai

WORKDIR /app
RUN chown -R solaceai:solaceai /app /tmp

# Switch to non-root user and install Playwright browser
USER solaceai
RUN playwright install chromium

# Install the Solace Agent Mesh package
USER root
COPY --from=builder /app/dist/solace_agent_mesh-*.whl /tmp/

# Use built-in pip for runtime installation (avoids uv licensing in final image)
# uv is only used in build stage which is discarded
RUN python -m pip install --no-cache-dir /tmp/solace_agent_mesh-*.whl && \
    rm -rf /tmp/solace_agent_mesh-*.whl

# Copy sample SAM applications
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
