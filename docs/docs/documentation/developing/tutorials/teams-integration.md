---
title: "Microsoft Teams Gateway Setup \u2014 Manual Configuration (Docker & Wheel)"
sidebar_position: 70
---

# Microsoft Teams Gateway Setup — Manual Configuration (Docker & Wheel)

:::info[Which guide is this?]
This guide is for users deploying the Teams Gateway **manually** using Docker or wheel-based installations. If you are using the Agent Mesh Enterprise web interface, see the [Web Interface guide](../../enterprise/gateways/teams-gateway.md) instead.
:::

This tutorial shows you how to configure and run a Microsoft Teams Gateway with Agent Mesh Enterprise using Docker or wheel-based deployments.

:::warning[Enterprise Feature]
The Microsoft Teams Gateway requires:
- Agent Mesh Enterprise
- Azure Active Directory tenant access
- Azure Bot Service setup
:::

:::info[Learn about gateways]
For an introduction to gateways and how they work, see [Gateways](../../components/gateways.md).
:::

## Prerequisites

Before you begin, make sure you have the following:

1. Agent Mesh Enterprise deployed via Docker, Kubernetes, or Wheel file
2. Access to an Azure Active Directory tenant
3. An Azure subscription for creating Bot Service resources
4. A public HTTPS endpoint for production, or ngrok for development and testing

## Azure Setup and Teams App Installation

Complete Steps 1 through 3 in the [Web Interface guide](../../enterprise/gateways/teams-gateway.md) to:

1. **Create an Azure App Registration** (Step 1) -- obtain your Application (client) ID, Directory (tenant) ID, and client secret
2. **Create an Azure Bot Service** (Step 2) -- register your bot and enable the Microsoft Teams channel
3. **Create and install the Teams App** (Step 3) -- create the manifest, package, and upload to Teams

After completing these steps, return here to configure and run the gateway.

## Configuring the Gateway

### Environment Variables

Set the following environment variables for Teams authentication and broker connectivity:

```bash
# Teams / Azure authentication
TEAMS_BOT_ID="<Application (client) ID from Step 1>"
TEAMS_BOT_PASSWORD="<Client secret Value from Step 1>"
TEAMS_TENANT_ID="<Directory (tenant) ID from Step 1>"

# Solace broker connection
SOLACE_BROKER_URL="<Solace broker WebSocket URL, e.g. ws://localhost:8080>"
SOLACE_BROKER_USERNAME="<Solace broker username>"
SOLACE_BROKER_PASSWORD="<Solace broker password>"
SOLACE_BROKER_VPN="<Solace broker VPN name>"

# Namespace
NAMESPACE="<your message broker topic namespace>"
```

### Gateway Configuration

Create a YAML configuration file for the Teams gateway:

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: "teams-gateway.log"

apps:
  - name: "teams-gateway"
    app_base_path: "."
    app_module: solace_agent_mesh.gateway.generic.app
    broker:
      dev_mode: ${SOLACE_DEV_MODE, false}
      broker_url: ${SOLACE_BROKER_URL}
      broker_username: ${SOLACE_BROKER_USERNAME}
      broker_password: ${SOLACE_BROKER_PASSWORD}
      broker_vpn: ${SOLACE_BROKER_VPN}
      temporary_queue: ${USE_TEMPORARY_QUEUES, true}
    app_config:
      namespace: "${NAMESPACE}"
      gateway_adapter: sam_teams_gateway_adapter.adapter.TeamsAdapter
      adapter_config:
        microsoft_app_id: ${TEAMS_BOT_ID}
        microsoft_app_password: ${TEAMS_BOT_PASSWORD}
        microsoft_app_tenant_id: ${TEAMS_TENANT_ID}
        http_host: "0.0.0.0"
        http_port: 8092
        default_agent_name: "OrchestratorAgent"
        initial_status_message: "Processing your request..."
        enable_typing_indicator: true
        buffer_update_interval_seconds: 2
      artifact_service:
        type: ${ARTIFACT_SERVICE_TYPE, filesystem}
        base_path: ${ARTIFACT_BASE_PATH, /tmp/samv2}
        artifact_scope: namespace
      enable_embed_resolution: true
      gateway_artifact_content_limit_bytes: 10000000
      gateway_recursive_embed_depth: 3
      authorization_service:
        type: "none"
      system_purpose: |
        The system is an AI Chatbot with agentic capabilities. It is responding to a query on Microsoft Teams Chat.
        **Always return artifacts and files that you create to the user using the `signal_artifact_for_return` tool.**
        Provide a status update before each tool call.
      response_format: |
        Format responses using Markdown.
