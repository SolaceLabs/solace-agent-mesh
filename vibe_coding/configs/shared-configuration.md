# Shared Configuration

The `shared_config.yaml` file contains reusable configuration blocks referenced by agents and gateways using YAML anchors. This centralized approach eliminates duplication and ensures consistency across your entire project.

## Overview

Shared configuration provides:
- **Centralized Management** - Define common settings once
- **Consistency** - All components use the same base configuration
- **Maintainability** - Update settings in one place
- **Flexibility** - Override shared settings when needed

## File Structure

```yaml
shared_config:
  - broker_connection: &broker_connection
      # Broker settings
  
  - models:
      planning_model: &planning_model
        # Planning model config
      general_model: &general_model
        # General model config
      multimodal_model: &multimodal_model
        # Multimodal model config
  
  - services:
      session_service: &default_session_service
        # Session service config
      artifact_service: &default_artifact_service
        # Artifact service config
      data_tools_config: &default_data_tools_config
        # Data tools config
```

## Configuration Sections

### 1. Broker Connection

Defines Solace PubSub+ Event Broker connection settings.

```yaml
shared_config:
  - broker_connection: &broker_connection
      broker_type: "solace"
      broker_url: "${SOLACE_BROKER_URL}"
      broker_username: "${SOLACE_BROKER_USERNAME}"
      broker_password: "${SOLACE_BROKER_PASSWORD}"
      broker_vpn: "${SOLACE_BROKER_VPN}"
```

See [Broker Configuration](./broker-configuration.md) for detailed options.

### 2. Model Definitions

Defines LLM models for different use cases.

```yaml
shared_config:
  - models:
      planning_model: &planning_model
        model: "openai/gpt-4"
        api_key: "${OPENAI_API_KEY}"
        temperature: 0.3
        max_tokens: 4096
      
      general_model: &general_model
        model: "openai/gpt-3.5-turbo"
        api_key: "${OPENAI_API_KEY}"
        temperature: 0.7
      
      multimodal_model: &multimodal_model
        model: "gemini/gemini-1.5-pro"
        api_key: "${GEMINI_API_KEY}"
```

See [Model Configuration](./model-configuration.md) for all model options.

### 3. Service Definitions

Defines shared services for session storage, artifacts, and data tools.

```yaml
shared_config:
  - services:
      session_service: &default_session_service
        type: "memory"
        default_behavior: "PERSISTENT"
      
      artifact_service: &default_artifact_service
        type: "filesystem"
        base_path: "/tmp/sam-artifacts"
      
      data_tools_config: &default_data_tools_config
        max_rows_to_analyze: 1000
        enable_query_caching: true
```

See [Service Configuration](./service-configuration.md) for service options.

## Using Shared Configuration

### In Agent Configuration

```yaml
!include shared_config.yaml

components:
  - name: my-agent
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection  # Reference broker config
    
    app_config:
      namespace: "${NAMESPACE}"
      agent_name: "my-agent"
      model: *general_model  # Reference model config
      session_service: *default_session_service  # Reference service
      artifact_service: *default_artifact_service
```

### In Gateway Configuration

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
      artifact_service: *default_artifact_service
```

## YAML Anchor Syntax

### Defining Anchors

Use `&anchor_name` to create a reusable block:

```yaml
broker_connection: &broker_connection
  broker_type: "solace"
  broker_url: "${SOLACE_BROKER_URL}"
```

### Referencing Anchors

#### Simple Reference
Use `*anchor_name` to reference a value:

```yaml
model: *general_model
```

#### Merge Reference
Use `<<: *anchor_name` to merge an object:

```yaml
broker:
  <<: *broker_connection
```

#### Override Values
Merge and override specific fields:

```yaml
broker:
  <<: *broker_connection
  broker_queue_name: "custom-queue"  # Override specific field
```

## Multiple Shared Configuration Files

You can create multiple shared configuration files for different environments or purposes.

### Naming Convention

Files must start with `shared_config`:
- `shared_config.yaml` - Default configuration
- `shared_config_aws.yaml` - AWS-specific settings
- `shared_config_production.yaml` - Production settings
- `shared_config_dev.yaml` - Development settings

### Using Different Shared Configs

```yaml
# Use AWS-specific configuration
!include shared_config_aws.yaml

components:
  - name: my-agent
    broker:
      <<: *broker_connection
```

### Organizing by Directory

```
configs/
├── shared_config.yaml
├── environments/
│   ├── shared_config_dev.yaml
│   ├── shared_config_staging.yaml
│   └── shared_config_prod.yaml
└── agents/
    └── my-agent.yaml
