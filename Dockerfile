
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Install dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl ffmpeg && \
    curl -sL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get purge -y --auto-remove && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Installing python hatch package and building the Solace Agent Mesh package
WORKDIR /sam-temp
COPY . /sam-temp
RUN python3.11 -m pip install --no-cache-dir hatch
RUN python3.11 -m hatch build -t wheel

# Install the Solace Agent Mesh package
RUN python3.11 -m pip install --no-cache-dir dist/solace_agent_mesh-*.whl

# Clean up temporary files
WORKDIR /app
RUN rm -rf /sam-temp

# Install chromium through playwright cli (installed already as project python dependency)
RUN playwright install-deps chromium

# Create a non-root user and group
RUN groupadd -r solaceai && useradd --create-home -r -g solaceai solaceai
RUN chown -R solaceai:solaceai /app /tmp

# Copy sample SAM applications
COPY preset /preset

# Switch to the non-root user
USER solaceai

RUN playwright install chromium

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
