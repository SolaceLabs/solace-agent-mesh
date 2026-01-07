# Skill: Initialize Solace Agent Mesh Project

## Skill ID
`initialize-agent-mesh-project`

## Description
Initialize and configure a new Solace Agent Mesh project with proper broker connections, LLM services, session storage, and artifact management. This skill covers the complete project setup process from scratch.

## Prerequisites
- Python 3.10.16 or higher installed
- pip or uv package manager available
- Solace Agent Mesh CLI installed (`pip install solace-agent-mesh`)
- LLM API key from a supported provider (OpenAI, Anthropic, Google, etc.)
- Access to a Solace PubSub+ broker (or ability to run local container)

## Related Skills
- `configure-shared-settings` - Manage shared configuration files
- `run-and-debug-projects` - Run and debug Agent Mesh applications
- `create-and-manage-agents` - Create agents after project initialization

---

## Why Use This Skill?

**Business Value:**
- **Rapid Prototyping**: Get from idea to working prototype in minutes
- **Standardization**: Ensure consistent project structure across teams
- **Best Practices**: Built-in security and scalability patterns
- **Reduced Errors**: Automated setup prevents common configuration mistakes
- **Cost Efficiency**: Avoid expensive trial-and-error in production

**Technical Benefits:**
- Automated directory structure creation
- Pre-configured broker and LLM connections
- Environment-based configuration management
- Built-in storage service setup
- Ready-to-run orchestrator agent

## When to Use This Skill?

**Use This Skill When:**
- ✅ Starting a new Agent Mesh project from scratch
- ✅ Creating proof-of-concept or MVP
- ✅ Setting up development, staging, or production environments
- ✅ Onboarding new team members to Agent Mesh
- ✅ Standardizing project structure across organization

**Skip This Skill When:**
- ❌ Adding to existing Agent Mesh project (use `add agent` or `add gateway` instead)
- ❌ Just exploring documentation (no setup needed)
- ❌ Working with pre-configured project templates

**Decision Points:**
- **New to Agent Mesh?** → Use browser GUI method (easiest)
- **Automating setup?** → Use non-interactive CLI method
- **Team environment?** → Use interactive CLI for flexibility
- **CI/CD pipeline?** → Use non-interactive with environment variables

---

## Core Concepts

### What is Project Initialization?

Project initialization creates the foundational structure for an Agent Mesh application. The `sam init` command sets up:

1. **Directory Structure**: Creates `configs/` directories for agents, gateways, and shared configurations
2. **Broker Connection**: Configures connection to Solace event mesh (the communication backbone)
3. **LLM Configuration**: Sets up language model endpoints and API keys
4. **Service Configuration**: Configures session storage and artifact management
5. **Environment Files**: Creates `.env` file for sensitive configuration
6. **Main Orchestrator**: Creates the primary agent that coordinates the system

### Initialization Modes

The CLI offers three initialization approaches:

- **Interactive CLI Mode**: Terminal-based prompts (default)
- **Browser GUI Mode**: Web-based configuration portal at `http://127.0.0.1:5002`
- **Non-Interactive Mode**: Automated setup using command-line flags

### Broker Types

Agent Mesh supports three broker deployment options:

1. **Existing Solace Broker** (`solace`): Connect to an existing PubSub+ broker
2. **Local Container** (`container`): Automatically start a local broker in Docker/Podman
3. **Dev Mode** (`dev`): Use in-memory broker for testing (no external dependencies)

---

## Step-by-Step Instructions

### Method 1: Interactive Browser-Based Setup (Recommended)

This is the easiest method for new users, providing a visual interface for configuration.

#### Step 1: Create Project Directory

```bash
mkdir my-agent-mesh-project
cd my-agent-mesh-project
```

#### Step 2: Launch Browser-Based Initialization

```bash
sam init --gui
```

**Expected Output:**
```
Starting configuration portal...
Configuration portal available at: http://127.0.0.1:5002
Opening browser...
```

#### Step 3: Configure in Browser

The browser interface will guide you through:

1. **Broker Configuration**
   - Select broker type (Solace/Container/Dev)
   - Enter connection details if using existing broker
   - Choose container engine (Docker/Podman) if using container

2. **LLM Configuration**
   - Enter LLM service endpoint URL
   - Provide API key
   - Select planning model (e.g., `gpt-4`, `claude-3-opus`)
   - Select general model (e.g., `gpt-3.5-turbo`, `claude-3-sonnet`)

3. **Project Settings**
   - Set namespace (e.g., `myorg/dev`)
   - Configure agent name
   - Enable/disable streaming support

