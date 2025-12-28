#!/bin/bash
# Cleanup script for SAM Lambda Executor test function
#
# Prerequisites:
#   - AWS CLI installed
#   - AWS credentials configured (e.g., source ~/bin/set-aws-auth)
#
# Usage:
#   ./cleanup-lambda.sh [region]
#
# This script removes the Lambda function and IAM role created by setup-lambda.sh

set -e

REGION="${1:-ca-central-1}"
FUNCTION_NAME="sam-lambda-executor-test"
ROLE_NAME="sam-lambda-executor-test-role"

echo "Cleaning up Lambda executor test resources in region: $REGION"

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "Error: AWS credentials not configured. Run 'source ~/bin/set-aws-auth' first."
    exit 1
fi

# Delete Lambda function
echo "Deleting Lambda function '$FUNCTION_NAME'..."
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" > /dev/null 2>&1; then
    aws lambda delete-function \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION"
    echo "Lambda function deleted."
else
    echo "Lambda function '$FUNCTION_NAME' not found (already deleted?)."
fi

# Detach policies and delete IAM role
echo "Cleaning up IAM role '$ROLE_NAME'..."
if aws iam get-role --role-name "$ROLE_NAME" > /dev/null 2>&1; then
    # List and detach all attached policies
    ATTACHED_POLICIES=$(aws iam list-attached-role-policies \
        --role-name "$ROLE_NAME" \
        --query 'AttachedPolicies[].PolicyArn' \
        --output text)

    for POLICY_ARN in $ATTACHED_POLICIES; do
        echo "Detaching policy: $POLICY_ARN"
        aws iam detach-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-arn "$POLICY_ARN"
    done

    # Delete inline policies if any
    INLINE_POLICIES=$(aws iam list-role-policies \
        --role-name "$ROLE_NAME" \
        --query 'PolicyNames' \
        --output text)

    for POLICY_NAME in $INLINE_POLICIES; do
        echo "Deleting inline policy: $POLICY_NAME"
        aws iam delete-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-name "$POLICY_NAME"
    done

    # Delete the role
    aws iam delete-role --role-name "$ROLE_NAME"
    echo "IAM role deleted."
else
    echo "IAM role '$ROLE_NAME' not found (already deleted?)."
fi

echo ""
echo "=========================================="
echo "Cleanup complete!"
echo "=========================================="
