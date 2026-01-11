#!/bin/bash
# Setup script for SAM Lambda Executor test function
#
# Prerequisites:
#   - AWS CLI installed
#   - AWS credentials configured (e.g., source ~/bin/set-aws-auth)
#
# Usage:
#   ./setup-lambda.sh [region]
#
# The script will output the Lambda ARN to use in your agent config.

set -e

REGION="${1:-ca-central-1}"
FUNCTION_NAME="sam-lambda-executor-test"
ROLE_NAME="sam-lambda-executor-test-role"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Setting up Lambda executor test function in region: $REGION"

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "Error: AWS credentials not configured. Run 'source ~/bin/set-aws-auth' first."
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account: $ACCOUNT_ID"

# Create temporary directory for Lambda package
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Create the Lambda function code
cat > "$TEMP_DIR/lambda_function.py" << 'PYTHON_EOF'
"""
SAM Lambda Executor Test Function

This Lambda demonstrates the expected request/response format for the
SAM Lambda executor. It provides simple tools for testing including
artifact handling.

Expected Request Format:
{
    "args": { ... tool arguments ... },
    "context": {
        "session_id": "...",
        "user_id": "...",
        "app_name": "..."
    },
    "tool_config": { ... }
}

Artifact Format (when pre-loaded by SAM):
{
    "filename": "example.txt",
    "content": "file content or base64 encoded",
    "is_binary": false,
    "mime_type": "text/plain",
    "version": 1,
    "metadata": {}
}

Expected Response Format:
{
    "success": true/false,
    "data": { ... result data ... },
    "error": "error message if failed",
    "error_code": "ERROR_CODE"
}
"""

import base64
import hashlib
import json


def lambda_handler(event, context):
    """Main Lambda handler that routes to different tool implementations."""

    # Extract the tool operation from tool_config or default to echo
    tool_config = event.get("tool_config", {})
    operation = tool_config.get("operation", "echo")
    args = event.get("args", {})
    request_context = event.get("context", {})

    try:
        if operation == "echo":
            return echo_handler(args, request_context)
        elif operation == "calculate":
            return calculate_handler(args)
        elif operation == "reverse":
            return reverse_handler(args)
        elif operation == "info":
            return info_handler(args, request_context, context)
        elif operation == "analyze_artifact":
            return analyze_artifact_handler(args)
        elif operation == "compare_artifacts":
            return compare_artifacts_handler(args)
        elif operation == "generate_file":
            return generate_file_handler(args)
        elif operation == "generate_files":
            return generate_files_handler(args)
        elif operation == "generate_binary":
            return generate_binary_handler(args)
        else:
            return {
                "success": False,
                "error": f"Unknown operation: {operation}",
                "error_code": "UNKNOWN_OPERATION"
            }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "error_code": "EXECUTION_ERROR",
            "metadata": {"traceback": traceback.format_exc()}
        }


def echo_handler(args, request_context):
    """Echo back the input message with context info."""
    message = args.get("message", "Hello from Lambda!")

    return {
        "success": True,
        "data": {
            "echo": message,
            "session_id": request_context.get("session_id"),
            "user_id": request_context.get("user_id"),
        }
    }


def calculate_handler(args):
    """Perform simple arithmetic operations."""
    operation = args.get("operation", "add")
    a = float(args.get("a", 0))
    b = float(args.get("b", 0))

    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            return {
                "success": False,
                "error": "Division by zero",
                "error_code": "DIVISION_BY_ZERO"
            }
        result = a / b
    else:
        return {
            "success": False,
            "error": f"Unknown operation: {operation}",
            "error_code": "UNKNOWN_OPERATION"
        }

    return {
        "success": True,
        "data": {
            "operation": operation,
            "a": a,
            "b": b,
            "result": result
        }
    }


def reverse_handler(args):
    """Reverse a string."""
    text = args.get("text", "")

    return {
        "success": True,
        "data": {
            "original": text,
            "reversed": text[::-1]
        }
    }


