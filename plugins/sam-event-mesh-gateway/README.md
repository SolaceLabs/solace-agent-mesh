# SAM Event Mesh Gateway: User Guide

## Overview

The Solace Agent Mesh (SAM) Event Mesh Gateway is a powerful plugin that acts as a bridge between a Solace PubSub+ event mesh and the SAM agent ecosystem. It allows external systems to trigger AI agent tasks by publishing events to the mesh, and it enables agents to publish their results back to the mesh for consumption by other applications.

**Key Features:**

*   **Event-Driven Agent Invocation**: Subscribes to topics on a "data plane" event mesh and triggers agent tasks based on received messages.
*   **Flexible Message Transformation**: Uses the Solace AI Connector's expression engine to transform incoming message payloads into prompts for AI agents.
*   **Dynamic Response Routing**: Publishes agent responses back to the event mesh on dynamically determined topics.
*   **Context Forwarding**: Preserves and forwards correlation data from an incoming event to the corresponding outgoing response, enabling request-reply patterns.
*   **Differentiated Success/Error Handling**: Routes successful agent responses and error conditions to different topics with different payload structures.
*   **Self-Contained Payloads**: Intelligently embeds agent-produced artifacts (text and binary files) directly into the output message payload.

## Installation
To install the SAM Event Mesh Gateway plugin, run the following command in your SAM project directory:

```bash
solace-agent-mesh plugin add <your-new-component-name> --plugin sam-event-mesh-gateway
```
This will create a new component configuration at `configs/plugins/<your-new-component-name-kebab-case>.yaml`.

## Configuration

The gateway is configured within the `app_config` section of its app definition in your main SAM Host YAML file.

### Core Configuration

*   `event_mesh_broker_config` (object, required): Standard SAC broker connection parameters (`broker_url`, `broker_vpn`, etc.) for the dedicated data plane client.
*   `event_handlers` (list, required): Defines how to process incoming messages from the data plane.
*   `output_handlers` (list, optional): Defines how to format and publish agent responses back to the data plane.

### `event_handlers`

Each item in the `event_handlers` list defines a listener for one or more topics.

*   `name` (string, required): A unique name for the handler.
*   `subscriptions` (list, required): A list of topic subscriptions for the data plane.
*   `input_expression` (string, required): A SAC template expression that transforms the incoming Solace message into the main text prompt for the A2A task.
*   `target_agent_name` (string, optional): The static name of the agent to send the task to.
*   `target_agent_name_expression` (string, optional): A SAC expression to dynamically determine the target agent.
*   `on_success` (string, optional): The name of the `output_handler` to use when the agent task completes successfully.
*   `on_error` (string, optional): The name of the `output_handler` to use when the agent task fails.
*   `forward_context` (object, optional): A dictionary for extracting and forwarding correlation data. Keys are custom names, and values are SAC expressions evaluated against the incoming message.

**Example `forward_context`:**
```yaml
forward_context:
  correlation_id: "input.user_properties:correlation_id"
  original_topic: "input.topic:"
```

#### Artifact Processing

The gateway can automatically create artifacts from incoming messages before generating the agent prompt. This is controlled by the optional `artifact_processing` block within an `event_handler`.

*   `artifact_processing` (object, optional): If present, enables artifact creation.
    *   `extract_artifacts_expression` (string, required): A SAC expression that resolves to the data to be processed. This can be a single item (like the raw payload) or a list of items (like a list of file objects in a JSON payload).
    *   `artifact_definition` (object, required): Defines how to extract the necessary fields for each artifact.
        *   `filename` (string, required): An expression to get the artifact's filename.
        *   `content` (string, required): An expression to get the artifact's content.
        *   `mime_type` (string, required): An expression to get the artifact's MIME type.
        *   `content_encoding` (string, optional): An expression to get the content's encoding (`base64`, `text`, or `binary`). This is crucial for correctly handling binary data.

