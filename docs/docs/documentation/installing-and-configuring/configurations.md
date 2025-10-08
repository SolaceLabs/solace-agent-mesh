---
title: Configuring Agent Mesh
sidebar_position: 330
toc_max_heading_level: 4
---

The [`shared_config.yaml`](shared_config.yaml) file serves as the central configuration hub for Agent Mesh, allowing you to define settings that multiple agents and components can share. This centralized approach simplifies management of common configurations such as Solace event broker connections, language model settings, and service definitions.

## Understanding Shared Configuration

Every agent and gateway in Agent Mesh requires access to a `shared_config` object. This requirement ensures consistent behavior across your entire mesh deployment. You have two primary approaches for providing this configuration, each suited to different development scenarios and organizational needs.

The first approach involves hard-coding configuration values directly within your agent or gateway YAML files. Although this method works for simple setups or quick prototyping, it becomes unwieldy as your deployment grows. The second approach uses the `!include` directive to reference a centralized configuration file, which promotes consistency and simplifies maintenance across your entire project.

When you install a plugin, it often comes with hard-coded default values embedded in its configuration. Although these defaults allow the plugin to function immediately, best practice dictates removing this embedded section and replacing it with an `!include` directive that points to your centralized `shared_config` file. This practice ensures all components operate with identical base configurations, reducing configuration drift and potential inconsistencies.

## Managing Multiple Configuration Files

Complex deployments often require different configuration sets for various environments or cloud providers. Agent Mesh supports this requirement through multiple shared configuration files, although you must follow specific naming and organizational conventions.

The filename must always begin with `shared_config`, followed by any descriptive suffix that helps identify the configuration's purpose. Examples include `shared_config_aws.yaml` for Amazon Web Services deployments or `shared_config_production.yaml` for production environments. This naming convention ensures the system can locate and process these files correctly.

You can organize configuration files into subdirectories to further improve project structure. For instance, you might place files in `configs/agents/shared_config.yaml` or `environments/dev/shared_config_dev.yaml`. When using subdirectories, you must update the `!include` path in your agent or gateway configurations to reflect the correct file location.

The configuration system uses YAML anchors (`&anchor_name`) to create reusable configuration blocks. These anchors allow you to define a configuration once and reference it multiple times throughout your agent configurations, promoting consistency and reducing duplication.

## Configuration Structure

The following example shows the structure of the configuration file:

```yaml
shared_config:
  - broker_connection: &broker_connection
      dev_mode: ${SOLACE_DEV_MODE, false}
      broker_url: ${SOLACE_BROKER_URL, ws://localhost:8008}
      broker_username: ${SOLACE_BROKER_USERNAME, default}
      broker_password: ${SOLACE_BROKER_PASSWORD, default}
      broker_vpn: ${SOLACE_BROKER_VPN, default}
      temporary_queue: ${USE_TEMPORARY_QUEUES, true}
      # Ensure high enough limits if many agents are running
      # max_connection_retries: -1 # Retry forever

  - models:
    planning: &planning_model
      # This dictionary structure tells ADK to use the LiteLlm wrapper.
      # 'model' uses the specific model identifier your endpoint expects.
      model: ${LLM_SERVICE_PLANNING_MODEL_NAME} # Use env var for model name
      # 'api_base' tells LiteLLM where to send the request.
      api_base: ${LLM_SERVICE_ENDPOINT} # Use env var for endpoint URL
      # 'api_key' provides authentication.
      api_key: ${LLM_SERVICE_API_KEY} # Use env var for API key
      # Enable parallel tool calls for planning model
      parallel_tool_calls: true 
      # max_tokens: ${MAX_TOKENS, 16000} # Set a reasonable max token limit for planning
      # temperature: 0.1 # Lower temperature for more deterministic planning
    
    general: &general_model
      # This dictionary structure tells ADK to use the LiteLlm wrapper.
      # 'model' uses the specific model identifier your endpoint expects.
      model: ${LLM_SERVICE_GENERAL_MODEL_NAME} # Use env var for model name
      # 'api_base' tells LiteLLM where to send the request.
      api_base: ${LLM_SERVICE_ENDPOINT} # Use env var for endpoint URL
      # 'api_key' provides authentication.
      api_key: ${LLM_SERVICE_API_KEY} # Use env var for API key

      # ... (similar structure)

  - services:
    # Default session service configuration
    session_service: &default_session_service
      type: "memory"
      default_behavior: "PERSISTENT"
    
    # Default artifact service configuration
    artifact_service: &default_artifact_service
      type: "filesystem"
      base_path: "/tmp/samv2"
      artifact_scope: namespace
    
    # Default data tools configuration
    data_tools_config: &default_data_tools_config
      sqlite_memory_threshold_mb: 100
      max_result_preview_rows: 50
      max_result_preview_bytes: 4096
```