```

Key adapter configuration parameters:

- `microsoft_app_id`: Azure Bot ID (Application client ID)
- `microsoft_app_password`: Client secret from Azure App Registration
- `microsoft_app_tenant_id`: Azure AD Tenant ID for single-tenant authentication
- `http_port`: HTTP server port for the Teams webhook (default: 8092)
- `default_agent_name`: Agent that handles incoming messages
- `enable_typing_indicator`: Shows typing indicator while processing requests
- `buffer_update_interval_seconds`: Controls streaming response update frequency
- `initial_status_message`: Feedback shown when users first send a message

### Running the Gateway

**With Wheel install:**

Start the gateway using the SAM CLI:

```bash
sam run your-teams-gateway-config.yaml
```

**With Docker:**

Use the Docker Compose example below to start the gateway in a container.

### Docker Compose Example

```yaml
services:
  teams-gateway:
    image: <your-registry>/solace-agent-mesh-enterprise:<version>
    ports:
      - "8092:8092"
    volumes:
      - ./your-teams-gateway-config.yaml:/config/teams-gateway.yaml
    environment:
      - TEAMS_BOT_ID=${TEAMS_BOT_ID}
      - TEAMS_BOT_PASSWORD=${TEAMS_BOT_PASSWORD}
      - TEAMS_TENANT_ID=${TEAMS_TENANT_ID}
      - SOLACE_BROKER_URL=${SOLACE_BROKER_URL}
      - SOLACE_BROKER_USERNAME=${SOLACE_BROKER_USERNAME}
      - SOLACE_BROKER_PASSWORD=${SOLACE_BROKER_PASSWORD}
      - SOLACE_BROKER_VPN=${SOLACE_BROKER_VPN}
      - NAMESPACE=${NAMESPACE}
    command: ["run", "/config/teams-gateway.yaml"]
```

The Docker Compose file references environment variables using `${...}` syntax. Create a `.env` file in the same directory as your `docker-compose.yaml` with all the required values:

```bash
# .env
TEAMS_BOT_ID=your-app-client-id
TEAMS_BOT_PASSWORD=your-client-secret
TEAMS_TENANT_ID=your-tenant-id
SOLACE_BROKER_URL=ws://broker:8080
SOLACE_BROKER_USERNAME=your-broker-username
SOLACE_BROKER_PASSWORD=your-broker-password
SOLACE_BROKER_VPN=your-vpn-name
NAMESPACE=your-namespace
```

Docker Compose automatically reads the `.env` file. Start the gateway:

```bash
docker compose up -d
```

If `docker compose` is not available, try the standalone command:

```bash
docker-compose up -d
```

## Configure the Gateway Endpoint

After the gateway is running, configure the Azure Bot Service to route messages to the gateway.

1. Obtain your public HTTPS URL. The gateway listens on port 8092 at the `/api/messages` endpoint. You must make this endpoint publicly accessible via HTTPS so that Microsoft Teams can reach the gateway.
2. Go to the [Azure Portal](https://portal.azure.com) and navigate to your **Azure Bot** resource
3. Go to **Configuration**
4. Set the **Messaging endpoint** to your webhook URL
5. Click **Apply**

## Verification

1. Open Microsoft Teams
2. Find and open your bot app
3. Send a message (e.g., "Hello")
4. You should see a processing indicator followed by a response from your agent

## Troubleshooting

### Error: "App is missing service principal in tenant"

This error occurs when using single-tenant configuration (with `microsoft_app_tenant_id` set) but the app isn't properly registered in that tenant.

**Solution:**
1. Verify the `TEAMS_TENANT_ID` matches your Azure AD tenant
2. Register service principal: `az ad sp create --id YOUR-APP-ID`
3. Verify your configuration in the [Azure Portal](https://portal.azure.com) under your Azure Bot resource