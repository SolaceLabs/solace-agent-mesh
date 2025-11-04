---
title: Microsoft Teams Integration (Enterprise)
sidebar_position: 70
---

# Microsoft Teams Integration (Enterprise)

This tutorial shows you how to integrate Microsoft Teams with Agent Mesh Enterprise, allowing users to interact with the system directly from Teams workspaces and channels.

:::warning[Enterprise Feature - Docker Deployment Only]
The Microsoft Teams Gateway is an Enterprise feature included in the Docker image. It is not available when installing via PyPI or wheel files. This feature requires:
- Agent Mesh Enterprise Docker deployment
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

## Azure Setup

Setting up the Teams integration requires creating several Azure resources. You configure these resources in a specific order because each one depends on information from the previous step.

### Step 1: Create Azure App Registration

The App Registration establishes your bot's identity within Azure Active Directory. Begin by navigating to the Azure Portal at https://portal.azure.com. In the portal, go to Azure Active Directory and then select App registrations. Click New registration to create a new app.

For the registration name, enter SAM Teams Bot or another descriptive name for your organization. Under supported account types, select Accounts in this organizational directory only (Single tenant). This configuration restricts the bot to users within your Azure AD tenant. Leave the redirect URI field blank because the bot does not require OAuth redirect flows.

After you click Register, Azure creates the app registration and displays its details. Take note of both the Application (client) ID and the Directory (tenant) ID—you need these values for subsequent steps. The Application ID identifies your bot, while the tenant ID specifies your organization's Azure AD tenant.

Next, create a client secret that the bot uses to authenticate itself. Go to Certificates & secrets, then click New client secret. Enter SAM Bot Secret as the description, or use another name that helps you identify this secret later. Choose an expiration period based on your organization's security policies—options include 90 days, 180 days, or a custom duration.

:::danger[Save Your Secret]
The client secret value is only shown once. Copy it immediately and store it securely.
:::

After you create the secret, Azure displays its value. Copy this value immediately because Azure never displays it again. This value becomes your TEAMS_BOT_PASSWORD environment variable.

### Step 2: Create Azure Bot Service

The Bot Service connects your bot to Microsoft Teams and other channels. In the Azure Portal, search for Azure Bot and click Create. You need to provide several configuration details.

For the bot handle, enter a globally unique name like sam-teams-bot. This name appears in the bot's URL and must be unique across all Azure Bot Services. Select your Azure subscription and either create a new resource group or use an existing one. Choose a pricing tier—F0 (Free) works for development and small deployments, while S1 (Standard) provides higher limits for production use.

Under Microsoft App ID, select Use existing app registration. Paste the Application (client) ID from Step 1 into the App ID field. Enter your Azure AD tenant ID in the Tenant ID field. These values link the Bot Service to the App Registration you created earlier.

Click Review + create, then click Create to deploy the bot resource. After deployment completes, navigate to the bot resource and go to its Configuration section. Set the messaging endpoint to your public URL followed by /api/messages, such as https://your-public-url.com/api/messages. The endpoint must use HTTPS and must be publicly accessible from the internet. Click Apply to save your configuration.

