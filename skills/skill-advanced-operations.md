# Skill: Advanced Operations in Solace Agent Mesh

## Skill ID
`advanced-operations`

## Description
Advanced configuration and operational techniques for Solace Agent Mesh including A2A proxies, evaluations, observability, deployment strategies, security, and production best practices.

## Prerequisites
- Solid understanding of all basic skills
- Production deployment experience
- System administration knowledge
- Understanding of distributed systems

## Related Skills
- All other skills (this builds on them)

---

## Core Concepts

### Advanced Topics Covered

1. **A2A Proxies**: Bridge external HTTP agents to mesh
2. **Evaluations**: Test and benchmark agent performance
3. **Observability**: Monitoring, logging, and debugging
4. **Deployment**: Kubernetes, Docker, production strategies
5. **Security**: RBAC, authentication, secure communication
6. **Performance**: Optimization and scaling
7. **Integration**: External systems and services

---

## A2A Proxies for Remote Agents

### What are A2A Proxies?

Proxies enable external agents (running on different infrastructure) to participate in the agent mesh by translating between A2A over HTTPS and A2A over Solace event mesh.

### Use Cases

- Integrate third-party agents from vendors
- Connect agents in different cloud environments
- Maintain service isolation while enabling collaboration
- Gradually migrate existing agents to mesh

### Create A2A Proxy

```bash
sam add proxy external-agent-proxy --skip
```

**Configuration** (`configs/agents/external_agent_proxy.yaml`):

```yaml
apps:
  - name: external-agent-proxy
    app_module: solace_agent_mesh.agent.a2a_proxy.app
    
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: ${NAMESPACE}
      agent_name: "external-agent-proxy"
      
      # External agent configuration
      external_agent:
        # HTTP endpoint of external agent
        base_url: ${EXTERNAL_AGENT_URL}
        
        # Authentication
        auth_type: "bearer"  # or "api_key", "basic"
        auth_token: ${EXTERNAL_AGENT_TOKEN}
        
        # Timeout settings
        timeout: 300
        
        # Retry configuration
        max_retries: 3
        retry_delay: 5
      
      # Agent card for discovery
      agent_card:
        description: "Proxy to external agent service"
        skills:
          - id: "external_capability"
            name: "External Capability"
            description: "Capability provided by external agent"
      
      # Discovery settings
      agent_discovery_enabled: true
```

**External Agent Requirements:**

The external agent must implement A2A protocol over HTTPS:

```
POST /a2a/invoke
Content-Type: application/json

{
  "stimulus": {
    "content": "user request",
    "metadata": {...}
  }
}
```

---

## Evaluations and Testing

### What are Evaluations?

Evaluations systematically test agent performance using predefined test cases and metrics.

### Create Test Suite

**Directory Structure:**
```
evaluations/
├── test_suites/
│   └── my_test_suite.yaml
└── test_cases/
    ├── test_case_1.json
    └── test_case_2.json
```

**Test Suite** (`evaluations/test_suites/my_test_suite.yaml`):

```yaml
name: "Agent Performance Test Suite"
description: "Test agent accuracy and response quality"

test_cases:
  - file: "test_cases/test_case_1.json"
  - file: "test_cases/test_case_2.json"

metrics:
  - accuracy
  - response_time
  - token_usage

agents_to_test:
  - "data-analyst"
  - "api-connector"
```

**Test Case** (`evaluations/test_cases/test_case_1.json`):

```json
{
  "id": "test_001",
  "description": "Test data analysis capability",
  "input": {
    "message": "Analyze the sales data and create a chart"
  },
  "expected_output": {
    "contains": ["chart", "analysis"],
    "artifacts": ["chart.png"]
  },
  "timeout": 60
}
```

### Run Evaluations

```bash
sam eval run evaluations/test_suites/my_test_suite.yaml
```

**Output:**
```
Running evaluation: Agent Performance Test Suite
Test case test_001: PASS (45.2s)
Test case test_002: PASS (32.1s)

Results:
- Accuracy: 95%
- Avg Response Time: 38.7s
- Total Token Usage: 12,450

Report saved to: evaluations/reports/report_2024-01-01.html
```