4. **Storage Configuration**
   - Choose session service type (memory/SQL)
   - Choose artifact service type (memory/filesystem/GCS)
   - Configure storage paths

5. **Optional Components**
   - Add Web UI gateway
   - Configure built-in tools
   - Set up agent discovery

#### Step 4: Complete Setup

Click "Initialize Project" in the browser. The system will:
- Create directory structure
- Generate configuration files
- Create `.env` file with your settings
- Set up the main orchestrator agent

**Success Indicators:**
- Configuration files created in `configs/` directory
- `.env` file created with environment variables
- Terminal shows "Project initialized successfully"

---

### Method 2: Interactive CLI Mode

For users who prefer terminal-based workflows.

#### Step 1: Start Interactive Setup

```bash
sam init
```

#### Step 2: Answer Prompts

The CLI will ask a series of questions:

**Broker Configuration:**
```
? Select broker type:
  1. Existing Solace broker
  2. New local container
  3. Dev mode (in-memory)
```

**For Existing Broker:**
```
? Broker URL: ws://your-broker-url:8008
? VPN Name: default
? Username: your-username
? Password: ********
```

**For Container:**
```
? Container engine:
  1. Docker
  2. Podman
```

**LLM Configuration:**
```
? LLM Service Endpoint: https://api.openai.com/v1
? LLM API Key: sk-****
? Planning Model Name: gpt-4
? General Model Name: gpt-3.5-turbo
```

**Project Settings:**
```
? Namespace: myorg/dev
? Agent Name: main-orchestrator
? Enable streaming support? (Y/n): Y
```

**Storage Configuration:**
```
? Session service type:
  1. Memory
  2. SQL (SQLite/PostgreSQL)
? Artifact service type:
  1. Memory
  2. Filesystem
  3. Google Cloud Storage
```

#### Step 3: Verify Setup

```bash
ls -la configs/
```

**Expected Structure:**
```
configs/
├── agents/
│   └── main_orchestrator.yaml
├── gateways/
└── shared_config.yaml
.env
```

---

### Method 3: Non-Interactive Mode (Automation)

For CI/CD pipelines and automated deployments.

#### Complete Example with All Options

```bash
sam init \
  --skip \
  --namespace "myorg/production" \
  --broker-type solace \
  --broker-url "wss://production-broker.example.com:443" \
  --broker-vpn "production-vpn" \
  --broker-username "agent-mesh-user" \
  --broker-password "${BROKER_PASSWORD}" \
  --llm-service-endpoint "https://api.openai.com/v1" \
  --llm-service-api-key "${OPENAI_API_KEY}" \
  --llm-service-planning-model-name "gpt-4" \
  --llm-service-general-model-name "gpt-3.5-turbo" \
  --agent-name "production-orchestrator" \
  --supports-streaming \
  --session-service-type sql \
  --artifact-service-type filesystem \
  --artifact-service-base-path "/var/lib/agent-mesh/artifacts" \
  --enable-builtin-artifact-tools \
  --enable-builtin-data-tools \
  --add-webui-gateway \
  --webui-fastapi-port 8080
```

#### Minimal Dev Mode Example

```bash
sam init \
  --skip \
  --dev-mode \
  --llm-service-endpoint "https://api.openai.com/v1" \
  --llm-service-api-key "${OPENAI_API_KEY}" \
  --llm-service-planning-model-name "gpt-4" \
  --llm-service-general-model-name "gpt-3.5-turbo"
```

---

## Common Configuration Patterns

### Pattern 1: Local Development Setup

**Use Case:** Quick local testing with minimal dependencies

```bash
sam init --gui
```

**Configuration Choices:**
- Broker Type: Dev Mode
- Session Service: Memory
- Artifact Service: Memory
- Add Web UI: Yes

**Advantages:**
- No external dependencies
- Fast startup
- Easy cleanup

**Limitations:**
- No persistence across restarts
- Single machine only

---

### Pattern 2: Production Setup with PostgreSQL

**Use Case:** Production deployment with persistent storage

```bash
sam init \
  --skip \
  --namespace "myorg/production" \
  --broker-type solace \
  --broker-url "${SOLACE_BROKER_URL}" \
  --broker-vpn "production-vpn" \
  --broker-username "${SOLACE_USERNAME}" \
  --broker-password "${SOLACE_PASSWORD}" \
  --llm-service-endpoint "${LLM_ENDPOINT}" \
  --llm-service-api-key "${LLM_API_KEY}" \
  --llm-service-planning-model-name "gpt-4" \
  --llm-service-general-model-name "gpt-3.5-turbo" \
  --session-service-type sql \
  --artifact-service-type filesystem \
  --artifact-service-base-path "/var/lib/agent-mesh/artifacts"
```