def info_handler(args, request_context, lambda_context):
    """Return information about the Lambda execution environment."""
    return {
        "success": True,
        "data": {
            "function_name": lambda_context.function_name,
            "function_version": lambda_context.function_version,
            "memory_limit_mb": lambda_context.memory_limit_in_mb,
            "remaining_time_ms": lambda_context.get_remaining_time_in_millis(),
            "request_context": request_context,
            "received_args": args
        }
    }


def _get_artifact_content(artifact):
    """
    Extract content from an artifact dict.
    Handles base64-encoded binary content.
    """
    if not isinstance(artifact, dict):
        return str(artifact)

    content = artifact.get("content", "")
    is_binary = artifact.get("is_binary", False)

    if is_binary:
        # Decode base64 content
        return base64.b64decode(content)
    return content


def analyze_artifact_handler(args):
    """
    Analyze a single artifact and return statistics.

    Expects args:
        artifact: dict with filename, content, mime_type, etc.
    """
    artifact = args.get("artifact")
    if not artifact:
        return {
            "success": False,
            "error": "Missing 'artifact' parameter",
            "error_code": "MISSING_PARAMETER"
        }

    content = _get_artifact_content(artifact)
    filename = artifact.get("filename", "unknown")
    mime_type = artifact.get("mime_type", "application/octet-stream")

    # Calculate statistics
    if isinstance(content, bytes):
        size = len(content)
        md5_hash = hashlib.md5(content).hexdigest()
        is_text = False
        line_count = None
        word_count = None
        # Try to decode as text for preview
        try:
            text_preview = content[:200].decode("utf-8", errors="replace")
        except:
            text_preview = f"[Binary content, {size} bytes]"
    else:
        size = len(content)
        md5_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
        is_text = True
        lines = content.split("\n")
        line_count = len(lines)
        word_count = len(content.split())
        text_preview = content[:200] + ("..." if len(content) > 200 else "")

    return {
        "success": True,
        "data": {
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": size,
            "md5_hash": md5_hash,
            "is_text": is_text,
            "line_count": line_count,
            "word_count": word_count,
            "preview": text_preview,
            "version": artifact.get("version", 0),
            "metadata": artifact.get("metadata", {})
        }
    }


def compare_artifacts_handler(args):
    """
    Compare multiple artifacts and return comparison results.

    Expects args:
        artifacts: list of artifact dicts
    """
    artifacts = args.get("artifacts", [])
    if not artifacts:
        return {
            "success": False,
            "error": "Missing or empty 'artifacts' parameter",
            "error_code": "MISSING_PARAMETER"
        }

    if len(artifacts) < 2:
        return {
            "success": False,
            "error": "Need at least 2 artifacts to compare",
            "error_code": "INSUFFICIENT_ARTIFACTS"
        }

    # Analyze each artifact
    comparisons = []
    total_size = 0
    all_hashes = []

    for i, artifact in enumerate(artifacts):
        content = _get_artifact_content(artifact)
        filename = artifact.get("filename", f"artifact_{i}")

        if isinstance(content, bytes):
            size = len(content)
            md5_hash = hashlib.md5(content).hexdigest()
        else:
            size = len(content)
            md5_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

        total_size += size
        all_hashes.append(md5_hash)

        comparisons.append({
            "index": i,
            "filename": filename,
            "size_bytes": size,
            "md5_hash": md5_hash,
            "mime_type": artifact.get("mime_type", "unknown")
        })

    # Check for duplicates
    unique_hashes = set(all_hashes)
    has_duplicates = len(unique_hashes) < len(all_hashes)

    # Find duplicate pairs
    duplicate_pairs = []
    for i in range(len(all_hashes)):
        for j in range(i + 1, len(all_hashes)):
            if all_hashes[i] == all_hashes[j]:
                duplicate_pairs.append({
                    "file1": comparisons[i]["filename"],
                    "file2": comparisons[j]["filename"],
                    "hash": all_hashes[i]
                })

    return {
        "success": True,
        "data": {
            "artifact_count": len(artifacts),
            "total_size_bytes": total_size,
            "unique_files": len(unique_hashes),
            "has_duplicates": has_duplicates,
            "duplicate_pairs": duplicate_pairs,
            "artifacts": comparisons
        }
    }


