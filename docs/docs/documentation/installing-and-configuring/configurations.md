---
title: Configuring Agent Mesh
sidebar_position: 330
toc_max_heading_level: 4
---

The `shared_config.yaml` file is used to define configurations that can be shared across multiple agents or components in Agent Mesh. This centralized approach simplifies management of common configurations such as Solace event broker connections, language model settings, and service definitions.

## Understanding Shared Configuration

All agents and gateways require access to a `shared_config` object. You can provide configuration in the following ways:

 * hard-coding configuration values directly within your agent or gateway YAML files. This method works for simple setups or quick prototyping, but it becomes unwieldy as your deployment grows. 
 * using the `!include` directive to reference a centralized configuration file. This approach promotes consistency and simplifies maintenance across your entire project.

When a plugin is installed, it may come with hard-coded default values. It is a best practice to remove this section and use `!include` to point to the centralized `shared_config` file. This ensures that all components are using the same base configuration.

### Managing Multiple Shared Configuration Files

You can use multiple shared configuration files to manage different environments or setups (e.g., for different cloud providers), as follows: 

 * The filename must always begin with `shared_config`, followed by any descriptive suffix that helps identify the configuration's purpose. Examples include `shared_config_aws.yaml` for Amazon Web Services deployments or `shared_config_production.yaml` for production environments. This naming convention ensures the system can locate and process these files correctly.

 * You can organize configuration files into subdirectories to further improve project structure. For instance, you might place files in `configs/agents/shared_config.yaml` or `environments/dev/shared_config_dev.yaml`. When you use subdirectories, you must update the `!include` path in your agent or gateway configurations to reflect the correct file location.

The configuration file uses YAML anchors (`&anchor_name`) to create reusable configuration blocks, which can then be referenced in agent configuration files.

## Configuration Structure

The following example shows the structure of the `shared_config.yaml` configuration file:

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
      # Prompt Caching Strategy
      cache_strategy: "5m" # none, 5m, 1h
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
      type: "sql"
      database_url: "${DATABASE_URL, sqlite:///session.db}"
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

## Event Broker Connection

The `broker_connection` section configures the connection to the Solace event broker. The connection parameters are described in the following table:



| Parameter | Environment Variable | Description | Default |
| :--- | :--- | :--- | :--- |
| `dev_mode` | `SOLACE_DEV_MODE` | When set to `true`, uses an in-memory broker for testing. | `false` |
| `broker_url` | `SOLACE_BROKER_URL` | The URL of the Solace event broker. | `ws://localhost:8008` |
| `broker_username` | `SOLACE_BROKER_USERNAME` | The username for authenticating with the event broker. | `default` |
| `broker_password` | `SOLACE_BROKER_PASSWORD` | The password for authenticating with the event broker. | `default` |
| `broker_vpn` | `SOLACE_BROKER_VPN` | The Message VPN to connect to on the event broker. | `default` |
| `temporary_queue` | `USE_TEMPORARY_QUEUES` | Whether to use temporary queues for communication. If `false`, a durable queue will be created. | `true` |
| `max_connection_retries` | `MAX_CONNECTION_RETRIES` | The maximum number of times to retry connecting to the event broker if the connection fails. A value of `-1` means retry forever. | `-1` |

:::tip
If you need to configure multiple brokers, you can do so by adding additional entries under `shared_config` with a unique name (For example,  `broker_connection_eu: &broker_connection_eu` or `broker_connection_us: &broker_connection_us`). Reference these configurations in your agent files using the appropriate anchor, such as `<<: *broker_connection_eu`.
:::