```

Reference with relative path:

```yaml
!include ../environments/shared_config_prod.yaml
```

## Complete Example

### shared_config.yaml

```yaml
shared_config:
  # Broker Connection
  - broker_connection: &broker_connection
      broker_type: "solace"
      broker_url: "${SOLACE_BROKER_URL}"
      broker_username: "${SOLACE_BROKER_USERNAME}"
      broker_password: "${SOLACE_BROKER_PASSWORD}"
      broker_vpn: "${SOLACE_BROKER_VPN}"
  
  # Model Definitions
  - models:
      planning_model: &planning_model
        model: "openai/gpt-4"
        api_key: "${OPENAI_API_KEY}"
        temperature: 0.3
        max_tokens: 4096
      
      general_model: &general_model
        model: "openai/gpt-3.5-turbo"
        api_key: "${OPENAI_API_KEY}"
        temperature: 0.7
        max_tokens: 2048
      
      multimodal_model: &multimodal_model
        model: "gemini/gemini-1.5-pro"
        api_key: "${GEMINI_API_KEY}"
        temperature: 0.5
      
      image_generation_model: &image_generation_model
        model: "openai/dall-e-3"
        api_key: "${OPENAI_API_KEY}"
      
      audio_transcription_model: &audio_transcription_model
        model: "openai/whisper-1"
        api_key: "${OPENAI_API_KEY}"
  
  # Service Definitions
  - services:
      session_service: &default_session_service
        type: "sql"
        database_url: "${DATABASE_URL}"
        default_behavior: "PERSISTENT"
      
      artifact_service: &default_artifact_service
        type: "s3"
        bucket_name: "${S3_BUCKET_NAME}"
        region: "${AWS_REGION}"
      
      data_tools_config: &default_data_tools_config
        max_rows_to_analyze: 5000
        enable_query_caching: true
        query_timeout_seconds: 60
```

### Using in Agent

```yaml
!include shared_config.yaml

components:
  - name: data-analyst-agent
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: "${NAMESPACE}"
      agent_name: "data-analyst"
      display_name: "Data Analyst Agent"
      
      instruction: |
        You are a data analyst agent that can analyze data and create visualizations.
      
      model: *general_model
      
      tools:
        - tool_type: builtin-group
          group_name: "data_analysis"
        - tool_type: builtin-group
          group_name: "artifact_management"
      
      session_service: *default_session_service
      artifact_service: *default_artifact_service
      data_tools_config: *default_data_tools_config
```

## Best Practices

### 1. Use Environment Variables

Always use environment variables for sensitive data:

```yaml
broker_password: "${SOLACE_BROKER_PASSWORD}"
api_key: "${OPENAI_API_KEY}"
```

Never hardcode secrets in configuration files.

### 2. Organize by Purpose

Group related configurations together:

```yaml
shared_config:
  - broker_connection: &broker_connection
      # All broker settings
  
  - models:
      # All model definitions
  
  - services:
      # All service definitions
```

### 3. Use Descriptive Anchor Names

Choose clear, descriptive names for anchors:

```yaml
# Good
planning_model: &planning_model
default_session_service: &default_session_service

# Avoid
model1: &m1
service: &svc
```

### 4. Document Configuration

Add comments to explain configuration choices:

```yaml
shared_config:
  - models:
      # High-quality model for complex reasoning and planning tasks
      planning_model: &planning_model
        model: "openai/gpt-4"
        temperature: 0.3  # Lower temperature for more consistent planning
```

### 5. Version Control

- Commit `shared_config.yaml` to version control
- Never commit `.env` files with secrets
- Use `.env.example` to document required variables

### 6. Environment-Specific Configs

Create separate shared configs for different environments:

```yaml
# shared_config_dev.yaml - Development
artifact_service: &default_artifact_service
  type: "filesystem"
  base_path: "/tmp/sam-artifacts"

# shared_config_prod.yaml - Production
artifact_service: &default_artifact_service
  type: "s3"
  bucket_name: "${S3_BUCKET_NAME}"
  region: "${AWS_REGION}"
```

## Troubleshooting

### Anchor Not Found

**Error**: `Unknown anchor: broker_connection`

**Solution**: Ensure the anchor is defined before it's referenced:

```yaml
# Define first
shared_config:
  - broker_connection: &broker_connection
      # ...

# Then reference
components:
  - name: agent
    broker:
      <<: *broker_connection
```

### Include File Not Found

**Error**: `File not found: shared_config.yaml`

**Solution**: Check the file path is correct relative to the including file:

```yaml
# If shared_config.yaml is in parent directory
!include ../shared_config.yaml

# If in same directory
!include shared_config.yaml
```

### Merge Conflicts

**Error**: Unexpected behavior when merging anchors

**Solution**: Use `<<:` for object merging, not simple reference:

```yaml
# Correct - merges object
broker:
  <<: *broker_connection
  broker_queue_name: "custom"

# Incorrect - replaces entire value
broker: *broker_connection
```

## Related Documentation

- [Broker Configuration](./broker-configuration.md) - Detailed broker settings
- [Model Configuration](./model-configuration.md) - LLM model options
- [Service Configuration](./service-configuration.md) - Service definitions
- [Environment Variables](./environment-variables.md) - Environment variable reference
- [Best Practices](./best-practices.md) - Configuration best practices