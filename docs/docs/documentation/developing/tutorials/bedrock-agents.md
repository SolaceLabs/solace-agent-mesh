---
title: Amazon Bedrock Agents
sidebar_position: 30
toc_max_heading_level: 4
---

# Amazon Bedrock Agents Integration

This tutorial walks you through the process of integrating Amazon Bedrock Agents and Flows into Agent Mesh. This integration allows you to create agents that can interact with one or multiple Bedrock Agents or Flows, extending your Agent Mesh project with powerful AI capabilities from AWS.

## What are Amazon Bedrock Agents and Flows?

Amazon Bedrock Agents are AI assistants that can be customized to perform specific tasks using foundation models (FMs). They can connect to enterprise systems and data sources, allowing them to take actions on behalf of users.

Amazon Bedrock Flows are visual workflows that orchestrate multiple foundation models to solve complex problems. They allow you to chain together different AI capabilities without writing code.

By integrating these services with Agent Mesh, you can:
- Use the extensible Agent Mesh framework to combine Bedrock agents and flows with other agents.
- Create conversational interfaces that leverage Bedrock agents and flows.
- Connect your Agent Mesh agents to enterprise data sources through Bedrock.
- Maintain a consistent experience across different agent providers by centralizing them in Agent Mesh.

:::info[Learn about Bedrock Agents and Flows]
Check the official documentation for [Amazon Bedrock Agents](https://aws.amazon.com/bedrock/agents/) and [Amazon Bedrock Flows](https://aws.amazon.com/bedrock/flows/) to learn more about these features.
:::


## Setting Up the Environment

### Create Bedrock Agents and Flows

Follow these steps to create your Bedrock resources:

1. **Log in to your AWS console**
   - Navigate to the Amazon Bedrock service

2. **Create Bedrock Agents**
   - Go to the **Agents** tab in the Bedrock console
   - Click "Create agent"
   - Follow the wizard to configure your agent:
     - Select a foundation model
     - Define the agent's instructions
     - Configure knowledge bases (optional)
     - Set up action groups (if needed)
   - Once created, **create an alias** for your agent by selecting it and clicking "Create alias"
   - **Copy the Agent ID and Alias ID** from the agent details page - you'll need these for the Agent Mesh configuration

3. **Create Bedrock Flows**
   - Go to the **Flows** tab in the Bedrock console
   - Click "Create flow"
   - Use the visual editor to design your flow
   - Connect nodes to create your workflow
   - Test and publish your flow
   - **Create an alias** for your flow
   - **Copy the Flow ID and Alias ID** - you'll need these for the Agent Mesh configuration

4. **Set up IAM permissions**
   - Ensure your IAM user or role has the following permissions:
     - `bedrock:InvokeAgent`
     - `bedrock:InvokeFlow`
     - Any other permissions required by your specific Bedrock configuration

### Create an Agent Mesh Project

You must [install Agent Mesh and Solace Mesh Agent CLI](../../installing-and-configuring/installation.md), and then you'll want to [create a new Agent Mesh project](../../installing-and-configuring/run-project.md).


## Integrating Bedrock with Agent Mesh

### Adding the Bedrock Agent Plugin

The `sam-bedrock-agent` plugin from the [solace-agent-mesh-core-plugins](https://github.com/SolaceLabs/solace-agent-mesh-core-plugins/tree/main/sam-bedrock-agent) repository creates a bridge between Agent Mesh and Amazon Bedrock services. This plugin allows your Agent Mesh agents to invoke Bedrock Agents and Flows as tools.

1. **Add the plugin to your Agent Mesh project**:

```sh
sam plugin add aws-agent --plugin sam-bedrock-agent
```

Replace `aws-agent` with a descriptive name for your agent, such as `bedrock-summarizer` or `bedrock-customer-service`.

This command:
- Installs the `sam-bedrock-agent` plugin
- Creates a new agent configuration file in `configs/agents/aws-agent.yaml`


2. **Locate the configuration file**:

The command creates an `aws-agent.yaml` file in the `configs/agents/` directory of your Agent Mesh project.

:::tip[Naming Convention]
Choose a descriptive name that reflects the purpose of your Bedrock integration. This name is used to reference the agent in your Agent Mesh project.
:::

## Configuring the Bedrock Agent

The configuration file you created needs to be edited to connect to your specific Amazon Bedrock resources. This section explains each part of the configuration and how to customize it.

### Understanding the Configuration Structure

Open the `aws-agent.yaml` file in your editor. The core of the agent's configuration consists of:

1. **amazon_bedrock_runtime_config**: AWS connection settings
2. **tools**: List of Bedrock agents and flows to expose as tools
3. **agent_card**: Agent capabilities and skills definition

### Example Configuration

Here's an annotated example based on the actual plugin structure:

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: aws-agent.log

!include ../shared_config.yaml

apps:
  - name: aws-agent-app
    app_base_path: . 
    app_module: solace_agent_mesh.agent.sac.app 
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE} 
      supports_streaming: true 
      agent_name: "AwsAgent" 
      display_name: "AwsAgent Component" 
      model: *general_model 

      instruction: |
        You're AwsAgent responsible for handling user queries by 
        interacting with Amazon Bedrock agents or flows.

      # AWS Connection Configuration
      amazon_bedrock_runtime_config: &amazon_bedrock_runtime_config
        endpoint_url: # Optional: Custom AWS endpoint URL
        boto3_config:
          region_name: "us-east-1" # AWS region where your Bedrock resources are located
          aws_access_key_id: # Your AWS access key (or use profiles/env vars)
          aws_secret_access_key: # Your AWS secret key

      tools:
        # Bedrock Agent Tool
        - tool_type: python
          component_module: sam_bedrock_agent.bedrock_agent
          component_base_path: . 
          function_name: invoke_bedrock_agent
          tool_name: "text_transformer" # Customizable, Name exposed to the LLM
          tool_description: "Transforms text using the Text Transformer agent which summarizes the given text and extracts key points." # Customizable, Optional description
          tool_config:
            amazon_bedrock_runtime_config: *amazon_bedrock_runtime_config
            bedrock_agent_id: "XXXXXXXXXX" # Your actual Bedrock agent ID
            bedrock_agent_alias_id: "XXXXXXXXXX" # Your actual Bedrock agent alias ID
            allow_files: true # Whether to allow file uploads (5 files, 10MB total max)

        # Bedrock Flow Tool
        - tool_type: python
          component_module: sam_bedrock_agent.bedrock_flow
          component_base_path: .
          function_name: invoke_bedrock_flow
          tool_name: "poem_writer" # Name exposed to the LLM
          tool_config: 
            amazon_bedrock_runtime_config: *amazon_bedrock_runtime_config
            bedrock_flow_id: "XXXXXXXXXX" # Your actual Bedrock flow ID
            bedrock_flow_alias_id: "XXXXXXXXXX" # Your actual Bedrock flow alias ID

      # Agent capabilities
      agent_card:
        description: "Agent that integrates with Amazon Bedrock agents and flows for various AI tasks."
        defaultInputModes: ["text"]
        defaultOutputModes: ["text"]
        skills: 
          - id: "text_transformer"
            name: "Text Transformer"
            description: "Transforms text using the Text Transformer agent."
          - id: "poem_writer"
            name: "Poem Writer"
            description: "Generates poems based on user input."

      # A2A Protocol settings
      agent_card_publishing: { interval_seconds: 10 }
      agent_discovery: { enabled: true }
      inter_agent_communication:
        allow_list: ["*"]
        request_timeout_seconds: 30
```

### Customizing Your Configuration

Follow these steps to customize your configuration:

1. **Configure AWS Connection**:
   - Set the `region_name` to the AWS region where your Bedrock resources are located
   - Choose one of these authentication methods:
     - Set `aws_access_key_id` and `aws_secret_access_key` directly in the config.
     - Use AWS profiles by removing these fields and configuring your AWS CLI profile.
     - Use environment variables (see Environment Variables section below).

Check the [boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html) for more details.

2. **Configure Bedrock Agent Tools**:
   - For each Bedrock agent you want to expose, add a tool entry:
     - Set a descriptive `tool_name` (for example, `text_summarizer`, `content_generator`).
     - Provide a clear `tool_description` of what the agent does.
     - Replace `bedrock_agent_id` with your actual Bedrock agent ID.
     - Replace `bedrock_agent_alias_id` with your actual Bedrock agent alias ID.
     - Set `allow_files` to `true` if your agent can process file uploads.

3. **Configure Bedrock Flow Tools**:
   - For each Bedrock flow you want to expose, add a tool entry:
     - Set a descriptive `tool_name` for the flow.
     - Provide a clear `tool_description` of what the flow does (optional).
     - Replace `bedrock_flow_id` with your actual Bedrock flow ID.
     - Replace `bedrock_flow_alias_id` with your actual Bedrock flow alias ID.

4. **Update Agent Card Skills**:
   - Update the `agent_card.description` to reflect the purpose of your Bedrock agent (This is what other agents see).
   - For each tool you add, create a corresponding skill entry in the `agent_card.skills` section.
   - Use the same `id` as the `tool_name`.
   - Provide a user-friendly `name` and `description`.

5. **Update Agent Instructions**:
   - Modify the `instruction` field to provide clear guidance on how the agent should respond to user queries.
   - This instruction is used by the Agent's LLM to understand its role and capabilities.

:::info
You must provide at least one Bedrock agent or flow tool. You can mix and match agents and flows in the same configuration.
:::

### Environment Variables

The Bedrock agent integration requires standard Solace connection variables and can use AWS environment variables for authentication.

#### Required Solace Variables:
- **SOLACE_BROKER_URL**: URL of your Solace broker
- **SOLACE_BROKER_USERNAME**: Username for Solace broker authentication
- **SOLACE_BROKER_PASSWORD**: Password for Solace broker authentication
- **SOLACE_BROKER_VPN**: Solace message VPN name
- **SOLACE_AGENT_MESH_NAMESPACE**: Namespace for your Agent Mesh project

#### Optional AWS Variables:
If you prefer to use environment variables for AWS authentication instead of configuration in the YAML file:
- **AWS_ACCESS_KEY_ID**: Your AWS access key
- **AWS_SECRET_ACCESS_KEY**: Your AWS secret key
- **AWS_SESSION_TOKEN**: If using temporary credentials
- **AWS_REGION** or **AWS_DEFAULT_REGION**: AWS region for Bedrock services

:::tip[AWS Credentials Precedence]
AWS credentials are loaded in this order:
1. Explicit credentials in the YAML configuration
2. Environment variables
3. AWS configuration files (~/.aws/credentials)
4. EC2/ECS instance profiles (if running on AWS)
:::

## Running and Testing Your Integration

### Starting Your Agent Mesh Project

After configuring your Bedrock agent integration, run your Agent Mesh project:

```sh
sam run configs/agents/aws-agent.yaml
```

This command starts the Bedrock agent with your specific configuration.

### Testing the Integration

You can test your Bedrock agent integration through any gateway in your Agent Mesh project:

#### Using the Web UI Gateway

1. Ensure you have a Web UI gateway running (typically at http://localhost:8000)
2. Start a conversation with your agent
3. Ask a question that would trigger your Bedrock agent or flow

**Example**: If you configured a Bedrock agent for text transformation:
```
Transform this text: "The quick brown fox jumps over the lazy dog. The lazy dog did not chase the fox. The fox was brown and quick, while the dog was lazy and slow. Despite their differences, they both enjoyed the sunny day in the meadow."
```

**Example**: If you configured a Bedrock flow for poem writing:
```
Write a poem about a sunset over the ocean.
```

#### Testing with File Uploads

If you have enabled file uploads for your Bedrock agent (`allow_files: true`), you can test file processing:

1. In the Web UI, use the file upload button to attach a supported file
2. Include a prompt that references the file, such as "Analyze this document" or "Summarize the content of this file"
3. The file is sent to the Bedrock agent along with your prompt

**Example with file upload**:
```
Please analyze the attached document and provide key insights.
```

:::info[Supported File Types]
Bedrock agents support these file types for uploads:
- PDF documents (.pdf)
- Text files (.txt)
- Word documents (.doc, .docx)
- CSV files (.csv)
- Excel spreadsheets (.xls, .xlsx)

There's a limit of 5 files with a total size of 10MB per request.
:::

## Troubleshooting

### Common Issues and Solutions

#### Authentication Errors

**Issue**: "Unable to locate credentials" or "Access denied" errors
**Solution**:
- Verify your AWS credentials are correctly configured
- Check that your IAM user/role has the necessary permissions
- Try using AWS CLI to test your credentials: `aws bedrock list-foundation-models`

#### Configuration Errors

**Issue**: "Invalid agent ID" or "Invalid flow ID" errors
**Solution**:
- Double-check your Bedrock agent and flow IDs in the configuration
- Ensure you've created aliases for your agents and flows
- Verify the region in your configuration matches where your Bedrock resources are located

#### Connection Issues

**Issue**: Agent Mesh can't connect to Bedrock services
**Solution**:
- Check your network connectivity
- Verify that Bedrock services are available in your configured region
- Check for any VPC or firewall restrictions

#### File Upload Issues

**Issue**: Files aren't being processed by the Bedrock agent
**Solution**:
- Verify `allow_files` is set to `true` in your configuration
- Check that your file type is supported
- Ensure the file size is under the 10MB limit
- Check the model context length