:::info
Setting the `temporary_queue` parameter to `true` (default) will use [temporary endpoints](https://docs.solace.com/Messaging/Guaranteed-Msg/Endpoints.htm#temporary-endpoints) for A2A communication. Temporary queues are automatically created and deleted by the broker, which simplifies management and reduces the need for manual cleanup. However, it does not allow for multiple client connections to the same queue, which may be a limitation in some scenarios where you're running multiple instances of the same agent or a new instance needs to be started while an old instance is still running.

If you set `temporary_queue` to `false`, the system will create a durable queue for the client. Durable queues persist beyond the lifetime of the client connection, allowing multiple clients to connect to the same queue and ensuring that messages are not lost if the client disconnects. However, this requires manual management of the queues, including cleanup of unused queues.

Check the [Setting up Queue Templates](../deploying/deployment-options.md#setting-up-queue-templates) section for guidance on configuring queue templates to manage message TTL.
:::

## LLM Configuration

The models section configures the various Large Language Models and other generative models that power your agents' intelligence. This configuration leverages the [LiteLLM](https://litellm.ai/) library, which provides a standardized interface for interacting with [different model providers](https://docs.litellm.ai/docs/providers), simplifying the process of switching between or combining multiple AI services.

### Model Configuration Parameters

Each model configuration requires specific parameters that tell the system how to communicate with the model provider. The model parameter specifies the exact model identifier in the format expected by your provider, such as `openai/gpt-4` or `anthropic/claude-3-opus-20240229`. The API base URL points to your provider's endpoint, but some providers use default endpoints that don't require explicit specification.

Authentication typically requires an API key, but some providers use alternative authentication mechanisms. Additional parameters control model behavior, such as enabling parallel tool calls for models that support this feature, setting maximum token limits to control response length and costs, and adjusting temperature values to influence response creativity versus determinism.

| Parameter | Environment Variable | Description |
| :--- | :--- | :--- |
| `model` | `LLM_SERVICE_<MODEL_NAME>_MODEL_NAME` | The specific model identifier that the endpoint expects in the format of `provider/model` (e.g., `openai/gpt-4`, `anthropic/claude-3-opus-20240229`). |
| `api_base` | `LLM_SERVICE_ENDPOINT` | The base URL of the LLM provider's API endpoint. |
| `api_key` | `LLM_SERVICE_API_KEY` | The API key for authenticating with the service. |
| `parallel_tool_calls` |  | Enable parallel tool calls for the model. |
| `cache_strategy` |  | Set the prompt caching strategy (one of: `none`, `5m`, `1h`). For more details check [LLM Configuration](./large_language_models.md#prompt-caching) page. |
| `max_tokens` | `MAX_TOKENS` | Set a reasonable max token limit for the model. |
| `temperature` | `TEMPERATURE` | Lower temperature for more deterministic planning. |

For Google's Gemini models, you can use a simplified configuration approach that references the model directly:

```yaml
model: gemini-2.5-pro
```

For detailed information about configuring Gemini models and setting up the required environment variables, see the [Gemini model documentation](https://google.github.io/adk-docs/agents/models/#using-google-gemini-models).

### Predefined Model Types

The `shared_config.yaml` configuration file defines predefined model types that serve as aliases for specific use cases. These aliases allow you to reference models by their intended purpose rather than their technical specifications, making your agent configurations more readable and maintainable. The model types are as follows:

- `planning`: Used by agents for planning and decision-making. It's configured for deterministic outputs (`temperature: 0.1`) and can use tools in parallel.
- `general`: A general-purpose model for various tasks.
- `image_gen`: A model for generating images.
- `image_describe`: A model for describing the content of images.
- `audio_transcription`: A model for transcribing audio files.
- `report_gen`: A model specialized for generating reports.
- `multimodal`: A simple string reference to a multimodal model (e.g., `"gemini-1.5-flash-latest"`).

You can define any number of models in this section and reference them in your agent configurations. The system uses only the `planning` and `general` models by default; you don't need to configure the specialized models unless your agents specifically require those capabilities. 

For information about configuring different LLM providers and SSL/TLS security settings, see [Configuring LLMs](./large_language_models.md).

## Service Configuration

The `services` section in `shared_config.yaml` is used to configure various services that are available to agents. These services handle concerns such as session persistence, artifact storage, and data processing optimization.

### Session Service

The session service manages conversation history and context persistence across agent interactions. This service determines whether your agents remember previous conversations and how long that memory persists. The preset agent configurations default to SQL with SQLite for persistent sessions. For detailed information about session storage backends, architecture, and configuration examples, see [Session Storage](./session-storage.md).

| Parameter | Options | Description | Default |
| :--- | :--- | :--- | :--- |
| `type` | `memory`, `sql` | The storage backend for session data. The `memory` option stores sessions in application memory. The `sql` option stores sessions in a database. | `sql` |
| `database_url` | Database URL string | The connection string for your database. Required when `type` is `sql`. Supports SQLite (`sqlite:///path/to/db.db`) and PostgreSQL (`postgresql://user:pass@host:port/dbname`). | (none) |
| `default_behavior` | `PERSISTENT`, `RUN_BASED` | The retention policy for session history. The `PERSISTENT` option keeps session history indefinitely, while `RUN_BASED` clears history between runs. | `PERSISTENT` |

:::tip
The preset agent configurations default to SQL with SQLite databases. You can configure PostgreSQL by setting database URL environment variables as described in the [Session Storage](./session-storage.md) guide.
:::

### Artifact Service

The `artifact_service` is responsible for managing artifacts, which are files or data generated by agents, such as generated documents, processed data files, and intermediate results. For detailed information about artifact storage backends, versioning, and production configurations, see [Artifact Storage](./artifact-storage.md).

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

Result preview settings control how much data agents display when showing query results or data samples. These limits prevent overwhelming users with massive datasets while ensuring they see enough information to understand the results.

| Parameter | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `sqlite_memory_threshold_mb` | `integer` | The memory threshold in megabytes for using an in-memory SQLite database. | `100` |
| `max_result_preview_rows` | `integer` | The maximum number of rows to show in a result preview. | `50` |
| `max_result_preview_bytes` | `integer` | The maximum number of bytes to show in a result preview. | `4096` |
