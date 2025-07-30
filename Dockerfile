
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

ENV CONFIG_PORTAL_HOST="0.0.0.0"

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
RUN python3.11 -m hatch build

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

# Switch to the non-root user
USER solaceai

RUN playwright install chromium

LABEL org.opencontainers.image.source=https://github.com/SolaceLabs/solace-agent-mesh

EXPOSE 3000 5002 5003 8000 8088

# CLI entry point
ENTRYPOINT ["solace-agent-mesh"]