## Configuring the Event Broker Connection

The Solace event broker connection section establishes how your agents and gateways communicate with the Solace event broker. This configuration determines the reliability, security, and performance characteristics of your mesh communication.

The development mode setting (`dev_mode`) provides a convenient way to switch between production Solace event broker connections and an in-memory event broker for testing. When enabled, this setting bypasses external event broker requirements, allowing you to develop and test your agents without a full Solace infrastructure.

Connection parameters include the event broker URL, which specifies the endpoint for your Solace event broker, and authentication credentials consisting of username, password, and Message VPN. The temporary queue setting controls whether agents use ephemeral queues that disappear when the agent disconnects or durable queues that persist messages even during agent downtime.

| Parameter | Environment Variable | Description | Default |
| :--- | :--- | :--- | :--- |
| `dev_mode` | `SOLACE_DEV_MODE` | When set to `true`, uses an in-memory broker for testing. | `false` |
| `broker_url` | `SOLACE_BROKER_URL` | The URL of the Solace event broker. | `ws://localhost:8008` |
| `broker_username` | `SOLACE_BROKER_USERNAME` | The username for authenticating with the event broker. | `default` |
| `broker_password` | `SOLACE_BROKER_PASSWORD` | The password for authenticating with the event broker. | `default` |
| `broker_vpn` | `SOLACE_BROKER_VPN` | The Message VPN to connect to on the event broker. | `default` |
| `temporary_queue` | `USE_TEMPORARY_QUEUES` | Whether to use temporary queues for communication. If `false`, a durable queue will be created. | `true` |
| `max_connection_retries` | `MAX_CONNECTION_RETRIES` | The maximum number of times to retry connecting to the event broker if the connection fails. A value of `-1` means retry forever. | `-1` |

For deployments requiring multiple Solace event broker connections, you can define additional event broker configurations with unique names. For example, create `broker_connection_eu: &broker_connection_eu` for European deployments or `broker_connection_us: &broker_connection_us` for United States deployments. Reference these configurations in your agent files using the appropriate anchor, such as `<<: *broker_connection_eu`.

## Language Model Configuration

The models section configures the various Large Language Models and other generative models that power your agents' intelligence. This configuration leverages the [LiteLLM](https://litellm.ai/) library, which provides a standardized interface for interacting with [different model providers](https://docs.litellm.ai/docs/providers), simplifying the process of switching between or combining multiple AI services.

### Model Configuration Parameters

Each model configuration requires specific parameters that tell the system how to communicate with the model provider. The model parameter specifies the exact model identifier in the format expected by your provider, such as `openai/gpt-4` or `anthropic/claude-3-opus-20240229`. The API base URL points to your provider's endpoint, although some providers use default endpoints that don't require explicit specification.

Authentication typically requires an API key, although some providers use alternative authentication mechanisms. Additional parameters control model behavior, such as enabling parallel tool calls for models that support this feature, setting maximum token limits to control response length and costs, and adjusting temperature values to influence response creativity versus determinism.

| Parameter | Environment Variable | Description |
| :--- | :--- | :--- |
| `model` | `LLM_SERVICE_<MODEL_NAME>_MODEL_NAME` | The specific model identifier that the endpoint expects in the format of `provider/model` (e.g., `openai/gpt-4`, `anthropic/claude-3-opus-20240229`). |
| `api_base` | `LLM_SERVICE_ENDPOINT` | The base URL of the LLM provider's API endpoint. |
| `api_key` | `LLM_SERVICE_API_KEY` | The API key for authenticating with the service. |
| `parallel_tool_calls` | `PARALLEL_TOOL_CALLS` | Enable parallel tool calls for the model. |
| `max_tokens` | `MAX_TOKENS` | Set a reasonable max token limit for the model. |
| `temperature` | `TEMPERATURE` | Lower temperature for more deterministic planning. |

For Google's Gemini models, you can use a simplified configuration approach that references the model directly:

```yaml
model: gemini-2.5-pro
```

