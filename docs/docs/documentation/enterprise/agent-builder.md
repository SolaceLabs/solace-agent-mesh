---
title: Agent Builder
sidebar_position: 8
---

# Agent Builder

Agent Builder provides a visual, form-based interface for creating and managing agents without writing configuration files. This tool offers optional AI assistance that suggests initial configuration values based on a description of the agent you want to build.

When you click the "Create Agent" button from the Agents page, a dialog appears offering AI assistance. You can describe what you want the agent to do in natural language, and the AI generates initial configuration values for you to review and modify. Alternatively, you can skip AI assistance and manually enter all configuration details yourself.

After you configure the agent in the form and save it, the agent appears in the Inactive tab with Not Deployed status. At this point, you can further edit the configuration, download it as a YAML file, or deploy it to make it available for use in Chat.

## Creating Your First Agent

Agent Builder offers two paths for beginning your agent configuration.

### AI-Assisted Creation

You can provide a natural language description of what you want the agent to do. Explain the agent's purpose, the types of tasks it handles, and any specific capabilities it needs. For example, "An agent that helps users search company documentation and answer questions about internal policies" or "An agent that analyzes sales data and generates reports."

When you submit your description, the AI analyzes it and generates suggested values for several configuration fields. The AI creates a unique agent name, writes a description explaining the agent's purpose, drafts system instructions defining agent behavior, suggests appropriate toolsets, recommends connectors if applicable, and provides default settings for skills and communication modes.

These AI-generated values serve as suggestions only. You proceed to the configuration form where you can review, modify, or completely rewrite any of these values before saving the agent.

:::note[LLM Cache Configuration]
If you encounter an error about "minimum token count to start caching" when using AI-assisted creation, set the `LLM_CACHE_STRATEGY` environment variable to `none` in your Platform Service configuration. This disables LLM prompt caching which requires a minimum token threshold that the AI Assistant's prompts may not meet. See [LLM Configuration](../installing-and-configuring/large_language_models.md#prompt-caching) for more details.
:::

### Manual Creation

You can skip AI assistance entirely by clicking the secondary button. The system prompts you to manually enter the agent's name and description in a simple dialog. After you provide these details and click continue, you proceed to the agent configuration form where the Agent Details section is pre-filled with your entered name and description. Other sections (instructions, toolsets, and connectors) remain empty for you to configure manually.

## Configuring the Agent

The agent configuration form is where you configure all agent settings. You have complete control to manually configure or refine every setting, whether you work with AI-generated suggestions or enter values from scratch.

### Agent Details

The name field provides a unique identifier that describes the agent's purpose. Names must be unique across your deployment.

The description field explains what the agent does and when users should interact with it. This description helps users understand the agent's purpose and capabilities.

### Instructions

Instructions define how the agent behaves during interactions and form the basis of the agent system prompt. Your instructions should explain the agent's role, communication style, and any specific rules or constraints it should follow.

For example, you can instruct an agent to always provide sources for information, maintain a formal or casual tone, follow specific steps when handling requests, or apply particular business rules or constraints.

### Toolsets

Toolsets provide the agent with capabilities it can use to accomplish tasks. Available toolsets include Artifact Management (list, read, create, update and delete artifacts), Data Analysis (query, transform and visualize data from artifacts), and Web (perform internet searches).

You can assign multiple toolsets to a single agent, giving it access to diverse capabilities. If you select Data Analysis, you should also include Artifact Management because data analysis operations typically require artifact access.

### Connectors

Connectors link agents to external data sources such as databases and APIs. You assign connectors that were previously created in the Connectors section. All agents sharing a connector use the same credentials.

For detailed information about creating and configuring connectors, see [Connectors](connectors/connectors.md).

## Deploying and Managing Agents

### How Deployment Works

When you deploy an agent through Agent Builder, the deployment process involves several components working together to create running agent instances.

The Platform Service receives your deployment request and validates the agent configuration. It creates a deployment record in the database and publishes a deployment message to the Solace broker. The Deployer component (a separate containerized service) receives this message and creates a running agent instance using the configuration you provided. The Deployer sends status updates back to the Platform Service through heartbeat messages, and the Platform Service updates the deployment status you see in the UI.

