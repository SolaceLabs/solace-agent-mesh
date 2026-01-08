---
title: Gateways
sidebar_position: 260
---

# Gateways

Gateways are a crucial component of the Agent Mesh framework that expose the agent mesh to external systems through various protocols. Built on a common base gateway architecture, they provide the following functions:

- serve as the primary interface between Agent Mesh and the outside world
- manage the flow of information in and out of the system through the A2A protocol
- handle authentication, user enrichment, and message processing
- support multiple interface types including REST, HTTP SSE, webhooks, and event mesh connectivity

:::tip[In one sentence]
Gateways are the external interfaces that connect various systems to the A2A agent mesh through standardized protocols.
:::

## Key Functions

1. **Entry Points**: Gateways act as the entry points from the outside world and translate external requests into A2A protocol messages and route them through the Solace event mesh to appropriate agents.

2. **Authentication & Authorization**: Common authentication and user enrichment flow across all gateway types, with pluggable identity providers.

3. **Configurable System Purpose**: Each gateway has a configurable system purpose that sets the context for all stimuli entering Agent Mesh through that gateway. This design allows for tailored processing based on the specific use case or domain.

4. **Customizable Output Formatting**: Gateways have a configurable output description that controls how stimuli responses are formatted when sent back to the outside world. This configurable output description ensures that the output meets the requirements of the receiving system or user interface.

5. **Multiple Interface Types**: Gateways can have different interfaces to accommodate various communication protocols and systems. Some examples include REST APIs, event meshes, Slack integrations, browser-based interfaces, and so on.

## How Gateways Work

The following diagram illustrates the complete flow of information through a gateway in Agent Mesh:

```mermaid
sequenceDiagram
    participant External as External System/User
    participant Gateway
    participant Mesh as Agent Mesh

    rect rgba(234, 234, 234, 1)
        Note over External,Gateway: Authentication Phase [Optional]
        External->>Gateway: Send Request
        Gateway->> Gateway: Authenticate Request
        alt Authentication Failed
            Gateway-->>External: Return Error
        end
    end

    rect rgba(234, 234, 234, 1)
        Note over Gateway: Authorization Phase [Optional]
    end

    rect rgba(234, 234, 234, 1)
        Note over Gateway,Mesh: Processing Phase
        Gateway->>Gateway: Apply System Purpose
        Gateway->>Gateway: Attach Format Rules
        Gateway->>Gateway: Format Response
        Gateway->>Gateway: Transform to Stimulus
        Gateway->>Mesh: Send Stimulus

        alt Response Expected
            Mesh-->>Gateway: Return Response
            Gateway-->>External: Send Formatted Response
        end
    end

    %%{init: {
        'theme': 'base',
        'themeVariables': {
            'actorBkg': '#00C895',
            'actorBorder': '#00C895',
            'actorTextColor': '#000000',
            'noteBkgColor': '#FFF7C2',
            'noteTextColor': '#000000',
            'noteBorderColor': '#FFF7C2'
        }
    }}%%

```

## Available Gateways

Agent Mesh comes with several built-in gateway types:

### Core Gateways

1. **HTTP SSE Gateway**
   - Real-time web interface with streaming responses
   - Server-sent events for live updates
   - Agent discovery API
   - File upload and download handling

2. **REST Gateway**
   - Task submission with immediate task ID return
   - Polling-based result retrieval
   - Authentication integration

3. **Webhook Gateway**
   - Handles incoming webhook requests
   - Transforms webhook payloads to A2A messages

### Plugin Gateways

Additional gateway types are available through the plugin ecosystem:

- **Event Mesh Gateway**: External event mesh connectivity with message transformation
- **Slack Gateway**: Slack bot integration for team collaboration
- **Microsoft Teams Gateway** *(Enterprise)*: Teams bot integration with Azure AD authentication, file sharing, and real-time streaming responses (Docker deployment only)
- **Custom Gateways**: Create your own gateway implementations

For more information about plugins and how to configure them, see [Plugins](./plugins.md).

One of the official core plugin gateway interfaces is the [Solace Event Mesh Gateway](https://github.com/SolaceLabs/solace-agent-mesh-core-plugins/tree/main/sam-event-mesh-gateway), which enables communication with the PubSub+ event broker directly as an input interface.

:::note
Each gateway type has its own configuration options and specific features. See the individual gateway documentation pages for detailed information on setup and usage.
:::

## Create a Gateway

To create a gateway, you can either [use one of the pre-existing plugins](./plugins.md#use-a-plugin) or create yours from scratch.


### Gateway from Scratch

To create a gateway from scratch, you need to use the CLI `add gateway` command without any interfaces. This command creates a _python gateway template file_ which you can then customize to your needs.

```sh
sam add gateway my-interface
```

To learn more about creating your own gateway, see [Creating Custom Gateways](../developing/create-gateways.md).

:::tip[Share and Reuse]
If you would like to share your custom gateway with the community or re-use it within other projects, you can create a plugin for it. For more information, see [Create Plugins](./plugins.md#create-a-plugin).
:::
