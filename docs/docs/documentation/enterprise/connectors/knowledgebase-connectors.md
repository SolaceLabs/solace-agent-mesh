---
title: Knowledge Base Connectors
sidebar_position: 1
---

:::info Coming Soon
Knowledge Base connectors will be available in an upcoming release.
:::

Knowledge Base connectors allow agents to retrieve context from enterprise documentation stored in cloud-based knowledge repositories.

## Overview

Knowledge Base connectors enable Retrieval-Augmented Generation (RAG) by connecting agents to organizational knowledge repositories. When users ask questions, agents search the knowledge base for relevant information and use that context to provide accurate, company-specific responses grounded in your enterprise documentation.

The connector retrieves information from knowledge bases, which can contain both unstructured documents and structured data. It returns ranked results with relevance scores to the agent. The agent's language model then synthesizes this information to generate responses based on your organizational knowledge rather than relying solely on general training data.

This reduces hallucinations and ensures agents provide answers consistent with company policies, procedures, and documentation.

## Supported Knowledge Bases

Agent Mesh Enterprise supports the following knowledge base platforms:

- Amazon Bedrock Knowledge Bases

The connector works with all Amazon Bedrock Knowledge Base configurations, regardless of the underlying data store type. Your knowledge base can contain unstructured content from sources like Amazon S3, web crawlers, Confluence, SharePoint, or Salesforce. It can also include structured data from Amazon Redshift. The connector retrieves information using the same API regardless of the source type.

## Prerequisites

Before you create an Amazon Bedrock Knowledge Base connector, ensure you have the following:

### Amazon Bedrock Knowledge Base

You need an existing Amazon Bedrock Knowledge Base configured with your enterprise documentation. The knowledge base must be set up in the Amazon Bedrock console with documents indexed and ready for retrieval.

### Knowledge Base ID

You need the unique identifier for your knowledge base. You can find this in the Amazon Bedrock console in the knowledge base details page. The ID follows the format of a random alphanumeric string such as `CIQYSFEKU3`.

### AWS Region

You need the AWS region where your knowledge base is deployed, such as `us-east-1` or `eu-west-1`. The connector must specify the correct region to communicate with the knowledge base.

### AWS Credentials or IAM Role

You need AWS authentication credentials to access the knowledge base. The connector supports two authentication methods:

**Static Credentials:** An AWS Access Key ID and Secret Access Key with permissions to retrieve from the knowledge base. Create these credentials in the AWS IAM console for a user or service account.

**IAM Role-Based Authentication:** If Agent Mesh Enterprise runs on AWS infrastructure (Amazon EKS with IRSA or EC2 with instance roles), the connector can use IAM roles without explicit credentials. This requires configuring the appropriate IAM role with knowledge base permissions and associating it with the Agent Mesh deployment.

### AWS Permissions

The AWS credentials or IAM role must have the `bedrock:Retrieve` permission for the specific knowledge base. The minimum IAM policy required is:

```json
{
  "Effect": "Allow",
  "Action": ["bedrock:Retrieve"],
  "Resource": "arn:aws:bedrock:REGION:ACCOUNT:knowledge-base/KB_ID"
}
```

Replace `REGION`, `ACCOUNT`, and `KB_ID` with your specific values.

### Network Connectivity

Ensure Agent Mesh Enterprise can reach Amazon Bedrock endpoints over the network. The connector requires HTTPS access to `https://bedrock-agent-runtime.{region}.amazonaws.com`. Verify that firewalls and security groups allow outbound traffic to this endpoint.

## Creating an Amazon Bedrock Knowledge Base Connector

You create Amazon Bedrock Knowledge Base connectors through the Connectors section in the Agent Mesh Enterprise web interface. Navigate to Connectors and click the Create Connector button to begin.

### Configuration Fields

The Amazon Bedrock Knowledge Base connector creation form requires the following information:

**Connector Name**

A unique identifier for this connector within your Agent Mesh deployment. Choose a descriptive name that indicates the knowledge base contents or purpose, such as `Company Policies KB`, `Technical Documentation KB`, or `HR Procedures KB`. This name appears in Agent Builder when you assign connectors to agents.

The connector name must be unique across all connectors in your deployment, regardless of type. You cannot change the name after creation.

**Description**

A description of what the connector should be used for. This required field helps document the connector's purpose and guides users on when to use it. The description helps the agent's language model understand when to invoke the knowledge base tool.

Example: "Search company procurement policies and supplier documentation. Use this when users ask about purchasing procedures, supplier agreements, or approval workflows."

**Knowledge Base ID**

The unique identifier of the Amazon Bedrock Knowledge Base. Find this value in the Amazon Bedrock console under your knowledge base details. The ID is a random alphanumeric string, not a descriptive name.

**AWS Region**

The AWS region where your knowledge base is deployed. Enter the region code such as `us-east-1`, `us-west-2`, or `eu-west-1`. The region must match where you created the knowledge base in AWS.

**Authentication Scheme**

The authentication method for connecting to Amazon Bedrock Knowledge Base. Select one of the following options from the dropdown:

- **AWS Access Key**: Use static AWS credentials (Access Key ID and Secret Access Key)
- **AWS IAM Role Chaining**: Use IAM role assumption for authentication

AWS IAM Role Chaining is only supported when Agent Mesh Enterprise runs on AWS infrastructure.

