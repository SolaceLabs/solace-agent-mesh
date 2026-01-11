"""
SAM Lambda Tools - Lambda execution support for Solace Agent Mesh tools.

This package enables tools written for SAM to run as AWS Lambda functions
without modification. It provides:

- LambdaToolHandler: Wraps tool functions for Lambda execution
- LambdaToolContext: Implements ToolContextBase for Lambda environment
- FastAPI app creation for Lambda Web Adapter streaming

Quick Start:
    1. Write your tool using SAM types:

        from agent_tools import ToolResult, Artifact, ToolContextBase

        async def my_tool(
            input_file: Artifact,
            ctx: ToolContextBase,
        ) -> ToolResult:
            ctx.send_status("Processing...")
            content = input_file.as_text()
            return ToolResult.ok("Done", data={"size": len(content)})

    2. Create a Lambda handler:

        # lambda_handler.py
        from sam_lambda_tools import LambdaToolHandler
        from my_tool import my_tool

        handler = LambdaToolHandler(my_tool)
        app = handler.create_fastapi_app()

    3. Deploy with Lambda Web Adapter:

        # Dockerfile
        FROM public.ecr.aws/docker/library/python:3.12-slim
        COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

        WORKDIR /app
        COPY requirements.txt .
        RUN pip install -r requirements.txt
        COPY . .

        ENV AWS_LWA_INVOKE_MODE=RESPONSE_STREAM
        ENV PORT=8000

        CMD ["uvicorn", "lambda_handler:app", "--host", "0.0.0.0", "--port", "8000"]

Re-exported from agent_tools for convenience:
    - ToolResult, DataObject, DataDisposition
    - Artifact
    - ToolContextBase
    - StreamMessage, StreamMessageType
"""

# Lambda-specific exports
from .handler import LambdaToolHandler, deserialize_artifact, deserialize_args
from .context import LambdaToolContext
from .fastapi_app import create_app

# Re-export from agent_tools for convenience
from agent_tools import (
    # Result types
    ToolResult,
    DataObject,
    DataDisposition,
    # Artifact types
    Artifact,
    # Context types
    ToolContextBase,
    # Streaming types
    StreamMessage,
    StreamMessageType,
)

__version__ = "0.1.0"

__all__ = [
    # Lambda-specific
    "LambdaToolHandler",
    "LambdaToolContext",
    "create_app",
    "deserialize_artifact",
    "deserialize_args",
    # Re-exported from agent_tools
    "ToolResult",
    "DataObject",
    "DataDisposition",
    "Artifact",
    "ToolContextBase",
    "StreamMessage",
    "StreamMessageType",
]
