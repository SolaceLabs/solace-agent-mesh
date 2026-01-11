# Lambda Executor Example

This example demonstrates how to use the Lambda executor to run SAM tools on AWS Lambda functions.

## Overview

The Lambda executor allows you to define tools that invoke AWS Lambda functions instead of running code locally. This is useful for:

- Running tools in a serverless environment
- Isolating tool execution from the agent
- Leveraging existing Lambda functions as tools
- Scaling tool execution independently

## Setup

### 1. Configure AWS Credentials

Ensure you have AWS credentials configured:

```bash
source ~/bin/set-aws-auth
```

### 2. Create the Test Lambda Function

Run the setup script to create a test Lambda function:

```bash
cd examples/agents/lambda-executor
./setup-lambda.sh
```

This creates:
- An IAM role (`sam-lambda-executor-test-role`) with basic Lambda execution permissions
- A Lambda function (`sam-lambda-executor-test`) with several test operations

The script outputs the function ARN and region to use.

### 3. Set Environment Variables

Export the Lambda ARN (printed by the setup script):

```bash
export SAM_LAMBDA_TEST_ARN="arn:aws:lambda:ca-central-1:ACCOUNT_ID:function:sam-lambda-executor-test"
export SAM_LAMBDA_TEST_REGION="ca-central-1"
```

### 4. Run the Agent

```bash
sam run examples/agents/lambda-executor/lambda_executor_example.yaml
```

## Test Lambda Function

The test Lambda function (`setup-lambda.sh`) provides several operations controlled by `tool_config.operation`:

### echo
Echoes back a message with session context information.

**Args:**
- `message` (string): The message to echo

**Response:**
```json
{
  "success": true,
  "data": {
    "echo": "Hello!",
    "session_id": "...",
    "user_id": "..."
  }
}
```

### calculate
Performs basic arithmetic operations.

**Args:**
- `operation` (string): "add", "subtract", "multiply", or "divide"
- `a` (number): First operand
- `b` (number): Second operand

**Response:**
```json
{
  "success": true,
  "data": {
    "operation": "add",
    "a": 5,
    "b": 3,
    "result": 8
  }
}
```

### reverse
Reverses a string.

**Args:**
- `text` (string): The text to reverse

**Response:**
```json
{
  "success": true,
  "data": {
    "original": "hello",
    "reversed": "olleh"
  }
}
```

### info
Returns Lambda execution environment information.

**Args:**
- `debug_info` (string, optional): Debug info to include

**Response:**
```json
{
  "success": true,
  "data": {
    "function_name": "sam-lambda-executor-test",
    "function_version": "$LATEST",
    "memory_limit_mb": 128,
    "remaining_time_ms": 29500,
    "request_context": {...},
    "received_args": {...}
  }
}
```

## Artifact Operations

The test Lambda also includes operations that demonstrate artifact (file) handling.

### analyze_artifact
Analyzes a single artifact and returns statistics.

**Args:**
- `artifact` (artifact): The file to analyze (SAM pre-loads the content)

**Response:**
```json
{
  "success": true,
  "data": {
    "filename": "example.txt",
    "mime_type": "text/plain",
    "size_bytes": 1234,
    "md5_hash": "abc123...",
    "is_text": true,
    "line_count": 50,
    "word_count": 200,
    "preview": "First 200 characters...",
    "version": 1
  }
}
```

### compare_artifacts
Compares multiple artifacts and detects duplicates.

**Args:**
- `artifacts` (array of artifacts): List of files to compare

**Response:**
```json
{
  "success": true,
  "data": {
    "artifact_count": 3,
    "total_size_bytes": 5000,
    "unique_files": 2,
    "has_duplicates": true,
    "duplicate_pairs": [
      {"file1": "a.txt", "file2": "b.txt", "hash": "abc123..."}
    ],
    "artifacts": [...]
  }
}
```

### generate_file
Generates a single file with specified content.

