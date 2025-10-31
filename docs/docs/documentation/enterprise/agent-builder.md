---
title: Agent Builder
sidebar_position: 10
---

# Agent Builder

Agent Builder provides a visual, form-based interface for creating and managing agents without writing configuration files. This tool simplifies agent creation by offering optional AI assistance that suggests initial configuration values based on a description of the agent you want to build.

## Overview

When you click the "Create Agent" button from the Agents page (which requires the `sam:agent_builder:create` capability), a dialog appears that offers optional AI assistance. You can describe what you want the agent to do in natural language (between 10 and 1000 characters), and the AI generates initial configuration values for you to review and modify. Alternatively, you can skip this step and manually enter all configuration details yourself.

After you configure the agent in the form and save it, the agent appears in the Inactive tab with `Not Deployed` status. At this point, you can further edit the configuration, download it as a YAML file, or deploy it to make it available for use in Chat.

Use the "Refresh" button next to "Create Agent" to update the displayed agent list and sync deployment status information from the backend. For more information about access control, see Access Control.

## Creating Agents

When you click "Create Agent" from the Agents page, the AI assistance dialog opens by default. This dialog provides two paths for beginning your agent configuration.

### Using AI to Suggest Initial Values

You can provide a natural language description of what you want the agent to do. This description should be between 10 and 1000 characters and should explain the agent's purpose, the types of tasks it handles, and any specific capabilities it needs. For example:

- "An agent that helps users search company documentation and answer questions about internal policies"
- "An agent that analyzes sales data and generates reports"
- "An agent that assists with employee onboarding by answering HR-related questions"

When you submit your description, the AI analyzes it and generates suggested values for several configuration fields. The AI creates a unique agent name derived from your description, writes a detailed description field explaining the agent's purpose, and drafts system instructions that define how the agent should behave. The AI also suggests appropriate toolsets based on the capabilities mentioned in your description and recommends connectors if they match your needs. Finally, it provides default settings for skills and communication modes.

These AI-generated values serve as suggestions only. After the AI generates them, you proceed to the configuration form where you can review, modify, or completely rewrite any of these values before saving the agent. The AI makes its best judgment based on your description, but you retain complete control over the final configuration.

