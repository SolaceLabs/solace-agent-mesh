---
title: Agent Builder
sidebar_position: 10
---

# Agent Builder

Agent Builder provides a visual, form-based interface for creating and managing agents without writing configuration files. This tool simplifies agent creation by optionally leveraging AI assistance to suggest initial configuration values based on a description of the agent.

## Overview

When you click the "Create Agent" button from the Agents page (requiring the `sam:agent_builder:create` capability to view, see Access Control) a dialog appears offering optional AI assistance. You can either describe what you want the agent to do in natural language (10-1000 characters), and the AI will generate initial configuration values, or you can skip this step and manually enter basic information.

Once you've configured the agent in the form and saved it, the agent appears in the Inactive tab with `Not Deployed` status, ready for further editing or deployment.

Use the "Refresh" button next to "Create Agent" to update the displayed agent list and sync deployment status information from the backend.

## Optional AI Assistance

When you click "Create Agent" from the Agents page, the AI assistance dialog opens by default. This dialog provides two options for how to begin configuring your agent.

**Option 1: Use AI to suggest initial values**

Provide a natural language description of what you want the agent to do. This description should be between 10 and 1000 characters and should explain the agent's purpose, the types of tasks it will handle, and any specific capabilities it needs. For example:

- "An agent that helps users search company documentation and answer questions about internal policies"
- "An agent that analyzes sales data and generates reports"
- "An agent that assists with employee onboarding by answering HR-related questions"

When you submit your description, the AI analyzes it and generates suggested values for:

- A unique agent name derived from your description
- A detailed description field explaining the agent's purpose
- System instructions that define how the agent should behave
- Appropriate toolsets based on the capabilities mentioned in your description
- Appropriate connectors (if available, see Connectors) based on your description
- Default settings for skills and communication modes

These AI-generated values are suggestions only. After the AI generates them, you proceed to the configuration form where you can review, modify, or completely rewrite any of these values before saving the agent. 

**Option 2: Skip AI assistance**

Click the secondary button to bypass AI assistance. You'll be prompted to manually enter the agent's name and description in a simple dialog. After providing these basic details and clicking continue, you proceed to the agent configuration form where the Agent Details section is pre-filled with your entered name and description. Other sections (instructions, toolsets, connectors, agent card) remain empty for you to configure. Minimally, the name, description and instructions must be completed before your agent can be deployed (see Agent Lifecycle and Management).

## Agent Configuration Form

The agent configuration form is where you configure all agent settings. You have complete control to manually configure or refine every setting, whether you're working with AI-generated suggestions or entering values from scratch.

### Agent Details

Agent details form the foundation of your agent configuration:

**Name**: Choose a unique name between 3 and 40 characters that identifies the agent's purpose. Names must be unique across your deployment. If you used AI assistance, review the suggested name and modify it if needed.

**Description**: Write a description between 10 and 1000 characters that explains what the agent does and when users should interact with it.

### Instructions

Instructions define how the agent behaves during interactions. This field is between 100 and 10,000 characters and is the basis of the agent system prompt. The instructions should explain the agent's role, communication style, and any specific rules or constraints it should follow.

For example, you might instruct an agent to:
- Always provide sources for information
- Maintain a formal or casual tone
- Follow specific steps when handling requests
- Apply particular business rules or constraints

If you used AI assistance, the system generates initial instructions based on your description. Review these carefully and modify them to match your exact requirements. The AI makes its best judgment, but you should verify the instructions align with your needs.

### Toolsets

Toolsets provide the agent with capabilities it can use to accomplish tasks. Select from available toolsets such as:

- `Artifact Management` to list, read, create, update and delete artifacts
- `Data Analysis` to query, transform and visualize data from artifacts
- `Web` to perform internet searches

You can assign multiple toolsets to a single agent, giving it access to diverse capabilities. If you select `Data Analysis`, include `Artifact Management` as well.

If you used AI assistance, the system suggests toolsets based on your description. Review these selections and add or remove toolsets as needed to match your agent's actual requirements.

### Connectors

Connectors link agents to external data sources like SQL databases. You can assign connectors that were previously created in the Connectors section. Each connector provides access to a specific database with configured credentials.

**Important**: All agents sharing a connector use the same database credentials. Implement database-level access controls to restrict what each agent can access. The system supports MySQL, PostgreSQL, and MariaDB connectors.