def generate_file_handler(args):
    """
    Generate a single file with the specified content.

    Returns a ToolResult with the file as a DataObject that will be
    automatically saved as an artifact by the SAM framework.

    Expects args:
        filename: name for the generated file
        content_type: "text", "json", "csv", or "binary"
        data: content to include (varies by type)
    """
    filename = args.get("filename", "generated_file.txt")
    content_type = args.get("content_type", "text")
    data = args.get("data", "")
    is_binary = False

    if content_type == "text":
        content = str(data) if data else "This is generated text content.\nLine 2.\nLine 3."
        mime_type = "text/plain"
    elif content_type == "json":
        if isinstance(data, dict):
            content = json.dumps(data, indent=2)
        else:
            content = json.dumps({"generated": True, "data": data, "message": "Generated JSON"}, indent=2)
        mime_type = "application/json"
    elif content_type == "csv":
        if isinstance(data, list):
            lines = ["col1,col2,col3"]
            for row in data:
                if isinstance(row, (list, tuple)):
                    lines.append(",".join(str(x) for x in row))
                else:
                    lines.append(str(row))
            content = "\n".join(lines)
        else:
            content = "name,value,description\nitem1,100,First item\nitem2,200,Second item\nitem3,300,Third item"
        mime_type = "text/csv"
    elif content_type == "binary":
        # Generate some binary data (simple pattern)
        binary_data = bytes(range(256)) * 4  # 1KB of pattern
        content = base64.b64encode(binary_data).decode("utf-8")
        mime_type = "application/octet-stream"
        is_binary = True
    else:
        # Return error as ToolResult
        return {
            "_schema": "ToolResult",
            "_schema_version": "1.0",
            "status": "error",
            "message": f"Unknown content_type: {content_type}",
            "error_code": "INVALID_CONTENT_TYPE",
            "data": None,
            "data_objects": []
        }

    # Return ToolResult with DataObject - framework will save as artifact
    return {
        "_schema": "ToolResult",
        "_schema_version": "1.0",
        "status": "success",
        "message": f"Generated file: {filename}",
        "data": {"content_type": content_type},
        "data_objects": [
            {
                "name": filename,
                "content": content,
                "is_binary": is_binary,
                "mime_type": mime_type,
                "disposition": "artifact",
                "description": f"Generated {content_type} file",
                "preview": None,
                "metadata": {"generator": "lambda_executor_test"}
            }
        ],
        "error_code": None
    }


