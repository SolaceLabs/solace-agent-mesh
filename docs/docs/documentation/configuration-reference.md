# Configuration Reference

This comprehensive reference provides configuration snippets, field descriptions, and possible values for all Solace Agent Mesh components.

## Table of Contents

- [Shared Configuration](#shared-configuration)
- [Agent Configuration](#agent-configuration)
- [Gateway Configuration](#gateway-configuration)
- [Tool Configuration](#tool-configuration)
- [Service Configuration](#service-configuration)
- [Broker Configuration](#broker-configuration)

---

## Shared Configuration

Shared configuration provides common settings that can be referenced across multiple components using YAML anchors.

### Complete Shared Config Example

```yaml
shared_config:
  - broker_connection: &broker_connection
      dev_mode: ${SOLACE_DEV_MODE, false}
      broker_url: ${SOLACE_BROKER_URL, ws://localhost:8008}
      broker_username: ${SOLACE_BROKER_USERNAME, default}
      broker_password: ${SOLACE_BROKER_PASSWORD, default}
      broker_vpn: ${SOLACE_BROKER_VPN, default}
      temporary_queue: ${USE_TEMPORARY_QUEUES, true}
      
  - models:
    planning: &planning_model
      model: ${LLM_SERVICE_PLANNING_MODEL_NAME}
      api_base: ${LLM_SERVICE_ENDPOINT}
      api_key: ${LLM_SERVICE_API_KEY}
      parallel_tool_calls: true
      cache_strategy: "5m"  # none, 5m, 1h
      # max_tokens: ${MAX_TOKENS, 16000}
      # temperature: 0.1

    general: &general_model
      model: ${LLM_SERVICE_GENERAL_MODEL_NAME}
      api_base: ${LLM_SERVICE_ENDPOINT}
      api_key: ${LLM_SERVICE_API_KEY}
      cache_strategy: "5m"

    image_gen: &image_generation_model
      model: ${IMAGE_MODEL_NAME}
      api_base: ${IMAGE_SERVICE_ENDPOINT}
      api_key: ${IMAGE_SERVICE_API_KEY}

    oauth_planning: &oauth_planning_model
      model: ${LLM_SERVICE_OAUTH_PLANNING_MODEL_NAME}
      api_base: ${LLM_SERVICE_OAUTH_ENDPOINT}
      oauth_token_url: ${LLM_SERVICE_OAUTH_TOKEN_URL}
      oauth_client_id: ${LLM_SERVICE_OAUTH_CLIENT_ID}
      oauth_client_secret: ${LLM_SERVICE_OAUTH_CLIENT_SECRET}
      oauth_scope: ${LLM_SERVICE_OAUTH_SCOPE}
      oauth_token_refresh_buffer_seconds: ${LLM_SERVICE_OAUTH_TOKEN_REFRESH_BUFFER_SECONDS, 300}
      parallel_tool_calls: true

  - services:
    session_service: &default_session_service
      type: "memory"
      default_behavior: "PERSISTENT"
    
    artifact_service: &default_artifact_service
      type: "filesystem"
      base_path: "/tmp/samv2"
      artifact_scope: "namespace"
    
    data_tools_config: &default_data_tools_config
      sqlite_memory_threshold_mb: 100
      max_result_preview_rows: 50
      max_result_preview_bytes: 4096
```

### Field Descriptions

#### Broker Connection Fields
- **`dev_mode`** (`boolean`): Enable development mode for simplified broker setup
- **`broker_url`** (`string`): Solace broker connection URL
- **`broker_username`** (`string`): Authentication username
- **`broker_password`** (`string`): Authentication password  
- **`broker_vpn`** (`string`): Solace VPN name
- **`temporary_queue`** (`boolean`): Use temporary queues for messaging

#### Model Configuration Fields
- **`model`** (`string`): LLM model identifier
- **`api_base`** (`string`): LLM service endpoint URL
- **`api_key`** (`string`): Authentication API key
- **`parallel_tool_calls`** (`boolean`): Enable parallel tool execution
- **`cache_strategy`** (`string`): Caching strategy - `none`, `5m`, `1h`
- **`max_tokens`** (`integer`): Maximum token limit
- **`temperature`** (`float`): Model temperature for randomness

#### OAuth Model Configuration Fields
- **`oauth_token_url`** (`string`): OAuth token endpoint URL
- **`oauth_client_id`** (`string`): OAuth client identifier
- **`oauth_client_secret`** (`string`): OAuth client secret
- **`oauth_scope`** (`string`): OAuth scope (space-separated)
- **`oauth_token_refresh_buffer_seconds`** (`integer`): Token refresh buffer time

---

## Agent Configuration

Agent configuration defines AI agents that can execute tasks and communicate with other agents.

### Complete Agent Example

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: agent.log

!include ../shared_config.yaml

apps:
  - name: my_agent_app
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      # Core Configuration
      namespace: "myorg/ai-agents"
      agent_name: "DataAnalyst" 
      display_name: "Data Analysis Agent"
      supports_streaming: true
      model: *planning_model

      # Agent Instructions
      instruction: |
        You are a specialized data analysis agent with expertise in 
        SQL queries, data visualization, and statistical analysis.

      # Tools Configuration
      tools:
        - tool_type: builtin-group
          group_name: "data_analysis"
        - tool_type: builtin-group  
          group_name: "artifact_management"
        - tool_type: builtin
          tool_name: "web_request"
        - tool_type: mcp
          connection_params:
            type: stdio
            command: "npx"
            args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

      # Services Configuration
      session_service:
        type: "sql"
        database_url: "sqlite:///agent-sessions.db"
        default_behavior: "PERSISTENT"
      
      artifact_service:
        type: "filesystem"
        base_path: "/tmp/artifacts"
        artifact_scope: "namespace"
      
      # Artifact Handling
      artifact_handling_mode: "reference"
      enable_embed_resolution: true
      enable_artifact_content_instruction: true
      data_tools_config: *default_data_tools_config

      # Agent Card (Discovery)
      agent_card:
        description: "AI agent specialized in data analysis and visualization"
        defaultInputModes: ["text", "file"]
        defaultOutputModes: ["text", "file", "image"]
        skills:
          - id: "sql_analysis"
            name: "SQL Analysis" 
            description: "Execute SQL queries and analyze database content"
          - id: "data_visualization"
            name: "Data Visualization"
            description: "Create charts and graphs from data"

      # Discovery & Communication
      agent_card_publishing:
        interval_seconds: 10
      agent_discovery:
        enabled: true
      inter_agent_communication:
        allow_list: ["*"]
        deny_list: []
        request_timeout_seconds: 300

      # Advanced Configuration
      inject_current_time: true
      inject_system_purpose: true
      inject_response_format: true
      stream_batching_threshold_bytes: 50
      max_llm_calls_per_task: 25
      enable_auto_continuation: true
      schema_max_keys: 100
```

### Core Agent Configuration Fields

#### Basic Settings
- **`namespace`** (`string`, **required**): A2A topic namespace for the agent
- **`agent_name`** (`string`, **required**): Unique identifier for the agent
- **`display_name`** (`string`): Human-readable agent name
- **`supports_streaming`** (`boolean`): Enable streaming responses
- **`model`** (`object/string`, **required**): LLM model configuration reference

#### Instructions
- **`instruction`** (`string`, **required**): System prompt defining agent behavior and capabilities

#### Artifact Handling
- **`artifact_handling_mode`** (`string`): How to represent created artifacts in messages
  - **Possible Values**: `ignore`, `embed`, `reference`
  - **Default**: `ignore`
- **`enable_embed_resolution`** (`boolean`): Enable dynamic embed processing
  - **Default**: `true`
- **`enable_artifact_content_instruction`** (`boolean`): Enable artifact content instructions
  - **Default**: `false`

#### Advanced Settings
- **`inject_current_time`** (`boolean`): Include current time in agent instructions
  - **Default**: `true`
- **`inject_system_purpose`** (`boolean`): Inject system purpose into instructions
  - **Default**: `false`
- **`inject_response_format`** (`boolean`): Inject response format instructions
  - **Default**: `false`
- **`stream_batching_threshold_bytes`** (`integer`): Threshold for batching streaming responses
  - **Default**: `0`
- **`max_llm_calls_per_task`** (`integer`): Maximum LLM calls per task
  - **Default**: `50`
- **`enable_auto_continuation`** (`boolean`): Auto-continue when interrupted by token limits
  - **Default**: `true`
- **`schema_max_keys`** (`integer`): Maximum dictionary keys for schema inference
  - **Default**: `50`

### Agent Card Configuration

The agent card enables discovery and describes the agent's capabilities to other agents.

#### Agent Card Fields
- **`description`** (`string`, **required**): Brief description of the agent's purpose
- **`defaultInputModes`** (`array[string]`): Supported input formats
  - **Possible Values**: `text`, `file`, `image`, `audio`, `application/json`
  - **Default**: `["text"]`
- **`defaultOutputModes`** (`array[string]`): Supported output formats  
  - **Possible Values**: `text`, `file`, `image`, `audio`
  - **Default**: `["text"]`
- **`skills`** (`array[object]`): Array of skill definitions

#### Skill Definition Fields
- **`id`** (`string`, **required**): Unique skill identifier
- **`name`** (`string`, **required**): Human-readable skill name
- **`description`** (`string`, **required**): Detailed skill description

### Agent Discovery & Communication

#### Agent Card Publishing
- **`agent_card_publishing.interval_seconds`** (`integer`): Publishing interval in seconds
  - **Default**: `30`

#### Agent Discovery  
- **`agent_discovery.enabled`** (`boolean`): Enable peer agent discovery
  - **Default**: `false`

#### Inter-Agent Communication
- **`inter_agent_communication.allow_list`** (`array[string]`): Allowed agent names or patterns
  - **Special Value**: `["*"]` allows all agents
- **`inter_agent_communication.deny_list`** (`array[string]`): Denied agent names or patterns
- **`inter_agent_communication.request_timeout_seconds`** (`integer`): Request timeout
  - **Default**: `30`

---

## Gateway Configuration

Gateways bridge external platforms with the A2A messaging system.

### WebUI Gateway Example

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: webui_gateway.log

!include ../shared_config.yaml

apps:
  - name: webui_gateway_app
    app_base_path: .
    app_module: solace_agent_mesh.gateway.http_sse.app

    broker:
      <<: *broker_connection

    app_config:
      # Core Gateway Configuration
      namespace: "myorg/ai-agents"
      gateway_id: "web-ui-gateway"
      session_secret_key: "${SESSION_SECRET_KEY}"
      
      # FastAPI Server Configuration
      fastapi_host: "0.0.0.0"
      fastapi_port: 8000
      cors_allowed_origins:
        - "http://localhost:3000"
        - "http://127.0.0.1:3000"

      # Services
      artifact_service: *default_artifact_service
      session_service:
        type: "sql"
        database_url: "sqlite:///webui-gateway.db"
        default_behavior: "PERSISTENT"

      # Optional Configuration
      model: *general_model
      system_purpose: "Web interface for AI agent interactions"
      response_format: "Provide clear, helpful responses suitable for web display"
      enable_embed_resolution: true
      gateway_artifact_content_limit_bytes: 10485760  # 10MB
      gateway_recursive_embed_depth: 3
```

### Slack Gateway Example

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: slack_gateway.log

!include ../shared_config.yaml

apps:
  - name: slack_gateway_app
    app_base_path: .
    app_module: solace_agent_mesh.gateway.generic.app

    broker:
      <<: *broker_connection

    app_config:
      namespace: "${NAMESPACE}"
      gateway_adapter: sam_slack_gateway_adapter.adapter.SlackAdapter
      
      adapter_config:
        slack_bot_token: "${SLACK_BOT_TOKEN}"
        slack_app_token: "${SLACK_APP_TOKEN}"
        slack_initial_status_message: ":thinking_face: Thinking..."
        correct_markdown_formatting: true
        slack_email_cache_ttl_seconds: 0

      artifact_service: *default_artifact_service
      system_purpose: "Slack interface for team AI agent interactions"
      response_format: "Format responses appropriately for Slack channels"
```

### Gateway Configuration Fields

#### Core Gateway Fields
- **`namespace`** (`string`, **required**): A2A topic namespace
- **`gateway_id`** (`string`): Unique gateway identifier (auto-generated if omitted)
- **`system_purpose`** (`string`): Description of the gateway's purpose
- **`response_format`** (`string`): Instructions for response formatting

#### WebUI Gateway Specific Fields
- **`session_secret_key`** (`string`, **required**): Secret for web session signing
- **`fastapi_host`** (`string`): FastAPI server host
  - **Default**: `127.0.0.1`
- **`fastapi_port`** (`integer`): FastAPI server port  
  - **Default**: `8000`
- **`cors_allowed_origins`** (`array[string]`): CORS allowed origins
  - **Example**: `["http://localhost:3000"]`
- **`gateway_artifact_content_limit_bytes`** (`integer`): Artifact size limit
  - **Default**: `10485760` (10MB)
- **`gateway_recursive_embed_depth`** (`integer`): Max recursive embed depth
  - **Default**: `3`

#### Generic Gateway Fields
- **`gateway_adapter`** (`string`): Adapter module for the gateway implementation
- **`adapter_config`** (`object`): Adapter-specific configuration

---

## Tool Configuration

Tools extend agent capabilities with various functionalities.

### Built-in Tool Group Configuration

```yaml
tools:
  - tool_type: builtin-group
    group_name: "artifact_management"
    tool_config:
      specific_tool_name:
        custom_parameter: "value"

  - tool_type: builtin-group
    group_name: "data_analysis"
    tool_config:
      sqlite_memory_threshold_mb: 100
      max_result_preview_rows: 50
      max_result_preview_bytes: 4096

  - tool_type: builtin-group
    group_name: "web"
    tool_config:
      web_request:
        timeout: 30
        max_retries: 3

  - tool_type: builtin-group
    group_name: "audio"

  - tool_type: builtin-group
    group_name: "image"

  - tool_type: builtin-group
    group_name: "general"
```

### Individual Built-in Tool Configuration

```yaml
tools:
  - tool_type: builtin
    tool_name: "web_request"
    tool_config:
      timeout: 30
      max_retries: 3
      
  - tool_type: builtin
    tool_name: "query_data_with_sql"
    tool_config:
      sqlite_memory_threshold_mb: 50
      
  - tool_type: builtin
    tool_name: "text_to_speech"
    tool_config:
      default_voice: "female"
      default_tone: "professional"
```

### Python Tool Configuration

```yaml
tools:
  - tool_type: python
    tool_name: "custom_calculator"
    tool_description: "Performs custom mathematical calculations"
    component_module: "my_company.tools.calculators"
    function_name: "calculate_advanced_metrics"
    component_base_path: "src/plugins"
    tool_config:
      precision: 6
      use_cache: true
    required_scopes: ["calculation", "data_access"]
```

### MCP Tool Configuration

#### Stdio MCP Connection

```yaml
tools:
  - tool_type: mcp
    tool_name: "read_file"  # Optional: specific tool filter
    connection_params:
      type: stdio
      command: "npx"
      args:
        - "-y"
        - "@modelcontextprotocol/server-filesystem"
        - "/tmp/samv2"
      timeout: 300
    environment_variables:
      DEBUG_MODE: "true"
      CONFIG_PATH: "/etc/config"
```

#### SSE MCP Connection

```yaml
tools:
  - tool_type: mcp
    connection_params:
      type: sse
      url: "https://mcp.example.com/v1/sse"
      headers:
        Authorization: "Bearer ${MCP_AUTH_TOKEN}"
        Custom-Header: "value"
    tool_config:
      custom_setting: "value"
```

#### OAuth2 MCP Tool

```yaml
tools:
  - tool_type: mcp
    connection_params:
      type: sse
      url: "https://mcp.example.com/v1/sse"
    auth:
      type: oauth2
    manifest:
      - name: "search_documents"
        description: "Search through document repository"
        inputSchema:
          type: object
          properties:
            query:
              type: string
              description: "Search query"
            limit:
              type: integer
              description: "Maximum results"
          required: ["query"]
          additionalProperties: false
          $schema: "http://json-schema.org/draft-07/schema#"
```

### Tool Configuration Fields

#### Built-in Tool Group Fields
- **`tool_type`** (`string`, **required**): Must be `builtin-group`
- **`group_name`** (`string`, **required**): Tool group identifier
  - **Available Groups**: `artifact_management`, `data_analysis`, `web`, `audio`, `image`, `general`, `communication`
- **`tool_config`** (`object`): Group-specific configuration parameters
- **`required_scopes`** (`array[string]`): Required security scopes

#### Individual Built-in Tool Fields  
- **`tool_type`** (`string`, **required**): Must be `builtin`
- **`tool_name`** (`string`, **required**): Specific tool name to enable
- **`tool_config`** (`object`): Tool-specific configuration parameters
- **`required_scopes`** (`array[string]`): Required security scopes

#### Python Tool Fields
- **`tool_type`** (`string`, **required**): Must be `python`
- **`tool_name`** (`string`): Tool name for the LLM
- **`tool_description`** (`string`): Tool description for the LLM
- **`component_module`** (`string`, **required**): Python module path
- **`function_name`** (`string`, **required**): Function name within the module
- **`component_base_path`** (`string`): Base path for module resolution
- **`tool_config`** (`object`): Custom tool configuration
- **`required_scopes`** (`array[string]`): Required security scopes

#### MCP Tool Fields
- **`tool_type`** (`string`, **required**): Must be `mcp`
- **`tool_name`** (`string`): Optional filter for specific MCP tool
- **`connection_params`** (`object`, **required**): Connection configuration
- **`environment_variables`** (`object`): Environment variables for stdio connections
- **`auth`** (`object`): Authentication configuration for remote MCP
- **`manifest`** (`array[object]`): Tool manifest for remote MCP
- **`tool_config`** (`object`): MCP-specific configuration
- **`required_scopes`** (`array[string]`): Required security scopes

#### MCP Connection Parameters
**Stdio Connection:**
- **`type`** (`string`, **required**): Must be `stdio`
- **`command`** (`string`, **required**): Executable command
- **`args`** (`array[string]`): Command arguments
- **`timeout`** (`integer`): Connection timeout in seconds

**SSE Connection:**
- **`type`** (`string`, **required**): Must be `sse`
- **`url`** (`string`, **required**): MCP server URL
- **`headers`** (`object`): HTTP headers for requests

---

## Service Configuration

Services provide persistent storage and session management for agents and gateways.

### Session Service Configuration

#### Memory Session Service
```yaml
session_service:
  type: "memory"
  default_behavior: "PERSISTENT"  # or "RUN_BASED"
```

#### SQL Session Service
```yaml
session_service:
  type: "sql"
  database_url: "sqlite:///sessions.db"
  # database_url: "postgresql://user:pass@host:port/db"
  default_behavior: "PERSISTENT"
```

#### Vertex RAG Session Service
```yaml
session_service:
  type: "vertex_rag"
  default_behavior: "PERSISTENT"
  # Additional Vertex AI configuration may be required
```

### Artifact Service Configuration

#### Memory Artifact Service
```yaml
artifact_service:
  type: "memory"
  artifact_scope: "namespace"  # or "app", "custom"
```

#### Filesystem Artifact Service
```yaml
artifact_service:
  type: "filesystem"
  base_path: "/tmp/artifacts"
  artifact_scope: "namespace"
```

#### Google Cloud Storage Artifact Service
```yaml
artifact_service:
  type: "gcs"
  bucket_name: "my-artifacts-bucket"
  artifact_scope: "namespace"
```

#### Custom Scope Artifact Service
```yaml
artifact_service:
  type: "filesystem"
  base_path: "/tmp/artifacts"
  artifact_scope: "custom"
  artifact_scope_value: "my-custom-scope"
```

### Service Configuration Fields

#### Session Service Fields
- **`type`** (`string`, **required**): Service type
  - **Possible Values**: `memory`, `sql`, `vertex_rag`
- **`database_url`** (`string`): Database connection URL (required for `sql` type)
- **`default_behavior`** (`string`): Session persistence behavior
  - **Possible Values**: `PERSISTENT`, `RUN_BASED`
  - **Default**: `PERSISTENT`

#### Artifact Service Fields
- **`type`** (`string`, **required**): Service type
  - **Possible Values**: `memory`, `filesystem`, `gcs`
- **`base_path`** (`string`): File system base directory (required for `filesystem` type)
- **`bucket_name`** (`string`): GCS bucket name (required for `gcs` type)
- **`artifact_scope`** (`string`): Scope for artifact organization
  - **Possible Values**: `namespace`, `app`, `custom`
  - **Default**: `namespace`
- **`artifact_scope_value`** (`string`): Custom scope value (required when `artifact_scope` is `custom`)

### Data Tools Configuration

```yaml
data_tools_config:
  sqlite_memory_threshold_mb: 100
  max_result_preview_rows: 50
  max_result_preview_bytes: 4096
```

#### Data Tools Fields
- **`sqlite_memory_threshold_mb`** (`integer`): Memory threshold for SQLite operations
  - **Default**: `100`
- **`max_result_preview_rows`** (`integer`): Maximum rows in result previews
  - **Default**: `50`  
- **`max_result_preview_bytes`** (`integer`): Maximum bytes in result previews
  - **Default**: `4096`

---

## Broker Configuration

Broker configuration defines how components connect to the Solace PubSub+ event broker.

### Complete Broker Configuration

```yaml
broker:
  # Connection Settings
  dev_mode: false
  broker_url: "ws://localhost:8008"
  broker_username: "default"
  broker_password: "default"
  broker_vpn: "default"
  
  # Queue and Topic Settings
  temporary_queue: true
  input_enabled: true
  output_enabled: true
  
  # Security Settings (Optional)
  cert_validated: true
  
  # Connection Management (Optional)
  connection_timeout: 30
  reconnect_attempts: 5
  reconnect_delay: 1.0
```

### Broker Configuration Fields

#### Connection Fields
- **`dev_mode`** (`boolean`): Enable development mode
  - **Default**: `false`
  - **Description**: Simplifies broker configuration for development
- **`broker_url`** (`string`, **required**): Broker connection URL
  - **Examples**: `ws://localhost:8008`, `wss://broker.example.com:443`
- **`broker_username`** (`string`, **required**): Authentication username
- **`broker_password`** (`string`, **required**): Authentication password
- **`broker_vpn`** (`string`, **required**): Solace VPN name

#### Queue and Messaging Fields
- **`temporary_queue`** (`boolean`): Use temporary queues for responses
  - **Default**: `true`
- **`input_enabled`** (`boolean`): Enable message receiving
  - **Default**: `true`
- **`output_enabled`** (`boolean`): Enable message publishing  
  - **Default**: `true`

#### Security Fields
- **`cert_validated`** (`boolean`): Validate SSL certificates
  - **Default**: `false`

#### Connection Management Fields
- **`connection_timeout`** (`integer`): Connection timeout in seconds
  - **Default**: `30`
- **`reconnect_attempts`** (`integer`): Maximum reconnection attempts
  - **Default**: `5`
- **`reconnect_delay`** (`float`): Delay between reconnection attempts
  - **Default**: `1.0`

---

## Environment Variables Reference

Common environment variables used in configurations:

### Broker Variables
- **`SOLACE_DEV_MODE`**: Enable development mode (`true`/`false`)
- **`SOLACE_BROKER_URL`**: Broker connection URL
- **`SOLACE_BROKER_USERNAME`**: Broker username
- **`SOLACE_BROKER_PASSWORD`**: Broker password
- **`SOLACE_BROKER_VPN`**: Broker VPN name
- **`USE_TEMPORARY_QUEUES`**: Use temporary queues (`true`/`false`)

### LLM Service Variables
- **`LLM_SERVICE_ENDPOINT`**: LLM service endpoint URL
- **`LLM_SERVICE_API_KEY`**: LLM service API key
- **`LLM_SERVICE_PLANNING_MODEL_NAME`**: Planning model name
- **`LLM_SERVICE_GENERAL_MODEL_NAME`**: General model name

### OAuth Variables
- **`LLM_SERVICE_OAUTH_TOKEN_URL`**: OAuth token endpoint
- **`LLM_SERVICE_OAUTH_CLIENT_ID`**: OAuth client ID
- **`LLM_SERVICE_OAUTH_CLIENT_SECRET`**: OAuth client secret
- **`LLM_SERVICE_OAUTH_SCOPE`**: OAuth scope

### Application Variables
- **`NAMESPACE`**: A2A topic namespace
- **`SESSION_SECRET_KEY`**: Web session secret key
- **`FASTAPI_HOST`**: FastAPI server host
- **`FASTAPI_PORT`**: FastAPI server port

### Gateway-Specific Variables
- **`SLACK_BOT_TOKEN`**: Slack bot token (starts with `xoxb-`)
- **`SLACK_APP_TOKEN`**: Slack app token (starts with `xapp-`)

### Database Variables
- **`ORCHESTRATOR_DATABASE_URL`**: Orchestrator database URL
- **`WEB_UI_GATEWAY_DATABASE_URL`**: WebUI gateway database URL

---

## Configuration Validation

All configuration files are validated using Pydantic models. Common validation errors and their solutions:

### Agent Configuration Errors
- **Missing required fields**: Ensure `namespace`, `agent_name`, and `model` are provided
- **Invalid tool configurations**: Verify `tool_type` matches one of: `builtin`, `builtin-group`, `python`, `mcp`, `openapi`
- **Invalid artifact scope**: Use `namespace`, `app`, or `custom` for `artifact_scope`

### Gateway Configuration Errors
- **Missing session secret**: WebUI gateways require `session_secret_key`
- **Invalid CORS origins**: Ensure CORS origins are properly formatted URLs
- **Adapter configuration**: Generic gateways require valid `gateway_adapter` module

### Service Configuration Errors
- **Database URL format**: SQL session services require valid database URLs
- **File system permissions**: Filesystem artifact services need write access to `base_path`
- **GCS bucket access**: GCS artifact services require valid bucket names and credentials

### Tool Configuration Errors
- **MCP connection parameters**: Ensure `connection_params` contains required fields for the connection type
- **Python module paths**: Verify `component_module` and `function_name` are correct
- **Built-in tool names**: Use exact tool names from the registry

For detailed troubleshooting, check the application logs for specific validation error messages.