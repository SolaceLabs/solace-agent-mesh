FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Install system dependencies in a single layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    ffmpeg && \
    rm -rf /var/lib/apt/lists/* && \
    curl -sL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get purge -y --auto-remove && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Builder stage for creating wheels
FROM base AS builder

WORKDIR /app

# Install hatch first (this layer will be cached unless hatch version changes)
RUN python3.11 -m pip install --no-cache-dir hatch

# Copy source code
COPY . .

# Create wheels for dependencies (this will be cached unless pyproject.toml changes)
RUN python3.11 -m pip wheel --wheel-dir=/wheels --find-links=/wheels --no-build-isolation .

# Build the project wheel
RUN python3.11 -m hatch build -t wheel

# Runtime stage
FROM base AS runtime

# Install Playwright early (large download, rarely changes)
RUN python3.11 -m pip install playwright && \
    playwright install-deps chromium

# Create non-root user
RUN groupadd -r solaceai && useradd --create-home -r -g solaceai solaceai

WORKDIR /app
RUN chown -R solaceai:solaceai /app /tmp

# Switch to non-root user and install Playwright browser
USER solaceai
RUN playwright install chromium

# Install the Solace Agent Mesh package (this layer changes when source code changes)
USER root
COPY --from=builder /app/dist/solace_agent_mesh-*.whl /tmp/
COPY --from=builder /wheels /tmp/wheels

RUN python3.11 -m pip install --find-links=/tmp/wheels \
    /tmp/solace_agent_mesh-*.whl && \
    rm -rf /tmp/wheels /tmp/solace_agent_mesh-*.whl

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
