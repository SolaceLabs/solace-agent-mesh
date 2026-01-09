# Skill: Run and Debug Solace Agent Mesh Projects

## Skill ID
`run-and-debug-projects`

## Description
Execute and debug Solace Agent Mesh applications with proper environment management, logging configuration, and troubleshooting techniques. This skill covers running complete applications, individual components, and debugging common issues.

## Prerequisites
- Initialized Agent Mesh project (see `skill-initialize-project`)
- Configured shared settings (see `skill-configure-shared-settings`)
- At least one agent or gateway configured
- Terminal access

## Related Skills
- `initialize-agent-mesh-project` - Project setup
- `configure-shared-settings` - Configuration management
- `create-and-manage-agents` - Agent creation and configuration

---

## Why Use This Skill?

**Business Value:**
- **Faster Time-to-Market**: Quickly validate and iterate on agent behavior
- **Reduced Downtime**: Proactive debugging prevents production issues
- **Cost Optimization**: Identify and fix resource-intensive operations
- **Quality Assurance**: Ensure agents work correctly before deployment
- **Operational Excellence**: Monitor and maintain healthy systems

**Technical Benefits:**
- Multiple execution modes (dev, staging, production)
- Comprehensive logging and debugging
- Performance monitoring
- Environment management
- Production deployment strategies

## When to Use This Skill?

**Use This Skill When:**
- ✅ Testing new agent configurations
- ✅ Debugging agent behavior or tool execution
- ✅ Deploying to production environments
- ✅ Monitoring system performance
- ✅ Troubleshooting connectivity issues
- ✅ Validating configuration changes

**Skip This Skill When:**
- ❌ Still designing agent architecture (use planning first)
- ❌ Writing custom tools (test tools separately first)
- ❌ Just reading documentation

**Decision Points:**
- **Development?** → Use dev mode with verbose logging
- **Testing?** → Run specific components in isolation
- **Production?** → Use systemd/Docker with monitoring
- **Debugging?** → Enable debug logging and trace execution
- **Performance issues?** → Use profiling and metrics

---

## Core Concepts

### What is Running Agent Mesh?

Running Agent Mesh means starting the application components (agents and gateways) that:

1. **Connect to Event Broker**: Establish communication channels
2. **Initialize Services**: Set up session storage, artifact management
3. **Load Tools**: Make capabilities available to agents
4. **Start Listening**: Begin processing messages and requests
5. **Enable Discovery**: Announce agent capabilities to the mesh

### Execution Modes

Agent Mesh supports several execution patterns:

- **Full Application**: Run all configured components
- **Selective Components**: Run specific agents or gateways
- **Development Mode**: Quick iteration with auto-reload
- **Production Mode**: Optimized for stability and performance

### Environment Management

The `sam run` command automatically loads environment variables from `.env` files, but you can override this behavior:

- **Default**: Loads `.env` file automatically
- **System Environment**: Use `--system-env` to skip `.env` loading
- **Custom Environment**: Set variables before running

---

## Step-by-Step Instructions

### Method 1: Run Complete Application

This is the standard way to run all configured components.

#### Step 1: Verify Configuration

```bash
# Check that configuration files exist
ls configs/agents/
ls configs/gateways/
ls configs/shared_config.yaml
```

#### Step 2: Run Application

```bash
sam run
```

**Expected Output:**
```
Loading environment from .env
Loading configuration from configs/
Starting agent: main-orchestrator
Starting gateway: webui-gateway
Connected to broker at ws://localhost:8008
Agent mesh is running...
Press Ctrl+C to stop
```

#### Step 3: Verify Components Started

Check logs for successful initialization:

```
[INFO] Agent 'main-orchestrator' initialized successfully
[INFO] Gateway 'webui-gateway' listening on port 8000
[INFO] Agent discovery enabled
[INFO] All components started
```

---

### Method 2: Run Specific Components

Run only selected configuration files.