---

## Observability and Monitoring

### Logging Configuration

**Advanced Logging** (`configs/logging_config.yaml`):

```yaml
version: 1
disable_existing_loggers: false

formatters:
  json:
    class: pythonjsonlogger.jsonlogger.JsonFormatter
    format: '%(asctime)s %(name)s %(levelname)s %(message)s'
  
  detailed:
    format: '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: detailed
    stream: ext://sys.stdout
  
  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: json
    filename: logs/agent-mesh.log
    maxBytes: 10485760  # 10MB
    backupCount: 5
  
  error_file:
    class: logging.handlers.RotatingFileHandler
    level: ERROR
    formatter: json
    filename: logs/errors.log
    maxBytes: 10485760
    backupCount: 5

loggers:
  solace_agent_mesh:
    level: DEBUG
    handlers: [console, file, error_file]
    propagate: false
  
  google.adk:
    level: INFO
    handlers: [console, file]
    propagate: false

root:
  level: INFO
  handlers: [console, file]
```

### Metrics Collection

**Prometheus Integration:**

```python
# src/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Define metrics
request_count = Counter(
    'agent_requests_total',
    'Total agent requests',
    ['agent_name', 'status']
)

request_duration = Histogram(
    'agent_request_duration_seconds',
    'Request duration',
    ['agent_name']
)

active_sessions = Gauge(
    'agent_active_sessions',
    'Number of active sessions',
    ['agent_name']
)

# Start metrics server
start_http_server(9090)
```

**Usage in Tools:**

```python
@request_duration.labels(agent_name='my-agent').time()
async def my_tool(**kwargs):
    request_count.labels(agent_name='my-agent', status='started').inc()
    
    try:
        result = await process_request()
        request_count.labels(agent_name='my-agent', status='success').inc()
        return result
    except Exception as e:
        request_count.labels(agent_name='my-agent', status='error').inc()
        raise
```

### Distributed Tracing

**OpenTelemetry Integration:**

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

# Configure tracer
trace.set_tracer_provider(TracerProvider())
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(jaeger_exporter)
)

tracer = trace.get_tracer(__name__)

# Use in code
async def my_tool(**kwargs):
    with tracer.start_as_current_span("my_tool_execution"):
        # Tool logic
        pass
```

---

## Kubernetes Deployment

### Deployment Configuration

**Deployment** (`k8s/deployment.yaml`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-mesh
  labels:
    app: agent-mesh
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agent-mesh
  template:
    metadata:
      labels:
        app: agent-mesh
    spec:
      containers:
      - name: agent-mesh
        image: my-registry/agent-mesh:latest
        ports:
        - containerPort: 8000
        env:
        - name: NAMESPACE
          value: "production"
        - name: SOLACE_BROKER_URL
          valueFrom:
            secretKeyRef:
              name: agent-mesh-secrets
              key: broker-url
        - name: LLM_SERVICE_API_KEY
          valueFrom:
            secretKeyRef:
              name: agent-mesh-secrets
              key: llm-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

**Service** (`k8s/service.yaml`):

```yaml
apiVersion: v1
kind: Service
metadata:
  name: agent-mesh-service
spec:
  selector:
    app: agent-mesh
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

**ConfigMap** (`k8s/configmap.yaml`):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-mesh-config
data:
  shared_config.yaml: |
    shared_config:
      - broker_connection: &broker_connection
          broker_url: ${SOLACE_BROKER_URL}
          # ... other config
```

**Secrets** (`k8s/secrets.yaml`):

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: agent-mesh-secrets
type: Opaque
stringData:
  broker-url: "wss://broker.example.com:443"
  llm-api-key: "sk-your-api-key"
```

### Deploy to Kubernetes

