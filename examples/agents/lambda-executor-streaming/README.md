# Lambda Executor Streaming Example

This example demonstrates **streaming status updates** from AWS Lambda functions using the Lambda Web Adapter and Function URLs with response streaming.

## Overview

Unlike standard Lambda invocation (which returns results only after completion), streaming mode allows Lambda functions to send real-time progress updates during execution. This is useful for:

- Long-running operations with progress indicators
- Data processing pipelines with status checkpoints
- Any tool that benefits from user feedback during execution

## Architecture

```
┌─────────────────┐     NDJSON Stream      ┌──────────────────────────────────────┐
│                 │◄──────────────────────│  Lambda Function URL (IAM Auth)      │
│   SAM Agent     │                        │                                      │
│   (httpx)       │  {"type":"status",...} │  ┌────────────────────────────────┐  │
│                 │  {"type":"status",...} │  │  Lambda Web Adapter            │  │
│                 │  {"type":"result",...} │  │  ┌────────────────────────────┐│  │
└─────────────────┘                        │  │  │  FastAPI + sam-lambda-tools││  │
                                           │  │  │  ┌──────────────────────┐  ││  │
                                           │  │  │  │  Your Tool Function  │  ││  │
                                           │  │  │  │  ctx.send_status()   │  ││  │
                                           │  │  │  └──────────────────────┘  ││  │
                                           │  │  └────────────────────────────┘│  │
                                           │  └────────────────────────────────┘  │
                                           └──────────────────────────────────────┘
```

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **Docker or Podman** installed and running
3. **AWS permissions** to create:
   - ECR repositories
   - Lambda functions
   - IAM roles
   - Function URLs

## Quick Start

### 1. Deploy the Lambda Function

From the **repository root** directory:

```bash
./examples/agents/lambda-executor-streaming/setup-streaming-lambda.sh
```

This script will:
- Create an ECR repository
- Build and push the container image
- Create an IAM role for Lambda
- Create the Lambda function
- Configure a Function URL with IAM authentication

### 2. Set the Environment Variable

The setup script outputs the Function URL. Set it as an environment variable:

```bash
export SAM_LAMBDA_STREAMING_URL="https://xxxxx.lambda-url.us-east-1.on.aws/"
```

### 3. Run the Agent

```bash
sam run examples/agents/lambda-executor-streaming/lambda_streaming_example.yaml
```

### 4. Test Streaming

In the SAM UI or CLI, try these prompts:

- `Process the message 'hello' with 5 steps`
- `Run a slow process on 'analyzing data' in 3 steps`
- `Process 'test' with 10 steps to see streaming updates`

You should see status updates appear in real-time as the tool executes each step.

## Files

| File | Description |
|------|-------------|
| `tool.py` | Example tool with `ctx.send_status()` calls |
| `lambda_handler.py` | FastAPI entry point using `LambdaToolHandler` |
| `Dockerfile` | Container with Lambda Web Adapter |
| `setup-streaming-lambda.sh` | Deployment script |
| `cleanup-streaming-lambda.sh` | Teardown script |
| `lambda_streaming_example.yaml` | SAM agent configuration |

## How Streaming Works

### Tool Code

Tools send status updates using `ctx.send_status()`:

```python
from agent_tools import ToolResult, ToolContextBase

async def slow_process(message: str, steps: int, ctx: ToolContextBase) -> ToolResult:
    ctx.send_status(f"Starting: {message}")

    for i in range(steps):
        await asyncio.sleep(1)  # Simulate work
        ctx.send_status(f"Step {i + 1}/{steps} complete...")

    return ToolResult.ok(f"Processed in {steps} steps")
```

### Streaming Protocol (NDJSON)

The Lambda streams newline-delimited JSON messages:

```
{"type":"status","payload":{"message":"Starting: hello"},"timestamp":1704067200.1}
{"type":"status","payload":{"message":"Step 1/5 complete..."},"timestamp":1704067201.2}
{"type":"status","payload":{"message":"Step 2/5 complete..."},"timestamp":1704067202.3}
{"type":"result","payload":{"tool_result":{...}},"timestamp":1704067205.6}
```

### Agent Configuration

Use `function_url` instead of `function_arn` to enable streaming:

```yaml
tools:
  - tool_type: executor
    name: "slow_process"
    executor: lambda
    function_url: ${SAM_LAMBDA_STREAMING_URL}  # Function URL enables streaming
    include_context: true
    timeout_seconds: 120
    parameters:
      # ...
```

## Authentication

Function URLs use IAM authentication with SigV4 request signing. The Lambda executor automatically signs requests using your AWS credentials.

Ensure your AWS credentials have permission to invoke the Lambda function URL.

## Cleanup

To remove all AWS resources:

```bash
./examples/agents/lambda-executor-streaming/cleanup-streaming-lambda.sh
```

## Troubleshooting

### No status updates appearing

- Ensure the Function URL ends with `/` - some browsers/tools require it
- Check that `AWS_LAMBDA_STREAMING_URL` is set correctly
- Verify your AWS credentials have `lambda:InvokeFunctionUrl` permission

### Authentication errors (403)

- Verify AWS credentials are available and valid
- Check that the IAM user/role has permission to invoke the Function URL
- The Lambda executor uses SigV4 signing - ensure `httpx-auth-awssigv4` is installed

### Container build failures

- Make sure to run the build from the **repository root**, not the example directory
- The Dockerfile expects `shared/` and `packages/` directories at the build context root
- Both Docker and Podman are supported (auto-detected by the setup script)

### Lambda timeout

- The example tool takes ~1 second per step
- Increase `timeout_seconds` in the agent config if needed
- Default Lambda timeout is 120 seconds

## Comparison: Standard vs Streaming Mode

| Feature | Standard Mode | Streaming Mode |
|---------|---------------|----------------|
| **Config** | `function_arn` | `function_url` |
| **Authentication** | IAM role (boto3) | SigV4 signed HTTP |
| **Status updates** | After completion | Real-time |
| **Deployment** | .zip or container | Container + LWA |
| **Use case** | Quick operations | Long-running with feedback |