**The `list_item:` Selector**

When `extract_artifacts_expression` resolves to a list, the gateway iterates through it. Inside the `artifact_definition` block, you must use the special `list_item:` selector to refer to fields of the current item in the list. The standard `input.payload:` selector always refers to the original, complete message payload.

### `output_handlers`

Each item in the `output_handlers` list defines a template for publishing a response.

*   `name` (string, required): A unique name for the handler.
*   `topic_expression` (string, required): A SAC expression to generate the output topic.
*   `payload_expression` (string, required): A SAC expression to generate the output payload.
*   `max_file_size_for_base64_bytes` (integer, optional, default: 1048576): The maximum size in bytes for an artifact file to be embedded in the payload.
*   `output_transforms` (list, optional): A list of standard SAC transforms to process the agent response before the payload expression is evaluated.

## Data Flow and Expression Selectors

The gateway introduces two special selectors to simplify configuration.

1.  **Incoming Message**: An event arrives on the data plane. The matching `event_handler` processes it.
    *   If `artifact_processing` is configured, artifacts are created from the message payload and saved. Their URIs are stored in `user_data.created_artifacts:uris`.
    *   `forward_context` expressions are evaluated against the incoming message. The results are stored.
    *   `input_expression` is evaluated to create the agent prompt. This expression can reference the newly created artifact URIs.
    *   The task, including the prompt and file parts for the created artifacts, is submitted to the agent.

2.  **Agent Response**: The agent completes the task and returns a final response.
    *   The gateway receives the A2A `Task` object and transforms it into a **Simplified Response Object**.
    *   The matching `output_handler` (`on_success` or `on_error`) is selected.

3.  **Outgoing Message**: The `output_handler` generates the response.
    *   The **Simplified Response Object** is made available to expressions via the `task_response:` selector.
    *   The data from `forward_context` is available via the `user_data.forward_context:` selector.
    *   `topic_expression` and `payload_expression` are evaluated to create the final message, which is then published to the data plane.

### The Simplified Response Object (`task_response:`)

This object is the primary source for the `payload_expression`.

**Structure:**
```json
{
  "text": "Combined text from the agent's response.",
  "files": [
    {
      "name": "notes.md",
      "mimeType": "text/markdown",
      "content": "Raw text content...",
      "bytes": null,
      "error": null
    },
    {
      "name": "logo.png",
      "mimeType": "image/png",
      "content": null,
      "bytes": "iVBORw0KGgo...",
      "error": null
    }
  ],
  "data": [ { "data": {"key": "value"}, ... } ],
  "a2a_task_response": { /* The original, full A2A Task or Error object */ }
}
```

*   `task_response:text`: Access the combined text.
*   `task_response:files`: Access the list of file objects.
*   `task_response:data`: Access the list of data objects.
*   `task_response:a2a_task_response`: Access the raw A2A object for advanced use cases.

### Forwarded Context (`user_data.forward_context:`)

This selector allows you to use data from the original incoming message when creating the outgoing response.

**Example:**
If `forward_context` was `{ correlation_id: "input.user_properties:correlation_id" }`, you can use it in the output handler like this:
```yaml
topic_expression: "template:my_app/response/{{text://user_data.forward_context:correlation_id}}"
```

## Advanced Examples: Artifact Handling

Here are two examples demonstrating how to use the `artifact_processing` feature.

### Processing a Raw Binary Payload

This example configures a handler to listen for raw image data on a topic. It saves the entire payload as a JPEG artifact and then asks an agent to analyze it.

