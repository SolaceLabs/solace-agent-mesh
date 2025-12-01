# Configuration Best Practices

Guidelines for effective Agent Mesh configuration.

## General Principles

### 1. Use Environment Variables for Secrets

```yaml
# Good
api_key: "${OPENAI_API_KEY}"

# Bad
api_key: "sk-actual-key-here"
```

### 2. Use Shared Configuration

```yaml
shared_config:
  - broker_connection: &broker_connection
      broker_type: "solace"
      # ...

# Reference in components
broker:
  <<: *broker_connection
```

### 3. Separate Environments

Create different configs for dev/staging/prod:
- `shared_config_dev.yaml`
- `shared_config_staging.yaml`
- `shared_config_prod.yaml`

### 4. Document Configuration

Add comments explaining choices:

```yaml
# Use GPT-4 for complex reasoning tasks
planning_model: &planning_model
  model: "openai/gpt-4"
  temperature: 0.3  # Lower temp for consistent planning
```

### 5. Validate Early

Use Pydantic models for configuration validation:

```python
class ToolConfig(BaseModel):
    api_key: str
    timeout: int = 30
```

## Security Best Practices

### 1. Never Commit Secrets

- Use `.env` files (add to `.gitignore`)
- Use environment variables
- Use secret management services

### 2. Use TLS in Production

```yaml
broker_url: "tcps://broker.example.com:55443"
```

### 3. Rotate Credentials Regularly

Update API keys and passwords periodically.

### 4. Limit Permissions

Use least-privilege principle for:
- Database users
- S3 bucket policies
- API keys

## Performance Best Practices

### 1. Choose Appropriate Models

```yaml
# Simple tasks
model: *general_model

# Complex reasoning
model: *planning_model
```

### 2. Set Token Limits

```yaml
model:
  max_tokens: 2048  # Prevent excessive costs
```

### 3. Use Caching

```yaml
data_tools_config:
  enable_query_caching: true
```

### 4. Configure Timeouts

```yaml
model:
  timeout: 60
tool_config:
  timeout: 30
```

## Deployment Best Practices

### 1. Use SQL for Production Sessions

```yaml
session_service:
  type: "sql"
  database_url: "${DATABASE_URL}"
```

### 2. Use Cloud Storage for Artifacts

```yaml
artifact_service:
  type: "s3"
  bucket_name: "${S3_BUCKET_NAME}"
```

### 3. Configure Data Retention

```yaml
data_retention:
  enabled: true
  task_retention_days: 90
```

### 4. Enable Monitoring

- Configure logging
- Set up metrics collection
- Enable health checks

## Configuration Organization

### Directory Structure

```
configs/
├── shared_config.yaml
├── agents/
│   ├── agent1.yaml
│   └── agent2.yaml
├── gateways/
│   ├── webui.yaml
│   └── rest.yaml
└── environments/
    ├── dev/
    ├── staging/
    └── prod/
```

### Naming Conventions

- Use lowercase with hyphens: `my-agent.yaml`
- Be descriptive: `data-analyst-agent.yaml`
- Group related configs: `agents/analytics/`

## Testing Configuration

### 1. Test Locally First

```bash
# Development config
sam run configs/agents/my-agent.yaml
```

### 2. Validate YAML Syntax

```bash
# Check YAML is valid
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

### 3. Test with Minimal Config

Start with minimal configuration and add complexity gradually.

### 4. Use Debug Logging

```yaml
log:
  level: DEBUG
```

## Related Documentation

- [Shared Configuration](./shared-configuration.md)
- [Agent Configuration](./agent-configuration.md)
- [Service Configuration](./service-configuration.md)
- [Environment Variables](./environment-variables.md)
