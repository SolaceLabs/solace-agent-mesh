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

## REST API Reference

This section provides detailed curl commands for interacting with the Solace Agent Mesh v2 REST API.

### Setup

Set the required environment variables:

```sh
export SAM_TOKEN="your-access-token"
export SAM_HOST="http://localhost:8000"  # adjust for your environment
```

:::note[Getting Your Access Token]
You can retrieve your access token from the WebUI gateway by opening the browser developer console and entering:

```javascript
console.log(window.localStorage.access_token)
```

Copy the displayed token and use it as your `SAM_TOKEN` value.
:::

### API Operations

#### 1. Create Task

Create a new task with a prompt.

```sh
curl -s -X POST "${SAM_HOST}/api/v2/tasks" \
    -H "Authorization: Bearer ${SAM_TOKEN}" \
    -F "agent_name=OrchestratorAgent" \
    -F "prompt=Hi!"
```

**Parameters:**
- `agent_name` - The agent to handle the task (e.g., OrchestratorAgent)
- `prompt` - The task prompt/question

**Response:**

```json
{
  "taskId": "abc123-def456",
  ...
}
```

#### 2. Create Task with Artifact Generation

Create a task that generates an artifact (file).

```sh
curl -s -X POST "${SAM_HOST}/api/v2/tasks" \
    -H "Authorization: Bearer ${SAM_TOKEN}" \
    -F "agent_name=OrchestratorAgent" \
    -F "prompt=Create a csv file with 10 mock employees. Make sure to provide the created artifact."
```

#### 3. Create Task with File Input

Create a task with a file attachment.

```sh
curl -s -X POST "${SAM_HOST}/api/v2/tasks" \
    -H "Authorization: Bearer ${SAM_TOKEN}" \
    -F "agent_name=OrchestratorAgent" \
    -F "prompt=Give a summary of the attached file" \
    -F "files=@/path/to/your/file.pdf"
```

**Parameters:**
- `files` - File attachment (use @ prefix for file path)

#### 4. Poll Task Status

Poll the status of a task until completion.

```sh
curl -s -X GET "${SAM_HOST}/api/v2/tasks/${TASK_ID}" \
    -H "Authorization: Bearer ${SAM_TOKEN}"
```

**Response includes:**
- `taskId` - The task identifier
- `contextId` - Context ID (use this value for the `session_id` parameter in artifact operations)
- `status` - Task status (e.g., `completed`, `in_progress`)

:::warning
It might take a while for the system to respond. See the [observability](../../deploying/observability.md) page for more information about monitoring the system while it processes the request.
:::

#### 5. List Artifacts

List all artifacts for a context.

```sh
curl -s -X GET "${SAM_HOST}/api/v2/artifacts/?session_id=${CONTEXT_ID}" \
    -H "Authorization: Bearer ${SAM_TOKEN}"
```

:::info
The query parameter is `session_id`, but the value comes from `contextId` in the poll response.
:::

**Response:**

```json
[
  {
    "filename": "employees.csv",
    ...
  }
]
```

#### 6. Get Artifact

Download a specific artifact and save to a file.

```sh
# Save to file (works for binary files like images)
curl -s -X GET "${SAM_HOST}/api/v2/artifacts/${FILENAME}?session_id=${CONTEXT_ID}" \
    -H "Authorization: Bearer ${SAM_TOKEN}" \
    -o "${FILENAME}"
```

**Examples:**

```sh
# Download a CSV file
curl -s -X GET "${SAM_HOST}/api/v2/artifacts/report.csv?session_id=${CONTEXT_ID}" \
    -H "Authorization: Bearer ${SAM_TOKEN}" \
    -o "report.csv"

# Download a PNG image
curl -s -X GET "${SAM_HOST}/api/v2/artifacts/chart.png?session_id=${CONTEXT_ID}" \
    -H "Authorization: Bearer ${SAM_TOKEN}" \
    -o "chart.png"

# Output text file to stdout (for piping)
curl -s -X GET "${SAM_HOST}/api/v2/artifacts/data.json?session_id=${CONTEXT_ID}" \
    -H "Authorization: Bearer ${SAM_TOKEN}"
```

#### 7. Refresh Token

Refresh an access token.

```sh
curl -s -X POST "${SAM_HOST}/refresh_token" \
    -H "Authorization: Bearer ${SAM_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{
        "provider": "azure",
        "refresh_token": "your-refresh-token"
    }'
```

**Response:**

```json
{
  "access_token": "new-access-token",
  "refresh_token": "new-refresh-token"
}
```

### Typical Workflow

```sh
# 1. Set your token
export SAM_TOKEN="your-token"
export SAM_HOST="http://localhost:8000"

# 2. Create a task
RESPONSE=$(curl -s -X POST "${SAM_HOST}/api/v2/tasks" \
    -H "Authorization: Bearer ${SAM_TOKEN}" \
    -F "agent_name=OrchestratorAgent" \
    -F "prompt=Create a CSV with 5 products")

TASK_ID=$(echo $RESPONSE | jq -r '.taskId')
echo "Task ID: $TASK_ID"

# 3. Poll until complete
POLL_RESPONSE=$(curl -s -X GET "${SAM_HOST}/api/v2/tasks/${TASK_ID}" \
    -H "Authorization: Bearer ${SAM_TOKEN}")

echo $POLL_RESPONSE | jq .

# 4. Get context ID from poll response, then list artifacts
CONTEXT_ID=$(echo $POLL_RESPONSE | jq -r '.contextId')

curl -s -X GET "${SAM_HOST}/api/v2/artifacts/?session_id=${CONTEXT_ID}" \
    -H "Authorization: Bearer ${SAM_TOKEN}" | jq .

# 5. Download artifact
FILENAME="products.csv"
curl -s -X GET "${SAM_HOST}/api/v2/artifacts/${FILENAME}?session_id=${CONTEXT_ID}" \
    -H "Authorization: Bearer ${SAM_TOKEN}" \
    -o "${FILENAME}"

echo "Saved to: ${FILENAME}"
```

### API Endpoints Summary

| Operation | Method | Endpoint |
|-----------|--------|----------|
| Create Task | POST | `/api/v2/tasks` |
| Poll Task | GET | `/api/v2/tasks/{taskId}` |
| List Artifacts | GET | `/api/v2/artifacts/?session_id={contextId}` |
| Get Artifact | GET | `/api/v2/artifacts/{filename}?session_id={contextId}` |
| Refresh Token | POST | `/refresh_token` |

## Legacy API (v1) - Synchronous

:::warning[Deprecated]
The v1 API is deprecated. Please use the v2 API for new integrations.
:::

```sh
curl --location 'http://localhost:8080/api/v1/invoke' \
--header 'Authorization: Bearer None' \
--form 'prompt="Suggest some good outdoor activities in London given the season and current weather conditions."' \
--form 'agent_name="OrchestratorAgent"' \
--form 'stream="false"'
```

**Sample output:**

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
