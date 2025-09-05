FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install all dependencies including Node.js and Playwright browser dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl && \
    curl -sL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get purge -y --auto-remove && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . /app
RUN python3.11 -m pip wheel --wheel-dir=/wheels .
RUN python3.11 -m pip install --no-cache-dir hatch
RUN python3.11 -m hatch build -t wheel

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl && \
    curl -sL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    python3.11 -m pip install playwright && \
    playwright install-deps chromium && \
    apt-get purge -y --auto-remove && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user and group
RUN groupadd -r solaceai && useradd --create-home -r -g solaceai solaceai
WORKDIR /app
RUN chown -R solaceai:solaceai /app /tmp

# Switch to the non-root user
USER solaceai
RUN playwright install chromium

# Install the Solace Agent Mesh package
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
