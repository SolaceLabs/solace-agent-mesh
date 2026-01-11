# Dockerfile for Lambda with Web Adapter (streaming support)
#
# Build from the repository root:
#   docker build -f examples/agents/lambda-executor-streaming/Dockerfile -t sam-streaming-example .
#   podman build -f examples/agents/lambda-executor-streaming/Dockerfile -t sam-streaming-example .
#
FROM public.ecr.aws/docker/library/python:3.12-slim

# Install Lambda Web Adapter for response streaming
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /app

# Install dependencies only (not the full package build which has relative path issues)
RUN pip install --no-cache-dir \
    pydantic>=2.0.0 \
    fastapi>=0.100.0 \
    "uvicorn[standard]>=0.20.0"

# Copy source code directly
COPY shared/agent_tools/ /app/agent_tools/
COPY packages/sam-lambda-tools/src/sam_lambda_tools/ /app/sam_lambda_tools/

# Copy example tool code
COPY examples/agents/lambda-executor-streaming/tool.py .
COPY examples/agents/lambda-executor-streaming/lambda_handler.py .

# Set PYTHONPATH so imports work
ENV PYTHONPATH=/app

# Lambda Web Adapter configuration
ENV AWS_LWA_INVOKE_MODE=RESPONSE_STREAM
ENV PORT=8000

# Run uvicorn server
CMD ["uvicorn", "lambda_handler:app", "--host", "0.0.0.0", "--port", "8000"]
