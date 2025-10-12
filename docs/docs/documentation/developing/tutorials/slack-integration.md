---
title: Slack Integration
sidebar_position: 60
---

# Slack Integration

This tutorial integrates a Slack interface into Agent Mesh, enabling interaction with the system directly from your Slack workspace and channels.

:::info[Learn about gateways]
Read about [Gateways](../../components/gateways.md) before you start this tutorial.
:::

## Setting Up the Environment

First, you need to [install Agent Mesh and the CLI](../../installing-and-configuring/installation.md), and then [create a new Agent Mesh project](../../installing-and-configuring/run-project.md) or [create a new gateway plugin](../../components/plugins.md#create-a-plugin).

## Creating the Slack App

Next, create a [Slack Application](https://api.slack.com/apps) in your workspace.

1. Go to the [Slack Application](https://api.slack.com/apps) website.
2. Select **Your Apps** and click **Create New App**.
3. Choose **From a manifest** and apply the following configuration.
   - You can customize the name and description, but keep the rest of the configuration and settings unchanged.

```yaml
display_information:
  name: solace-agent-mesh-bot
  description: An app to integrate with Agent Mesh
features:
  app_home:
    home_tab_enabled: false
    messages_tab_enabled: true
    messages_tab_read_only_enabled: false
  bot_user:
    display_name: Agent Mesh
    always_online: false
oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - bookmarks:read
      - channels:history
      - channels:join
      - channels:manage
      - channels:read
      - chat:write
      - chat:write.customize
      - chat:write.public
      - files:read
      - files:write
      - groups:history
      - groups:read
      - groups:write
      - im:history
      - im:read
      - im:write
      - links:read
      - links:write
      - mpim:history
      - mpim:read
      - mpim:write
      - pins:read
      - pins:write
      - reactions:read
      - reactions:write
      - reminders:read
      - reminders:write
      - team:read
      - usergroups:read
      - usergroups:write
      - users.profile:read
      - users:read.email
      - users:read
      - users:write
      - conversations.connect:read
      - conversations.connect:write
      - incoming-webhook
settings:
  event_subscriptions:
    bot_events:
      - app_mention
      - message.groups
      - message.im
  interactivity:
    is_enabled: true
  org_deploy_enabled: false
  socket_mode_enabled: true
  token_rotation_enabled: false
```

Then select `Create` to create your new App.

### App-Level Tokens

In your created App, select `Basic Information` under `Settings`. Scroll down to `App-Level Tokens` and click `Generate Token and Scopes`.

Provide your token a name, add all available scopes, and then click `Generate`.

Make note of the resulting application token (beginning with `xapp-`) - you need it in a future step.

### Installing the App in Your Slack Workspace

Next, select **Install App** under **Settings** and follow the installation flow to install the App in your workspace.

After installation, the bot token (beginning with `xoxb-`) is visible. Make note of this token.

## Installing the Slack Gateway

After configuring your Slack App, the next step is to add the Slack gateway to Agent Mesh.

1. Add the gateway plugin using the Agent Mesh CLI:

   ```sh
   sam plugin add slack-bot --plugin sam-slack
   ```

    You can change `slack-bot` to any name you prefer for your gateway.

2. Configure the required environment variables:

   The Slack interface requires two authentication tokens. Add these to your `.env` file in the project root directory using the tokens generated during Slack App setup:

   ```env
   SLACK_BOT_TOKEN=xoxb-xxxxxxxxxx
   SLACK_APP_TOKEN=xapp-xxxxxxxxxx
   ```

  :::tip

  You can further customize the Slack gateway by updating the `configs/gateways/slack-bot.yaml` file. This file contains the configuration for the Slack gateway, including the initial status message, the gateway system purpose, and response format.

  :::

## Running the Slack Gateway

Launch the Slack gateway with:

```sh
sam run configs/gateways/slack-bot.yaml
```

For detailed information about available Agent Mesh CLI commands, see [Agent Mesh CLI](../../components/cli.md).

## Testing the Installation

To test your installation:

1. Open your Slack workspace in the desktop app or browser.
2. Find and click on the **Agent Mesh** app under the **Apps** section.
3. Send a test message by typing `hello` and click **Enter**.
4. You should see:
   - A "Chatbot is thinking..." status message
   - A response from the chatbot within a few seconds