#### Run Specific Agent

```bash
sam run configs/agents/my_agent.yaml
```

#### Run Multiple Specific Files

```bash
sam run configs/agents/agent1.yaml configs/agents/agent2.yaml configs/gateways/rest_gateway.yaml
```

#### Run All Files in Directory

```bash
sam run configs/agents/
```

#### Run with Shared Config

```bash
sam run configs/shared_config.yaml configs/agents/my_agent.yaml
```

---

### Method 3: Run with Environment Overrides

#### Use System Environment Variables

```bash
sam run --system-env
```

This skips loading `.env` and uses only system environment variables.

#### Set Variables Inline

```bash
NAMESPACE=myorg/test LLM_SERVICE_API_KEY=sk-test sam run
```

#### Use Different Environment File

```bash
# Load specific environment
export $(cat .env.production | xargs)
sam run --system-env
```

---

### Method 4: Run with Exclusions

Skip specific files while running a directory.

```bash
# Skip specific agent
sam run configs/agents/ --skip my_test_agent.yaml

# Skip multiple files
sam run configs/ --skip agent1.yaml --skip gateway1.yaml
```

---

## Common Run Patterns

### Pattern 1: Development Workflow

**Use Case:** Quick iteration during development

```bash
# Terminal 1: Run with dev configuration
sam run configs/shared_config_dev.yaml configs/agents/

# Terminal 2: Monitor logs
tail -f logs/agent-mesh.log

# Make changes to code/config, then restart
# Ctrl+C in Terminal 1, then sam run again
```

**Tips:**
- Use dev mode broker for faster startup
- Enable verbose logging
- Use memory-based storage for speed

---

### Pattern 2: Production Deployment

**Use Case:** Stable production environment

```bash
# Load production environment
export $(cat .env.production | xargs)

# Run with production config
sam run configs/shared_config_prod.yaml configs/agents/ configs/gateways/

# Or use systemd service (see below)
```

**Production Checklist:**
- [ ] Use persistent storage (PostgreSQL, filesystem)
- [ ] Enable TLS for broker connection
- [ ] Configure proper logging
- [ ] Set up monitoring
- [ ] Use durable queues

---

### Pattern 3: Testing Individual Components

**Use Case:** Test single agent in isolation

```bash
# Run only the agent being tested
sam run configs/agents/test_agent.yaml

# In another terminal, send test messages
# (using gateway or direct broker connection)
```

---

### Pattern 4: Multi-Environment Setup

**Use Case:** Switch between environments easily

```bash
# Development
sam run configs/shared_config_dev.yaml configs/agents/

# Staging
sam run configs/shared_config_staging.yaml configs/agents/

# Production
sam run configs/shared_config_prod.yaml configs/agents/
```

**Directory Structure:**
```
configs/
├── shared_config_dev.yaml
├── shared_config_staging.yaml
├── shared_config_prod.yaml
├── agents/
└── gateways/
```

---

## Debugging Techniques

### Enable Verbose Logging

Add logging configuration to see detailed output.

#### Create Logging Config

Create `configs/logging_config.yaml`:

```yaml
version: 1
disable_existing_loggers: false

formatters:
  detailed:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  simple:
    format: '%(levelname)s - %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: DEBUG
    formatter: detailed
    stream: ext://sys.stdout
  
  file:
    class: logging.FileHandler
    level: DEBUG
    formatter: detailed
    filename: logs/agent-mesh.log
    mode: a

loggers:
  solace_agent_mesh:
    level: DEBUG
    handlers: [console, file]
    propagate: false
  
  google.adk:
    level: INFO
    handlers: [console, file]
    propagate: false

root:
  level: INFO
  handlers: [console, file]
```

#### Use Logging Config

```bash
# Set environment variable
export LOGGING_CONFIG=configs/logging_config.yaml

# Run with logging
sam run
```

---

### Monitor Component Status

#### Check Running Processes

