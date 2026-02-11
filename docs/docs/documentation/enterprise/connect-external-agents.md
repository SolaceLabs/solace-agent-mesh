---
title: Connect External Agents
sidebar_position: 9
---

# Connect External Agents

The Connect External Agent feature allows you to integrate external A2A (Agent-to-Agent) protocol agents into your Agent Mesh deployment through a guided wizard interface. External agents run on separate infrastructure and communicate over HTTPS, but once connected, they appear and behave like native agents within your mesh.

This feature provides a user-friendly alternative to manually configuring YAML proxy files. The wizard guides you through providing agent location details, configuring authentication, and reviewing the final configuration before connecting the agent.

## How External Agent Connections Work

When you connect an external agent through the Enterprise UI, the system creates a proxy configuration that bridges the external agent to your Solace event mesh. The proxy performs protocol translation between A2A over HTTPS (used by the external agent) and A2A over Solace event mesh (used by agents in your mesh).

The proxy handles several responsibilities on your behalf:

- It fetches and publishes the external agent's capabilities (agent card) so other agents can discover it.
- It manages authentication to the external agent using the credentials you provide.
- It translates artifact references between the mesh format and the external agent's format.
- It forwards task requests and streams responses back to the requesting agent.

Once connected, the external agent appears in your agents list and other agents can delegate tasks to it through natural language requests. For detailed technical information about how proxies work, see [Proxies](../components/proxies.md).

## Connecting an External Agent

You connect external agents through the Agents section of the Agent Mesh Enterprise web interface. Navigate to the Agents page and click the Connect External Agent button to launch the connection wizard.

The wizard consists of three steps: providing the agent location, entering additional information, and reviewing the configuration.

### Step 1: Provide Agent Location

The first step collects the external agent's URL and agent card configuration.

#### Agent URL

Enter the base URL where the external agent is hosted. This is the root URL that the proxy uses to communicate with the agent. For example, `https://external-agent.example.com` or `https://api.partner.com/agents/customer-service`.

#### Agent Card Location

The agent card is a JSON document that describes the external agent's capabilities, including its name, description, and supported skills. You specify where the proxy should look for this card:

- Select "Well-known URI" if the agent publishes its card at the standard location (`/.well-known/agent-card.json` relative to the agent URL). This is the most common configuration for A2A-compliant agents.
- Select "Custom" if the agent card is available at a different URL. You then enter the full URL to the agent card.
- Select "No Agent Card" if the external agent does not provide an agent card. You must manually enter the agent's name, description, and capabilities in the next step.

#### Agent Card Authentication

If the external agent requires authentication to fetch its agent card, configure the credentials in this section. You can choose from four authentication types:

- "No Authentication" when the agent card endpoint is publicly accessible.
- "Static Bearer Token" when the agent expects a bearer token in the Authorization header. Enter the token value that will be sent as `Authorization: Bearer <token>`.
- "Static API Key" when the agent expects an API key header. Enter the key value that will be sent as `X-API-Key: <value>`.
- "OAuth 2.0 Client Credentials" when the agent uses OAuth 2.0 for authentication. Enter the token URL (must be HTTPS), client ID, client secret, and optionally the scopes to request.

#### Custom Headers

If the external agent requires additional HTTP headers when fetching the agent card (for example, API version headers or tenant identifiers), add them as key-value pairs in the Custom Headers section.

#### Fetching the Agent Card

After you configure the location and authentication, click the Fetch Agent Card button to retrieve and validate the agent card. The system displays a success message if the card is fetched successfully, along with the agent's name and description from the card. If the fetch fails, an error message explains what went wrong so you can correct the configuration.

### Step 2: Enter Additional Information

The second step configures how the agent appears in your mesh and how task invocations are authenticated.

#### Agent Display Name

If the external agent has an agent card, the wizard displays the external agent's name as read-only. You can customize the name that appears in your Agent Mesh deployment by clicking the Customize button and entering a different display name. The display name must be unique within your deployment.

If you selected "No Agent Card" in the previous step, you enter the agent's name and description manually. The name you provide becomes the identifier that other agents use when delegating tasks.

#### Skills and Communication Modes

When you connect an agent without an agent card, you must manually define its capabilities:

- Add skills to describe what the agent can do. Each skill has a name and a description that helps the orchestrator understand when to delegate tasks to this agent.
- Select the input modes (file, text) to indicate what types of information the agent can receive.
- Select the output modes (file, text) to indicate what types of responses the agent can produce.

When you connect an agent with an agent card, these values are read from the card and displayed for reference.

#### Task Invocation Authentication

Configure the authentication credentials used when invoking tasks on the external agent. These credentials may differ from the agent card authentication if the agent uses separate authentication for its card endpoint and task endpoints.

The authentication options are the same as for agent card authentication: no authentication, static bearer token, static API key, or OAuth 2.0 client credentials.

#### Task Headers

If the external agent requires additional HTTP headers for task invocations, add them as key-value pairs. These headers are sent with every task request to the external agent.

### Step 3: Review Agent

The final step displays a summary of your configuration for review. Verify the following details before connecting:

- The agent URL and agent card location.
- The display name and description.
- The authentication configuration for task invocations.
- The skills and communication modes.
- Any custom headers.

If you need to make changes, use the Back button to return to previous steps. When you are satisfied with the configuration, click Connect Agent to complete the connection.

## Deploying and Managing External Agents

After you connect an external agent, it appears in the Inactive tab of the Agents page with Not Deployed status. You must deploy the agent before other agents can discover and use it. The deployment and management workflow for external agents follows the same patterns as agents created through Agent Builder. For detailed information about deployment states, managing deployed agents, and downloading configurations, see the [Deploying and Managing Agents](agent-builder.md#deploying-and-managing-agents) section in Agent Builder.

### Status for Agents Without Agent Cards

External agents that have an agent card publish periodic heartbeats that allow the system to track their liveness. When deployed, these agents appear in the Active tab with standard status indicators.

External agents configured without an agent card cannot publish heartbeats because the system has no way to verify their availability. When you deploy an external agent without an agent card, it appears in the Active tab with Registered status instead of Running status. The Registered status indicates that the agent is configured and deployed, but the system cannot independently verify that the external agent is running and responsive.

## Troubleshooting

### Agent Card Fetch Fails

If fetching the agent card fails, verify the following:

- The agent URL is correct and the agent is running.
- The agent card URL is accessible from your Agent Mesh deployment.
- Authentication credentials are correct if the endpoint requires authentication.
- Network connectivity allows outbound HTTPS connections to the external agent.

### Duplicate Name Warning

If you see a warning about a duplicate agent name, another agent in your deployment already uses that name. You can proceed with a duplicate name, but unique names make it easier for others in your organization to find the correct agent.

### Authentication Errors During Task Invocation

If tasks fail with authentication errors after connecting, verify that the task invocation authentication is configured correctly. The agent card authentication and task invocation authentication are separate configurations, and the external agent may require different credentials for each.

## Access Control

External agent operations use the same RBAC capabilities as Agent Builder. For the list of required capabilities and detailed information about configuring role-based access control, see [Access Control](agent-builder.md#access-control) in Agent Builder.
