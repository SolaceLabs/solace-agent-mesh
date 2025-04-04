---
title: Embedding Service
sidebar_position: 40
---

# Embedding Service

The Embedding service is a global service that acts as an abstraction layer between the embedding models and the user.

The Embedding service runs as an independent centralized service that provides embedding access to the [agents](../../../concepts/agents.md) in Solace Agent Mesh through the PubSub+ event broker.

## Usage

Embedding service allows users to call the model based on the category/type and not the model names.

For example, instead of a component calling a specific model like `openai/text-embedding-3-small`, they can choose from one of the following types:

- text
- image
- multi-modal

Each one of these values corresponds to a specific model and configuration.

To simplify usage, the default configuration maps all types to the same model. This can be changed in the configuration file. Check the [Custom Configuration](#custom-configuration) section for more information.

:::warning
If your embedding model doesn't support images, you should not use the `image` type.
:::

### Usage in Agents

To use the Embedding service in your agent, update your configuration file to use the appropriate type topic in `component_config.embedding_service_topic`.

For example:

```yaml
- component_name: action_request_processor
  component_module: solace_agent_mesh.agents.global.global_agent_component
  component_config:
    embedding_service_topic: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/embedding-service/request/text/
```

You can then use `do_embedding_service_request` method provided by the `BaseAgentComponent` class to send a request to the Embedding service.

If sending a request from within an action, you'd first need to get the agent using `get_agent` method and then call the `do_embedding_service_request` method.

For example:

```python
agent = self.get_agent()

data = [
    "Hello World!",
    "Vectorize this text."
]

embeddings = agent.do_embedding_service_request(data)
```

:::note
If sending a file url from the [File Service](./file-service.md), set the `resolve_files` flag to True.

For example:

```python
file_url = file_metadata["url"]
file_url_2 = file2_metadata["url"]
data = [ file_url, file_url_2 ]

embeddings = agent.do_embedding_service_request(data, resolve_files=True)
```

:::

### Usage in Other Solace AI Event Connector Components

Embedding service can be accessed from any [Solace AI Event Connector](../../../user-guide/solace-ai-connector.md) components.

To get access to the Embedding service, you can change the extending parent class from `ComponentBase` to `LLMServiceComponentBase`.

For example:

```python
from solace_agent_mesh.services.llm_service.components.llm_service_component_base import LLMServiceComponentBase
```

Then, you can use the `do_embedding_service_request` method provided by the `LLMServiceComponentBase` class to send a request to the LLM Service.

## Custom Configuration

The Embedding service config file can be found in your build directory under `configs/service_embedding.yaml`.

To use multiple models or different configurations, duplicate the flow, and apply changes as needed.

:::info
To learn about how to overwrite the Embedding service, see [Overwrite](../overwrites.md).
:::

Sample embedding flow - duplicate the flow as many times as needed:

```yaml
  - name: custom-embedding-service # Must be unique
    components:
      - component_name: broker_input
        component_module: broker_input
        component_config:
          <<: *broker_connection
          broker_queue_name: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/embedding-service/custom # Must be unique
          broker_subscriptions:
            - topic: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/embedding-service/request/custom/> # Add your type/category here instead of 'custom'
              qos: 1

      - component_name: file_resolver # Optional if text only - this component resolve file urls to text
        component_base_path: .
        component_module: solace_agent_mesh.tools.components.file_resolver_component
        component_config:
          force_resolve: true
        input_selection:
          source_expression: input.payload

      - component_name: embedding_service_model # This component is all the embedding model configurations
        num_instances: 1
        component_module: litellm_embeddings
        component_config:
          load_balancer:
            - model_name: ${EMBEDDING_SERVICE_MODEL_NAME} # model alias
              litellm_params:
                model: ${EMBEDDING_SERVICE_MODEL_NAME}
                api_key: ${EMBEDDING_SERVICE_API_KEY}
                api_base: ${EMBEDDING_SERVICE_ENDPOINT}
        input_selection:
          source_expression: previous

      - component_name: broker_output # This component sends the response back to the broker - Do not change
        component_module: broker_output
        component_config:
          <<: *broker_connection
          copy_user_properties: true
        input_transforms:
          - type: copy
            source_expression: previous
            dest_expression: user_data.output:payload
          - type: copy
            source_expression: input.user_properties:__solace_ai_connector_broker_request_response_topic__
            dest_expression: user_data.output:topic
        input_selection:
          source_expression: user_data.output
```

:::tip
For more information about the available configuration options, see [LiteLLMChatModel](https://github.com/SolaceLabs/solace-ai-connector/blob/main/docs/components/litellm_embeddings.md) in the Solace AI Event Connector documentation.
:::