```bash
# Create namespace
kubectl create namespace agent-mesh

# Apply configurations
kubectl apply -f k8s/secrets.yaml -n agent-mesh
kubectl apply -f k8s/configmap.yaml -n agent-mesh
kubectl apply -f k8s/deployment.yaml -n agent-mesh
kubectl apply -f k8s/service.yaml -n agent-mesh

# Check status
kubectl get pods -n agent-mesh
kubectl logs -f deployment/agent-mesh -n agent-mesh
```

---

## Security Best Practices

### RBAC Configuration

**Role-Based Access Control:**

```yaml
# In agent configuration
app_config:
  rbac:
    enabled: true
    roles:
      - name: "admin"
        permissions:
          - "agent:*"
          - "gateway:*"
          - "artifact:*"
      
      - name: "user"
        permissions:
          - "agent:read"
          - "agent:invoke"
          - "artifact:read"
      
      - name: "analyst"
        permissions:
          - "agent:invoke:data-analyst"
          - "artifact:read"
          - "artifact:write"
    
    user_roles:
      "user@example.com": ["user"]
      "admin@example.com": ["admin"]
      "analyst@example.com": ["analyst"]
```

### Secure Communication

**TLS Configuration:**

```yaml
broker:
  broker_url: wss://broker.example.com:443
  broker_username: ${BROKER_USERNAME}
  broker_password: ${BROKER_PASSWORD}
  
  # TLS settings
  tls_enabled: true
  tls_verify: true
  tls_ca_cert: /path/to/ca.crt
  tls_client_cert: /path/to/client.crt
  tls_client_key: /path/to/client.key
```

### Secrets Management

**Using HashiCorp Vault:**

```python
# src/utils/secrets.py
import hvac

def get_secret(path):
    """Retrieve secret from Vault."""
    client = hvac.Client(url='https://vault.example.com')
    client.token = os.environ['VAULT_TOKEN']
    
    secret = client.secrets.kv.v2.read_secret_version(path=path)
    return secret['data']['data']

# Usage
api_key = get_secret('agent-mesh/llm-api-key')
```

**Using AWS Secrets Manager:**

```python
import boto3

def get_secret(secret_name):
    """Retrieve secret from AWS Secrets Manager."""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return response['SecretString']
```

---

## Performance Optimization

### Connection Pooling

```python
# Reuse broker connections
class ConnectionPool:
    def __init__(self, max_connections=10):
        self.pool = []
        self.max_connections = max_connections
    
    async def get_connection(self):
        if self.pool:
            return self.pool.pop()
        return await create_connection()
    
    async def return_connection(self, conn):
        if len(self.pool) < self.max_connections:
            self.pool.append(conn)
```

### Caching Strategy

```python
from functools import lru_cache
import asyncio

# Cache expensive operations
@lru_cache(maxsize=1000)
def expensive_computation(param):
    # Expensive operation
    return result

# Async cache
class AsyncCache:
    def __init__(self, ttl=300):
        self.cache = {}
        self.ttl = ttl
    
    async def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
        return None
    
    async def set(self, key, value):
        self.cache[key] = (value, time.time())
```

### Load Balancing

**Multiple Agent Instances:**

```yaml
# Deploy multiple instances of same agent
apps:
  - name: data-analyst-1
    app_config:
      agent_name: "data-analyst"
      # ... config
  
  - name: data-analyst-2
    app_config:
      agent_name: "data-analyst"
      # ... config
  
  - name: data-analyst-3
    app_config:
      agent_name: "data-analyst"
      # ... config
```

The event mesh automatically load balances across instances.

---

## Queue Management

### Configure Queue Templates

**On Solace Broker:**

```bash
# Create queue template with TTL
solace-cli queue-template create agent-mesh-template \
  --max-message-size 10000000 \
  --max-ttl 3600 \
  --permission delete \
  --access-type exclusive
```

**In Configuration:**

```yaml
broker:
  broker_url: wss://broker.example.com:443
  temporary_queue: false
  queue_template: "agent-mesh-template"
```

---

## Disaster Recovery

### Backup Strategy

