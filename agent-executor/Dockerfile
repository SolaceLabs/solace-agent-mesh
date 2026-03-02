# SAM Agent Executor Container
# Runs multiple agents as subprocesses within a single pod.
# Configs synced from S3, communicates via Solace broker.
#
# Build (from solace-agent-mesh root):
#   docker build -t sam-agent-executor -f agent-executor/Dockerfile .

FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /agents/work \
    && mkdir -p /app

WORKDIR /app

# Copy SAM source and install
COPY pyproject.toml /app/sam-src/
COPY src/ /app/sam-src/src/
COPY README.md /app/sam-src/
COPY .github/helper_scripts/ /app/sam-src/.github/helper_scripts/
COPY cli/ /app/sam-src/cli/
COPY templates/ /app/sam-src/templates/
COPY evaluation/ /app/sam-src/evaluation/
COPY config_portal/backend/ /app/sam-src/config_portal/backend/
COPY config_portal/__init__.py /app/sam-src/config_portal/__init__.py
COPY LICENSE /app/sam-src/LICENSE

# Create dummy static asset directories (agent executor doesn't need UI)
RUN mkdir -p /app/sam-src/config_portal/frontend/static \
    && mkdir -p /app/sam-src/client/webui/frontend/static \
    && mkdir -p /app/sam-src/docs/build

ENV SAM_SKIP_UI_BUILD=true
RUN pip install --no-cache-dir /app/sam-src/

# Remove curl after install to reduce attack surface
RUN apt-get update && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY agent-executor/entrypoint.py /app/entrypoint.py

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENV SAM_NAMESPACE=""
ENV SAM_EXECUTOR_ID="agent-executor-001"
ENV SOLACE_HOST=""
ENV SOLACE_VPN=""
ENV SOLACE_USERNAME=""
ENV SOLACE_PASSWORD=""

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8082/healthz')" || exit 1

ENTRYPOINT ["python", "/app/entrypoint.py"]