```bash
# Find Agent Mesh processes
ps aux | grep "sam run"

# Check specific agent
ps aux | grep "my_agent"
```

#### Monitor Resource Usage

```bash
# CPU and memory usage
top -p $(pgrep -f "sam run")

# Detailed process info
htop -p $(pgrep -f "sam run")
```

---

### Inspect Broker Connection

#### Verify Broker Connectivity

```bash
# Test broker connection
curl http://localhost:8080/health

# Check broker logs (if using container)
docker logs solace-pubsub
```

#### Monitor Message Flow

Use Solace PubSub+ Manager or CLI tools:

```bash
# Show queue statistics
solace-cli queue show my-agent-queue

# Monitor message rates
solace-cli stats
```

---

### Debug Configuration Issues

#### Validate YAML Syntax

```bash
# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('configs/agents/my_agent.yaml'))"

# Pretty print configuration
python -c "import yaml, json; print(json.dumps(yaml.safe_load(open('configs/agents/my_agent.yaml')), indent=2))"
```

#### Verify Environment Variables

```bash
# Show all environment variables
env | grep -E "(SOLACE|LLM|DATABASE)"

# Check specific variable
echo $LLM_SERVICE_API_KEY

# Verify .env loading
sam run --help  # Shows if .env is loaded
```

#### Test Configuration Loading

```bash
# Dry run (if available)
sam run --dry-run

# Check for errors without starting
sam run 2>&1 | grep -i error
```

---

### Debug Agent Behavior

#### Enable Agent Debug Mode

Add to agent configuration:

```yaml
app_config:
  debug_mode: true
  log_level: DEBUG
```

#### Trace Tool Execution

Add logging to tool functions:

```python
from solace_ai_connector.common.log import log

async def my_tool(param: str, **kwargs):
    log.debug(f"Tool called with param: {param}")
    log.debug(f"Tool context: {kwargs.get('tool_context')}")
    log.debug(f"Tool config: {kwargs.get('tool_config')}")
    # ... tool logic
    log.debug(f"Tool returning: {result}")
    return result
```

#### Monitor Agent State

```python
# In lifecycle or tool functions
host_component = tool_context._invocation_context.agent.host_component
state = host_component.get_agent_specific_state("my_state_key")
log.info(f"Current agent state: {state}")
```

---

## Troubleshooting

### Issue: "Connection refused" to broker

**Symptoms:**
```
Error: Failed to connect to broker at ws://localhost:8008
ConnectionRefusedError: [Errno 61] Connection refused
```

**Solutions:**

1. **Verify broker is running:**
```bash
# For container broker
docker ps | grep solace

# For external broker
nc -zv broker-hostname 8008
```

2. **Check broker URL in configuration:**
```bash
grep broker_url configs/shared_config.yaml
echo $SOLACE_BROKER_URL
```

3. **Start broker if needed:**
```bash
# Start container broker
docker start solace-pubsub

# Or initialize with container broker
sam init --broker-type container
```

4. **Use dev mode for testing:**
```bash
# In .env
SOLACE_DEV_MODE=true

# Or in shared_config.yaml
dev_mode: true
```

---

### Issue: "Module not found" errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'my_agent.tools'
ImportError: cannot import name 'my_function'
```

**Solutions:**

1. **Verify module path:**
```bash
# Check file exists
ls -la src/my_agent/tools.py

# Verify Python can find it
python -c "import my_agent.tools"
```

2. **Check component_base_path:**
```yaml
tools:
  - tool_type: python
    component_module: "my_agent.tools"
    component_base_path: "src"  # Add this
```

3. **Install plugin if needed:**
```bash
# For plugin-based agents
sam plugin build
sam plugin add my-agent --plugin ./dist/my_agent-0.1.0-py3-none-any.whl
```

4. **Check PYTHONPATH:**
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
sam run
```

---

### Issue: "Invalid API key" for LLM

