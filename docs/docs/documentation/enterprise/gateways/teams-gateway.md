---
title: Teams Gateway
sidebar_position: 3
---

# Microsoft Teams Gateway Integration Guide

This guide explains how to configure the Microsoft Teams Gateway in Agent Mesh Enterprise. The guide covers both **Solace Agent Mesh (SAM) Cloud** and **SAM Kubernetes** environments.

## Overview

The Teams Gateway connects your agents to Microsoft Teams, allowing users to interact with AI agents directly from Teams chats and channels. The gateway receives messages from Teams via an HTTPS webhook endpoint (`/api/messages`) and routes them to your agents.

Teams requires the gateway's webhook endpoint to be **publicly accessible via HTTPS**. The setup differs depending on your deployment environment.

### Supported Features

- **Personal chats**: Direct 1:1 messaging with the bot
- **Group chats**: The bot responds when @mentioned in group conversations
- **Team channels**: The bot responds when @mentioned in team channels
- **File uploads**: Send files to the bot in personal chats (CSV, JSON, PDF, YAML, XML, images, and more)
- **File downloads**: Receive files from agents via the Teams FileConsentCard approval flow
- **Streaming responses**: Real-time message updates as agents process requests
- **Typing indicator**: Shows a typing indicator while processing
- **Session management**: Sessions reset automatically at midnight UTC daily

:::info[Manual Deployment]
For Docker or wheel-based deployments without the Agent Mesh Enterprise web interface, see the [Teams Integration Tutorial](../../developing/tutorials/teams-integration.md).
:::

## Prerequisites

Before you begin, make sure you have:

1. An **Azure account** with:
   - Permission to create **App Registrations** in Microsoft Entra ID (most organizations allow this by default; if disabled, ask your admin for the **Application Developer** role)
   - **Contributor** role (or higher) on an Azure subscription or resource group to create the Bot Service resource
