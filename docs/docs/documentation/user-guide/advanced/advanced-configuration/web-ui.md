---
title: Web UI
sidebar_position: 20
---
# Advanced Web UI Configuration

The Web UI provides a web interface for interacting with Solace Agent Mesh. It supports feedback collection.

### Web UI Settings

:::info[Configuration Dependencies]
Setting `WEBUI_FRONTEND_COLLECT_FEEDBACK` to `true` requires additional configuration, which is detailed below.
:::

| Environment Variable | Description |
|----------------------|-------------|
| `WEBUI_ENABLED` | Set to `true` to enable Web UI. |
| `WEBUI_PORT` | Port number for the Web UI (default: 5001). |
| `WEBUI_HOST` | Host address for the Web UI (default: localhost). |
| `WEBUI_FRONTEND_URL` | Full URL where the frontend will be accessed from. Used for CORS policy configuration (e.g., http://localhost:5001). |
| `WEBUI_FRONTEND_COLLECT_FEEDBACK` | Set to `true` to enable feedback collection (requires additional feedback-related variables). |
| `WEBUI_FRONTEND_WELCOME_MESSAGE` | Custom welcome message (leave empty for default). |

### Feedback Collection Dependencies

To enable feedback collection, set `WEBUI_FRONTEND_COLLECT_FEEDBACK=True`. When enabled, the following additional environment variables are required:

| Environment Variable | Description |
|----------------------|-------------|
| `SOLACE_BROKER_REST_MESSAGING_URL` | Defines the messaging endpoint for Solace broker integration. |
| `SOLACE_BROKER_BASIC_AUTH` | Authentication credentials for the Solace broker. |

## Usage

To configure these settings, set the corresponding environment variables in your deployment. Example:

```sh
export WEBUI_PORT=5001
export WEBUI_HOST=127.0.0.1
export WEBUI_FRONTEND_URL=http://127.0.0.1:5001
export WEBUI_FRONTEND_COLLECT_FEEDBACK=true
export SOLACE_BROKER_REST_MESSAGING_URL="your-rest-messaging-url"
export SOLACE_BROKER_BASIC_AUTH="your-auth-credentials"
```

These settings can also be defined in an `.env` file for easier management.

```
WEBUI_PORT=5001
WEBUI_HOST=127.0.0.1
WEBUI_FRONTEND_URL=http://127.0.0.1:5001
WEBUI_FRONTEND_COLLECT_FEEDBACK=true
SOLACE_BROKER_REST_MESSAGING_URL=your-messaging-url
SOLACE_BROKER_BASIC_AUTH=your-auth-credentials
```