**Symptoms:**
```
Error: Authentication failed with LLM service
401 Unauthorized
```

**Solutions:**

1. **Verify API key is set:**
```bash
echo $LLM_SERVICE_API_KEY
# Should show: sk-...
```

2. **Test API key directly:**
```bash
curl -H "Authorization: Bearer $LLM_SERVICE_API_KEY" \
  https://api.openai.com/v1/models
```

3. **Check environment loading:**
```bash
# Ensure .env is loaded
cat .env | grep LLM_SERVICE_API_KEY

# Run without --system-env
sam run  # Loads .env by default
```

4. **Regenerate API key:**
- Visit provider dashboard
- Create new API key
- Update .env file

---

### Issue: Agent starts but doesn't respond

**Symptoms:**
- Agent starts successfully
- No errors in logs
- But doesn't respond to requests

**Solutions:**

1. **Check agent discovery:**
```yaml
app_config:
  agent_discovery_enabled: true
  agent_card_publishing_interval: 30
```

2. **Verify topic subscriptions:**
```bash
# Check broker subscriptions
# Use PubSub+ Manager or CLI
```

3. **Test with simple request:**
```bash
# Send test message via gateway
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'
```

4. **Check session service:**
```bash
# Verify database connection
psql $DATABASE_URL -c "SELECT 1;"

# Or check SQLite file
sqlite3 session.db ".tables"
```

---

### Issue: High memory usage

**Symptoms:**
```
Agent Mesh consuming excessive memory
System becomes slow
```

**Solutions:**

1. **Use appropriate storage:**
```yaml
# Instead of memory storage
session_service:
  type: sql
  database_url: sqlite:///session.db

artifact_service:
  type: filesystem
  base_path: /tmp/artifacts
```

2. **Configure session cleanup:**
```yaml
session_service:
  type: sql
  default_behavior: RUN_BASED  # Clear after each run
```

3. **Limit artifact size:**
```yaml
artifact_service:
  max_artifact_size_mb: 100
```

4. **Monitor and restart:**
```bash
# Monitor memory
watch -n 5 'ps aux | grep "sam run"'

# Restart if needed
pkill -f "sam run"
sam run
```

---

### Issue: Slow response times

**Symptoms:**
- Agent takes long time to respond
- Timeouts occur

**Solutions:**

1. **Enable parallel tool calls:**
```yaml
model:
  parallel_tool_calls: true
```

2. **Use faster model:**
```yaml
model:
  model: gpt-3.5-turbo  # Instead of gpt-4
```

3. **Enable prompt caching:**
```yaml
model:
  cache_strategy: "5m"
```

4. **Optimize tool execution:**
```python
# Use async operations
async def my_tool():
    # Use asyncio for concurrent operations
    results = await asyncio.gather(
        fetch_data_1(),
        fetch_data_2()
    )
```

---

## Production Deployment

### Using Systemd Service

Create `/etc/systemd/system/agent-mesh.service`:

```ini
[Unit]
Description=Solace Agent Mesh
After=network.target

[Service]
Type=simple
User=agent-mesh
WorkingDirectory=/opt/agent-mesh
Environment="PATH=/opt/agent-mesh/.venv/bin"
EnvironmentFile=/opt/agent-mesh/.env
ExecStart=/opt/agent-mesh/.venv/bin/sam run
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Manage Service:**
```bash
# Enable and start
sudo systemctl enable agent-mesh
sudo systemctl start agent-mesh

# Check status
sudo systemctl status agent-mesh

# View logs
sudo journalctl -u agent-mesh -f

# Restart
sudo systemctl restart agent-mesh
```

---

### Using Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY configs/ configs/
COPY src/ src/
COPY .env .env

# Run application
CMD ["sam", "run"]
```

**Build and Run:**
```bash
# Build image
docker build -t my-agent-mesh .

# Run container
docker run -d \
  --name agent-mesh \
  --env-file .env \
  -p 8000:8000 \
  my-agent-mesh

# View logs
docker logs -f agent-mesh

# Stop
docker stop agent-mesh
```