This architecture enables multiple Deployer instances to run independently for scalability and allows deployment operations to complete asynchronously without blocking the UI. You see status transitions (Deploying, Deployed, or Deployment Failed) as the Deployer works in the background.

Agent deployments are currently only supported through Helm. The Deployer runs as a containerized service using the `sam-agent-deployer` image. For detailed deployment configuration and setup instructions, see the [Solace Agent Mesh Helm Quickstart](https://solaceproducts.github.io/solace-agent-mesh-helm-quickstart/docs-site/).

### Agent States

Agents move through distinct states as you create, edit, and deploy them.

Not Deployed is the initial status for newly created agents. These agents appear in the Inactive tab where you can edit their configurations, download them as YAML files, or prepare them for deployment. Agents remain in this status until you explicitly deploy them.

Deploying and Undeploying are the in-progress statuses that appear when an agent is being deployed or undeployed. You should not interact with an agent when it is in this transitory state.

Deployed agents move to the Active tab and become available for user interactions. You cannot delete deployed agents—you must undeploy them first to remove them from the system.

Deployment Failed displays if your agent failed to deploy for any reason. You should verify all agent configuration and try again, or contact an administrator if the problem persists.

### Managing Deployed Agents

When you deploy an agent, the system records its configuration. If you later edit the agent's configuration in the UI, the system detects this mismatch and displays "Undeployed changes" on both the Active and Inactive agent tiles. The "Preview Updates" action in the agent side panel compares the running agent with its undeployed configuration. Changes to deployed agents require the "Deploy Updates" action to take effect in the running agent.

Downloading agents as YAML files provides portability and version control. These files support backing up agent configurations, sharing configurations between deployments, tracking configuration changes in version control systems, and deploying agents using infrastructure-as-code tools.

## Downloading Agent Configurations

The Download button allows you to export agent configurations as YAML files. These files are designed for the **Agent Deployer** running in Kubernetes/Helm environments.

### What Downloaded YAML Files Are Designed For

Agent Builder generates YAML files optimized for automated deployment through the Agent Deployer. These files:

- Use S3-compatible artifact storage (expects SeaweedFS or similar in K8s)
- Contain environment variable placeholders for credentials and settings
- Do not reference `shared_config.yaml` (unlike agents created with `sam add agent`)
- Are ready to deploy through the Agent Deployer without modification

:::info[Agent Deployer vs Manual Deployment]
**Agent Deployer (Recommended):** Click "Deploy" in Agent Builder to deploy agents directly to your Kubernetes cluster. The agent deployer handles all configuration automatically.

**Download for Manual Use:** Download the YAML file if you need to run agents outside Kubernetes or want to review/customize the configuration.
:::

### When to Download

**Use the Download button when you need to:**
- Back up agent configurations for version control
- Review generated configuration before deployment
- Share agent configurations between teams or environments
- Run agents in workshops or demos without K8s infrastructure

**Use the Deploy button when:**
- You have Kubernetes/Helm infrastructure set up
- You want automated deployment without manual configuration
- You want the agent deployer to manage the agent lifecycle

:::warning[Configuration Required]
Downloaded YAML files are designed for the agent deployer and require manual configuration changes to run locally. For local development, consider using `sam add agent` instead, which generates files with `shared_config` references.
:::

## Access Control

Agent Builder operations require specific RBAC capabilities. The table below shows the capabilities and what they control:

| Capability | Purpose |
|------------|---------|
| `sam:agent_builder:create` | Create new agents through Agent Builder interface |
| `sam:agent_builder:update` | Edit existing agent configurations |
| `sam:agent_builder:delete` | Delete agents (must undeploy first) |
| `sam:deployments:create` | Deploy agents to make them available in Chat |
| `sam:deployments:read` | View deployment status and history |

For information about connector-related capabilities, see [Connectors](connectors/connectors.md#access-control). For detailed information about configuring role-based access control and assigning capabilities to users, see [Setting Up RBAC](rbac-setup-guide.md). For Kubernetes-specific RBAC configuration, see the [Helm Chart RBAC documentation](https://solaceproducts.github.io/solace-agent-mesh-helm-quickstart/docs-site/#role-based-access-control-rbac).