2. Access to the **Agent Mesh Enterprise web interface** with permissions to create and deploy gateways
3. Permission to upload custom apps in **Microsoft Teams**:
   - For personal or team use: Your Teams admin must enable the **"Upload custom apps"** policy for your account
   - For organization-wide deployment: A **Teams Administrator** must upload and approve the app via the [Teams Admin Center](https://admin.teams.microsoft.com)

## Step 1: Create an Azure App Registration

The App Registration provides authentication credentials for the gateway.

1. Go to the [Azure Portal](https://portal.azure.com)
2. Navigate to **App registrations**
3. Click **New registration**
   - **Name**: Choose a name (e.g., `SAM Teams Bot`)
   - **Supported account types**: Select **Accounts in this organizational directory only** (single tenant)
   - **Redirect URI**: Leave blank
4. Click **Register**
5. On the overview page, copy the **Application (client) ID** -- this is your **Microsoft App ID** for Agent Mesh
6. Copy the **Directory (tenant) ID** -- this is your **Microsoft App Tenant ID** for Agent Mesh
7. Go to **Certificates & secrets** > **Client secrets** > **New client secret**
   - **Description**: e.g., `SAM Bot Secret`
   - **Expires**: Choose an appropriate duration
8. Copy the secret **Value** immediately (it will not be shown again) -- this is your **Microsoft App Password** for Agent Mesh

## Step 2: Create an Azure Bot Service

The Bot Service registers your bot with Microsoft Teams.

1. In the Azure Portal, search for **Azure Bot** and click **Create**
2. Fill in the required fields:
   - **Bot handle**: A globally unique name (e.g., `sam-teams-bot`)
   - **Subscription**: Your Azure subscription
   - **Resource group**: Create new or select existing
   - **Pricing tier**: **F0 (Free)** for testing, or **S1 (Standard)** for production
   - **Type of App**: Select **Single Tenant**
   - **Creation type**: **Use existing app registration**
   - **App ID**: Paste the Application (client) ID from Step 1
   - **Tenant ID**: Paste the Directory (tenant) ID from Step 1
3. Click **Review + create** > **Create**
4. After the resource is created, go to the bot resource
5. Navigate to **Configuration**
   - **Messaging endpoint**: Leave blank for now. You will set the webhook URL in Step 6.
6. Navigate to **Channels** > click the **Microsoft Teams** icon
7. Ensure **Messaging** is enabled, leave **Calling** disabled
8. Accept the terms of service and click **Apply**

## Step 3: Create and Install the Teams App

Create a Teams app package and upload it to make the bot available in Microsoft Teams.

### 3.1: Create the App Manifest

Create a file named `manifest.json` using the template below. Replace `<YOUR_APP_ID>` with the **Application (client) ID** from Step 1. Update the developer information with your organization's details.

> **Note**: The manifest schema may change over time. See the [Teams app manifest schema reference](https://learn.microsoft.com/en-us/microsoftteams/platform/resources/schema/manifest-schema) for the latest version.

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/teams/v1.22/MicrosoftTeams.schema.json",
  "version": "1.0.0",
  "manifestVersion": "1.22",
  "id": "<YOUR_APP_ID>",
  "name": {
    "short": "Agent Mesh Bot",
    "full": "Solace Agent Mesh Teams Gateway"
  },
  "developer": {
    "name": "Your Organization",
    "websiteUrl": "https://yourorg.com/",
    "privacyUrl": "https://yourorg.com/privacy",
    "termsOfUseUrl": "https://yourorg.com/terms"
  },
  "description": {
    "short": "AI-powered intelligent assistant for Teams",
    "full": "Connect to the Solace Agent Mesh Teams Gateway to access AI agents for task automation, data analysis, document creation, and intelligent assistance directly through Microsoft Teams."
  },
  "icons": {
    "outline": "outline.png",
    "color": "color.png"
  },
  "accentColor": "#ffffff",
  "bots": [
    {
      "botId": "<YOUR_APP_ID>",
      "scopes": [
        "personal",
        "team",
        "groupChat"
      ],
      "isNotificationOnly": false,
      "supportsCalling": false,
      "supportsVideo": false,
      "supportsFiles": true
    }
  ],
  "permissions": [
    "identity",
    "messageTeamMembers"
  ],
  "validDomains": []
}
```

### 3.2: Create Icon Files

Prepare two icon files:
- `color.png` -- 192x192 pixels, full color
- `outline.png` -- 32x32 pixels, white icon on transparent background

### 3.3: Package and Upload

1. Create a ZIP file containing: `manifest.json`, `color.png`, `outline.png`
2. Upload using one of the following methods:

**Option A: Import via Teams Developer Portal**
1. Go to the [Teams Developer Portal](https://dev.teams.microsoft.com)
2. Select **Apps** > **Import app** and upload the ZIP file
3. Review and edit the app configuration if needed
4. Go to **Publish** > **Publish to org** to submit for admin approval

**Option B: Upload via Teams (for personal or team use)**
1. In Microsoft Teams, go to **Apps** > **Manage your apps** > **Upload an app**
2. Select **Upload a custom app** and choose the ZIP file

**Option C: Upload via Teams Admin Center (for organization-wide deployment)**
1. Ask your Teams Administrator to upload the app via the [Teams Admin Center](https://admin.teams.microsoft.com) under **Teams apps** > **Manage apps** > **Upload new app**
2. Once uploaded, the app is available to users in the organization

> **Note**: All options may require Teams Administrator approval depending on your organization's app policies.

## Step 4: Create and Deploy the Gateway in Agent Mesh

In the Agent Mesh Enterprise web interface, create a new Teams Gateway and provide the Azure credentials:

| Field | Value |
|-------|-------|
| **Microsoft App ID** | Application (client) ID from Step 1 |
| **Microsoft App Password** | Client secret Value from Step 1 |
| **Microsoft App Tenant ID** | Directory (tenant) ID from Step 1 |
| **Default Agent** | The agent to handle messages (defaults to OrchestratorAgent) |

After saving, **deploy the gateway** from the Agent Mesh Enterprise web interface. SAM creates the gateway pod and networking resources only after you deploy the gateway.

## Step 5: Obtain the Gateway Webhook URL

This step differs based on your SAM environment.

---

### Option A: SAM Cloud

In SAM Cloud, the platform automatically provisions a public endpoint for your Teams gateway when you deploy it.

1. After deploying the gateway in the Agent Mesh Enterprise web interface, the platform provides you with the **gateway webhook URL**
2. Your webhook URL is:

   ```
   https://<provided-gateway-hostname>/api/messages
   ```

3. Copy this webhook URL -- you will configure the URL in Azure Bot Service in Step 6

> **Note**: The webhook URL is publicly accessible via HTTPS. No additional networking setup is required.

---

### Option B: SAM Kubernetes

In SAM Kubernetes, the platform creates a **ClusterIP Service** for the gateway. This service is accessible only within the Kubernetes cluster. You must expose the webhook URL to the public internet so that Microsoft Teams can reach the gateway.

#### What SAM Creates

When you deploy the Teams gateway, SAM creates a ClusterIP Kubernetes Service. For example:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: gw-<dns-id>
spec:
  type: ClusterIP
  ports:
    - port: 8092
      targetPort: 8092
      protocol: TCP
      name: gateway
```

The `<dns-id>` is a unique identifier generated by SAM for each gateway. The platform configures the service name and port automatically during deployment.

#### Expose the Endpoint Publicly

You need to make `https://<your-domain>/api/messages` publicly accessible. Common approaches:

**Option 1: Ingress Controller**

Create an Ingress resource that routes traffic to the gateway service. The following is an example using an AWS ALB Ingress (replace `gw-example.yourdomain.com` with your own hostname):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: teams-gateway-ingress
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
    alb.ingress.kubernetes.io/certificate-arn: <your-acm-certificate-arn>
    # Recommended: ensure the ALB health check targets the gateway's health endpoint
    alb.ingress.kubernetes.io/healthcheck-path: /health
    alb.ingress.kubernetes.io/success-codes: "200"
    # If using external-dns, add this annotation to create DNS records automatically:
    # external-dns.alpha.kubernetes.io/hostname: gw-example.yourdomain.com
spec:
  ingressClassName: alb
  rules:
    - host: gw-example.yourdomain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: gw-<dns-id>
                port:
                  number: 8092
```

To expose **multiple Teams gateways**, add a rule per gateway with a unique hostname. You can use a single Ingress resource for all gateways rather than creating separate Ingress resources:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: teams-gateway-ingress
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
    alb.ingress.kubernetes.io/certificate-arn: <your-acm-certificate-arn>
    alb.ingress.kubernetes.io/healthcheck-path: /health
    alb.ingress.kubernetes.io/success-codes: "200"
    # List all gateway hostnames (comma-separated) for external-dns:
    # external-dns.alpha.kubernetes.io/hostname: gw-first.yourdomain.com,gw-second.yourdomain.com
spec:
  ingressClassName: alb
  rules:
    - host: gw-first.yourdomain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: gw-<first-dns-id>
                port:
                  number: 8092
    - host: gw-second.yourdomain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: gw-<second-dns-id>
                port:
                  number: 8092
```

When adding a new gateway, add a new rule with its hostname and service name, and update the `external-dns` hostname annotation to include the new hostname.

If your cluster does not have [external-dns](https://github.com/kubernetes-sigs/external-dns) configured, you will also need to create a DNS record manually. For example:

1. Get the load balancer hostname (may take 1-2 minutes to provision):
   ```bash
   kubectl get ingress teams-gateway-ingress -n <namespace> -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
   ```
2. In your DNS provider (Route 53, Cloudflare, etc.), create a **CNAME** record:
   ```
   sam-teams.yourdomain.com -> <load balancer hostname from above>
   ```
   If using Route 53 with an ALB, you can use an **Alias** record instead.

> **Note**: The `gw-<dns-id>` in the Ingress backend is the Kubernetes Service name created by SAM during deployment. To find this value, run `kubectl get services -n <namespace>` and look for the service prefixed with `gw-`. This example uses AWS ALB annotations -- for other ingress controllers (NGINX, Traefik, GKE), adapt the annotations accordingly. The key requirements are:
> - TLS termination (HTTPS) at the ingress
> - Route to the gateway service on port 8092

**Option 2: LoadBalancer Service**

Create a new LoadBalancer Service that forwards traffic to the gateway pod. Configure TLS termination on the cloud load balancer.

**Option 3: Reverse Proxy**

Place the gateway behind an existing reverse proxy (e.g., NGINX, Envoy) that handles TLS and forwards traffic to the ClusterIP service.

#### Your Webhook URL

Once exposed, your webhook URL will be:

```
https://<your-gateway-hostname>/api/messages
```

> **Important**: The endpoint **must** be accessible via HTTPS. Microsoft Teams will not send messages to HTTP endpoints.

To verify your setup, open `https://<your-gateway-hostname>/health` in a browser. You should see a JSON health response from the gateway, confirming the gateway is publicly accessible.

---

## Step 6: Configure the Webhook URL in Azure Bot Service

1. Go to the [Azure Portal](https://portal.azure.com)
2. Navigate to your **Azure Bot** resource
3. Go to **Configuration**
4. Set the **Messaging endpoint** to your webhook URL:
   - SAM Cloud: `https://<provided-gateway-hostname>/api/messages`
   - SAM Kubernetes: `https://<your-gateway-hostname>/api/messages`
5. Click **Apply**

## Verification

After completing all steps, verify the setup:

1. Open Microsoft Teams
2. Find and open your bot app (search by the name you gave it)
3. Send a message (e.g., "Hello")
4. You should see a processing indicator followed by a response from your agent

## Troubleshooting

### Bot does not respond to messages

- Verify the **Messaging endpoint** in Azure Bot Service matches your gateway URL exactly (including `/api/messages`)
- Confirm the gateway pod is running: check the deployment status in the Agent Mesh Enterprise web interface
- For SAM Kubernetes: verify the endpoint is publicly accessible by opening `https://<your-domain>/health` in a browser -- you should see a JSON health response
- Check that the **Microsoft App ID** and **Microsoft App Password** in Agent Mesh match your Azure App Registration credentials

### Authentication errors

- Ensure the **Microsoft App Password** (client secret) has not expired in Azure -- regenerate in **App registrations** > **Certificates & secrets** if needed
- Verify the **Tenant ID** is set correctly in both Agent Mesh and Azure

### Webhook URL requirements

- Must use **HTTPS** (not HTTP)
- Must be **publicly accessible** from the internet