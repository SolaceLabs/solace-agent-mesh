---
title: Event Mesh Gateway
sidebar_position: 20
---

# Event Mesh Gateway

If you already have an [event mesh](https://solace.com/what-is-an-event-mesh/) in place, you can integrate Agent Mesh into it. This allows you to leverage existing infrastructure while introducing intelligence and automation through Agent Mesh.

## Benefits of Integrating with an Event Mesh

- **Seamless Communication**: Agent Mesh can subscribe to and publish events across the entire event mesh
- **Event-Driven Automation**: Intelligent event processing based on patterns and AI-driven insights
- **Scalability**: Agent Mesh can dynamically participate in large-scale event-driven systems

The Event Mesh Gateway connects Agent Mesh to your existing event mesh infrastructure. Through its asynchronous interfaces, applications within your event mesh can seamlessly access and utilize Agent Mesh capabilities.

This tutorial shows you how to build an Event Mesh Gateway that automatically generates and adds concise summaries to Jira bug reports, making them easier to understand at a glance.

## Prerequisites

This tutorial assumes you have an existing Jira application integrated with your event mesh that:

1. Publishes a "jira_created" event to topic `jira/issue/created/<jira_id>` when a new Jira issue is created
2. Listens for "jira_update" events on topic `jira/issue/update` to update existing issues

Create an Event Mesh Gateway that:

1. Monitors for new Jira issues
2. Automatically generates a concise summary
3. Creates an event to update the original Jira issue with this summary

This creates a streamlined workflow where bug reports are automatically enhanced with clear, AI-generated summaries.

## Setting Up the Environment

First, you need to [install Agent Mesh and the Agent Mesh CLI](../../installing-and-configuring/installation.md), and then [create a new Agent Mesh project](../../installing-and-configuring/run-project.md).

For this tutorial, you need to create or use an existing [Solace Event Broker](https://solace.com/products/event-broker/) or [event mesh](https://solace.com/solutions/initiative/event-mesh/) created using Solace event brokers.

## Adding the Event Mesh Gateway Plugin

Once you have your project set up, add the Event Mesh Gateway plugin:

```sh
sam plugin add jira-event-mesh --plugin sam-event-mesh-gateway
```

You can use any name for your agent, in this tutorial we use `jira-event-mesh`.

This command:
1. Installs the `sam-event-mesh-gateway` plugin
2. Creates a new gateway configuration named `jira-event-mesh` in your `configs/gateways/` directory

#### Configuring the Event Mesh Gateway

After adding the plugin, you can see a new configuration file in `configs/gateways/jira-event-mesh.yaml`. This file contains the gateway configuration that needs to be customized for your Jira integration use case.

#### Environment Variables

First, set up the required environment variables for the data plane connection:

```sh
# Data plane Solace broker connection (can be same or different from control plane)
export JIRA_EVENT_MESH_SOLACE_BROKER_URL="ws://localhost:8008"
export JIRA_EVENT_MESH_SOLACE_BROKER_VPN="default"
export JIRA_EVENT_MESH_SOLACE_BROKER_USERNAME="default"
export JIRA_EVENT_MESH_SOLACE_BROKER_PASSWORD="default"
```

### Gateway Configuration

The main configuration includes several key sections:

#### Event Handlers

Configure the event handler to listen for new Jira issues and generate summaries:

```yaml
event_handlers:
  - name: "jira_issue_handler"
    subscriptions:
      - topic: "jira/issue/created/>"
        qos: 1
    input_expression: "template:Create a concise summary for the newly created Jira issue: Title: {{text://input.payload:title}}, Body: {{text://input.payload:body}}, ID: {{text://input.payload:id}}. Return a JSON object with fields 'id', 'type' (value should be 'summary'), and 'summary'."
    payload_encoding: "utf-8"
    payload_format: "json"
    target_agent_name: "OrchestratorAgent"
    on_success: "jira_summary_handler"
    on_error: "error_response_handler"
    forward_context:
      jira_id: "input.payload:id"
      correlation_id: "input.user_properties:correlation_id"
```

#### Output Handlers

Configure output handlers to publish the summary back to the event mesh:

```yaml
output_handlers:
  - name: "jira_summary_handler"
    topic_expression: "static:jira/issue/update"
    payload_expression: "task_response:text"
    payload_encoding: "utf-8"
    payload_format: "json"
    
  - name: "error_response_handler"
    topic_expression: "template:jira/issue/error/{{text://user_data.forward_context:jira_id}}"
    payload_expression: "task_response:a2a_task_response.error"
    payload_encoding: "utf-8"
    payload_format: "json"
```

### Complete Configuration Example

Here is a complete configuration file based on the plugin template:

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: jira-event-mesh.log

!include ../shared_config.yaml

apps:
  - name: jira-event-mesh-app
    app_module: sam_event_mesh_gateway.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      gateway_id: "jira-event-mesh-gw-01"
      artifact_service: *default_artifact_service
      default_user_identity: "anonymous_event_mesh_user" # If no identity from event



      # Data plane connection
      event_mesh_broker_config:
        broker_url: ${JIRA_EVENT_MESH_SOLACE_BROKER_URL}
        broker_vpn: ${JIRA_EVENT_MESH_SOLACE_BROKER_VPN}
        broker_username: ${JIRA_EVENT_MESH_SOLACE_BROKER_USERNAME}
        broker_password: ${JIRA_EVENT_MESH_SOLACE_BROKER_PASSWORD}

      event_handlers:
        - name: "jira_issue_handler"
          subscriptions:
            - topic: "jira/issue/created/>"
              qos: 1
          input_expression: "template:Create a concise summary for the newly created Jira issue: Title: {{text://input.payload:title}}, Body: {{text://input.payload:body}}, ID: {{text://input.payload:id}}. Return a JSON object with fields 'id', 'type' (value should be 'summary'), and 'summary'."
          payload_encoding: "utf-8"
          payload_format: "json"
          target_agent_name: "OrchestratorAgent"
          on_success: "jira_summary_handler"
          on_error: "error_response_handler"
          forward_context:
            jira_id: "input.payload:id"

      output_handlers:
        - name: "jira_summary_handler"
          topic_expression: "static:jira/issue/update"
          payload_expression: "task_response:text"
          payload_encoding: "utf-8"
          payload_format: "json"
          
        - name: "error_response_handler"
          topic_expression: "template:jira/issue/error/{{text://user_data.forward_context:jira_id}}"
          payload_expression: "task_response:a2a_task_response.error"
          payload_encoding: "utf-8"
          payload_format: "json"
```

## Running the Event Mesh Gateway

Now you can run the Event Mesh Gateway:

```sh
sam run configs/gateways/jira-event-mesh.yaml
```

The gateway:
1. Connects to both the A2A control plane and the data plane event mesh
2. Subscribes to the configured topics on the data plane
3. Starts processing incoming events and routing them to agents

## Testing the Event Mesh Gateway

Now that the system is running, let's test the Event Mesh Gateway.

### Using The Solace Broker Manager

1. Open the **Try Me!** tab of the [Solace Broker Manager](https://docs.solace.com/Admin/Broker-Manager/PubSub-Manager-Overview.htm)

2. Connect both the **Publisher** and **Subscriber** panels by clicking their respective **Connect** buttons

3. In the Subscriber panel:
   - Enter `jira/issue/update` in the `Topic Subscriber` field
   - Click `Subscribe`

4. In the Publisher panel:
   - Use the topic `jira/issue/created/JIRA-143321`
   - In the `Message Content` field, enter:

```json
{
  "id": "JIRA-143321",
  "title": "Exception when reading customer record",
  "body": "I got a DatabaseReadException when trying to get the data for customer ABC. The error indicated that the customer didn't exist, while they are our biggest customer!"
}
```

5. Click **Publish**

After a few seconds, you can see a new message in the **Subscriber** messages with the topic `jira/issue/update` and a body similar to:

```json
{
  "id": "JIRA-143321",
  "type": "summary",
  "summary": "Database read error: Unable to retrieve record for key customer ABC despite confirmed existence"
}
```

## Advanced Features

The Event Mesh Gateway supports several advanced features:

### Artifact Processing

You can configure the gateway to automatically create artifacts from incoming message payloads before sending them to agents. This is useful for processing files, images, or other binary data embedded in events.

### Dynamic Agent Routing

Instead of using a static `target_agent_name`, you can use `target_agent_name_expression` to dynamically determine which agent should process each event based on the message content.

### Context Forwarding

The `forward_context` configuration allows you to extract data from incoming messages and make it available when generating outgoing responses, enabling request-reply patterns and correlation tracking.

### Error Handling

Configure separate output handlers for success and error scenarios to ensure proper error reporting and system monitoring.

