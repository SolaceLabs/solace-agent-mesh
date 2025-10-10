---
title: REST Gateway
sidebar_position: 15
---


Agent Mesh REST API Gateway provides a standard, robust, and secure HTTP-based entry point for programmatic and system-to-system integrations. It allows external clients to submit tasks to Agent Mesh agents, manage files, and discover agent capabilities using a familiar RESTful interface.

The gateway is designed to be highly configurable and supports two distinct operational modes to cater to both modern, asynchronous workflows and legacy, synchronous systems.

## Key Features

*   **Dual API Versions**: Supports both a modern asynchronous API (v2) and a deprecated synchronous API (v1) for backward compatibility.
*   **Asynchronous by Default**: The v2 API uses a "202 Accepted + Poll" pattern, ideal for long-running agent tasks.
*   **Delegated Authentication**: Integrates with an external authentication service via bearer tokens for secure access.
*   **File Handling**: Supports file uploads for tasks and provides download URLs for generated artifacts.
*   **Dynamic Configuration**: All gateway behaviors, including server settings and authentication, are configured via the main Agent Mesh Host YAML file.

## Setting Up the Environment

First, you need to [install Agent Mesh and the Agent Mesh CLI](../../installing-and-configuring/installation.md), and then [create a new Agent Mesh project](../../installing-and-configuring/run-project.md).

## Adding the REST Gateway Plugin

Once you have your project set up, add the REST Gateway plugin:

```sh
sam plugin add my-http-rest --plugin sam-rest-gateway
```

You can use any name for your agent, in this tutorial we use `my-http-rest`.

This command:
1. Installs the `sam-rest-gateway` plugin
2. Creates a new gateway configuration named `my-http-rest` in your `configs/gateways/` directory


### Configuring the REST Gateway

For further configuration, you can edit the `configs/gateways/my-http-rest.yaml` file. This file contains the gateway configuration that can be customized for your use case.

:::info[Using a local Solace Broker container]
The Solace broker container uses port 8080. You need to edit the `rest_api_server_port` field and `external_auth_service_url` field in the `configs/gateways/my-http-rest.yaml` file to a free port other than 8080 (for example: 8081).

You can edit the YAML file directly or add environment variables `REST_API_PORT=8081` and `EXTERNAL_AUTH_SERVICE_URL=http://localhost:8081`.

Make sure you change the REST API gateway to your new port in the following request examples.
:::

## Running the REST Gateway

To run the REST Gateway, use the following command:

```sh
sam run configs/gateways/my-http-rest.yaml
```

## Sending a Request via REST API

You can also interact with Agent Mesh via the **REST API**.

The REST API gateway runs on `http://localhost:8080` by default. You can use either the legacy v1 API or the modern async v2 API.

### Modern API (v2) - Asynchronous
```sh
# Submit task
curl --location 'http://localhost:8080/api/v2/tasks' \
--header 'Authorization: Bearer token' \
--form 'agent_name="OrchestratorAgent"' \
--form 'prompt="Hi\!"'

# Poll for result using returned task ID
curl --location 'http://localhost:8080/api/v2/tasks/{taskId}' \
--header 'Authorization: Bearer token'
```

:::warning
It might take a while for the system to respond. See the [observability](../../deploying/observability.md) page for more information about monitoring the system while it processes the request.
:::

Sample output:

From `api/v2/tasks`
```json
{
  "taskId":"task-6a0e682f4f6c4927a5997e4fd06eea83"
}
```

From `api/v2/tasks/{taskId}`

```json
{
  "id": "task-6a0e682f4f6c4927a5997e4fd06eea83",
  "sessionId": "rest-session-4df0c24fcecc45fcb69692db9876bc5c",
  "status": {
    "state": "completed",
    "message": {
      "role": "agent",
      "parts": [{ "type": "text", "text": "Outdoor Activities in London: Spring Edition. Today's Perfect Activities (13°C, Light Cloud): - Royal Parks Exploration : Hyde Park and Kensington Gardens..." }]
    },
    "timestamp": "2025-07-03T16:54:15.273085"
  },
  "artifacts": [],
  "metadata": { "agent_name": "OrchestratorAgent" }
}
```


### Legacy API (v1) - Synchronous
```sh
curl --location 'http://localhost:8080/api/v1/invoke' \
--header 'Authorization: Bearer None' \
--form 'prompt="Suggest some good outdoor activities in London given the season and current weather conditions."' \
--form 'agent_name="OrchestratorAgent"' \
--form 'stream="false"'
```

Sample output:

```json
{
  "id": "task-9f7d5f465f5a4f1ca799e8e5ecb35a43",
  "sessionId": "rest-session-36b36eeb69b04da7b67708f90e5512dc",
  "status": {
    "state": "completed",
    "message": {
      "role": "agent",
      "parts": [
        { "type": "text", "text": "Outdoor Activities in London: Spring Edition. Today's Perfect Activities (13°C, Light Cloud): - Royal Parks Exploration : Hyde Park and Kensington Gardens..." }
      ]
    },
    "timestamp": "2025-07-03T16:59:37.486480"
  },
  "artifacts": [],
  "metadata": { "agent_name": "OrchestratorAgent" }
}
```