### AWS Access Key Authentication

When you select "AWS Access Key" as the authentication scheme, provide the following credentials:

**AWS Access Key**

The Access Key ID for AWS authentication. This credential grants the connector permission to access the knowledge base.

**AWS Secret Key**

The Secret Access Key corresponding to the Access Key ID. This field uses password masking to protect the credential value.

You should create a dedicated IAM user for the connector rather than using personal or administrative credentials. This allows you to control permissions precisely and audit connector activity through AWS CloudTrail.

### AWS IAM Role Chaining Authentication

When you select "AWS IAM Role Chaining" as the authentication scheme, provide the following configuration:

**AWS Account ID**

The AWS Account ID where the Bedrock Knowledge Base is located. This is required for IAM role assumption. The account ID is a 12-digit number such as `123456789012`.

**Role Name**

Name of the IAM role with permissions to access the Bedrock Knowledge Base. Provide just the role name, not the full ARN. Example: `BedrockKBAccessRole` or `SolaceBedrockKBAccess`.

**Session Name** (Optional)

Session name for auditing the assumed role in AWS CloudTrail logs. This field is optional and defaults to `solace-kb-session` if not specified. The session name appears in CloudTrail logs to help identify connector activity.

**External ID** (Optional)

Optional security token for cross-account access. Required if configured in the IAM role's trust policy. AWS uses this value to prevent the confused deputy problem. Use this when your knowledge base is in a different AWS account than Agent Mesh Enterprise or when required by your security policies.

:::warning
AWS IAM Role Chaining requires Agent Mesh Enterprise to run on AWS infrastructure (Amazon EKS with IRSA, EC2 with instance profiles, or other AWS-native deployments). If you deploy outside AWS and select IAM Role Chaining without proper infrastructure, authentication will fail. Use AWS Access Key authentication for non-AWS deployments.
:::

## After Creating the Connector

After you successfully create the connector, the system redirects you to the Connectors list where you can see your new connector. The connector is now available for assignment to agents.

To assign the connector to an agent, navigate to Agent Builder, create a new agent or edit an existing one, and select the connector from the available connectors list during agent configuration. You can assign the same connector to multiple agents.

For detailed information about creating and configuring agents, see [Agent Builder](../agent-builder.md).

## Security Considerations

Knowledge Base connectors implement a shared credential model where all agents assigned to a connector use the same AWS credentials and have identical access to the knowledge base.

If you assign a Knowledge Base connector to multiple agents, those agents can all access any documentation in the knowledge base. You cannot restrict one agent to HR policies and another agent to technical documentation if they share the same connector. Security boundaries exist at the AWS IAM permission level, not at the connector assignment level within Agent Mesh Enterprise.

To implement different access levels for different agents, create multiple connectors with different AWS credentials. Configure each credential set with IAM permissions that grant access to different knowledge bases or use resource-based policies in AWS to control access.

AWS credentials are stored securely in the Agent Mesh deployment infrastructure. The Secret Access Key uses the `SecretStr` type to prevent credential leakage in logs and error messages. When the connector is deployed, credentials are stored as Kubernetes secrets or environment variables depending on your deployment platform.

Users can potentially retrieve any information accessible to the connector by phrasing questions appropriately. Knowledge base content should already be appropriate for the target audience. Consider using AWS IAM policies to restrict knowledge base access to approved documentation sets.

## Troubleshooting

### Authentication Failures

If the connector fails to authenticate:

1. Verify the AWS Access Key ID and Secret Access Key are correct and not expired
2. Check that the credentials have the `bedrock:Retrieve` permission for the knowledge base
3. For IAM role-based authentication, confirm the IAM role is properly configured and associated with the Agent Mesh deployment
4. Ensure the Account ID and Role Name are correct if using role assumption
5. Verify the External ID matches what is configured in the IAM role's trust policy for cross-account scenarios

### Knowledge Base Not Found

If the connector reports that the knowledge base does not exist:

1. Verify the Knowledge Base ID is correct and matches the value in the Amazon Bedrock console
2. Check that the AWS Region matches where you created the knowledge base
3. Confirm the knowledge base is in the `Available` state in Amazon Bedrock
4. Ensure the AWS credentials have permission to access knowledge bases in the specified region

### Network Connectivity Issues

If the connector experiences network timeouts or connection errors:

1. Verify that firewalls allow outbound HTTPS traffic to Amazon Bedrock endpoints
2. Check security groups allow egress to `bedrock-agent-runtime.{region}.amazonaws.com`
3. Confirm DNS resolution works for AWS endpoints from the Agent Mesh deployment
4. Review network policies in Kubernetes if using network policy enforcement

### Empty or No Results

If the connector returns no results for queries:

1. Verify the knowledge base contains indexed documents in Amazon Bedrock
2. Check that the knowledge base synchronization completed successfully
3. Ensure the query is relevant to the knowledge base content
4. Try broader or different query terms to test retrieval
5. Review the knowledge base configuration in AWS to confirm documents are properly indexed

### Different Response Types

Knowledge bases can contain different types of data sources. Unstructured document sources return text chunks with content and S3 locations. Structured data sources like Amazon Redshift return rows with column names and values.

The connector handles both response types transparently. However, you should configure the Tool Description to help the language model understand what type of information the knowledge base provides. This helps the model interpret the results correctly when generating responses.