```bash
#!/bin/bash
# backup.sh

# Backup configurations
tar -czf configs-backup-$(date +%Y%m%d).tar.gz configs/

# Backup database
pg_dump $DATABASE_URL > db-backup-$(date +%Y%m%d).sql

# Backup artifacts
tar -czf artifacts-backup-$(date +%Y%m%d).tar.gz /var/lib/agent-mesh/artifacts/

# Upload to S3
aws s3 cp configs-backup-$(date +%Y%m%d).tar.gz s3://backups/agent-mesh/
aws s3 cp db-backup-$(date +%Y%m%d).sql s3://backups/agent-mesh/
aws s3 cp artifacts-backup-$(date +%Y%m%d).tar.gz s3://backups/agent-mesh/
```

### Recovery Procedure

```bash
#!/bin/bash
# restore.sh

# Download from S3
aws s3 cp s3://backups/agent-mesh/configs-backup-20240101.tar.gz .
aws s3 cp s3://backups/agent-mesh/db-backup-20240101.sql .

# Restore configurations
tar -xzf configs-backup-20240101.tar.gz

# Restore database
psql $DATABASE_URL < db-backup-20240101.sql

# Restart services
kubectl rollout restart deployment/agent-mesh -n agent-mesh
```

---

## Multi-Region Deployment

### Architecture

```
Region 1 (US-East)
├── Agent Mesh Instance
├── Solace Broker
└── Database (Primary)

Region 2 (EU-West)
├── Agent Mesh Instance
├── Solace Broker
└── Database (Replica)

Global Load Balancer
└── Routes to nearest region
```

### Configuration

**Region-Specific Config:**

```yaml
# configs/shared_config_us_east.yaml
shared_config:
  - broker_connection: &broker_connection
      broker_url: wss://us-east-broker.example.com:443
      # ... config

# configs/shared_config_eu_west.yaml
shared_config:
  - broker_connection: &broker_connection
      broker_url: wss://eu-west-broker.example.com:443
      # ... config
```

---

## Best Practices Summary

### Development
1. Use version control for all configurations
2. Implement comprehensive testing
3. Document all custom components
4. Follow coding standards

### Deployment
1. Use infrastructure as code
2. Implement CI/CD pipelines
3. Use blue-green deployments
4. Maintain rollback procedures

### Security
1. Enable TLS everywhere
2. Use secrets management
3. Implement RBAC
4. Regular security audits
5. Keep dependencies updated

### Operations
1. Monitor all metrics
2. Set up alerting
3. Implement logging aggregation
4. Regular backups
5. Disaster recovery testing

### Performance
1. Use connection pooling
2. Implement caching
3. Load balance across instances
4. Optimize database queries
5. Monitor resource usage

---

## Troubleshooting Advanced Issues

### High Latency

**Diagnosis:**
```bash
# Check broker latency
solace-cli stats latency

# Check database performance
psql $DATABASE_URL -c "SELECT * FROM pg_stat_activity;"

# Check network
ping broker.example.com
traceroute broker.example.com
```

**Solutions:**
- Enable caching
- Optimize database queries
- Use connection pooling
- Deploy closer to users

### Memory Leaks

**Diagnosis:**
```bash
# Monitor memory over time
watch -n 5 'ps aux | grep sam'

# Python memory profiling
python -m memory_profiler agent.py
```

**Solutions:**
- Review lifecycle cleanup
- Check for circular references
- Limit cache sizes
- Restart periodically

---

## Validation Checklist

Production readiness:

- [ ] All secrets in secure storage
- [ ] TLS enabled everywhere
- [ ] RBAC configured
- [ ] Monitoring and alerting set up
- [ ] Logging aggregation configured
- [ ] Backup strategy implemented
- [ ] Disaster recovery tested
- [ ] Load testing completed
- [ ] Security audit passed
- [ ] Documentation complete

---

## Additional Resources

- [Kubernetes Deployment Guide](https://docs.cline.bot/deploying/kubernetes/kubernetes-deployment-guide)
- [Observability Guide](https://docs.cline.bot/deploying/observability)
- [Security Best Practices](https://docs.cline.bot/enterprise/rbac-setup-guide)
- [Performance Tuning](https://docs.cline.bot/deploying/deployment-options)