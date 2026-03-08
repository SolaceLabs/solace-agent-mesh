---
title: Slack Gateway
sidebar_position: 2
---

# Slack Gateway

Slack gateways integrate Agent Mesh with Slack workspaces, enabling users to interact with agents through Slack channels and direct messages. The gateway uses Socket Mode for real-time message processing without requiring public endpoints.

## Overview

Slack gateways connect to Slack workspaces using the Slack Events API and Socket Mode. When users send messages in configured channels or direct messages to the bot, the gateway receives these events and forwards them to Agent Mesh as stimuli. Agent responses are sent back to Slack as reply messages.

Socket Mode establishes a WebSocket connection from the gateway to Slack's servers, eliminating the need for public-facing endpoints or webhook URLs.

## Prerequisites

Before creating a Slack gateway, verify that you have the following:

### Slack App Configuration

You need a Slack App created in your workspace with the following:

1. Bot Token Scopes: The app must have appropriate OAuth scopes for messaging.
2. Socket Mode: Socket Mode must be enabled for the app.
3. Event Subscriptions: The app must subscribe to message events.

### Required Slack Tokens

You need two tokens from your Slack App configuration:

| Token Type | Prefix | Purpose |
|------------|--------|---------|
| Bot Token | `xoxb-` | Authenticates API calls to send messages |
| App Token | `xapp-` | Establishes Socket Mode WebSocket connection |

### Slack App Setup Steps

If you have not created a Slack App yet, follow these steps:

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click "Create New App"
2. Choose "From scratch" and provide an app name and workspace
3. Navigate to Socket Mode and enable it. Create an app-level token with `connections:write` scope. Save this token (starts with `xapp-`).
4. Navigate to OAuth & Permissions and add the following Bot Token Scopes:
   - `app_mentions:read`—Receive mention events
   - `channels:history`—Read channel messages
   - `chat:write`—Send messages
   - `im:history`—Read direct messages
   - `im:write`—Send direct messages
   - `users:read`—Read user information
5. Navigate to Event Subscriptions and enable events. Subscribe to bot events:
   - `app_mention`—When the bot is mentioned
   - `message.channels`—Messages in public channels
   - `message.im`—Direct messages to the bot
6. Install the app to your workspace. Save the Bot User OAuth Token (starts with `xoxb-`)

## Creating a Slack Gateway

You create Slack gateways through the Gateways section in the Agent Mesh Enterprise web interface. Navigate to Gateways and click the Create Gateway button, then select "Slack" as the gateway type.

### Configuration Fields

The Slack gateway creation form requires the following information:

#### Basic Details

Provide a unique gateway name (3–255 characters) and a description of its purpose (10–1000 characters).

#### Slack Configuration

##### Bot Token

The Bot User OAuth Token from your Slack App. This token must start with `xoxb-` and is used to authenticate API calls for sending messages and accessing Slack resources.

Example: `xoxb-your-bot-token`

##### App Token

The App-Level Token from your Slack App's Socket Mode configuration. This token must start with `xapp-` and is used to establish the Socket Mode WebSocket connection.

Example: `xapp-your-app-token`

##### Default Agent

The agent that handles incoming messages. Select from available deployed agents in your Agent Mesh deployment. This field is optional—if you do not select an agent, messages are routed to the Orchestrator, which determines the appropriate agent based on the message content.

### Example Configuration

The following example shows a configuration for a Slack gateway:

Basic Details:
- Name: `Engineering Support Bot`
- Description: `Slack bot for the engineering team to interact with documentation and code analysis agents`

Slack Configuration:
- Bot Token: `xoxb-...` (from Slack App OAuth settings)
- App Token: `xapp-...` (from Slack App Socket Mode settings)
- Default Agent: `engineering-assistant`

## After Creating the Gateway

After you save the gateway, it appears in the Gateways list with "Not Deployed" status. You can edit, download the YAML configuration, or deploy it. Once deployed, the gateway connects to Slack through Socket Mode and users can interact with the bot by mentioning it in channels or sending direct messages. For details on deployment, states, and lifecycle management, see [Gateways](gateways.md).

## How Message Processing Works

The following diagram shows the message processing flow when a user sends a message to the Slack bot.

```mermaid
sequenceDiagram
    participant User as Slack User
    participant Slack as Slack Platform
    participant Gateway as Slack Gateway
    participant Mesh as Agent Mesh
    participant Agent as Default Agent

    User->>Slack: Send Message
    Slack->>Gateway: Socket Mode Event
    Gateway->>Gateway: Parse Message
    Gateway->>Gateway: Build Stimulus
    Gateway->>Mesh: Send Stimulus
    Mesh->>Agent: Route to Agent
    Agent->>Agent: Process Request
    Agent->>Mesh: Return Response
    Mesh->>Gateway: Deliver Response
    Gateway->>Slack: Post Reply
    Slack->>User: Display Reply
```

## Security Considerations

### Token Security

Slack tokens provide access to your workspace. These tokens are stored encrypted, redacted from API responses, and injected at deployment time through Kubernetes Secrets. For more details on credential handling, see [Gateways](gateways.md).

:::warning[Token Security]
Never commit downloaded YAML files containing actual tokens to version control. Never share Bot or App tokens publicly. If tokens are compromised, regenerate them immediately in your Slack App settings.
:::

### Workspace Access

The Slack bot has access to messages in channels where it has been added and direct messages sent to it. Consider the following:

- Only add the bot to channels where agent access is appropriate
- Users should be aware that messages to the bot are processed by Agent Mesh
- The bot's responses may contain information from connected data sources

### Token Rotation

If you need to rotate Slack tokens:

1. Generate new tokens in your Slack App settings
2. Update the gateway configuration with new tokens
3. Deploy the gateway update
4. Revoke the old tokens in Slack

## Troubleshooting

### Gateway Shows Disconnected

A deployed gateway shows "Disconnected" connection status.

This issue can occur when the gateway pod crashed or was evicted, when the Bot Token or App Token is invalid, when Socket Mode is not enabled in the Slack App, or when there are network connectivity issues to Slack.

To resolve this issue:
1. Check Kubernetes pod status: `kubectl get pods | grep gateway`
2. Check pod logs: `kubectl logs <pod-name>`
3. Verify tokens are correct and start with expected prefixes
4. Confirm Socket Mode is enabled in your Slack App settings
5. Consider undeploying and redeploying the gateway

### Bot Not Responding to Messages

Users send messages to the bot but receive no response.

This issue can occur when the bot is not added to the channel, when event subscriptions are not configured, when the default agent is not deployed, or when message events are not reaching the gateway.

To resolve this issue:
1. Ensure the bot is added to channels where users are messaging
2. Verify Event Subscriptions are configured in the Slack App
3. Check that the default agent is deployed and responding
4. Review gateway logs for incoming events

### Authentication Errors

Gateway logs show authentication or token errors.

This issue can occur when tokens are invalid or expired, when tokens are from different Slack Apps, or when the incorrect token type is used (such as using an App Token where a Bot Token is expected).

To resolve this issue:
1. Verify Bot Token starts with `xoxb-`
2. Verify App Token starts with `xapp-`
3. Ensure both tokens are from the same Slack App
4. Regenerate tokens if they may have been revoked

### Missing Permissions

The bot can connect but cannot read messages or send replies.

This issue can occur when OAuth scopes are missing on the Bot Token, or when the app was not reinstalled after adding scopes.

To resolve this issue:
1. Review required scopes in the Prerequisites section
2. Add any missing scopes in Slack App OAuth settings
3. Reinstall the app to your workspace to apply new scopes
