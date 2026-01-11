#!/bin/bash
#
# Setup script for the streaming Lambda example.
#
# This script:
# 1. Creates an ECR repository
# 2. Builds and pushes the container image
# 3. Creates an IAM role for Lambda execution
# 4. Creates the Lambda function
# 5. Configures a Function URL with IAM authentication
#
# Prerequisites:
# - AWS CLI configured with appropriate credentials
# - Docker or Podman installed and running
# - Run from the repository root directory
#
# Usage:
#   ./examples/agents/lambda-executor-streaming/setup-streaming-lambda.sh
#

set -e

# Configuration
FUNCTION_NAME="sam-streaming-example"
ECR_REPO_NAME="sam-streaming-example"
ROLE_NAME="sam-streaming-example-role"
REGION="${AWS_REGION:-us-east-1}"
MEMORY_SIZE=512
TIMEOUT=120

# Auto-detect container runtime (docker or podman)
if command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
elif command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
else
    echo "Error: Neither docker nor podman found. Please install one of them."
    exit 1
fi

echo "=== SAM Streaming Lambda Example Setup ==="
echo "Container runtime: $CONTAINER_CMD"
echo "Region: $REGION"
echo "Function: $FUNCTION_NAME"
echo ""

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account: $ACCOUNT_ID"

# ECR repository URI
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}"

# Step 1: Create ECR repository (if it doesn't exist)
echo ""
echo "=== Step 1: Creating ECR repository ==="
if aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "ECR repository already exists: $ECR_REPO_NAME"
else
    aws ecr create-repository \
        --repository-name "$ECR_REPO_NAME" \
        --region "$REGION" \
        --image-scanning-configuration scanOnPush=true
    echo "Created ECR repository: $ECR_REPO_NAME"
fi

# Try to set ECR repository policy to allow Lambda to pull images
# This may fail if user doesn't have SetRepositoryPolicy permission
echo "Setting ECR repository policy for Lambda access..."
ECR_POLICY='{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "LambdaECRImageRetrievalPolicy",
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": [
                "ecr:BatchGetImage",
                "ecr:GetDownloadUrlForLayer"
            ],
            "Condition": {
                "StringLike": {
                    "aws:sourceArn": "arn:aws:lambda:'"$REGION"':'"$ACCOUNT_ID"':function:*"
                }
            }
        }
    ]
}'

if aws ecr set-repository-policy \
    --repository-name "$ECR_REPO_NAME" \
    --policy-text "$ECR_POLICY" \
    --region "$REGION" >/dev/null 2>&1; then
    echo "ECR policy set for Lambda access"
else
    echo "Warning: Could not set ECR repository policy (may already be set or lack permission)"
fi

# Step 2: Build and push container image
echo ""
echo "=== Step 2: Building and pushing container image ==="

# Login to ECR
aws ecr get-login-password --region "$REGION" | $CONTAINER_CMD login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.${REGION}.amazonaws.com"

# Build the image (from repo root)
echo "Building container image..."
$CONTAINER_CMD build -f examples/agents/lambda-executor-streaming/Dockerfile -t "$ECR_REPO_NAME" .

# Tag and push
$CONTAINER_CMD tag "$ECR_REPO_NAME:latest" "$ECR_URI:latest"
echo "Pushing image to ECR..."
$CONTAINER_CMD push "$ECR_URI:latest"
echo "Image pushed: $ECR_URI:latest"

# Step 3: Create IAM role (if it doesn't exist)
echo ""
echo "=== Step 3: Creating IAM role ==="

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

if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    echo "IAM role already exists: $ROLE_NAME"
else
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document "$TRUST_POLICY"

    # Attach basic Lambda execution policy
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

    # Attach ECR read-only policy for pulling container images
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"

    echo "Created IAM role: $ROLE_NAME"
    echo "Waiting for role to propagate..."
    sleep 10
fi

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

# Step 4: Create or update Lambda function
echo ""
echo "=== Step 4: Creating/updating Lambda function ==="

if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "Updating existing Lambda function..."
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --image-uri "$ECR_URI:latest" \
        --region "$REGION"
else
    echo "Creating new Lambda function..."
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --package-type Image \
        --code ImageUri="$ECR_URI:latest" \
        --role "$ROLE_ARN" \
        --memory-size "$MEMORY_SIZE" \
        --timeout "$TIMEOUT" \
        --region "$REGION"
fi

# Wait for function to be active
echo "Waiting for function to be active..."
aws lambda wait function-active --function-name "$FUNCTION_NAME" --region "$REGION"
echo "Lambda function is active: $FUNCTION_NAME"

# Step 5: Create Function URL with IAM auth
echo ""
echo "=== Step 5: Creating Function URL ==="

# Check if Function URL exists
EXISTING_URL=$(aws lambda get-function-url-config --function-name "$FUNCTION_NAME" --region "$REGION" 2>/dev/null | jq -r '.FunctionUrl' || echo "")

if [ -n "$EXISTING_URL" ] && [ "$EXISTING_URL" != "null" ]; then
    echo "Function URL already exists: $EXISTING_URL"
    FUNCTION_URL="$EXISTING_URL"
else
    # Create Function URL with IAM authentication and streaming
    FUNCTION_URL=$(aws lambda create-function-url-config \
        --function-name "$FUNCTION_NAME" \
        --auth-type AWS_IAM \
        --invoke-mode RESPONSE_STREAM \
        --region "$REGION" \
        --query 'FunctionUrl' \
        --output text)
    echo "Created Function URL: $FUNCTION_URL"
fi

# Summary
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Function URL: $FUNCTION_URL"
echo ""
echo "To use this in your SAM agent config, set the environment variable:"
echo ""
echo "  export SAM_LAMBDA_STREAMING_URL=\"$FUNCTION_URL\""
echo ""
echo "Then run your agent with:"
echo ""
echo "  sam run examples/agents/lambda-executor-streaming/lambda_streaming_example.yaml"
echo ""
echo "Test prompt: 'Process the message hello with 5 steps'"
echo ""