**Environment Variables (.env):**
```bash
# Broker Configuration
SOLACE_BROKER_URL=wss://production-broker.example.com:443
SOLACE_BROKER_VPN=production-vpn
SOLACE_USERNAME=agent-mesh-user
SOLACE_PASSWORD=secure-password

# LLM Configuration
LLM_ENDPOINT=https://api.openai.com/v1
LLM_API_KEY=sk-your-api-key

# Database Configuration
DATABASE_URL=postgresql://user:password@db-host:5432/agent_mesh
```

---

### Pattern 3: Multi-Environment Setup

**Use Case:** Separate dev, staging, and production configurations

**Directory Structure:**
```
my-project/
├── .env.dev
├── .env.staging
├── .env.production
├── configs/
│   ├── shared_config.yaml
│   ├── shared_config_dev.yaml
│   ├── shared_config_staging.yaml
│   └── shared_config_production.yaml
```

**Initialize for Each Environment:**

```bash
# Development
sam init --skip --dev-mode --namespace "myorg/dev" \
  --llm-service-api-key "${DEV_API_KEY}"

# Staging
sam init --skip --broker-type container --namespace "myorg/staging" \
  --llm-service-api-key "${STAGING_API_KEY}"

# Production
sam init --skip --broker-type solace --namespace "myorg/production" \
  --broker-url "${PROD_BROKER_URL}" \
  --llm-service-api-key "${PROD_API_KEY}"
```

---

## Configuration Reference

### Complete CLI Options

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `--gui` | flag | Launch browser-based configuration | false |
| `--skip` | flag | Non-interactive mode | false |
| `--namespace` | string | Project namespace (e.g., `myorg/dev`) | - |
| `--broker-type` | string | Broker type: `1/solace`, `2/container`, `3/dev` | - |
| `--broker-url` | string | Solace broker URL | `ws://localhost:8008` |
| `--broker-vpn` | string | Solace broker VPN name | `default` |
| `--broker-username` | string | Solace broker username | `default` |
| `--broker-password` | string | Solace broker password | `default` |
| `--container-engine` | string | Container engine: `docker`, `podman` | `docker` |
| `--dev-mode` | flag | Shortcut for dev broker type | false |
| `--llm-service-endpoint` | string | LLM service endpoint URL | - |
| `--llm-service-api-key` | string | LLM service API key | - |
| `--llm-service-planning-model-name` | string | Planning model identifier | - |
| `--llm-service-general-model-name` | string | General model identifier | - |
| `--agent-name` | string | Main orchestrator agent name | - |
| `--supports-streaming` | flag | Enable streaming support | false |
| `--session-service-type` | string | Session service: `memory`, `sql` | `memory` |
| `--session-service-behavior` | string | Session behavior: `PERSISTENT`, `RUN_BASED` | `PERSISTENT` |
| `--artifact-service-type` | string | Artifact service: `memory`, `filesystem`, `gcs` | `memory` |
| `--artifact-service-base-path` | string | Filesystem artifact base path | - |
| `--artifact-service-scope` | string | Artifact scope: `namespace`, `app`, `custom` | `namespace` |
| `--enable-builtin-artifact-tools` | flag | Enable built-in artifact tools | false |
| `--enable-builtin-data-tools` | flag | Enable built-in data analysis tools | false |
| `--add-webui-gateway` | flag | Add Web UI gateway | false |
| `--webui-fastapi-port` | integer | Web UI port | `8000` |

### Environment Variables

Key environment variables created in `.env`:

```bash
# Namespace
NAMESPACE=myorg/dev

# Broker Configuration
SOLACE_BROKER_URL=ws://localhost:8008
SOLACE_BROKER_VPN=default
SOLACE_BROKER_USERNAME=default
SOLACE_BROKER_PASSWORD=default
SOLACE_DEV_MODE=false

# LLM Configuration
LLM_SERVICE_ENDPOINT=https://api.openai.com/v1
LLM_SERVICE_API_KEY=sk-your-key
LLM_SERVICE_PLANNING_MODEL_NAME=gpt-4
LLM_SERVICE_GENERAL_MODEL_NAME=gpt-3.5-turbo

# Storage Configuration
DATABASE_URL=sqlite:///session.db
```

---

## Troubleshooting

### Issue: "Connection refused" when using container broker