For more information about connectors, see [Connectors](#connectors).

### Skipping AI Assistance

You can click the secondary button to bypass AI assistance entirely. The system prompts you to manually enter the agent's name and description in a simple dialog. After you provide these details and click continue, you proceed to the agent configuration form where the Agent Details section is pre-filled with your entered name and description. Other sections (instructions, toolsets, connectors, and agent card) remain empty for you to configure manually. At minimum, you must complete the name, description, and instructions before your agent can be deployed.

For more information about deployment requirements, see [Agent Lifecycle and Management](#agent-lifecycle-and-management).

## Agent Configuration Form

The agent configuration form is where you configure all agent settings. You have complete control to manually configure or refine every setting, whether you work with AI-generated suggestions or enter values from scratch.

### Agent Details

Agent details form the foundation of your agent configuration.

The name field requires a unique identifier between 3 and 40 characters that describes the agent's purpose. Names must be unique across your deployment. If you used AI assistance, you should review the suggested name and modify it if needed.

The description field requires text between 10 and 1000 characters that explains what the agent does and when users should interact with it. This description helps users understand the agent's purpose and capabilities.

### Instructions

Instructions define how the agent behaves during interactions. This field requires between 100 and 10,000 characters and forms the basis of the agent system prompt. Your instructions should explain the agent's role, communication style, and any specific rules or constraints it should follow.

For example, you might instruct an agent to always provide sources for information, maintain a formal or casual tone, follow specific steps when handling requests, or apply particular business rules or constraints.

If you used AI assistance, the system generates initial instructions based on your description. You should review these carefully and modify them to match your exact requirements because the AI makes its best judgment but cannot know all your specific needs.

### Toolsets

Toolsets provide the agent with capabilities it can use to accomplish tasks. You can select from available toolsets such as Artifact Management to list, read, create, update and delete artifacts, Data Analysis to query, transform and visualize data from artifacts, and Web to perform internet searches.

You can assign multiple toolsets to a single agent, giving it access to diverse capabilities. If you select Data Analysis, you should also include Artifact Management because data analysis operations typically require artifact access.

If you used AI assistance, the system suggests toolsets based on your description. You should review these selections and add or remove toolsets as needed to match your agent's actual requirements.

### Connectors

Connectors link agents to external data sources like SQL databases. You can assign connectors that were previously created in the Connectors section. Each connector provides access to a specific database with configured credentials.

All agents sharing a connector use the same database credentials. You should implement database-level access controls to restrict what each agent can access. The system supports MySQL, PostgreSQL, and MariaDB connectors.

Connectors must be created separately before they can be assigned to agents. For detailed information on creating and configuring database connectors, see [Working with SQL Connectors](#working-with-sql-connectors).

### Agent Card

Agent card configuration defines how the agent presents itself and communicates.

The skills field lets you specify what tasks the agent can perform. This information helps users and other agents understand your agent's capabilities.

The communication modes field lets you select how the agent interacts, such as text-based interaction or voice capabilities. Choose the modes that match your agent's intended use cases.

### Saving the Agent

After you configure all settings, you can save the agent. It appears in the Inactive tab with `Not Deployed` status, where you can further edit the configuration, download it as a YAML file, or deploy it to make it available for use in Chat.

## Working with SQL Connectors

SQL connectors enable agents to query and analyze database information using natural language. These connectors convert user questions into SQL queries, execute them, and return results in a conversational format.

Before you assign connectors to agents, you must create them in the Connectors section of the interface. Each connector configuration includes the database type (MySQL, PostgreSQL, or MariaDB), connection details (host, port, and database name), and authentication credentials (username and password).

Once you create connectors, they become available for assignment to any agent. This reusability means you can connect multiple agents to the same database without duplicating connection configuration.

### Security Considerations

Security considerations are essential when using SQL connectors. The framework does not sandbox database access at the agent level. All agents assigned to a connector share the same database credentials and permissions. This design has several implications.

Any agent with the connector can access all data the connector's credentials permit. Database-level access control is your primary security mechanism. You should create database users with minimal necessary privileges. Consider using database views or restricted schemas to limit what agents can access. You should also audit database queries to monitor what agents are accessing.

The natural language to SQL conversion capability makes databases accessible through conversation, but this also means users can potentially request any data the connector can access. You should plan your database permissions accordingly and consider what information should be available through agent interactions.

Each agent can be assigned a limited number of connectors. This limit helps manage complexity and prevents performance issues.

## Agent Lifecycle and Management

Agents move through distinct states as you create, edit, and deploy them.

### Agent States

Not Deployed is the initial status for newly created agents. These agents appear in the Inactive tab where you can edit their configurations, download them as YAML files, or prepare them for deployment. Agents remain in this status until you explicitly deploy them.

Deploying and Undeploying are the in-progress statuses that appear when an agent is being deployed or undeployed. You should not interact with an agent when it is in this transitory state.

Running agents move to the Active tab and become available for user interactions. Once deployed, agents cannot be deleted—you must undeploy them first to remove them from the system.

Deployment Failed displays if your agent failed to deploy for any reason. You should verify all agent configuration and try again, or contact an administrator if the problem persists.

### Managing Configuration Changes

Sync status tracking helps you manage configuration drift for deployed agents. When you deploy an agent, the system records its configuration. If you later edit the agent's configuration in the UI, the system detects this mismatch. The system continues to display the Running agent in the active section and also displays the agent updates as Not Deployed in the inactive section. Both tiles show "Undeployed changes" to help you understand when deployed agents do not match their stored configurations. The specific synchronization mechanism depends on your deployment approach. The "Preview Updates" action in the agent side panel can help you compare the running agent with its undeployed configuration.

You can edit agent configurations (of agents built with agent builder) at any time, whether they are deployed or not. Changes to deployed agents require the "Deploy Updates" action to take effect in the Running agent.

### Downloading Agent Configurations

Downloading agents as YAML files provides portability and version control. You can use these files to back up agent configurations, share configurations between deployments, track configuration changes in version control systems, and deploy agents using infrastructure-as-code tools.

## Configuration Validation and Constraints

The system enforces several validation rules to ensure agent configurations remain functional.

### Name Uniqueness

Name uniqueness is enforced across all agents in your deployment. If you attempt to create an agent with a name that already exists, the system rejects it. This prevents confusion and ensures each agent has a distinct identifier.

### Field Length Constraints

Field length constraints ensure configurations remain manageable. Agent names must be between 3 and 40 characters. Agent descriptions must be between 10 and 1000 characters. System instructions must be between 100 and 10,000 characters (this field is optional during creation but required before deployment). AI-assisted descriptions must be between 10 and 1000 characters.

### Deletion Restrictions

Deletion restrictions prevent accidentally removing active agents. You cannot delete deployed agents directly. You must first undeploy them, which moves them back to Not Deployed status in the Inactive tab. After undeployment completes, you can delete them. This two-step process helps prevent service disruptions.

### Connector Limits

Each agent can have a limited number of connectors. This restriction helps manage complexity and prevents performance issues that could arise from agents attempting to connect to too many databases simultaneously.