**Args:**
- `filename` (string): Name for the generated file
- `content_type` (string): "text", "json", "csv", or "binary"
- `data` (string, optional): Content to include

**Response:**
```json
{
  "success": true,
  "data": {
    "message": "Generated file: report.txt",
    "artifact": {
      "filename": "report.txt",
      "content": "file content here",
      "is_binary": false,
      "mime_type": "text/plain",
      "size_bytes": 100
    }
  }
}
```

### generate_files
Generates multiple files at once.

**Args:**
- `prefix` (string): Filename prefix (e.g., "report" -> report_1.txt)
- `count` (integer): Number of files (1-10)
- `content_type` (string): "text", "json", or "csv"

**Response:**
```json
{
  "success": true,
  "data": {
    "message": "Generated 3 files with prefix 'report'",
    "artifact_count": 3,
    "artifacts": [
      {"filename": "report_1.txt", "content": "...", ...},
      {"filename": "report_2.txt", "content": "...", ...},
      {"filename": "report_3.txt", "content": "...", ...}
    ]
  }
}
```

## Lambda Request/Response Format

### Request Format

The Lambda executor sends requests in this format:

```json
{
  "args": {
    "param1": "value1",
    "param2": "value2"
  },
  "context": {
    "session_id": "...",
    "user_id": "...",
    "app_name": "..."
  },
  "tool_config": {
    "operation": "echo",
    "custom_setting": "value"
  }
}
```

- `args`: Tool arguments from the LLM
- `context`: Session context (if `include_context: true`)
- `tool_config`: Custom configuration from the tool definition

### Response Format

Lambda functions should return responses in this format:

```json
{
  "success": true,
  "data": { ... },
  "metadata": { ... }
}
```

Or for errors:

```json
{
  "success": false,
  "error": "Error message",
  "error_code": "ERROR_CODE"
}
```

## Cleanup

To remove the test Lambda function and IAM role:

```bash
./cleanup-lambda.sh
```

## Creating Your Own Lambda Tools

1. Create a Lambda function that accepts the request format above
2. Return responses in the expected format
3. Configure the tool in your agent YAML:

```yaml
tools:
  - tool_type: executor
    name: "my_lambda_tool"
    description: "Description for the LLM"
    executor: lambda
    function_arn: ${MY_LAMBDA_ARN}
    region: ${AWS_REGION}
    include_context: true
    timeout_seconds: 60
    tool_config:
      custom_setting: "value"
    parameters:
      properties:
        param1:
          type: string
          description: "First parameter"
        param2:
          type: integer
          description: "Second parameter"
      required:
        - param1
```

## Using Artifact Parameters

To create a tool that receives file content, use `type: artifact` in your parameters:

```yaml
tools:
  - tool_type: executor
    name: "process_file"
    description: "Process a file"
    executor: lambda
    function_arn: ${MY_LAMBDA_ARN}
    region: ${AWS_REGION}
    parameters:
      properties:
        # Single artifact parameter
        input_file:
          type: artifact
          description: "The file to process"
        # List of artifacts
        additional_files:
          type: array
          items:
            type: artifact
          description: "Additional files to include"
      required:
        - input_file
```

When a parameter has `type: artifact`, SAM will:
1. Pre-load the artifact content before calling Lambda
2. Serialize the artifact as a dict with `filename`, `content`, `mime_type`, etc.
3. Base64-encode binary content (with `is_binary: true` flag)

Your Lambda receives artifacts in this format:
```json
{
  "args": {
    "input_file": {
      "filename": "data.csv",
      "content": "col1,col2\nval1,val2",
      "is_binary": false,
      "mime_type": "text/csv",
      "version": 1,
      "metadata": {}
    }
  }
}
```

For binary files, decode the content:
```python
import base64

def process_file(artifact):
    if artifact.get("is_binary"):
        content = base64.b64decode(artifact["content"])
    else:
        content = artifact["content"]
    # Process content...
```