def generate_files_handler(args):
    """
    Generate multiple files at once.

    Returns a ToolResult with multiple DataObjects that will be
    automatically saved as artifacts by the SAM framework.

    Expects args:
        prefix: filename prefix (default: "generated")
        count: number of files to generate (default: 3)
        content_type: type of content (default: "text")
    """
    prefix = args.get("prefix", "generated")
    count = min(int(args.get("count", 3)), 10)  # Cap at 10
    content_type = args.get("content_type", "text")

    data_objects = []
    for i in range(count):
        if content_type == "text":
            filename = f"{prefix}_{i+1}.txt"
            content = f"File {i+1} of {count}\nGenerated by Lambda\nPrefix: {prefix}\n"
            mime_type = "text/plain"
        elif content_type == "json":
            filename = f"{prefix}_{i+1}.json"
            content = json.dumps({
                "file_number": i + 1,
                "total_files": count,
                "prefix": prefix,
                "data": {"value": (i + 1) * 100}
            }, indent=2)
            mime_type = "application/json"
        elif content_type == "csv":
            filename = f"{prefix}_{i+1}.csv"
            content = f"id,name,value\n{i+1},item_{i+1},{(i+1)*100}"
            mime_type = "text/csv"
        else:
            filename = f"{prefix}_{i+1}.txt"
            content = f"File {i+1}"
            mime_type = "text/plain"

        data_objects.append({
            "name": filename,
            "content": content,
            "is_binary": False,
            "mime_type": mime_type,
            "disposition": "artifact",
            "description": f"Generated {content_type} file {i+1} of {count}",
            "preview": None,
            "metadata": {"generator": "lambda_executor_test", "index": i + 1}
        })

    # Return ToolResult with multiple DataObjects
    return {
        "_schema": "ToolResult",
        "_schema_version": "1.0",
        "status": "success",
        "message": f"Generated {count} files with prefix '{prefix}'",
        "data": {"file_count": count, "prefix": prefix, "content_type": content_type},
        "data_objects": data_objects,
        "error_code": None
    }


def generate_binary_handler(args):
    """
    Generate various types of binary files for testing.

    Expects args:
        binary_type: "png", "gif", "pdf", "zip", or "random"
        filename: optional custom filename
        size: size in bytes for random data (default 1024)
    """
    binary_type = args.get("binary_type", "random")
    size = min(int(args.get("size", 1024)), 1024 * 100)  # Cap at 100KB

    if binary_type == "png":
        # Minimal valid 1x1 red PNG
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 pixel
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
            0x00, 0x00, 0x03, 0x00, 0x01, 0x00, 0x18, 0xDD,
            0x8D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,  # IEND chunk
            0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        filename = args.get("filename", "test_image.png")
        mime_type = "image/png"
        content = base64.b64encode(png_data).decode("utf-8")
        description = "Minimal 1x1 red PNG image"

    elif binary_type == "gif":
        # Minimal valid 1x1 GIF
        gif_data = bytes([
            0x47, 0x49, 0x46, 0x38, 0x39, 0x61,  # GIF89a
            0x01, 0x00, 0x01, 0x00,              # 1x1 size
            0x00, 0x00, 0x00,                    # No global color table
            0x2C, 0x00, 0x00, 0x00, 0x00,        # Image descriptor
            0x01, 0x00, 0x01, 0x00, 0x00,
            0x02, 0x01, 0x44, 0x00, 0x3B         # Image data + trailer
        ])
        filename = args.get("filename", "test_image.gif")
        mime_type = "image/gif"
        content = base64.b64encode(gif_data).decode("utf-8")
        description = "Minimal 1x1 GIF image"

    elif binary_type == "pdf":
        # Minimal valid PDF
        pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000052 00000 n