Connectors must be created separately before they can be assigned to agents. See [Working with SQL Connectors](#working-with-sql-connectors) for detailed information on creating and configuring database connectors.

### Agent Card

Agent card configuration defines how the agent presents itself and communicates:

**Skills**: Specify what tasks the agent can perform. This helps users and other agents understand your agent's capabilities.

**Communication Modes**: Select how the agent interacts, such as text-based interaction or voice capabilities.

### Saving the Agent

After configuring all settings, save the agent. It will appear in the Inactive tab with `Not Deployed` status, where you can:
- Further edit the configuration
- Download it as a YAML file
- Deploy it to make it available for use in Chat

## Working with SQL Connectors

SQL connectors enable agents to query and analyze database information using natural language. These connectors convert user questions into SQL queries, execute them, and return results in a conversational format.

Before assigning connectors to agents, create them in the Connectors section of the interface. Each connector configuration includes:

- Database type (MySQL, PostgreSQL, or MariaDB)
- Connection details (host, port, database name)
- Authentication credentials (username and password)

Once created, connectors become available for assignment to any agent. This reusability means you can connect multiple agents to the same database without duplicating connection configuration.

**Security Considerations** are critical when using SQL connectors. The framework does not sandbox database access at the agent level. All agents assigned to a connector share the same database credentials and permissions. This means:

- Any agent with the connector can access all data the connector's credentials permit
- Database-level access control is your primary security mechanism
- You should create database users with minimal necessary privileges
- Consider using database views or restricted schemas to limit what agents can access
- Audit database queries to monitor what agents are accessing

The natural language to SQL conversion capability makes databases accessible through conversation, but this also means users can potentially request any data the connector can access. Plan your database permissions accordingly and consider what information should be available through agent interactions.

Each agent can be assigned a maximum of 5 connectors. This limit helps manage complexity and prevent performance issues.

## Agent Lifecycle and Management

Agents move through distinct states as you create, edit, and deploy them.

**Not Deployed** is the initial status for newly created agents. These agents appear in the Inactive tab where you can edit their configurations, download them as YAML files, or prepare them for deployment. Agents remain in this status until you explicitly deploy them.

**Deploying/Undeploying** are the in progress statuses when an agent is deploying or undeploying an agent. It's recommended not interact with an agent when its in this transitory state.

**Running** agents move to the Active tab and become available for user interactions. Once deployed, agents cannot be deleted—you must undeploy them first to remove them from the system.

**Deployment Failed** is displayed if your agent failed to deployed

**Sync Status** tracking helps you manage configuration drift for deployed agents. When you deploy an agent, the system records its configuration. If you later edit the agent's configuration in the UI, the system detects this mismatch and will continue to display the `Running` agent in the active section and display the updated agent in the inactive section. Both tiles will display with `Undeployed changes`. This visibility helps you understand when deployed agents don't match their stored configurations, though the specific synchronization mechanism depends on your deployment approach. The `Preview Updates` action surfaced in the agent side panel can help compare the running agent with its undeployed configuration.

You can edit agent configurations (of agents built with agent builder) at any time, whether they're deployed or not. Changes to deployed agents may require redeployment to take effect, depending on your deployment method.

Downloading agents as YAML files provides portability and version control. You can use these files to:

- Back up agent configurations
- Share configurations between deployments
- Track configuration changes in version control systems
- Deploy agents using infrastructure-as-code tools

## Configuration Validation and Constraints

The system enforces several validation rules to ensure agent configurations remain functional.

**Name Uniqueness** is enforced across all agents in your deployment. If you attempt to create an agent with a name that already exists, the system rejects it. This prevents confusion and ensures each agent has a distinct identifier.

**Field Length Constraints** ensure configurations remain manageable:
- Agent names: 3-40 characters
- Agent descriptions: 10-1000 characters
- System instructions: 100-10,000 characters (optional)
- AI-assisted descriptions: 10-1000 characters

**Deletion Restrictions** prevent accidentally removing active agents. You cannot delete deployed agents directly. You must first undeploy them, which moves them back to `Not Deployed` status in the Inactive tab, and then you can delete them. This two-step process helps prevent service disruptions.

**Connector Limits**: Each agent can have a maximum of 5 connectors. This restriction helps manage complexity and prevents performance issues that could arise from agents attempting to connect to too many databases simultaneously.

## Troubleshooting Common Issues

Several common situations may require attention when working with Agent Builder.

If the agent list or deployment status appears out of date, click the "Refresh" button next to "Create Agent" to sync the latest information from the backend. This is particularly useful after deploying or undeploying agents, or when checking whether deployment operations have completed.

If AI-generated suggestions don't match your requirements, remember that AI assistance only provides initial values. You have full control in the configuration form to modify or completely rewrite any AI-generated content. For better AI suggestions, provide clear, specific descriptions. Vague descriptions like "a helpful agent" produce generic suggestions, while specific descriptions like "an agent that searches company documentation and provides answers with citations" generate more targeted initial values.

When connector assignment fails, verify that:
- The connector was created successfully in the Connectors section
- The connector's database connection is functional
- You haven't exceeded the per-agent connector limit
- The connector type matches your requirements (MySQL, PostgreSQL, or MariaDB)

Note: Agent Mesh does not validate the connector configuration. If the connector was assigned but not functioning, verify this configuration.

If you cannot delete an agent, check its deployment status. Only agents in `Not Deployed` status can be deleted. If the agent is running, you must undeploy it first.

When deployed agents show as having `Undeployed changes`, this indicates the stored configuration differs from the deployed configuration. Review recent changes to the agent's settings and consider redeploying to apply those changes.

Name uniqueness errors occur when attempting to create or rename an agent using a name that already exists. Choose a different name or modify the existing agent instead of creating a new one.