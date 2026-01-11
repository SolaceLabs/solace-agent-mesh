#!/bin/bash
#
# Cleanup script for the streaming Lambda example.
#
# This script removes all AWS resources created by setup-streaming-lambda.sh:
# - Lambda function and Function URL
# - ECR repository and images
# - IAM role and policies
#
# Usage:
#   ./examples/agents/lambda-executor-streaming/cleanup-streaming-lambda.sh
#

set -e

# Configuration (must match setup script)
FUNCTION_NAME="sam-streaming-example"
ECR_REPO_NAME="sam-streaming-example"
ROLE_NAME="sam-streaming-example-role"
REGION="${AWS_REGION:-us-east-1}"

echo "=== SAM Streaming Lambda Example Cleanup ==="
echo "Region: $REGION"
echo ""
echo "This will delete:"
echo "  - Lambda function: $FUNCTION_NAME"
echo "  - ECR repository: $ECR_REPO_NAME"
echo "  - IAM role: $ROLE_NAME"
echo ""
read -p "Are you sure you want to proceed? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Step 1: Delete Lambda function (this also deletes the Function URL)
echo ""
echo "=== Step 1: Deleting Lambda function ==="
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
    # Delete Function URL first (if exists)
    aws lambda delete-function-url-config --function-name "$FUNCTION_NAME" --region "$REGION" 2>/dev/null || true

    # Delete the function
    aws lambda delete-function --function-name "$FUNCTION_NAME" --region "$REGION"
    echo "Deleted Lambda function: $FUNCTION_NAME"
else
    echo "Lambda function not found: $FUNCTION_NAME"
fi

# Step 2: Delete ECR repository
echo ""
echo "=== Step 2: Deleting ECR repository ==="
if aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" --region "$REGION" >/dev/null 2>&1; then
    # Force delete (removes all images)
    aws ecr delete-repository \
        --repository-name "$ECR_REPO_NAME" \
        --region "$REGION" \
        --force
    echo "Deleted ECR repository: $ECR_REPO_NAME"
else
    echo "ECR repository not found: $ECR_REPO_NAME"
fi

# Step 3: Delete IAM role
echo ""
echo "=== Step 3: Deleting IAM role ==="
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    # Detach all policies first
    POLICIES=$(aws iam list-attached-role-policies --role-name "$ROLE_NAME" --query 'AttachedPolicies[].PolicyArn' --output text)
    for POLICY_ARN in $POLICIES; do
        aws iam detach-role-policy --role-name "$ROLE_NAME" --policy-arn "$POLICY_ARN"
        echo "Detached policy: $POLICY_ARN"
    done

    # Delete the role
    aws iam delete-role --role-name "$ROLE_NAME"
    echo "Deleted IAM role: $ROLE_NAME"
else
    echo "IAM role not found: $ROLE_NAME"
fi

echo ""
echo "=== Cleanup Complete ==="
