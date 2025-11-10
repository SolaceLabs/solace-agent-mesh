---
title: Microsoft Teams Integration (Enterprise)
sidebar_position: 70
---

# Microsoft Teams Integration (Enterprise)

This tutorial shows you how to integrate Microsoft Teams with Agent Mesh Enterprise, allowing users to interact with the system directly from Teams workspaces and channels.

:::warning[Enterprise Feature - Docker Image Only]
The Microsoft Teams Gateway is an Enterprise feature included in the Docker image. It works with both Docker and Kubernetes deployments but is not available when installing via PyPI or wheel files. This feature requires:
- Agent Mesh Enterprise Docker image (deployed via Docker or Kubernetes)
- Azure Active Directory tenant access
- Azure Bot Service setup
:::

:::info[Learn about gateways]
For an introduction to gateways and how they work, see [Gateways](../../components/gateways.md).
:::

## Prerequisites

Before you begin, make sure you have the following:

1. Agent Mesh Enterprise deployed via Docker or Kubernetes
2. Access to an Azure Active Directory tenant
3. An Azure subscription for creating Bot Service resources
4. A public HTTPS endpoint for production, or ngrok for development and testing

## Overview

The Microsoft Teams Gateway connects your Agent Mesh deployment to Microsoft Teams, enabling several interaction modes. Users can chat directly with the bot in personal conversations, collaborate with the bot in group chats when they mention it, and interact with it in team channels. The gateway handles file uploads in formats including CSV, JSON, PDF, YAML, XML, and images. It also manages file downloads through Microsoft Teams' FileConsentCard approval flow.

When users send messages, the gateway streams responses back in real time, updating messages as the agent processes the request. The system automatically extracts user identities through Azure AD authentication, ensuring secure access control. To maintain performance and clarity, sessions reset automatically at midnight UTC each day.

The gateway operates in single-tenant mode, meaning it works within your organization's Azure AD tenant. This approach provides better security and simpler management for enterprise deployments.

## Bot Configuration: Multi-Tenant vs Single-Tenant

Microsoft Teams bots can be configured as either **multi-tenant** or **single-tenant**. The difference is controlled by the `microsoft_app_tenant_id` field:

### Single-Tenant (Recommended)
Users from **your organization only** can access the bot.

```yaml
microsoft_app_id: ${TEAMS_BOT_ID}
microsoft_app_password: ${TEAMS_BOT_PASSWORD}
microsoft_app_tenant_id: ${AZURE_TENANT_ID}  # Include this line
```

### Multi-Tenant (Deprecated July 2025)
Users from **any Azure AD organization** can access the bot.

```yaml
microsoft_app_id: ${TEAMS_BOT_ID}
microsoft_app_password: ${TEAMS_BOT_PASSWORD}
# Do NOT include microsoft_app_tenant_id
```

:::warning
Multi-tenant apps are being deprecated by Microsoft after July 2025. Use single-tenant configuration for new deployments.
:::

**This guide uses single-tenant configuration throughout.**

**Additional Configuration Resources:**
- Bot Framework Portal: https://dev.botframework.com/bots
- Teams Developer Portal: https://dev.teams.cloud.microsoft/

## Azure Setup

Setting up the Teams integration requires creating several Azure resources. You configure these resources in a specific order because each one depends on information from the previous step.

### Step 1: Create Azure App Registration

The App Registration establishes your bot's identity within Azure Active Directory. Go to https://portal.azure.com, then navigate to Azure Active Directory and select `App registrations`. Click `New registration`.

Enter a descriptive name like "SAM Teams Bot". Under `Supported account types`, select `Accounts in this organizational directory only (Single tenant)`. Leave the `Redirect URI` blank and click `Register`.

Copy both the `Application (client) ID` and `Directory (tenant) ID` from the details page—you need both for later steps.

Next, go to `Certificates & secrets` and click `New client secret`. Enter a description like "SAM Bot Secret" and choose an expiration period. Click `Add`.

:::danger[Save Your Secret]
The client secret value appears only once. Copy it immediately and store it securely. This becomes your `TEAMS_BOT_PASSWORD` environment variable.
:::

### Step 2: Create Azure Bot Service

In the Azure Portal, search for `Azure Bot` and click `Create`. Enter a unique name like `sam-teams-bot`, select your subscription and resource group, and choose a pricing tier (F0 for development, S1 for production).

Under `Microsoft App ID`, select `Use existing app registration`. Paste the `Application (client) ID` from Step 1 into the `App ID` field and enter your Azure AD tenant ID in the `Tenant ID` field. Click `Review + create`, then `Create`.

After deployment, navigate to the bot resource and go to the `Configuration` section. Set the `Messaging endpoint` to your public HTTPS URL with `/api/messages` appended (e.g., `https://your-domain.com/api/messages`). This endpoint must be publicly accessible from the internet. Click `Apply`.