:::tip[Development Setup]
For local testing, use [ngrok](https://ngrok.com/) to expose your local port:
```bash
ngrok http 8080
```
Then use the ngrok HTTPS URL as your messaging endpoint (e.g., `https://abc123.ngrok.io/api/messages`)
:::

### Step 3: Add Teams Channel

After you create the Bot Service, you need to enable the Microsoft Teams channel. In your Azure Bot resource, navigate to Channels and click the Microsoft Teams icon. The configuration page appears with options for calling and messaging.

Leave calling disabled unless you need voice or video call features. Ensure that messaging is enabled—this allows the bot to send and receive text messages in Teams. Click Apply to activate the channel. Teams can now route messages to your bot through the messaging endpoint you configured.

### Step 4: Create Teams App Package

Microsoft Teams requires a manifest file that describes your bot and its capabilities. Create a new directory to hold your Teams app files. In this directory, create a file named manifest.json with the following content:

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

In the manifest, replace YOUR-APP-ID-HERE with your Azure App Registration ID (the Application client ID from Step 1). Replace YOUR-BOT-ID-HERE with your Azure Bot ID, which is typically the same as your App Registration ID. Update the developer fields with your organization's information and URLs.

The supportsFiles property enables file upload and download capabilities. The scopes array specifies where users can interact with the bot—personal conversations, team channels, and group chats. The permissions array grants the bot access to user identity information and the ability to message team members.

Create two icon files for your bot. The color icon should be 192x192 pixels and display your bot's branding in full color. The outline icon should be 32x32 pixels, consisting of a white icon on a transparent background. Teams displays these icons in different contexts throughout its interface.

:::tip[Icon Requirements]
- Color icon: 192x192 pixels, full color
- Outline icon: 32x32 pixels, white icon on transparent background
:::

After you create the icons, place them in the same directory as manifest.json. Create a ZIP file containing all three files (manifest.json, color.png, and outline.png). Name this file teams-app.zip.

### Step 5: Upload Teams App

Now you can install your bot in Microsoft Teams. Open Microsoft Teams and click Apps in the left sidebar. Click Manage your apps, then click Upload an app. Select Upload a custom app and choose your teams-app.zip file.

Teams validates the manifest and displays information about your bot. Click Add to install the bot in your Teams workspace. The bot now appears in your Apps list and users can start conversations with it.

## Configuring the Gateway

After you set up the Azure resources, you need to configure Agent Mesh Enterprise to connect to Teams. This configuration requires setting environment variables and updating your deployment configuration.

### Environment Variables

Your deployment needs three environment variables to authenticate with Microsoft Teams. Set TEAMS_BOT_ID to your Azure Bot ID (the Application client ID from Step 1). Set TEAMS_BOT_PASSWORD to the client secret value you copied when creating the secret. Set AZURE_TENANT_ID to your Directory tenant ID.

```bash
TEAMS_BOT_ID="your-azure-bot-id"
TEAMS_BOT_PASSWORD="your-client-secret-value"
AZURE_TENANT_ID="your-azure-tenant-id"
```

:::info[Tenant ID]
The tenant ID is required for single-tenant authentication. Find it in Azure Portal → Azure Active Directory → Overview → Tenant ID.
:::

The tenant ID enables single-tenant authentication, which restricts bot access to users within your Azure AD tenant. You can find this ID in the Azure Portal by navigating to Azure Active Directory and looking at the Overview page.

### Docker Compose Example

If you deploy using Docker Compose, add the environment variables to your service configuration. The following example shows how to configure the Agent Mesh Enterprise container with Teams Gateway support:

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
    # ... other configuration
```

The container exposes port 8080, which must match the port in your messaging endpoint configuration. The NAMESPACE variable defines the message broker topic namespace for your deployment. Set SOLACE_BROKER_URL to point to your Solace broker instance.

### Kubernetes ConfigMap/Secret

For Kubernetes deployments, store sensitive credentials in a Secret resource and configuration values in a ConfigMap. Create these resources in the same namespace as your Agent Mesh deployment:

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

Reference these resources in your deployment configuration to inject the values as environment variables into your pods.

### Gateway Configuration Options

The Teams Gateway accepts several configuration parameters in your YAML configuration file. These parameters control the gateway's behavior and integration with your Agent Mesh deployment:

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

The microsoft_app_tenant_id parameter enables single-tenant authentication and must match your Azure AD tenant ID. The default_agent_name specifies which agent handles incoming messages when users do not specify a particular agent. Set http_port to match the port exposed by your container and referenced in your messaging endpoint URL.

When enable_typing_indicator is true, Teams displays a typing indicator while the agent processes requests. The buffer_update_interval_seconds parameter controls how frequently the gateway updates streaming responses—lower values provide more real-time updates but increase API calls to Teams. The initial_status_message appears when users first send a message, providing immediate feedback that the system received their request.

Use system_purpose to define the bot's role and behavior guidelines that apply to all interactions. The response_format parameter provides instructions for how the agent should format its responses, such as using markdown for better readability in Teams.
