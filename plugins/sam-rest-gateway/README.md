# Rest Gateway SAM Plugin
## Overview

The Solace Agent Mesh (SAM) REST API Gateway provides a standard, robust, and secure HTTP-based entry point for programmatic and system-to-system integrations. It allows external clients to submit tasks to SAM agents, manage files, and discover agent capabilities using a familiar RESTful interface.

The gateway is designed to be highly configurable and supports two distinct operational modes to cater to both modern, asynchronous workflows and legacy, synchronous systems.

## Key Features

*   **Dual API Versions**: Supports both a modern asynchronous API (v2) and a deprecated synchronous API (v1) for backward compatibility.
*   **Asynchronous by Default**: The v2 API uses a "202 Accepted + Poll" pattern, ideal for long-running agent tasks.
*   **Delegated Authentication**: Integrates with an external authentication service via bearer tokens for secure access.
*   **File Handling**: Supports file uploads for tasks and provides download URLs for generated artifacts.
*   **Dynamic Configuration**: All gateway behaviors, including server settings and authentication, are configured via the main SAM Host YAML file.

## Installation

Once the plugin is installed (e.g., from PyPI or a local wheel file):
```bash
sam plugin add <your-new-component-name> --plugin sam-rest-gateway
```
This will create a new component configuration at `configs/plugins/<your-new-component-name-kebab-case>.yaml`. 

## Configuration

The gateway is configured within the `app_config` section of its app definition in your main SAM Host YAML file.

**Example Configuration:**

```yaml
# In your main SAC config file, under the 'apps:' list
- name: my_rest_gateway_app
  app_module: solace_agent_mesh.gateway.rest.app
  app_base_path: src
  broker:
    # Standard A2A Control Plane broker connection details
    <<: *broker_connection
  app_config:
    # --- Base Gateway Config ---
    namespace: "my-org/dev"
    gateway_id: "rest-gw-01"
    artifact_service:
      type: "filesystem"
      base_path: "/tmp/sam_artifacts"
    identity_service:
      type: "local_file"
      file_path: "config/users.json"

    # --- REST Gateway Specific Config ---
    rest_api_server_host: "0.0.0.0"
    rest_api_server_port: 8080
    sync_mode_timeout_seconds: 60 # Timeout for the v1 synchronous API

    # --- Authentication Config ---
    enforce_authentication: true
    external_auth_service_url: "http://my-auth-server:8080"
```

### Configuration Parameters

*   `rest_api_server_host` (string, optional, default: "127.0.0.1"): Host address for the embedded FastAPI server.
*   `rest_api_server_port` (integer, optional, default: 8080): Port for the embedded FastAPI server.
*   `sync_mode_timeout_seconds` (integer, optional, default: 60): Timeout in seconds for synchronous v1 API calls.
*   `enforce_authentication` (boolean, optional, default: false): If true, all API endpoints (except `/health` and `/api/health`) will require a valid bearer token.
*   `external_auth_service_url` (string, optional): URL of the external authentication service for token validation. Required if `enforce_authentication` is true.

## API Documentation

The REST Gateway provides interactive API documentation (Swagger UI) for both of its API versions. The documentation is generated automatically from the code and is the single source of truth for all endpoints, parameters, and data models.

### v2 API (Asynchronous)

The v2 API is the recommended interface for all new integrations. It is non-blocking and suitable for tasks of any duration.

- **Interactive Documentation**: [http://localhost:8080/api/v2/docs](http://localhost:8080/api/v2/docs)

**Workflow:**
1.  Client sends `POST /api/v2/tasks` with the agent task details.
2.  Gateway immediately responds with `202 Accepted` and a `taskId`.
3.  Client polls `GET /api/v2/tasks/{taskId}` until it receives a `200 OK` with the final result.
4.  If the result contains artifacts, the client uses the endpoints under `/api/v2/artifacts` to download them.

### v1 API (Legacy, Synchronous - DEPRECATED)

The v1 API is provided for backward compatibility with systems that cannot handle an asynchronous workflow. **It is not recommended for new development and may be removed in a future version.**

- **Interactive Documentation**: [http://localhost:8080/api/v1/docs](http://localhost:8080/api/v1/docs)

**Workflow:**
1.  Client sends `POST /api/v1/invoke` with the agent task details.
2.  The gateway holds the HTTP connection open, waiting for the agent to complete the task.
3.  The gateway returns a `200 OK` with the final result in the response body, including any artifact content embedded as base64.

**Warning**: This endpoint is subject to the `sync_mode_timeout_seconds` configuration and is not suitable for long-running tasks.

### Health Check

The gateway provides a health check endpoint to verify its operational status. This endpoint bypasses authentication.

- **URL**: `http://localhost:8080/health`
- **Alternate URL (for backward compatibility)**: `http://localhost:8080/api/health`