**Symptoms:**
```
Error: Failed to connect to broker at ws://localhost:8008
```

**Solutions:**

1. **Verify container is running:**
```bash
docker ps | grep solace
```

2. **Check container logs:**
```bash
docker logs solace-pubsub
```

3. **Restart container:**
```bash
docker restart solace-pubsub
```

4. **Verify port mapping:**
```bash
docker port solace-pubsub
```

---

### Issue: "Invalid API key" for LLM service

**Symptoms:**
```
Error: Authentication failed with LLM service
```

**Solutions:**

1. **Verify API key format:**
```bash
echo $LLM_SERVICE_API_KEY
```

2. **Test API key directly:**
```bash
curl -H "Authorization: Bearer $LLM_SERVICE_API_KEY" \
  https://api.openai.com/v1/models
```

3. **Check environment variable loading:**
```bash
sam run --help  # Shows if .env is loaded
```

4. **Regenerate API key** from provider dashboard

---

### Issue: "Permission denied" for artifact storage

**Symptoms:**
```
Error: Cannot write to /var/lib/agent-mesh/artifacts
```

**Solutions:**

1. **Create directory with proper permissions:**
```bash
sudo mkdir -p /var/lib/agent-mesh/artifacts
sudo chown $USER:$USER /var/lib/agent-mesh/artifacts
```

2. **Use user-writable path:**
```bash
sam init --artifact-service-base-path "$HOME/.agent-mesh/artifacts"
```

3. **Verify directory permissions:**
```bash
ls -ld /var/lib/agent-mesh/artifacts
```

---

### Issue: Database connection fails

**Symptoms:**
```
Error: Could not connect to database at postgresql://...
```

**Solutions:**

1. **Test database connection:**
```bash
psql $DATABASE_URL -c "SELECT 1;"
```

2. **Verify database exists:**
```bash
psql -h hostname -U username -l
```

3. **Check network connectivity:**
```bash
nc -zv db-hostname 5432
```

4. **Use SQLite for testing:**
```bash
# In .env file
DATABASE_URL=sqlite:///./session.db
```

---

## Validation Checklist

After initialization, verify your setup:

- [ ] Directory structure created (`configs/agents/`, `configs/gateways/`)
- [ ] `.env` file exists with all required variables
- [ ] `shared_config.yaml` created with broker and model configuration
- [ ] Main orchestrator agent configuration exists
- [ ] Can connect to broker (test with `sam run`)
- [ ] LLM API key is valid (test with simple query)
- [ ] Session storage is accessible
- [ ] Artifact storage directory is writable
- [ ] No errors in initialization output

---

## Best Practices

### Security

1. **Never commit `.env` files** to version control
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Use environment-specific API keys**
   - Separate keys for dev/staging/production
   - Rotate keys regularly

3. **Secure broker credentials**
   - Use strong passwords
   - Enable TLS for production (`wss://` instead of `ws://`)

### Organization

1. **Use meaningful namespaces**
   ```
   Good: mycompany/production, mycompany/dev
   Bad: test, project1
   ```

2. **Document your configuration**
   - Add comments to YAML files
   - Maintain README with setup instructions

3. **Version control configuration templates**
   - Commit `.env.example` with dummy values
   - Document required environment variables

### Performance

1. **Choose appropriate storage backends**
   - Dev: Memory (fast, no persistence)
   - Staging: SQLite (simple, file-based)
   - Production: PostgreSQL (scalable, reliable)

2. **Configure session behavior**
   - `PERSISTENT`: For chatbots, customer service
   - `RUN_BASED`: For batch processing, one-off tasks

3. **Set reasonable artifact scope**
   - `namespace`: Share artifacts across all agents
   - `app`: Isolate artifacts per agent

---

## Next Steps

After successful initialization:

1. **Verify Setup**: Run `sam run` to test the configuration
2. **Add Agents**: Use `skill-create-and-manage-agents` to add specialized agents
3. **Configure Tools**: Use `skill-configure-agent-tools` to add capabilities
4. **Add Gateways**: Use `skill-create-and-manage-gateways` for external interfaces
5. **Customize Configuration**: Use `skill-configure-shared-settings` for advanced setup

---

## Additional Resources

- [Official Installation Guide](https://docs.cline.bot/installing-and-configuring/installation)
- [Configuration Reference](https://docs.cline.bot/installing-and-configuring/configurations)
- [Broker Setup Guide](https://docs.solace.com/Get-Started/Getting-Started.htm)
- [LLM Provider Documentation](https://docs.litellm.ai/docs/providers)