---
title: Configurations
sidebar_position: 10
toc_max_heading_level: 4
---

# Configurations

## Shared Configurations

The `shared_config.yaml` file is used to define configurations that can be shared across multiple agents or components in Solace Agent Mesh. This allows for centralized management of common settings like broker connections and language model configurations.

### Using Shared Configurations

All agents and gateways require access to a `shared_config` object. You can provide configuration in the following ways:

1.  **Hard-coding values**: You can directly embed the `shared_config` values within your agent or gateway YAML files.
2.  **Using `!include`**: For better project consistency and management, you can use the `!include` directive to load a shared configuration file.

When a plugin is installed, it may come with hard-coded default values. It is a best practice to remove this section and use `!include` to point to the centralized `shared_config` file. This ensures that all components are using the same base configuration.

### Managing Multiple Shared Configuration Files

You can use multiple shared configuration files to manage different environments or setups (e.g., for different cloud providers). You must follow these rules:

1.  **Filename**: The filename must always start with `shared_config` (e.g., `shared_config_aws.yaml`, `shared_config_gcp.yaml`).
2.  **Sub-directories**: You can organize these files into sub-directories (e.g., `configs/agents/shared_config.yaml`). When you do this, you must update the `!include` path in your agent or gateway configurations to point to the correct location.

The file uses YAML anchors (`&anchor_name`) to create reusable configuration blocks, which can then be referenced in agent configuration files.

### Parameters

##### Example `shared_config.yaml`

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

#### Broker Connection

The `broker_connection` section configures the connection to the Solace event broker. The connection parameters are described in the following table:

| Parameter | Environment Variable | Description | Default |
| :--- | :--- | :--- | :--- |
| `dev_mode` | `SOLACE_DEV_MODE` | When set to `true`, uses an in-memory broker for testing. | `false` |
| `broker_url` | `SOLACE_BROKER_URL` | The URL of the Solace broker. | `ws://localhost:8008` |
| `broker_username` | `SOLACE_BROKER_USERNAME` | The username for authenticating with the broker. | `default` |
| `broker_password` | `SOLACE_BROKER_PASSWORD` | The password for authenticating with the broker. | `default` |
| `broker_vpn` | `SOLACE_BROKER_VPN` | The Message VPN to connect to on the broker. | `default` |
| `temporary_queue` | `USE_TEMPORARY_QUEUES` | Whether to use temporary queues for communication. If `false`, a durable queue will be created. | `true` |
| `max_connection_retries` | `MAX_CONNECTION_RETRIES` | The maximum number of times to retry connecting to the broker if the connection fails. A value of `-1` means retry forever. | `-1` |

:::tip
If you need to configure multiple brokers, you can do so by adding additional entries under `shared_config` with a unique name (For example,  `broker_connection_eu: &broker_connection_eu` or `broker_connection_us: &broker_connection_us`) and then use the proper reference in your agent configurations. (Example: `<<: *broker_connection_eu`)
:::

#### Models

The `models` section is used to configure the various Large Language Models (LLMs) and other generative models used by the agents. The configuration uses the [LiteLLM](https://litellm.ai/) library, which provides a standardized way to interact with [different model providers](https://docs.litellm.ai/docs/providers).

##### Model Configuration Structure

The following table describes the parameters that tell the system how to interact with the model:

| Parameter | Environment Variable | Description |
| :--- | :--- | :--- |
| `model` | `LLM_SERVICE_<MODEL_NAME>_MODEL_NAME` | The specific model identifier that the endpoint expects in the format of `provider/model` (e.g., `openai/gpt-4`, `anthropic/claude-3-opus-20240229`). |
| `api_base` | `LLM_SERVICE_ENDPOINT` | The base URL of the LLM provider's API endpoint. |
| `api_key` | `LLM_SERVICE_API_KEY` | The API key for authenticating with the service. |
| `parallel_tool_calls` | `PARALLEL_TOOL_CALLS` | Enable parallel tool calls for the model. |
| `max_tokens` | `MAX_TOKENS` | Set a reasonable max token limit for the model. |
| `temperature` | `TEMPERATURE` | Lower temperature for more deterministic planning. |

Alternatively, you can use Gemini models directly through Google Studio AI or Vertex AI:

```yaml
model: gemini-2.5-pro
```

See the [documentation](https://google.github.io/adk-docs/agents/models/#using-google-gemini-models) for details on setting the environment for Gemini models.

##### Pre-Defined Model Types

The `shared_config.yaml` example defines several models for different purposes. A pre-defined model serves as an alias for the model configuration. This alias allows you to refer to a configuration by its use case rather than its specific parameters.

-   **`planning`**: Used by agents for planning and decision-making. It's configured for deterministic outputs (`temperature: 0.1`) and can use tools in parallel.
-   **`general`**: A general-purpose model for various tasks.
-   **`image_gen`**: A model for generating images.
-   **`image_describe`**: A model for describing the content of images.
-   **`audio_transcription`**: A model for transcribing audio files.
-   **`report_gen`**: A model specialized for generating reports.
-   **`multimodal`**: A simple string reference to a multimodal model (e.g., `"gemini-1.5-flash-latest"`).

You can define any number of models in this section and reference them in your agent configurations. **By default, the system only uses the `planning` and the `general` models. No need to fill the other fields**

:::info
For more information on configuring different LLM models and SSL/TLS settings, please refer to the [LLM Models](./litellm_models.md) documentation.
:::

#### Services

The `services` section in `shared_config.yaml` is used to configure various services that are available to agents.

##### Session Service

The parameters are described in the following table:

| Parameter | Options | Description | Default |
| :--- | :--- | :--- | :--- |
| `type` | `memory`, `sql`, `vertex_rag` | Configuration for ADK Session Service | `memory` |
| `default_behavior` | `PERSISTENT`, `RUN_BASED` | The default behavior of keeping the session history | `PERSISTENT` |

:::tip
Although the default session service type is `memory`, both Orchestrator Agent and Web UI gateway use `sql` as their session service to allow for persistent sessions.
:::

##### Artifact Service

The `artifact_service` is responsible for managing artifacts, which are files or data generated by agents.

| Parameter | Options | Description | Default |
| :--- | :--- | :--- | :--- |
| `type` | `memory`, `gcs`, `filesystem` | Service type for artifact storage. Use `memory` for in-memory, `gcs` for Google Cloud Storage, or `filesystem` for local file storage. | `memory` |
| `base_path` | local path | Base directory path for storing artifacts. Required only if `type` is `filesystem`. | (none) |
| `bucket_name` | bucket name | Google Cloud Storage bucket name. Required only if `type` is `gcs`. | (none) |
| `artifact_scope` | `namespace`, `app` | Scope for artifact sharing. `namespace`: shared by all components in the namespace. `app`: isolated by agent/gateway name. Must be consistent for all components in the same process. | `namespace` |
| `artifact_scope_value` | custom scope id | Custom identifier for artifact scope. Required if `artifact_scope` is set to a custom value. | (none) |

##### Data Tools Config

The `data_tools_config` section configures the behavior of data analysis tools.

| Parameter | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `sqlite_memory_threshold_mb` | `integer` | The memory threshold in megabytes for using an in-memory SQLite database. | `100` |
| `max_result_preview_rows` | `integer` | The maximum number of rows to show in a result preview. | `50` |
| `max_result_preview_bytes` | `integer` | The maximum number of bytes to show in a result preview. | `4096` |



## System Logs

For details on how to configure system logging, including log rotation and verbosity levels, please see the [System Logs](../../deployment/debugging.md#system-logs) section in the debugging documentation.
