# sam-lambda-tools

Lambda execution support for Solace Agent Mesh (SAM) tools.

This package allows SAM tools to run as AWS Lambda functions with streaming status updates via Lambda Function URLs and AWS Lambda Web Adapter.

## Installation

```bash
pip install sam-lambda-tools
```

## Usage

```python
from sam_lambda_tools import LambdaToolHandler
from agent_tools import ToolResult, ToolContextBase

async def my_tool(message: str, ctx: ToolContextBase) -> ToolResult:
    ctx.send_status("Processing...")
    # ... do work ...
    return ToolResult.ok("Done")

handler = LambdaToolHandler(my_tool)
app = handler.create_fastapi_app()
```

## Features

- **Streaming status updates**: Tools can send real-time progress via `ctx.send_status()`
- **NDJSON protocol**: Streams newline-delimited JSON for status and results
- **Portable tools**: Same tool code works in both SAM and Lambda environments
- **FastAPI integration**: Creates a FastAPI app for Lambda Web Adapter

## License

Apache-2.0