---

### Using Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  broker:
    image: solace/solace-pubsub-standard:latest
    ports:
      - "8008:8008"
      - "8080:8080"
    environment:
      - username_admin_globalaccesslevel=admin
      - username_admin_password=admin

  agent-mesh:
    build: .
    depends_on:
      - broker
    environment:
      - SOLACE_BROKER_URL=ws://broker:8008
      - LLM_SERVICE_API_KEY=${LLM_SERVICE_API_KEY}
    ports:
      - "8000:8000"
    volumes:
      - ./configs:/app/configs
      - ./logs:/app/logs
```

**Run:**
```bash
docker-compose up -d
docker-compose logs -f
```

---

## Monitoring and Observability

### Health Checks

Implement health check endpoint:

```python
# In gateway or custom endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "broker_connected": check_broker_connection(),
        "agents_running": get_running_agents(),
        "timestamp": datetime.now().isoformat()
    }
```

### Metrics Collection

Use Prometheus for metrics:

```python
from prometheus_client import Counter, Histogram, start_http_server

# Define metrics
request_count = Counter('agent_requests_total', 'Total requests')
request_duration = Histogram('agent_request_duration_seconds', 'Request duration')

# In tool or handler
@request_duration.time()
async def handle_request():
    request_count.inc()
    # ... handle request
```

### Log Aggregation

Configure structured logging:

```python
import structlog

log = structlog.get_logger()

log.info("agent_started", 
    agent_name="my-agent",
    namespace="myorg/prod",
    version="1.0.0"
)
```

---

## Best Practices

### Development

1. **Use dev mode for rapid iteration:**
```bash
SOLACE_DEV_MODE=true sam run
```

2. **Enable debug logging:**
```yaml
log_level: DEBUG
```

3. **Test components individually:**
```bash
sam run configs/agents/my_agent.yaml
```

### Production

1. **Use persistent storage:**
```yaml
session_service:
  type: sql
  database_url: postgresql://...

artifact_service:
  type: filesystem
  base_path: /var/lib/agent-mesh
```

2. **Enable TLS:**
```yaml
broker_url: wss://broker.example.com:443
```

3. **Configure proper logging:**
```yaml
log_level: INFO
log_file: /var/log/agent-mesh/app.log
```

4. **Set up monitoring:**
- Health checks
- Metrics collection
- Log aggregation
- Alerting

### Security

1. **Protect environment files:**
```bash
chmod 600 .env
```

2. **Use secrets management:**
```bash
# Use AWS Secrets Manager, HashiCorp Vault, etc.
export LLM_SERVICE_API_KEY=$(aws secretsmanager get-secret-value --secret-id llm-api-key --query SecretString --output text)
```

3. **Rotate credentials regularly**

---

## Validation Checklist

Before running in production:

- [ ] All configuration files are valid YAML
- [ ] Environment variables are set correctly
- [ ] Broker connection is working
- [ ] LLM API keys are valid
- [ ] Storage services are accessible
- [ ] Logging is configured properly
- [ ] Health checks are implemented
- [ ] Monitoring is set up
- [ ] Backup strategy is in place
- [ ] Restart policy is configured

---

## Next Steps

After successfully running your application:

1. **Monitor Performance**: Track metrics and logs
2. **Scale Components**: Add more agents as needed
3. **Optimize Configuration**: Tune based on usage patterns
4. **Implement CI/CD**: Automate deployment
5. **Set Up Alerts**: Get notified of issues

---

## Additional Resources

- [Deployment Options](https://docs.cline.bot/deploying/deployment-options)
- [Logging Configuration](https://docs.cline.bot/deploying/logging)
- [Observability Guide](https://docs.cline.bot/deploying/observability)
- [Debugging Guide](https://docs.cline.bot/deploying/debugging)