For detailed information about configuring Gemini models and setting up the required environment variables, see the [Gemini model documentation](https://google.github.io/adk-docs/agents/models/#using-google-gemini-models).

### Predefined Model Types

The shared configuration supports predefined model types that serve as aliases for specific use cases. These aliases allow you to reference models by their intended purpose rather than their technical specifications, making your agent configurations more readable and maintainable.

The planning model handles agent decision-making and task planning. This model typically uses lower temperature settings for more deterministic outputs and supports parallel tool calls to improve efficiency. The general model serves as a multipurpose option for various tasks that don't require specialized capabilities.

Specialized models include image generation for creating visual content, image description for analyzing visual inputs, audio transcription for converting speech to text, and report generation for creating structured documents. The multimodal model handles tasks requiring multiple input types, such as processing both text and images simultaneously.

The system uses only the planning and general models by default, so you need not configure the specialized models unless your agents specifically require those capabilities. This approach keeps your configuration simple although providing flexibility for advanced use cases.

For comprehensive information about configuring different LLM providers and SSL/TLS security settings, see the [Large Language Models configuration guide](./large_language_models.md).

## Service Configuration

The services section defines various supporting services that enhance agent capabilities and manage system resources. These services handle concerns such as session persistence, artifact storage, and data processing optimization.

### Session Service

The session service manages conversation history and context persistence across agent interactions. This service determines whether agents remember previous conversations and how long that memory persists.

The memory type provides fast, in-memory storage that doesn't persist across agent restarts. This option works well for development and testing although loses all session data when the agent stops. The SQL type offers persistent storage that survives agent restarts and system reboots, making it suitable for production deployments where conversation continuity matters.

The default behavior setting controls how sessions handle persistence. Persistent behavior maintains session history indefinitely, allowing agents to reference previous conversations across multiple interactions. Run-based behavior clears session history at the end of each interaction, providing a fresh start for each conversation.

| Parameter | Options | Description | Default |
| :--- | :--- | :--- | :--- |
| `type` | `memory`, `sql`, `vertex_rag` | Configuration for ADK Session Service | `memory` |
| `default_behavior` | `PERSISTENT`, `RUN_BASED` | The default behavior of keeping the session history | `PERSISTENT` |

Although the default session service uses memory storage, both the Orchestrator Agent and Web UI gateway use SQL storage to enable persistent sessions that survive system restarts and provide better user experiences.

### Artifact Service

The artifact service manages files and data that agents generate during their operations. This service handles storage, retrieval, and sharing of artifacts such as generated documents, processed data files, and intermediate results.

The memory storage type keeps artifacts in system memory, providing fast access although losing all data when the agent stops. This option suits development and testing scenarios where artifact persistence isn't critical. The filesystem type stores artifacts on local disk storage, providing persistence across agent restarts although limiting sharing to the local system.

Google Cloud Storage integration allows multiple agents across different systems to share artifacts through a centralized cloud repository. This option requires additional configuration including bucket names and authentication credentials.

The artifact scope determines how agents share artifacts with each other. Namespace scope allows all components within the same namespace to access shared artifacts, promoting collaboration between related agents. App scope isolates artifacts by individual agent or gateway name, providing security through isolation although limiting collaboration opportunities.

| Parameter | Options | Description | Default |
| :--- | :--- | :--- | :--- |
| `type` | `memory`, `gcs`, `filesystem` | Service type for artifact storage. Use `memory` for in-memory, `gcs` for Google Cloud Storage, or `filesystem` for local file storage. | `memory` |
| `base_path` | local path | Base directory path for storing artifacts. Required only if `type` is `filesystem`. | (none) |
| `bucket_name` | bucket name | Google Cloud Storage bucket name. Required only if `type` is `gcs`. | (none) |
| `artifact_scope` | `namespace`, `app` | Scope for artifact sharing. `namespace`: shared by all components in the namespace. `app`: isolated by agent/gateway name. Must be consistent for all components in the same process. | `namespace` |
| `artifact_scope_value` | custom scope id | Custom identifier for artifact scope. Required if `artifact_scope` is set to a custom value. | (none) |

### Data Tools Configuration

The data tools configuration optimizes how agents handle data analysis and processing tasks. These settings balance performance, memory usage, and user experience when agents work with databases and large datasets.

The SQLite memory threshold determines when the system switches from disk-based to memory-based database operations. Lower thresholds favor memory usage for better performance although consume more system RAM. Higher thresholds reduce memory pressure although may slow database operations.

Result preview settings control how much data agents display when showing query results or data samples. These limits prevent overwhelming users with massive datasets although ensuring they see enough information to understand the results.

| Parameter | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `sqlite_memory_threshold_mb` | `integer` | The memory threshold in megabytes for using an in-memory SQLite database. | `100` |
| `max_result_preview_rows` | `integer` | The maximum number of rows to show in a result preview. | `50` |
| `max_result_preview_bytes` | `integer` | The maximum number of bytes to show in a result preview. | `4096` |

## System Logging

System logging configuration controls how Agent Mesh records operational information, errors, and debugging details. Proper logging configuration helps with troubleshooting, monitoring, and maintaining your agent deployments.

For comprehensive information about configuring log rotation, verbosity levels, and log formatting options, see the [System Logs section](../deploying/debugging.md#system-logs) in the debugging documentation.
