---
title: Event Mesh Gateway
sidebar_position: 10
---

# Event Mesh Gateway

The Event Mesh Gateway connects Solace Agent Mesh (SAM) to your existing event mesh infrastructure. Through its asynchronous interfaces, applications within your event mesh can seamlessly access and utilize Solace Agent Mesh capabilities.

This tutorial shows you how to build an Event Mesh Gateway that automatically generates and adds concise summaries to Jira bug reports, making them easier to understand at a glance.

## Prerequisites

This tutorial assumes you have an existing Jira application integrated with your event mesh that:

1. Publishes a "jira_created" event to topic `jira/issue/created/<jira_id>` when a new Jira issue is created
2. Listens for "jira_update" events on topic `jira/issue/update` to update existing issues

You will create an Event Mesh Gateway that:

1. Monitors for new Jira issues.
2. Automatically generates a concise summary.
3. Creates an event to update the original Jira issue with this summary.

This creates a streamlined workflow where bug reports are automatically enhanced with clear, AI-generated summaries.

## Setting Up the Environment

First, you need to [install Solace Agent Mesh and the Solace Agent Mesh (SAM) CLI](../getting-started/installation.md), and then you'll want to [create a new Solace Agent Mesh project](../getting-started/quick-start.md)

For this tutorial, you will need to create or use an existing [Solace Event Broker](https://solace.com/products/event-broker/) or [event mesh](https://solace.com/solutions/initiative/event-mesh/) created using PubSub+ event brokers.

## Creating the Event Mesh Gateway

Once you have your project set up, you can add the plugin to Solace Agent Mesh:

```sh
solace-agent-mesh plugin add solace-event-mesh --pip -u git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=solace-event-mesh
```

Next, create an instance of Event Mesh Gateway. The following command will create the configuration for a new gateway (named `jira`) as well as the input and output configuration for the event mesh interface:

```sh
solace-agent-mesh add gateway jira --interface solace-event-mesh
```

Expected output:

```txt
Created the following gateway template files:
  - ./configs/gateways/jira/gateway.yaml
  - ./configs/gateways/jira/solace-event-mesh.yaml
```

## Configuring the Event Mesh Gateway

The Event Mesh Gateway configuration is located in `./configs/gateways/jira/solace-event-mesh.yaml`. You will modify its input and output processors to meet the requirements.

### Input Processor

First, let's configure the input processor, with the instruction to create summaries from newly created Jira tickets:

```yaml
- event_mesh_input_config: &event_mesh_input_config
    identity: jira_event_mesh
    event_handlers:
      - name: jira_event_handler
        subscriptions:
          - topic: jira/issue/created/>
            qos: 1
        input_expression: >
          template:Create a concise summary for the newly created jira: title:{{text://input.payload:title}} body:{{text://input.payload:body}} id:{{text://input.payload:id}}. Return a json file with fields `id`, `type` (value is "summary") and `summary`.
        payload_encoding: utf-8
        payload_format: json
        output_handler_name: jira_summary_emitter
```

This input processor subscribes on the topic for newly created Jiras (`jira/issue/created/>`), and creates a prompt using an input_expression that instructs Solace Event Mesh to create a summary of the Jira based on the title and body fields in the event. The response is returned as a JSON file.

### Output Processor

Next, you configure the output processor to publish the summary to the update topic:

```yaml
- event_mesh_output_config: &event_mesh_output_config
    output_handlers:
      - name: jira_summary_emitter
        attach_file_as_payload: true
        topic: jira/issue/update
        payload_encoding: none
        payload_format: text
```

The `jira_summary_emitter` output handler takes the json file with the summary, and adds it to the event payload. The event topic is `jira/issue/update`. The file contents added to the event payload using the specified encoding and format configuration parameters.

### Response Format

Finally, set up the response prompt so that the final output meets our expectations. For this example, we want only formatted JSON. Update the `response_format_prompt_config` with the following:

```yaml
- response_format_prompt_config: &response_format_prompt >
    The response should be a valid, well-formed JSON object with no markdown formatting or additional wrappers.
```

### Gateway

No customization is required for `./configs/gateways/jira/gateway.yaml`

## Building and Running the Event Mesh Gateway

Now, you can build and run the Event Mesh Gateway:

```sh
sam run -be
```

For more information, see [Solace Agent Mesh CLI](../concepts/cli.md).

## Testing the Event Mesh Gateway

Now that the system is running, let's test the Event Mesh Gateway.

1. Open the **Try Me!** tab of the [Solace PubSub+ Broker Manager](https://docs.solace.com/Admin/Broker-Manager/PubSub-Manager-Overview.htm).

2. Connect both the **Publisher** and **Subscriber** panels by clicking their respective **Connect** buttons.

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

Next, click **Publish**.

After a few seconds, you will see a new message in the **Subscriber** messages with topic `jira/issue/update` and a body similar to below:

```json
{
  "id": "JIRA-143321",
  "type": "summary",
  "summary": "Database read error: Unable to retrieve record for key customer ABC despite confirmed existence"
}
```
