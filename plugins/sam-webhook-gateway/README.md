# sam-webhook-gateway: Universal Webhook Gateway SAM Plugin

A Universal Webhook Gateway for the Solace Agent Mesh (SAM) that allows external systems to trigger A2A (Agent-to-Agent) tasks via HTTP webhooks.

This plugin implements a FastAPI-based HTTP server that receives webhook requests, authenticates them, translates the HTTP payloads into A2A task format, and submits the tasks to target agents. The gateway provides immediate HTTP acknowledgements while processing tasks asynchronously.

## Key Features

- **Dynamic Webhook Endpoints**: Configure multiple webhook endpoints with custom paths, methods, and authentication.
- **Flexible Payload Processing**: Supports JSON, YAML, text, form data, and binary formats.
- **A2A Integration**: Translates webhook requests into A2A tasks using configurable Jinja2 templates.
- **Pluggable Authentication**: Supports token-based, basic authentication, or no authentication per endpoint.
- **Artifact Support**: Can automatically save incoming payloads or form file uploads as artifacts for later use in the agent mesh.


## Configuration (`config.yaml`)

### Webhook Configuration

The primary configuration is done under the `component_config` section of the generated YAML file (e.g., `configs/plugins/my-webhook.yaml`).

#### Top-Level Options

-   `webhook_server_host`: The host to bind the HTTP server to (e.g., `0.0.0.0`).
-   `webhook_server_port`: The port for the HTTP server (e.g., `8080`).
-   `cors_allowed_origins`: A list of allowed origins for CORS (e.g., `["*"]`).
-   `webhook_endpoints`: A list of webhook endpoint configurations.

#### Endpoint Configuration

Each item in the `webhook_endpoints` list defines a webhook.

**Example:**

```yaml
webhook_endpoints:
  - path: "/hooks/data-feed"
    method: "POST"
    target_agent_name: "data_processor_agent"
    input_template: "Process this data: {{ payload }}"
    auth:
      type: "none"
    payload_format: "json"

  - path: "/hooks/secure-upload"
    method: "POST"
    target_agent_name: "file_processor"
    input_template: "Process uploaded file for {{ user_data:headers.X-User-ID }}. File URI: {{ user_data:webhook_payload_artifact_uri }}"
    auth:
      type: "token"
      token_config:
        location: "header"
        name: "X-API-Key"
        value: "${SECRET_API_KEY}" # Resolves from environment variable
    payload_format: "binary"
    save_payload_as_artifact: true
    artifact_filename_template: "uploads/{{ timestamp }}_{{ user_data:headers.X-File-Name | default('file.dat') }}"
```

#### Template Variables

The `input_template` and `artifact_filename_template` fields are Jinja2 templates and have access to the following variables:

-   `{{ payload }}`: The parsed request body.
-   `{{ topic }}`: The request path (e.g., `/hooks/data-feed`).
-   `{{ timestamp }}`: The ISO 8601 timestamp of the request.
-   `{{ user_properties }}`: Dictionary of query parameters.
-   `{{ user_data }}`: A dictionary containing additional request metadata:
    -   `method`: The HTTP method.
    -   `client_host`: The client's IP address.
    -   `headers`: Dictionary of request headers.
    -   `webhook_payload_artifact_uri`: The URI of the saved payload artifact (if `save_payload_as_artifact` is true).
    -   `uploaded_files`: A dictionary of saved file artifacts from a `form_data` request.

## Installation

```bash
sam plugin add <your-new-component-name> --plugin sam-webhook-gateway
```

This will create a new component configuration at `configs/plugins/<your-new-component-name-kebab-case>.yaml`. You can then edit this file to define your webhook endpoints.