# Gateway Configuration

Configures gateways that connect external systems to the agent mesh. Gateways serve as entry and exit points, translating between external protocols and the internal A2A communication standard.

## Overview

Gateway configuration enables:
- **WebUI Gateway** - Web-based user interface
- **REST Gateway** - HTTP REST API
- **Event Mesh Gateway** - Event-driven integration
- **Slack Gateway** - Slack bot integration
- **Custom Gateways** - Custom protocol adapters

## Common Gateway Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `namespace` | String | Yes | - | Topic namespace matching agents |
| `gateway_id` | String | Yes | - | Unique gateway identifier |
| `default_agent_name` | String | No | - | Default agent for requests |
| `artifact_service` | Object | Yes | - | Artifact storage configuration |

## WebUI Gateway

Web-based user interface for agent interaction.

### Configuration Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `webui_server_port` | Integer | No | `8000` | HTTP server port |
| `webui_session_secret_key` | String | Yes | - | Session encryption key |
| `session_service` | Object | Yes | - | Session storage config |
| `frontend_feature_enablement` | Object | No | - | Feature flags |
| `speech` | Object | No | - | Speech services config |
| `data_retention` | Object | No | - | Data cleanup policies |

### Basic Configuration

```yaml
!include shared_config.yaml

components:
  - name: webui-gateway
    app_module: solace_agent_mesh.gateway.http_sse.app
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: "${NAMESPACE}"
      gateway_id: "webui-gw-01"
      webui_server_port: 8000
      webui_session_secret_key: "${WEBUI_SESSION_SECRET_KEY}"
      default_agent_name: "OrchestratorAgent"
      
      artifact_service: *default_artifact_service
      session_service: *default_session_service
```

### Complete Configuration

```yaml
!include shared_config.yaml

components:
  - name: webui-gateway
    app_module: solace_agent_mesh.gateway.http_sse.app
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: "${NAMESPACE}"
      gateway_id: "webui-gw-01"
      webui_server_port: 8000
      webui_session_secret_key: "${WEBUI_SESSION_SECRET_KEY}"
      default_agent_name: "OrchestratorAgent"
      
      # Services
      artifact_service: *default_artifact_service
      session_service:
        type: "sql"
        database_url: "${DATABASE_URL}"
      
      # Feature flags
      frontend_feature_enablement:
        speech_to_text: true
        text_to_speech: true
        file_upload: true
        image_upload: true
        projects: true
        feedback: true
      
      # Speech services
      speech:
        stt_provider: "openai"
        stt_config:
          api_key: "${OPENAI_API_KEY}"
          model: "whisper-1"
        tts_provider: "openai"
        tts_config:
          api_key: "${OPENAI_API_KEY}"
          voice: "alloy"
          speed: 1.0
      
      # Data retention
      data_retention:
        enabled: true
        task_retention_days: 90
        cleanup_interval_hours: 24
```

### Feature Enablement

```yaml
frontend_feature_enablement:
  speech_to_text: true          # Enable STT
  text_to_speech: true          # Enable TTS
  file_upload: true             # Enable file uploads
  image_upload: true            # Enable image uploads
  projects: true                # Enable projects feature
  feedback: true                # Enable user feedback
  prompt_library: true          # Enable prompt library
```

### Speech Configuration

```yaml
speech:
  # Speech-to-text
  stt_provider: "openai"  # or "azure"
  stt_config:
    api_key: "${OPENAI_API_KEY}"
    model: "whisper-1"
  
  # Text-to-speech
  tts_provider: "openai"  # or "azure"
  tts_config:
    api_key: "${OPENAI_API_KEY}"
    voice: "alloy"  # alloy, echo, fable, onyx, nova, shimmer
    speed: 1.0      # 0.25 to 4.0
    output_format: "mp3"
```

## REST Gateway

HTTP REST API for programmatic access.

### Configuration Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `rest_api_server_port` | Integer | No | `8080` | REST API port |
| `external_auth_service_url` | String | No | - | External auth service |
| `cors_origins` | List | No | `["*"]` | CORS allowed origins |

### Basic Configuration

```yaml
!include shared_config.yaml

components:
  - name: rest-gateway
    app_module: sam_rest_gateway.app
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: "${NAMESPACE}"
      gateway_id: "rest-gw-01"
      rest_api_server_port: 8080
      default_agent_name: "OrchestratorAgent"
      
      artifact_service: *default_artifact_service
```

### With Authentication

```yaml
app_config:
  namespace: "${NAMESPACE}"
  gateway_id: "rest-gw-01"
  rest_api_server_port: 8080
  external_auth_service_url: "${AUTH_SERVICE_URL}"
  
  cors_origins:
    - "https://app.example.com"
    - "https://admin.example.com"
  
  artifact_service: *default_artifact_service
```

## Event Mesh Gateway

Event-driven integration with external systems.

### Configuration Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `input_topic` | String | Yes | - | Topic to subscribe to |
| `output_topic` | String | Yes | - | Topic to publish to |
| `message_format` | String | No | `"json"` | Message format |

### Basic Configuration

