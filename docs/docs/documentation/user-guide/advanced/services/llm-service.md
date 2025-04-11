---
title: LLM Service
sidebar_position: 30
---

# LLM Service

The LLM (Large Language Model) service is a global service that acts as an abstraction layer between the LLM configurations/models and the user.

The LLM service runs as an independent centralized service that provides LLM access to the [orchestrator](../../../concepts/orchestrator.md) and [agents](../../../concepts/agents.md) in Solace Agent Mesh through the PubSub+ event broker.

## Usage

The LLM service allows users to call the model based on category and not the model names.

For example, instead of a component calling a specific model like `openai/gpt-4o`, they can choose from one of the following categories:

- planning
- reasoning-expensive
- reasoning-normal
- general-good
- general-fast
- writing
- coding

Each one of these values corresponds to a specific model and configuration.

To simplify usage, the default configuration maps all categories to the same model. This can be changed in the configuration file. For more information, see [Custom Configuration](#custom-configuration).

### Usage in Agents

To use the LLM service in your agent, update your configuration file to use the appropriate category topic in `component_config.llm_service_topic`.

For example:

```yaml
- component_name: action_request_processor
  component_module: solace_agent_mesh.agents.global.global_agent_component
  component_config:
    llm_service_topic: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/llm-service/request/general-good/
```

You can then use `do_llm_service_request` method provided by the `BaseAgentComponent` class to send a request to the LLM service.

If sending a request from within an action, you'd first need to get the agent using `get_agent` method and then call the `do_llm_service_request` method.

For example:

```python
agent = self.get_agent()

message = [
    {
        "role": "system",
        "content": "You're a helpful assistant.",
    },
    {
        "role": "user",
        "content": "What is the capital of Canada?",
    }
]

response = agent.do_llm_service_request(message)
content = response.get("content")
```

### Usage in Other S-A-C Components

LLM service can be accessed from any [Solace AI Event Connector](../../../user-guide/solace-ai-connector.md) components.

To get access to the LLM service, simply change the extending parent class from `ComponentBase` to `LLMServiceComponentBase`.

For example:

```python
from solace_agent_mesh.services.llm_service.components.llm_service_component_base import LLMServiceComponentBase
```

Then, you can use the `do_llm_service_request` method provided by the `LLMServiceComponentBase` class to send a request to the LLM service.

## Custom Configuration

The LLM service configuration file can be found in your build directory under `configs/service_llm.yaml`.

To use multiple models or different configurations, duplicate the flow, and apply changes as needed.

:::info
You can overwrite the LLM service. For more information, see [Overwrites](../overwrites.md).
:::

Sample LLM flow - duplicate the flow as many times as needed:

```yaml
  - name: custom-llm-service # Must be unique
    components:
      - component_name: broker_input
        component_module: broker_input
        component_config:
          <<: *broker_connection
          broker_queue_name: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/llm-service/custom # Must be unique
          broker_subscriptions:
            - topic: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/llm-service/request/custom/> # Add your category here instead of 'custom'
              qos: 1

      - component_name: file_resolver # Optional if text only - this component resolve file urls to text
        component_base_path: .
        component_module: solace_agent_mesh.tools.components.file_resolver_component
        component_config:
          force_resolve: true
        input_selection:
          source_expression: input.payload

      - component_name: llm_service_planning # This component is all the LLM model configurations
        num_instances: 1
        component_module: litellm_chat_model
        component_config:
          <<: *llm_config
          load_balancer:
            - model_name: ${LLM_SERVICE_PLANNING_MODEL_NAME}
              litellm_params:
                <<: *llm_auth
                model: ${LLM_SERVICE_PLANNING_MODEL_NAME}
                temperature: 0.02
        <<: *llm_input_transforms_and_select

      - component_name: broker_output  # This component sends the response back to the PubSub+ event broker - Do not change
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
For more information about the available configuration options, see [LiteLLMChatModel](https://github.com/SolaceLabs/solace-ai-connector/blob/main/docs/components/litellm_chat_model.md) in the Solace AI Event Connector documentation.
:::
