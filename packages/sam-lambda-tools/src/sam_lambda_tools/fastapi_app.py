"""
FastAPI application for Lambda Web Adapter streaming.

This module provides the FastAPI app that handles tool invocation requests
and streams responses using NDJSON format. It's designed to work with
AWS Lambda Web Adapter (LWA) for response streaming.

The app provides:
    POST /invoke - Tool invocation with streaming response
    GET /health - Health check endpoint

Streaming Protocol:
    Each line in the response is a JSON object (NDJSON format):
    {"type":"status","payload":{"message":"..."},"timestamp":...}
    {"type":"result","payload":{"tool_result":{...}},"timestamp":...}

Example Dockerfile for Lambda:
    FROM public.ecr.aws/docker/library/python:3.12-slim
    COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

    WORKDIR /app
    COPY requirements.txt .
    RUN pip install -r requirements.txt
    COPY . .

    ENV AWS_LWA_INVOKE_MODE=RESPONSE_STREAM
    ENV PORT=8000

    CMD ["uvicorn", "lambda_handler:app", "--host", "0.0.0.0", "--port", "8000"]
"""

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from agent_tools import StreamMessage, StreamMessageType

if TYPE_CHECKING:
    from .handler import LambdaToolHandler

log = logging.getLogger(__name__)

# Configuration
HEARTBEAT_INTERVAL_SECONDS = 10.0
QUEUE_MAX_SIZE = 100
QUEUE_POLL_TIMEOUT_SECONDS = 1.0


def create_app(handler: "LambdaToolHandler") -> FastAPI:
    """
    Create a FastAPI application for Lambda tool invocation.

    This app provides streaming responses using NDJSON format,
    compatible with Lambda Function URLs and Lambda Web Adapter.

    Args:
        handler: LambdaToolHandler instance wrapping the tool function

    Returns:
        FastAPI application
    """
    app = FastAPI(
        title="SAM Lambda Tool",
        description="Lambda execution endpoint for SAM tools",
        version="0.1.0",
    )

    @app.post("/invoke")
    async def invoke(request: Request):
        """
        Invoke the tool with streaming response.

        Request body:
            {
                "args": { ... tool arguments ... },
                "context": {
                    "session_id": "...",
                    "user_id": "...",
                    "app_name": "..."
                },
                "tool_config": { ... }
            }

        Response:
            NDJSON stream with status updates and final result.
            Content-Type: application/x-ndjson

        Example response stream:
            {"type":"status","payload":{"message":"Starting..."},"timestamp":1704067200.0}
            {"type":"status","payload":{"message":"Processing..."},"timestamp":1704067201.0}
            {"type":"result","payload":{"tool_result":{...}},"timestamp":1704067202.0}
        """
        log_id = f"[invoke:{handler.tool_func.__name__}]"

        try:
            body = await request.json()
        except Exception as e:
            log.error("%s Failed to parse request body: %s", log_id, e)
            # Return error as streaming response
            async def error_stream():
                msg = StreamMessage.error(f"Invalid request body: {e}")
                yield msg.to_ndjson_line()
            return StreamingResponse(
                error_stream(),
                media_type="application/x-ndjson",
            )

        args = body.get("args", {})
        context = body.get("context", {})
        tool_config = body.get("tool_config", {})

        log.info(
            "%s Invocation started (args=%s)",
            log_id,
            list(args.keys()),
        )

        # Create stream queue for status updates
        stream_queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)

        async def generate():
            """Generate NDJSON stream with status updates and result."""
            nonlocal log_id

            # Send automatic "start" status
            start_msg = StreamMessage.status("Tool execution started")
            yield start_msg.to_ndjson_line()

            # Start tool execution in background
            result_task = asyncio.create_task(
                handler.execute(args, context, tool_config, stream_queue)
            )

            last_heartbeat = time.time()

            # Stream status updates while tool executes
            while not result_task.done():
                try:
                    # Wait for status messages with timeout
                    msg = await asyncio.wait_for(
                        stream_queue.get(),
                        timeout=QUEUE_POLL_TIMEOUT_SECONDS,
                    )
                    yield msg.to_ndjson_line()
                    last_heartbeat = time.time()

                except asyncio.TimeoutError:
                    # Check if we need to send heartbeat
                    now = time.time()
                    if now - last_heartbeat > HEARTBEAT_INTERVAL_SECONDS:
                        heartbeat = StreamMessage.heartbeat()
                        yield heartbeat.to_ndjson_line()
                        last_heartbeat = now

            # Drain any remaining messages in queue
            while not stream_queue.empty():
                try:
                    msg = stream_queue.get_nowait()
                    yield msg.to_ndjson_line()
                except asyncio.QueueEmpty:
                    break

            # Get final result
            try:
                result = result_task.result()
                final_msg = StreamMessage.result(result.to_serializable())
                log.info("%s Execution complete (status=%s)", log_id, result.status)
            except Exception as e:
                log.exception("%s Execution failed: %s", log_id, e)
                final_msg = StreamMessage.error(
                    str(e),
                    error_code="EXECUTION_ERROR",
                )

            yield final_msg.to_ndjson_line()

        return StreamingResponse(
            generate(),
            media_type="application/x-ndjson",
        )

    @app.get("/health")
    async def health():
        """
        Health check endpoint.

        Returns:
            JSON with status and tool name
        """
        return {
            "status": "healthy",
            "tool": handler.tool_func.__name__,
        }

    return app