```yaml
!include shared_config.yaml

components:
  - name: event-gateway
    app_module: sam_event_mesh_gateway.app
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: "${NAMESPACE}"
      gateway_id: "event-gw-01"
      
      input_topic: "external/events/>"
      output_topic: "external/responses"
      message_format: "json"
      
      default_agent_name: "EventProcessor"
      artifact_service: *default_artifact_service
```

## Slack Gateway

Slack bot integration.

### Configuration Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `slack_bot_token` | String | Yes | - | Slack bot token |
| `slack_app_token` | String | Yes | - | Slack app token |
| `slack_signing_secret` | String | Yes | - | Slack signing secret |

### Configuration

```yaml
!include shared_config.yaml

components:
  - name: slack-gateway
    app_module: sam_slack_gateway.app
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: "${NAMESPACE}"
      gateway_id: "slack-gw-01"
      
      slack_bot_token: "${SLACK_BOT_TOKEN}"
      slack_app_token: "${SLACK_APP_TOKEN}"
      slack_signing_secret: "${SLACK_SIGNING_SECRET}"
      
      default_agent_name: "SlackAssistant"
      artifact_service: *default_artifact_service
```

## Complete Examples

### Production WebUI Gateway

```yaml
!include shared_config.yaml

components:
  - name: webui-production
    app_module: solace_agent_mesh.gateway.http_sse.app
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: "${NAMESPACE}"
      gateway_id: "webui-prod-01"
      webui_server_port: 8000
      webui_session_secret_key: "${WEBUI_SESSION_SECRET_KEY}"
      default_agent_name: "OrchestratorAgent"
      
      artifact_service:
        type: "s3"
        bucket_name: "${S3_BUCKET_NAME}"
        region: "${AWS_REGION}"
      
      session_service:
        type: "sql"
        database_url: "${DATABASE_URL}"
      
      frontend_feature_enablement:
        speech_to_text: true
        text_to_speech: true
        file_upload: true
        image_upload: true
        projects: true
        feedback: true
      
      speech:
        stt_provider: "openai"
        stt_config:
          api_key: "${OPENAI_API_KEY}"
        tts_provider: "openai"
        tts_config:
          api_key: "${OPENAI_API_KEY}"
          voice: "alloy"
      
      data_retention:
        enabled: true
        task_retention_days: 90
        cleanup_interval_hours: 24
```

### Multi-Gateway Setup

```yaml
!include shared_config.yaml

components:
  # WebUI Gateway
  - name: webui
    app_module: solace_agent_mesh.gateway.http_sse.app
    broker:
      <<: *broker_connection
    app_config:
      namespace: "${NAMESPACE}"
      gateway_id: "webui-gw-01"
      webui_server_port: 8000
      webui_session_secret_key: "${WEBUI_SESSION_SECRET_KEY}"
      default_agent_name: "OrchestratorAgent"
      artifact_service: *default_artifact_service
      session_service: *default_session_service
  
  # REST Gateway
  - name: rest-api
    app_module: sam_rest_gateway.app
    broker:
      <<: *broker_connection
    app_config:
      namespace: "${NAMESPACE}"
      gateway_id: "rest-gw-01"
      rest_api_server_port: 8080
      default_agent_name: "OrchestratorAgent"
      artifact_service: *default_artifact_service
  
  # Slack Gateway
  - name: slack-bot
    app_module: sam_slack_gateway.app
    broker:
      <<: *broker_connection
    app_config:
      namespace: "${NAMESPACE}"
      gateway_id: "slack-gw-01"
      slack_bot_token: "${SLACK_BOT_TOKEN}"
      slack_app_token: "${SLACK_APP_TOKEN}"
      slack_signing_secret: "${SLACK_SIGNING_SECRET}"
      default_agent_name: "SlackAssistant"
      artifact_service: *default_artifact_service
```

## Best Practices

### 1. Use Secure Session Keys

```bash
# Generate secure key
openssl rand -hex 32

# Set in environment
export WEBUI_SESSION_SECRET_KEY="generated-key-here"
```

### 2. Configure Data Retention

```yaml
data_retention:
  enabled: true
  task_retention_days: 90
  cleanup_interval_hours: 24
```

### 3. Enable Appropriate Features

```yaml
frontend_feature_enablement:
  speech_to_text: true   # If needed
  file_upload: true      # If needed
  projects: false        # If not needed
```

### 4. Use SQL for Production Sessions

```yaml
session_service:
  type: "sql"
  database_url: "${DATABASE_URL}"
```

### 5. Shared Artifact Service

All gateways must use same artifact service:

```yaml
artifact_service: *default_artifact_service
```

## Troubleshooting

### Gateway Not Starting

**Solutions**:
1. Check port is not in use
2. Verify broker connection
3. Review gateway logs
4. Check environment variables

### Session Issues

**Solutions**:
1. Verify session service config
2. Check database connection
3. Verify session secret key
4. Review session logs

### Speech Not Working

**Solutions**:
1. Verify API keys are set
2. Check feature flags enabled
3. Review speech provider config
4. Test API keys independently

## Related Documentation

- [Agent Configuration](./agent-configuration.md) - Configuring agents
- [Service Configuration](./service-configuration.md) - Storage services
- [Environment Variables](./environment-variables.md) - Gateway variables
- [Best Practices](./best-practices.md) - Gateway best practices