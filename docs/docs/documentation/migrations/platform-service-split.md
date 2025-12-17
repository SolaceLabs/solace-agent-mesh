---
title: "Migration to Platform Service (Enterprise v1.25.0+)"
sidebar_position: 20
---

### ✅ This Guide Applies To:

- **Users running SAM manually with YAML files** - Typically after generating your SAM application with `sam init`, you run SAM directly using configuration files (e.g., `sam run configs/gateways/webui.yaml`)
- **Users using Enterprise features and have an existing `platform.db`** - You are using features like Agent Builder, Connectors, or other enterprise capabilities that have created a `platform.db` file

### ❌ This Guide Does NOT Apply To:

- **Users using Docker images** - If you're using Solace's pre-packaged Docker images via the Docker quickstart or Kubernetes deployments with Helm charts, this migration is handled automatically
- **Users with no existing `platform.db`** - If you don't have an existing `platform.db` file or have not been using enterprise features
- **SAM Community Edition users** - This migration only applies to SAM Enterprise

## Overview

Previously, backend enterprise functionality was served from the WebUI Gateway. With version 1.25.0+, the architecture splits the WebUI Gateway into two separate services:

- **WebUI Gateway** (port 8000): Handles chat sessions, task submissions, and real-time streaming
- **Platform Service** (port 8001): Handles Agent Builder, Connector management, and deployment orchestration

## What's Changing

### Split

|  | Until v1.24.x      | After v1.25.0                  |
|--------|--------------------|--------------------------------|
| **Architecture** | WebUI Gateway      | WebUI Gateway + Platform Service |
| **Ports** | Single port (8000) | WebUI (8000) + Platform (8001) |
| **Configuration** | One YAML file      | Two YAML files                 |

### Functionality Distribution

**WebUI Gateway (port 8000)**:
- Chat interface and sessions
- Task submission and management
- Server-Sent Events (SSE) streaming
- Artifact management
- Real-time agent interactions

**Platform Service (port 8001)**:
- Agent Builder (UI-based agent creation)
- Connector management
- Deployment orchestration
- Background tasks (heartbeat monitoring, deployment tracking)

:::warning
If you upgrade to v1.25.0+ without completing this migration, users will lose access to the Agent Builder, Connector management, and dynamic agent deployment capabilities. Chat functionality will continue to work, but enterprise features will be unavailable.
:::

## Migration Steps

### Step 1: Create Platform Service Configuration

Create a new file `configs/services/platform.yaml` in your project with the following content:

```yaml
log:
  stdout_log_level: INFO
  log_file_level: INFO
  log_file: platform_service.log

!include ../shared_config.yaml

apps:
  - name: platform_service_app
    app_base_path: .
    app_module: solace_agent_mesh.services.platform.app

    broker:
      <<: *broker_connection 

    app_config:
      namespace: ${NAMESPACE} 
      database_url: "${PLATFORM_DATABASE_URL, sqlite:///platform.db}" # Must point to your existing platform.db

      fastapi_host: ${PLATFORM_API_HOST, localhost}
      fastapi_port: ${PLATFORM_API_PORT, 8001}
      cors_allowed_origins:
        - "http://localhost:3000"
        - "http://127.0.0.1:3000"
        # Add other origins as needed

      # --- Message Size Configuration ---
      max_message_size_bytes: ${MAX_MESSAGE_SIZE_BYTES, 10000000} # 10MB default

      # --- OAuth2 Authentication ---
      external_auth_service_url: ${EXTERNAL_AUTH_SERVICE_URL}
      external_auth_provider: ${EXTERNAL_AUTH_PROVIDER, generic}
      frontend_use_authorization: ${FRONTEND_USE_AUTHORIZATION, false} # Set to true for production

      # --- Background Task Configuration ---
      # Deployment monitoring
      deployment_timeout_minutes: ${DEPLOYMENT_TIMEOUT_MINUTES, 5}
      deployment_check_interval_seconds: ${DEPLOYMENT_CHECK_INTERVAL, 60}

      # Deployer heartbeat monitoring
      heartbeat_timeout_seconds: ${HEARTBEAT_TIMEOUT_SECONDS, 90}
```
:::important
`database_url` must point to the existing `platform.db` to retain agent and deployment data.
:::

### Step 2: Update WebUI Configuration

Update your existing `configs/gateways/webui.yaml` to include the Platform Service URL:

```yaml
apps:
  - name: a2a_webui_app
    app_module: solace_agent_mesh.gateway.http_sse.app
     
    # Omitted sections for brevity...

    app_config:
      namespace: ${NAMESPACE}

      # Add the following section to point to the Platform Service
      platform_service:
        url: "${PLATFORM_SERVICE_URL, http://localhost:8001}"
```

Delete `platform_service.database_url` from your WebUI yaml, as it is no longer needed.

### Step 3: Run Platform Service

In addition to running the WebUI Gateway, also start the Platform Service:

Within the same process:
```bash
sam run configs/gateways/webui.yaml configs/services/platform.yaml
```

Or within its own process:
```bash
sam run configs/services/platform.yaml
```

## Verification

After completing the migration, verify both services are running correctly:

1. **Check WebUI Gateway**:
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status":"A2A Web UI Backend is running"}
   ```

2. **Check Platform Service**:
   ```bash
   curl http://localhost:8001/health
   # Should return: {"status":"healthy","service":"Platform Service"}
   ```

3. **Verify Frontend Configuration**:
   ```bash
   curl http://localhost:8000/api/v1/config
   # Should include frontend_platform_server_url set to the Platform Service URL"
   ```

4. **Test Agent Builder** - Access the web UI and navigate to Agent Builder. You should be able to create and manage agents through the UI.
