# Skill: Configure Shared Settings in Solace Agent Mesh

## Skill ID
`configure-shared-settings`

## Description
Manage and configure shared settings across multiple agents and gateways using `shared_config.yaml` files. This skill covers broker connections, LLM model configurations, service definitions, and multi-environment setups using YAML anchors and references.

## Prerequisites
- Initialized Agent Mesh project (see `skill-initialize-project`)
- Understanding of YAML syntax and anchors
- Access to broker and LLM service credentials
- Text editor or IDE

## Related Skills
- `initialize-agent-mesh-project` - Initial project setup
- `create-and-manage-agents` - Agent configuration that references shared settings
- `create-and-manage-gateways` - Gateway configuration that references shared settings

---

## Why Use This Skill?

**Business Value:**
- **Consistency**: Single source of truth for all configurations
- **Efficiency**: Update once, apply everywhere
- **Reduced Errors**: Eliminate configuration drift across components
- **Cost Control**: Centralized API key and resource management
- **Faster Deployment**: Quick environment switching (dev/staging/prod)

**Technical Benefits:**
- DRY principle (Don't Repeat Yourself)
- Environment-based configuration
- YAML anchors for reusability
- Centralized credential management
- Easy multi-environment support

## When to Use This Skill?

**Use This Skill When:**
- ✅ Managing multiple agents or gateways
- ✅ Setting up multi-environment deployments
- ✅ Standardizing configurations across team
- ✅ Switching between different LLM providers
- ✅ Managing multiple broker connections
- ✅ Updating shared settings (API keys, endpoints)

**Skip This Skill When:**
- ❌ Working with single-agent prototype
- ❌ All settings are agent-specific
- ❌ Using default configurations only

**Decision Points:**
- **Multiple environments?** → Create separate shared_config files per environment
- **Multiple LLM providers?** → Define multiple model anchors
- **Team collaboration?** → Use shared_config with environment variables
- **Frequent config changes?** → Centralize in shared_config for easy updates

---

## Core Concepts

### What is Shared Configuration?

The `shared_config.yaml` file is a centralized configuration hub that defines reusable settings for:

1. **Broker Connections**: Event mesh connectivity parameters
2. **LLM Models**: Language model endpoints and configurations
3. **Service Definitions**: Session storage, artifact management, and data tools
4. **Environment Variables**: Parameterized configuration using `${VAR_NAME}` syntax

### Why Use Shared Configuration?

**Benefits:**
- **DRY Principle**: Define once, reference everywhere
- **Consistency**: All components use the same base configuration
- **Maintainability**: Update settings in one place
- **Environment Management**: Easy switching between dev/staging/production
- **Security**: Centralized credential management

### YAML Anchors and References

Shared configuration uses YAML anchors (`&anchor_name`) to create reusable blocks:

```yaml
shared_config:
  - broker_connection: &broker_connection
      broker_url: ws://localhost:8008
      # ... other settings
```

Reference these anchors in agent/gateway files:

```yaml
broker:
  <<: *broker_connection
```

---

## Configuration File Structure

### Complete Template

```yaml
shared_config:
  # Broker Connection Configuration
  - broker_connection: &broker_connection
      dev_mode: ${SOLACE_DEV_MODE, false}
      broker_url: ${SOLACE_BROKER_URL, ws://localhost:8008}
      broker_username: ${SOLACE_BROKER_USERNAME, default}
      broker_password: ${SOLACE_BROKER_PASSWORD, default}
      broker_vpn: ${SOLACE_BROKER_VPN, default}
      temporary_queue: ${USE_TEMPORARY_QUEUES, true}
      max_connection_retries: -1

  # LLM Model Configurations
  - models:
      planning: &planning_model
        model: ${LLM_SERVICE_PLANNING_MODEL_NAME}
        api_base: ${LLM_SERVICE_ENDPOINT}
        api_key: ${LLM_SERVICE_API_KEY}
        parallel_tool_calls: true
        cache_strategy: "5m"
        max_tokens: 16000
        temperature: 0.1
      
      general: &general_model
        model: ${LLM_SERVICE_GENERAL_MODEL_NAME}
        api_base: ${LLM_SERVICE_ENDPOINT}
        api_key: ${LLM_SERVICE_API_KEY}
      
      image_gen: &image_gen_model
        model: ${IMAGE_GEN_MODEL_NAME, dall-e-3}
        api_base: ${LLM_SERVICE_ENDPOINT}
        api_key: ${LLM_SERVICE_API_KEY}
      
      multimodal: &multimodal_model
        model: ${MULTIMODAL_MODEL_NAME, gemini-1.5-flash}

  # Service Configurations
  - services:
      session_service: &default_session_service
        type: "sql"
        database_url: "${DATABASE_URL, sqlite:///session.db}"
        default_behavior: "PERSISTENT"
      
      artifact_service: &default_artifact_service
        type: "filesystem"
        base_path: "${ARTIFACT_BASE_PATH, /tmp/samv2}"
        artifact_scope: namespace
      
      data_tools_config: &default_data_tools_config
        sqlite_memory_threshold_mb: 100
        max_result_preview_rows: 50
        max_result_preview_bytes: 4096
```

---

## Step-by-Step Configuration

### Step 1: Locate Shared Configuration File

After initialization, find your shared config:

```bash
ls configs/shared_config.yaml
```

### Step 2: Edit Broker Configuration

Open `configs/shared_config.yaml` and configure broker settings:

```yaml
shared_config:
  - broker_connection: &broker_connection
      # Use dev mode for local testing (no external broker needed)
      dev_mode: ${SOLACE_DEV_MODE, false}
      
      # Broker URL (ws:// for plain, wss:// for TLS)
      broker_url: ${SOLACE_BROKER_URL, ws://localhost:8008}
      
      # Authentication credentials
      broker_username: ${SOLACE_BROKER_USERNAME, default}
      broker_password: ${SOLACE_BROKER_PASSWORD, default}
      
      # Message VPN name
      broker_vpn: ${SOLACE_BROKER_VPN, default}
      
      # Queue configuration
      temporary_queue: ${USE_TEMPORARY_QUEUES, true}
      
      # Connection retry behavior (-1 = retry forever)
      max_connection_retries: -1
```

**Environment Variables (.env):**
```bash
SOLACE_DEV_MODE=false
SOLACE_BROKER_URL=ws://localhost:8008
SOLACE_BROKER_USERNAME=default
SOLACE_BROKER_PASSWORD=default
SOLACE_BROKER_VPN=default
USE_TEMPORARY_QUEUES=true
```

### Step 3: Configure LLM Models

Define your language models:

```yaml
  - models:
      # Planning model for complex reasoning
      planning: &planning_model
        model: ${LLM_SERVICE_PLANNING_MODEL_NAME}
        api_base: ${LLM_SERVICE_ENDPOINT}
        api_key: ${LLM_SERVICE_API_KEY}
        parallel_tool_calls: true
        cache_strategy: "5m"
        max_tokens: 16000
        temperature: 0.1
      
      # General purpose model
      general: &general_model
        model: ${LLM_SERVICE_GENERAL_MODEL_NAME}
        api_base: ${LLM_SERVICE_ENDPOINT}
        api_key: ${LLM_SERVICE_API_KEY}
        temperature: 0.7
```

**Environment Variables (.env):**
```bash
LLM_SERVICE_ENDPOINT=https://api.openai.com/v1
LLM_SERVICE_API_KEY=sk-your-api-key
LLM_SERVICE_PLANNING_MODEL_NAME=gpt-4
LLM_SERVICE_GENERAL_MODEL_NAME=gpt-3.5-turbo
```

### Step 4: Configure Services

Set up session and artifact storage:

```yaml
  - services:
      # Session storage configuration
      session_service: &default_session_service
        type: "sql"
        database_url: "${DATABASE_URL, sqlite:///session.db}"
        default_behavior: "PERSISTENT"
      
      # Artifact storage configuration
      artifact_service: &default_artifact_service
        type: "filesystem"
        base_path: "${ARTIFACT_BASE_PATH, /tmp/samv2}"
        artifact_scope: namespace
```

**Environment Variables (.env):**
```bash
DATABASE_URL=sqlite:///session.db
ARTIFACT_BASE_PATH=/tmp/samv2
```

### Step 5: Reference in Agent Configuration

In your agent YAML files (e.g., `configs/agents/my_agent.yaml`):

```yaml
apps:
  - name: my-agent
    broker:
      <<: *broker_connection
    
    app_config:
      model: *planning_model
      session_service: *default_session_service
      artifact_service: *default_artifact_service
```

---

## Common Configuration Patterns

### Pattern 1: Multiple Broker Connections

**Use Case:** Connect to different brokers for different environments

```yaml
shared_config:
  # Development broker
  - broker_connection_dev: &broker_connection_dev
      dev_mode: true
      broker_url: ws://localhost:8008
      broker_username: dev-user
      broker_password: dev-pass
      broker_vpn: dev-vpn
  
  # Production broker
  - broker_connection_prod: &broker_connection_prod
      dev_mode: false
      broker_url: wss://prod-broker.example.com:443
      broker_username: ${PROD_BROKER_USERNAME}
      broker_password: ${PROD_BROKER_PASSWORD}
      broker_vpn: production-vpn
      temporary_queue: false
```

**Usage in Agent:**
```yaml
# Development agent
broker:
  <<: *broker_connection_dev

# Production agent
broker:
  <<: *broker_connection_prod
```

---

### Pattern 2: Multiple LLM Providers

**Use Case:** Use different providers for different models

```yaml
  - models:
      # OpenAI models
      openai_planning: &openai_planning
        model: gpt-4
        api_base: https://api.openai.com/v1
        api_key: ${OPENAI_API_KEY}
      
      # Anthropic models
      anthropic_general: &anthropic_general
        model: claude-3-sonnet-20240229
        api_base: https://api.anthropic.com
        api_key: ${ANTHROPIC_API_KEY}
      
      # Google Gemini models
      gemini_multimodal: &gemini_multimodal
        model: gemini-1.5-pro
        # Gemini uses default configuration
```

**Environment Variables:**
```bash
OPENAI_API_KEY=sk-openai-key
ANTHROPIC_API_KEY=sk-ant-key
```

---

### Pattern 3: Environment-Specific Configurations

**Use Case:** Separate configurations for dev, staging, production

**Directory Structure:**
```
configs/
├── shared_config.yaml          # Base configuration
├── shared_config_dev.yaml      # Development overrides
├── shared_config_staging.yaml  # Staging overrides
└── shared_config_prod.yaml     # Production overrides
```

**Base Configuration (shared_config.yaml):**
```yaml
shared_config:
  - broker_connection: &broker_connection
      broker_url: ${SOLACE_BROKER_URL}
      broker_username: ${SOLACE_BROKER_USERNAME}
      broker_password: ${SOLACE_BROKER_PASSWORD}
      broker_vpn: ${SOLACE_BROKER_VPN}
```

**Development Override (shared_config_dev.yaml):**
```yaml
shared_config:
  - broker_connection: &broker_connection
      dev_mode: true
      broker_url: ws://localhost:8008
      broker_username: dev-user
      broker_password: dev-pass
      broker_vpn: dev-vpn
```

**Production Override (shared_config_prod.yaml):**
```yaml
shared_config:
  - broker_connection: &broker_connection
      dev_mode: false
      broker_url: wss://prod-broker.example.com:443
      broker_username: ${PROD_BROKER_USERNAME}
      broker_password: ${PROD_BROKER_PASSWORD}
      broker_vpn: production-vpn
      temporary_queue: false
      max_connection_retries: 10
```

**Usage:**
```bash
# Development
sam run configs/agents/ configs/shared_config_dev.yaml

# Production
sam run configs/agents/ configs/shared_config_prod.yaml
```

---

### Pattern 4: Advanced Model Configuration

**Use Case:** Fine-tune model behavior for specific use cases

```yaml
  - models:
      # High-precision planning model
      planning_precise: &planning_precise
        model: gpt-4
        api_base: ${LLM_SERVICE_ENDPOINT}
        api_key: ${LLM_SERVICE_API_KEY}
        parallel_tool_calls: true
        cache_strategy: "1h"
        max_tokens: 8000
        temperature: 0.0  # Deterministic
        top_p: 0.1
      
      # Creative content generation model
      creative_general: &creative_general
        model: gpt-4
        api_base: ${LLM_SERVICE_ENDPOINT}
        api_key: ${LLM_SERVICE_API_KEY}
        max_tokens: 4000
        temperature: 0.9  # More creative
        top_p: 0.95
      
      # Fast response model
      fast_response: &fast_response
        model: gpt-3.5-turbo
        api_base: ${LLM_SERVICE_ENDPOINT}
        api_key: ${LLM_SERVICE_API_KEY}
        max_tokens: 1000
        temperature: 0.5
```

---

## Configuration Reference

### Broker Connection Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `dev_mode` | boolean | Use in-memory broker for testing | `false` |
| `broker_url` | string | Broker endpoint URL (ws:// or wss://) | `ws://localhost:8008` |
| `broker_username` | string | Authentication username | `default` |
| `broker_password` | string | Authentication password | `default` |
| `broker_vpn` | string | Message VPN name | `default` |
| `temporary_queue` | boolean | Use temporary queues (true) or durable (false) | `true` |
| `max_connection_retries` | integer | Max retry attempts (-1 = infinite) | `-1` |

### LLM Model Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `model` | string | Model identifier (e.g., `gpt-4`, `claude-3-opus`) | Required |
| `api_base` | string | API endpoint URL | Provider-specific |
| `api_key` | string | Authentication API key | Required |
| `parallel_tool_calls` | boolean | Enable parallel tool execution | `false` |
| `cache_strategy` | string | Prompt caching: `none`, `5m`, `1h` | `none` |
| `max_tokens` | integer | Maximum response tokens | Model-specific |
| `temperature` | float | Randomness (0.0-2.0) | `1.0` |
| `top_p` | float | Nucleus sampling (0.0-1.0) | `1.0` |

### Session Service Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `type` | string | Storage backend: `memory`, `sql` | `memory` |
| `database_url` | string | Database connection string | Required for SQL |
| `default_behavior` | string | `PERSISTENT` or `RUN_BASED` | `PERSISTENT` |

### Artifact Service Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `type` | string | Storage type: `memory`, `filesystem`, `gcs` | `memory` |
| `base_path` | string | Base directory for filesystem storage | Required for filesystem |
| `bucket_name` | string | GCS bucket name | Required for GCS |
| `artifact_scope` | string | Scope: `namespace`, `app`, `custom` | `namespace` |

---

## Advanced Techniques

### Using Include Directives

Reference shared config from agent files:

```yaml
# In configs/agents/my_agent.yaml
shared_config: !include ../shared_config.yaml

apps:
  - name: my-agent
    broker:
      <<: *broker_connection
```

### Merging Multiple Configurations

Combine base and environment-specific configs:

```yaml
# Base configuration
shared_config: !include shared_config.yaml

# Environment-specific overrides
environment_config: !include shared_config_${ENVIRONMENT}.yaml
```

### Dynamic Configuration with Environment Variables

Use environment variable substitution with defaults:

```yaml
broker_connection: &broker_connection
  # Syntax: ${VAR_NAME, default_value}
  broker_url: ${SOLACE_BROKER_URL, ws://localhost:8008}
  broker_username: ${SOLACE_BROKER_USERNAME, default}
  
  # Without default (required)
  broker_password: ${SOLACE_BROKER_PASSWORD}
```

### Conditional Configuration

Use different anchors based on environment:

```yaml
shared_config:
  - dev_broker: &dev_broker
      dev_mode: true
  
  - prod_broker: &prod_broker
      dev_mode: false
      broker_url: wss://prod.example.com:443

# In agent file, choose based on environment
broker:
  <<: *${BROKER_TYPE}_broker  # Expands to *dev_broker or *prod_broker
```

---

## Troubleshooting

### Issue: "Anchor not found" error

**Symptoms:**
```
Error: Unknown anchor 'broker_connection'
```

**Solutions:**

1. **Verify anchor definition:**
```yaml
# Must have & before anchor name
- broker_connection: &broker_connection
```

2. **Check file loading order:**
```bash
# Ensure shared_config is loaded first
sam run configs/shared_config.yaml configs/agents/
```

3. **Validate YAML syntax:**
```bash
python -c "import yaml; yaml.safe_load(open('configs/shared_config.yaml'))"
```

---

### Issue: Environment variables not substituted

**Symptoms:**
```
broker_url: ${SOLACE_BROKER_URL}  # Literal string, not substituted
```

**Solutions:**

1. **Verify .env file is loaded:**
```bash
sam run  # Loads .env by default
sam run --system-env  # Uses system environment only
```

2. **Check environment variable exists:**
```bash
echo $SOLACE_BROKER_URL
```

3. **Use default values:**
```yaml
broker_url: ${SOLACE_BROKER_URL, ws://localhost:8008}
```

---

### Issue: Configuration not taking effect

**Symptoms:**
Agent uses old configuration after changes

**Solutions:**

1. **Restart the application:**
```bash
# Stop running agents
pkill -f "sam run"

# Start fresh
sam run
```

2. **Clear cached configurations:**
```bash
rm -rf __pycache__
rm -rf .sam_cache
```

3. **Verify file is being loaded:**
```bash
# Add debug logging
sam run --verbose
```

---

### Issue: Multiple shared configs conflict

**Symptoms:**
```
Error: Duplicate anchor 'broker_connection'
```

**Solutions:**

1. **Use unique anchor names:**
```yaml
# shared_config_dev.yaml
- broker_connection_dev: &broker_connection_dev

# shared_config_prod.yaml
- broker_connection_prod: &broker_connection_prod
```

2. **Load only one shared config:**
```bash
sam run configs/shared_config_${ENVIRONMENT}.yaml configs/agents/
```

---

## Best Practices

### Organization

1. **Use descriptive anchor names:**
   ```yaml
   Good: &production_broker, &openai_gpt4_planning
   Bad: &broker1, &model_a
   ```

2. **Group related configurations:**
   ```yaml
   shared_config:
     - brokers:
         dev: &dev_broker
         prod: &prod_broker
     - models:
         planning: &planning_model
         general: &general_model
   ```

3. **Document configuration choices:**
   ```yaml
   # Planning model: GPT-4 for complex reasoning
   # Temperature: 0.1 for deterministic outputs
   planning: &planning_model
     model: gpt-4
     temperature: 0.1
   ```

### Security

1. **Never commit sensitive values:**
   ```yaml
   # Good: Use environment variables
   api_key: ${LLM_SERVICE_API_KEY}
   
   # Bad: Hardcoded secrets
   api_key: sk-actual-key-here
   ```

2. **Use separate credentials per environment:**
   ```bash
   # .env.dev
   LLM_SERVICE_API_KEY=sk-dev-key
   
   # .env.prod
   LLM_SERVICE_API_KEY=sk-prod-key
   ```

3. **Restrict file permissions:**
   ```bash
   chmod 600 .env
   chmod 600 configs/shared_config.yaml
   ```

### Maintainability

1. **Provide sensible defaults:**
   ```yaml
   broker_url: ${SOLACE_BROKER_URL, ws://localhost:8008}
   max_tokens: ${MAX_TOKENS, 4000}
   ```

2. **Version control configuration templates:**
   ```bash
   git add configs/shared_config.yaml.example
   git add .env.example
   ```

3. **Document required environment variables:**
   ```markdown
   # README.md
   ## Required Environment Variables
   - SOLACE_BROKER_URL: Broker endpoint
   - LLM_SERVICE_API_KEY: LLM provider API key
   ```

### Performance

1. **Use appropriate cache strategies:**
   ```yaml
   # Long-running agents: 1h cache
   planning: &planning_model
     cache_strategy: "1h"
   
   # Short-lived tasks: 5m cache
   general: &general_model
     cache_strategy: "5m"
   ```

2. **Set reasonable token limits:**
   ```yaml
   # Prevent excessive costs
   max_tokens: 4000
   ```

3. **Choose appropriate storage backends:**
   ```yaml
   # Development: Fast, no persistence
   session_service:
     type: memory
   
   # Production: Persistent, scalable
   session_service:
     type: sql
     database_url: postgresql://...
   ```

---

## Validation Checklist

After configuring shared settings:

- [ ] YAML syntax is valid (no parsing errors)
- [ ] All anchors are properly defined with `&`
- [ ] Environment variables are set in `.env`
- [ ] Sensitive values use environment variables
- [ ] Default values provided where appropriate
- [ ] Broker connection parameters are correct
- [ ] LLM API keys are valid
- [ ] Storage paths exist and are writable
- [ ] Configuration loads without errors (`sam run --help`)
- [ ] Agents can reference shared configuration

---

## Next Steps

After configuring shared settings:

1. **Test Configuration**: Run `sam run` to verify settings
2. **Create Agents**: Use `skill-create-and-manage-agents` with shared config
3. **Add Gateways**: Use `skill-create-and-manage-gateways` with shared config
4. **Monitor Performance**: Adjust model parameters based on usage
5. **Scale Up**: Add environment-specific configurations for production

---

## Additional Resources

- [Configuration Documentation](https://docs.cline.bot/installing-and-configuring/configurations)
- [LLM Configuration Guide](https://docs.cline.bot/installing-and-configuring/large_language_models)
- [Session Storage Guide](https://docs.cline.bot/installing-and-configuring/session-storage)
- [Artifact Storage Guide](https://docs.cline.bot/installing-and-configuring/artifact-storage)
- [YAML Specification](https://yaml.org/spec/)