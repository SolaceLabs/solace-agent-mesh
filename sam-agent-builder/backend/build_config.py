from helpers import get_agent_file,make_llm_api_call

def build_config(agent_name, agent_description, global_context ,is_api_key_required):
    agent_config_content = get_agent_file(agent_name, "agent_config")

    SYSTEM_PROMPT= \
   """
Your goal is to create a valid configuration file for an agent in the Solace Agent Mesh.

# PURPOSE
Configuration files are critical for defining how agents work in the Solace Agent Mesh. They:
1. Define how the agent connects to the message broker
2. Configure log settings
3. Set up processing flows
4. Define components the agent uses
5. Specify environment variables for external configuration

# STRUCTURE
The configuration file is a YAML document with these main sections:
- log: Log settings
- shared_config: Reusable configurations
- flows: Processing workflows with components

# ENVIRONMENT VARIABLES
Use syntax like: ${VARIABLE_NAME, default_value} or ${VARIABLE_NAME}
This allows for externalized configuration at runtime.

# WORKING WITH YOUR TASK
If the agent requires a specific configuration such as in most cases an API KEY or a customizable behavior you can add this to the configuration like so:

# EXAMPLES
Here is an example of a valid agent configuration file:

```yaml
# This is the configuration file for the test agent
#
# It fulfills a few functions:
# 1. A flow to do periodic registration of this agent with the orchestrator
# 2. A flow to process action requests and produce action responses
#    This requires a custom component to process the action requests
---
log:
  stdout_log_level: INFO
  log_file_level: INFO
  log_file: solace_ai_connector.log
shared_config:
  - broker_config: &broker_connection
      dev_mode: ${SOLACE_DEV_MODE, false}
      broker_url: ${SOLACE_BROKER_URL}
      broker_username: ${SOLACE_BROKER_USERNAME}
      broker_password: ${SOLACE_BROKER_PASSWORD}
      broker_vpn: ${SOLACE_BROKER_VPN}
      temporary_queue: ${USE_TEMPORARY_QUEUES, false}
flows:
  # Flow to handle action requests
  - name: test_action_request_processor
    components:
      # Input from a Solace broker
      - component_name: broker_input
        component_module: broker_input
        component_config:
          <<: *broker_connection
          payload_encoding: utf-8
          payload_format: json
          broker_queue_name: ${SOLACE_AGENT_MESH_NAMESPACE}agent_test_action_request
          broker_subscriptions:
            # Subscribe to all test actions - note that if we
            # wanted to handle some test actions elsewhere, we would
            # need to be more specific here
            - topic: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/actionRequest/*/*/test/>
              qos: 1
      # Custom component to process the action request
      - component_name: action_request_processor
        component_base_path: .
         # path is completed at build time
        component_module: {{MODULE_DIRECTORY}}.agents.test.test_agent_component
        component_config:
          llm_service_topic: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/llm-service/request/general-good/
          embedding_service_topic: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/embedding-service/request/text/
          # Pass required configuration to the component
        broker_request_response:
          enabled: true
          broker_config: *broker_connection
          request_expiry_ms: 120000
          payload_encoding: utf-8
          payload_format: json
          response_topic_prefix: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1
          response_queue_prefix: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1
        component_input:
          source_expression: input.payload
      # Output to a Solace broker
      - component_name: broker_output
        component_module: broker_output
        component_config:
          <<: *broker_connection
          payload_encoding: utf-8
          payload_format: json
          copy_user_properties: true
```
Here's an example of adding a custom configuration variable with an environment variable:
# Custom component to process the action request
- component_name: action_request_processor
    component_base_path: .
    #path is completed at build time
    component_module: {{MODULE_DIRECTORY}}.agents.test.test_agent_component
    component_config:
    llm_service_topic: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/llm-service/request/general-good/
    embedding_service_topic: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/embedding-service/request/text/
    # Pass required configuration to the component
    my_example_config: ${MY_EXAMPLE_CONFIG}


"""

    SYSTEM_PROMPT+= f"""
    You need to modify the following configuration file for the {agent_name} agent.
    Agent description: {agent_description}
    GLOBAL CONTEXT: {global_context}
    IS AN API KEY REQUIRED = {is_api_key_required}
    The current configuration is file to be edited is :
    {agent_config_content}

    OUTPUT FORMAT:
    Remember to provide your response as a JSON object with a  "file_content" field containing the complete YAML configuration and a "configs_added" field with just the names of the configs that were added as a list. ALways return the 
    complete configuration file, not just the changes.
    Example response:
    """

    response = make_llm_api_call(SYSTEM_PROMPT)

    return response

    