---
title: Teams Gateway
sidebar_position: 3
---

# Microsoft Teams Gateway Integration Guide

This guide explains how to configure the Microsoft Teams Gateway in Solace Agent Mesh (SAM). The guide covers both **SAM Cloud** and **SAM Kubernetes** environments.

## Overview

The Teams Gateway connects your SAM agents to Microsoft Teams, allowing users to interact with AI agents directly from Teams chats and channels. The gateway receives messages from Teams via an HTTPS webhook endpoint (`/api/messages`) and routes them to your SAM agents.

**How it works:**

```
Microsoft Teams --> Azure Bot Service --> HTTPS POST /api/messages --> Teams Gateway Pod --> SAM Agents
```

Teams requires the gateway's webhook endpoint to be **publicly accessible via HTTPS**. The setup differs depending on your SAM deployment environment.

## Prerequisites

Before you begin, make sure you have:

1. An **Azure account** with:
   - Permission to create **App Registrations** in Microsoft Entra ID (most organizations allow this by default; if disabled, ask your admin for the **Application Developer** role)
   - **Contributor** role (or higher) on an Azure subscription or resource group to create the Bot Service resource
2. A **Microsoft 365 account** with access to the [Teams Developer Portal](https://dev.teams.microsoft.com)
3. Access to the **SAM UI** with permissions to create and deploy gateways
4. Permission to upload custom apps in **Microsoft Teams**:
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
5. On the overview page, copy the **Application (client) ID** -- this is your **Microsoft App ID** for SAM
6. Copy the **Directory (tenant) ID** -- this is your **Microsoft App Tenant ID** for SAM
7. Go to **Certificates & secrets** > **Client secrets** > **New client secret**
   - **Description**: e.g., `SAM Bot Secret`
   - **Expires**: Choose an appropriate duration
8. Copy the secret **Value** immediately (it will not be shown again) -- this is your **Microsoft App Password** for SAM

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
   - **Messaging endpoint**: Leave blank for now. You will set the webhook URL in Step 5.
6. Navigate to **Channels** > click the **Microsoft Teams** icon
7. Ensure **Messaging** is enabled, leave **Calling** disabled
8. Accept the terms of service and click **Apply**

## Step 3: Create and Deploy the Gateway in SAM

In the SAM UI, create a new Teams Gateway and provide the Azure credentials:

| SAM Field | Value |
|-----------|-------|
| **Microsoft App ID** | Application (client) ID from Step 1 |
| **Microsoft App Password** | Client secret Value from Step 1 |
| **Microsoft App Tenant ID** | Directory (tenant) ID from Step 1 |
| **Default Agent** | The agent to handle messages (defaults to OrchestratorAgent) |

After saving, **deploy the gateway** from the SAM UI. SAM creates the gateway pod and networking resources only after you deploy the gateway.

## Step 4: Obtain the Gateway Webhook URL

This step differs based on your SAM environment.

---

### Option A: SAM Cloud

In SAM Cloud, the platform automatically provisions a public endpoint for your Teams gateway when you deploy it.

1. After deploying the gateway in the SAM UI, the platform provides you with the **gateway webhook URL**
2. Your webhook URL is:

   ```
   https://<provided-gateway-hostname>/api/messages
   ```

3. Copy this webhook URL -- you will configure the URL in Azure Bot Service in Step 5

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

Create an Ingress resource that routes traffic to the gateway service. The following is an example using an AWS ALB Ingress (replace `sam-teams.yourdomain.com` with your own hostname):

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
    # If using external-dns, add this annotation to create DNS records automatically:
    # external-dns.alpha.kubernetes.io/hostname: sam-teams.yourdomain.com
spec:
  ingressClassName: alb
  rules:
    - host: sam-teams.yourdomain.com
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

> **Note**: The `gw-<dns-id>` in the Ingress backend is the Kubernetes Service name created by SAM during deployment. This example uses AWS ALB annotations -- for other ingress controllers (NGINX, Traefik, GKE), adapt the annotations accordingly. The key requirements are:
> - TLS termination (HTTPS) at the ingress
> - Route to the gateway service on port 8092

**Option 2: LoadBalancer Service**

Change the service type to `LoadBalancer` and use a TLS-terminating load balancer in front of it.

**Option 3: Reverse Proxy**

Place the gateway behind an existing reverse proxy (e.g., NGINX, Envoy) that handles TLS and forwards traffic to the ClusterIP service.

#### Your Webhook URL

Once exposed, your webhook URL will be:

```
https://<your-public-domain>/api/messages
```

> **Important**: The endpoint **must** be accessible via HTTPS. Microsoft Teams will not send messages to HTTP endpoints.

To verify your setup, open `https://<your-public-domain>/health` in a browser. You should see a JSON health response from the gateway, confirming the gateway is publicly accessible.

---

## Step 5: Configure the Webhook URL in Azure Bot Service

1. Go to the [Azure Portal](https://portal.azure.com)
2. Navigate to your **Azure Bot** resource
3. Go to **Configuration**
4. Set the **Messaging endpoint** to your webhook URL:
   - SAM Cloud: `https://<provided-gateway-hostname>/api/messages`
   - SAM Kubernetes: `https://<your-public-domain>/api/messages`
5. Click **Apply**

## Step 6: Create and Install the Teams App

Create a Teams app package and upload it to make the bot available in Microsoft Teams.

### 6.1: Create the App Manifest

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

### 6.2: Create Icon Files

Prepare two icon files:
- `color.png` -- 192x192 pixels, full color
- `outline.png` -- 32x32 pixels, white icon on transparent background

### 6.3: Package and Upload

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

## Verification

After completing all steps, verify the setup:

1. Open Microsoft Teams
2. Find and open your bot app (search by the name you gave it)
3. Send a message (e.g., "Hello")
4. You should see a processing indicator followed by a response from your SAM agent

## Troubleshooting

### Bot does not respond to messages

- Verify the **Messaging endpoint** in Azure Bot Service matches your gateway URL exactly (including `/api/messages`)
- Confirm the gateway pod is running: check the deployment status in the SAM UI
- For SAM Kubernetes: verify the endpoint is publicly accessible by opening `https://<your-domain>/health` in a browser -- you should see a JSON health response
- Check that the **Microsoft App ID** and **Microsoft App Password** in SAM match your Azure App Registration credentials

### Authentication errors

- Ensure the **Microsoft App Password** (client secret) has not expired in Azure -- regenerate in **App registrations** > **Certificates & secrets** if needed
- Verify the **Tenant ID** is set correctly in both SAM and Azure

### Webhook URL requirements

- Must use **HTTPS** (not HTTP)
- Must be **publicly accessible** from the internet