:::tip[Development Setup]
For local testing, use [ngrok](https://ngrok.com/) to expose your local port:
```bash
ngrok http 8080
```
Then use the ngrok HTTPS URL as your messaging endpoint (e.g., `https://abc123.ngrok.io/api/messages`)
:::

### Step 3: Add Teams Channel

In your Azure Bot resource, navigate to `Channels` and click the `Microsoft Teams` icon. Leave `Calling` disabled and ensure `Messaging` is enabled. Click `Apply` to activate the channel.

### Step 4: Create Teams App Package

Create a new directory with a file named `manifest.json` containing the following:

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/teams/v1.16/MicrosoftTeams.schema.json",
  "manifestVersion": "1.16",
  "version": "1.0.0",
  "id": "YOUR-APP-ID-HERE",
  "packageName": "com.solace.agentmesh.teams",
  "developer": {
    "name": "Your Organization",
    "websiteUrl": "https://your-company.com",
    "privacyUrl": "https://your-company.com/privacy",
    "termsOfUseUrl": "https://your-company.com/terms"
  },
  "name": {
    "short": "Agent Mesh Bot",
    "full": "Solace Agent Mesh Bot"
  },
  "description": {
    "short": "AI-powered assistant for your organization",
    "full": "Solace Agent Mesh provides intelligent assistance through Microsoft Teams"
  },
  "icons": {
    "outline": "outline.png",
    "color": "color.png"
  },
  "accentColor": "#00C895",
  "bots": [
    {
      "botId": "YOUR-BOT-ID-HERE",
      "scopes": ["personal", "team", "groupchat"],
      "supportsFiles": true,
      "isNotificationOnly": false
    }
  ],
  "permissions": [
    "identity",
    "messageTeamMembers"
  ],
  "validDomains": []
}
```

Replace `YOUR-APP-ID-HERE` with your `Application (client) ID` from Step 1 and `YOUR-BOT-ID-HERE` with your Azure Bot ID (usually the same as your App ID). Update the `developer` fields with your organization's information and URLs.

The `supportsFiles` property enables file uploads and downloads. The `scopes` array specifies where users interact with the bot (personal, team, or group chat). The `permissions` array grants access to user identity and team messaging.

Create two icon files:

:::tip[Icon Requirements]
- `color.png`: 192x192 pixels, full color
- `outline.png`: 32x32 pixels, white icon on transparent background
:::

Create a ZIP file containing `manifest.json`, `color.png`, and `outline.png`. Name it `teams-app.zip`.

### Step 5: Upload Teams App

Open Microsoft Teams and click `Apps` in the left sidebar. Click `Manage your apps`, then `Upload an app`. Select `Upload a custom app` and choose your `teams-app.zip` file.

Click `Add` to install the bot in your Teams workspace.

## Configuring the Gateway

After you set up the Azure resources, you need to configure Agent Mesh Enterprise to connect to Teams. This configuration requires setting environment variables and updating your deployment configuration.

### Environment Variables

Set three environment variables for Teams authentication:

```bash
TEAMS_BOT_ID="your-azure-bot-id"
TEAMS_BOT_PASSWORD="your-client-secret-value"
AZURE_TENANT_ID="your-azure-tenant-id"
```

:::info[Tenant ID]
Find the tenant ID in Azure Portal → Azure Active Directory → Overview → `Tenant ID`. It enables single-tenant authentication, restricting bot access to your organization's Azure AD users.
:::

### Docker Compose Example

```yaml
version: '3.8'
services:
  agent-mesh-enterprise:
    image: solace-agent-mesh-enterprise:latest
    ports:
      - "8080:8080"
    environment:
      - TEAMS_BOT_ID=${TEAMS_BOT_ID}
      - TEAMS_BOT_PASSWORD=${TEAMS_BOT_PASSWORD}
      - AZURE_TENANT_ID=${AZURE_TENANT_ID}
      - NAMESPACE=your-namespace
      - SOLACE_BROKER_URL=ws://broker:8080
```

Set `NAMESPACE` to your message broker topic namespace and `SOLACE_BROKER_URL` to your Solace broker instance.

### Kubernetes ConfigMap/Secret

Create `Secret` and `ConfigMap` resources in your deployment namespace:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: teams-gateway-credentials
type: Opaque
stringData:
  bot-id: "your-azure-bot-id"
  bot-password: "your-client-secret-value"
  tenant-id: "your-azure-tenant-id"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: teams-gateway-config
data:
  default-agent: "orchestrator-agent"
  http-port: "8080"
```

Reference these resources in your deployment to inject values as environment variables.

### Gateway Configuration Options

```yaml
component_name: teams-gateway
component_module: sam_teams_gateway
component_config:
  microsoft_app_id: ${TEAMS_BOT_ID}
  microsoft_app_password: ${TEAMS_BOT_PASSWORD}
  microsoft_app_tenant_id: ${AZURE_TENANT_ID}  # Required for single-tenant auth
  default_agent_name: orchestrator-agent
  http_port: 8080
  enable_typing_indicator: true
  buffer_update_interval_seconds: 2
  initial_status_message: "Processing your request..."
  system_purpose: |
    You are an AI assistant helping users through Microsoft Teams.
  response_format: |
    Provide clear, concise responses. Use markdown formatting when appropriate.
```

Key parameters:

- `microsoft_app_tenant_id`: Required for single-tenant authentication; must match your Azure AD tenant ID
- `default_agent_name`: Agent that handles incoming messages
- `http_port`: Must match your container's exposed port
- `enable_typing_indicator`: Shows typing indicator while processing requests
- `buffer_update_interval_seconds`: Controls streaming response update frequency (lower = more real-time, higher = fewer API calls)
- `initial_status_message`: Feedback shown when users first send a message
- `system_purpose`: Defines the bot's role and behavior
- `response_format`: Instructions for response formatting (e.g., markdown)

## Troubleshooting

### Error: "App is missing service principal in tenant"

This error occurs when using single-tenant configuration (with `microsoft_app_tenant_id` set) but the app isn't properly registered in that tenant.

**Solution:**
1. Verify the `AZURE_TENANT_ID` matches your Azure AD tenant
2. Use multi-tenant by removing `microsoft_app_tenant_id` (temporary workaround)
3. Register service principal: `az ad sp create --id YOUR-APP-ID`
4. Verify your configuration: https://dev.botframework.com/bots