```yaml
# In your event_handlers list:
- name: "iot_image_handler"
  subscriptions:
    - topic: "iot/camera/+/image"
  payload_format: "binary" # Treat payload as raw bytes
  # --- Artifact Processing Block ---
  artifact_processing:
    extract_artifacts_expression: "input.payload" # The item to process is the raw payload
    artifact_definition:
      filename: "template:iot-image-{{text://input.user_properties:deviceId}}-{{text://input.user_properties:timestamp}}.jpg"
      content: "list_item:" # The content is the item itself (the raw payload)
      mime_type: "static:image/jpeg"
      content_encoding: "static:binary" # Explicitly state the content is raw bytes
  # --- Main Prompt ---
  input_expression: "template:Analyze the attached security camera image for anomalies. The device ID is {{text://input.user_properties:deviceId}}."
  target_agent_name: "ImageAnalysisAgent"
```

### Extracting Base64 Files from a JSON Payload

This example processes a JSON event that contains a list of embedded documents. It iterates through the list, decodes each base64 file, saves it as an artifact, and includes all artifact URIs in the final prompt.

**Incoming JSON Payload on `claims/new`:**
```json
{
  "caseId": "C-12345",
  "documents": [
    { "docName": "claim_form.pdf", "docContent": "JVBERi...", "docType": "application/pdf", "encoding": "base64" },
    { "docName": "notes.txt", "docContent": "This is a note.", "docType": "text/plain", "encoding": "text" }
  ]
}
```

**Handler Configuration:**
```yaml
# In your event_handlers list:
- name: "insurance_claim_handler"
  subscriptions:
    - topic: "claims/new"
  payload_format: "json"
  # --- Artifact Processing Block ---
  artifact_processing:
    extract_artifacts_expression: "input.payload:documents" # The item list
    artifact_definition:
      # These expressions are evaluated for EACH item in the 'documents' list
      filename: "list_item:docName"
      content: "list_item:docContent"
      mime_type: "list_item:docType"
      content_encoding: "list_item:encoding" # Dynamically get encoding from payload
  # --- Main Prompt ---
  input_expression: "template:Process insurance case {{text://input.payload:caseId}}. The relevant documents have been attached."
  target_agent_name: "ClaimsProcessingAgent"
```

## Full Configuration Example

```yaml
# In your main SAC config file, under the 'apps:' list
- name: my_event_mesh_gateway_app
  app_module: sam_event_mesh_gateway.app
  app_base_path: plugins/sam-event-mesh-gateway/src
  broker: # A2A Control Plane Connection
    <<: *broker_connection # Using a YAML anchor for connection details
  app_config:
    namespace: "my-org/dev"
    gateway_id: "event-mesh-gw-01"
    artifact_service:
      type: "filesystem"
      base_path: "/tmp/sam_artifacts"
    
    # Data Plane Connection
    event_mesh_broker_config:
      broker_url: ${DATAPLANE_SOLACE_BROKER_URL}
      broker_vpn: ${DATAPLANE_SOLACE_BROKER_VPN}
      broker_username: ${DATAPLANE_SOLACE_BROKER_USERNAME}
      broker_password: ${DATAPLANE_SOLACE_BROKER_PASSWORD}

    # --- Event Handlers: Define how to process incoming messages ---
    event_handlers:
      - name: "process_json_order_handler"
        subscriptions:
          - topic: "acme/orders/json/>"
        input_expression: "template:Summarize this order and check for issues: {{json://input.payload}}"
        target_agent_name: "OrderProcessingAgent"
        on_success: "order_success_handler"
        on_error: "order_error_handler"
        forward_context:
          order_id: "json://input.payload:orderId"
          reply_topic: "input.user_properties:replyTo"

    # --- Output Handlers: Define how to publish agent responses ---
    output_handlers:
      - name: "order_success_handler"
        max_file_size_for_base64_bytes: 2097152 # 2MB
        topic_expression: "user_data.forward_context:reply_topic" # Use replyTo from original message
        payload_expression: "task_response:" # Send the whole simplified object as JSON

      - name: "order_error_handler"
        topic_expression: "template:acme/orders/error/{{text://user_data.forward_context:order_id}}"
        payload_expression: "task_response:a2a_task_response.error" # Send just the error details
        payload_format: "json"
```