0000000101 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
166
%%EOF"""
        filename = args.get("filename", "test_document.pdf")
        mime_type = "application/pdf"
        content = base64.b64encode(pdf_content).decode("utf-8")
        description = "Minimal blank PDF document"

    elif binary_type == "zip":
        # Minimal valid empty ZIP
        zip_data = bytes([
            0x50, 0x4B, 0x05, 0x06,  # End of central directory signature
            0x00, 0x00, 0x00, 0x00,  # Disk numbers
            0x00, 0x00, 0x00, 0x00,  # Entry counts
            0x00, 0x00, 0x00, 0x00,  # Central directory size
            0x00, 0x00, 0x00, 0x00,  # Central directory offset
            0x00, 0x00              # Comment length
        ])
        filename = args.get("filename", "test_archive.zip")
        mime_type = "application/zip"
        content = base64.b64encode(zip_data).decode("utf-8")
        description = "Empty ZIP archive"

    elif binary_type == "random":
        # Generate random binary data
        import random
        random.seed(42)  # Reproducible for testing
        binary_data = bytes([random.randint(0, 255) for _ in range(size)])
        filename = args.get("filename", f"random_data_{size}b.bin")
        mime_type = "application/octet-stream"
        content = base64.b64encode(binary_data).decode("utf-8")
        description = f"Random binary data ({size} bytes)"

    else:
        return {
            "_schema": "ToolResult",
            "_schema_version": "1.0",
            "status": "error",
            "message": f"Unknown binary_type: {binary_type}. Use: png, gif, pdf, zip, or random",
            "error_code": "INVALID_BINARY_TYPE",
            "data": None,
            "data_objects": [],
        }

    return {
        "_schema": "ToolResult",
        "_schema_version": "1.0",
        "status": "success",
        "message": f"Generated {binary_type} file: {filename}",
        "data": {
            "binary_type": binary_type,
            "size_bytes": len(base64.b64decode(content)),
        },
        "data_objects": [
            {
                "name": filename,
                "content": content,
                "is_binary": True,
                "mime_type": mime_type,
                "disposition": "artifact",
                "description": description,
                "preview": f"[Binary {binary_type.upper()} file]",
                "metadata": {"generator": "lambda_executor_test", "binary_type": binary_type}
            }
        ],
        "error_code": None
    }
PYTHON_EOF

# Create the deployment package
echo "Creating deployment package..."
cd "$TEMP_DIR"
zip -q lambda_function.zip lambda_function.py

# Create IAM role trust policy
TRUST_POLICY='{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}'

# Check if role exists, create if not
echo "Setting up IAM role..."
if aws iam get-role --role-name "$ROLE_NAME" > /dev/null 2>&1; then
    echo "IAM role '$ROLE_NAME' already exists"
    ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
else
    echo "Creating IAM role '$ROLE_NAME'..."
    ROLE_ARN=$(aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document "$TRUST_POLICY" \
        --query 'Role.Arn' \
        --output text)

    # Attach basic execution policy
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

    # Wait for role to propagate
    echo "Waiting for IAM role to propagate..."
    sleep 10
fi

echo "IAM Role ARN: $ROLE_ARN"

# Check if function exists
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" > /dev/null 2>&1; then
    echo "Updating existing Lambda function..."
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file "fileb://lambda_function.zip" \
        --region "$REGION" \
        --output text > /dev/null

    FUNCTION_ARN=$(aws lambda get-function \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION" \
        --query 'Configuration.FunctionArn' \
        --output text)
else
    echo "Creating new Lambda function..."
    FUNCTION_ARN=$(aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime python3.11 \
        --role "$ROLE_ARN" \
        --handler lambda_function.lambda_handler \
        --zip-file "fileb://lambda_function.zip" \
        --timeout 30 \
        --memory-size 128 \
        --region "$REGION" \
        --query 'FunctionArn' \
        --output text)
fi

echo ""
echo "=========================================="
echo "Lambda function setup complete!"
echo "=========================================="
echo ""
echo "Function ARN: $FUNCTION_ARN"
echo "Region: $REGION"
echo ""
echo "To use in your agent config, set:"
echo "  function_arn: $FUNCTION_ARN"
echo "  region: $REGION"
echo ""
echo "Or set environment variables:"
echo "  export SAM_LAMBDA_TEST_ARN=\"$FUNCTION_ARN\""
echo "  export SAM_LAMBDA_TEST_REGION=\"$REGION\""
echo ""

# Test the function
echo "Testing Lambda function..."
TEST_PAYLOAD='{"args": {"message": "Hello from setup script!"}, "context": {"session_id": "test-session"}, "tool_config": {"operation": "echo"}}'
RESPONSE=$(aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --payload "$TEST_PAYLOAD" \
    --region "$REGION" \
    --cli-binary-format raw-in-base64-out \
    /dev/stdout 2>/dev/null | head -1)

echo "Test response: $RESPONSE"
echo ""
echo "Setup complete!"
