# Skill: Create and Manage Gateways in Solace Agent Mesh

## Skill ID
`create-and-manage-gateways`

## Description
Create, configure, and manage gateways in Solace Agent Mesh. Gateways serve as entry points connecting external systems to the agent mesh through various protocols including REST, HTTP SSE, webhooks, and event mesh connectivity.

## Prerequisites
- Initialized Agent Mesh project (see `skill-initialize-project`)
- At least one agent configured
- Understanding of gateway concepts
- Network/API knowledge for specific gateway types

## Related Skills
- `initialize-agent-mesh-project` - Project setup
- `create-and-manage-agents` - Agent configuration
- `manage-plugins` - Plugin-based gateways

---

## Core Concepts

### What is a Gateway?

A gateway is an interface component that:

1. **Exposes Agent Mesh**: Provides external access to agents
2. **Protocol Translation**: Converts external requests to A2A messages
3. **Authentication**: Manages user identity and authorization
4. **Message Routing**: Directs requests to appropriate agents
5. **Response Formatting**: Transforms agent responses for external systems

### Gateway Architecture

```
External System
      │
      ├──> Gateway (Entry Point)
      │     ├─> Authentication
      │     ├─> System Purpose
      │     ├─> Format Rules
      │     └─> A2A Translation
      │
      └──> Agent Mesh (via Event Broker)
            └─> Agents process requests
```

### Gateway Types

| Type | Protocol | Use Case |
|------|----------|----------|
| **HTTP SSE** | Server-Sent Events | Real-time web interfaces, streaming |
| **REST** | HTTP REST API | Task submission, polling |
| **Webhook** | HTTP POST | Incoming webhook events |
| **Event Mesh** | PubSub+ Events | External event integration |
| **Slack** | Slack API | Team collaboration |
| **Teams** | Microsoft Teams | Enterprise chat (Docker only) |

---

## Step-by-Step Instructions

### Method 1: Create Gateway with Browser GUI (Recommended)

#### Step 1: Launch Gateway Creation

```bash
sam add gateway my-gateway --gui
```

**Expected Output:**
```
Starting gateway configuration portal...
Configuration portal available at: http://127.0.0.1:5002
Opening browser...
```

#### Step 2: Configure in Browser

1. **Basic Information**
   - Gateway name
   - Namespace
   - Gateway ID

2. **Gateway Type**
   - Select interface type
   - Configure type-specific settings

3. **System Purpose**
   - Define gateway's role
   - Set context for incoming requests

4. **Response Format**
   - Configure output formatting
   - Set response structure

5. **Artifact Service**
   - Configure file handling
   - Set storage options

#### Step 3: Save Configuration

Gateway configuration saved to:
```
configs/gateways/my_gateway.yaml
```

---

### Method 2: Create Gateway with Interactive CLI

```bash
sam add gateway my-gateway
```

Follow prompts for:
- Namespace
- Gateway ID
- System purpose
- Response format
- Artifact service configuration

---

### Method 3: Create Gateway Non-Interactively

```bash
sam add gateway my-gateway \
  --skip \
  --namespace "myorg/production" \
  --gateway-id "my-gateway-001" \
  --system-purpose "Process customer support requests" \
  --response-format "Provide clear, helpful responses" \
  --artifact-service-type filesystem \
  --artifact-service-base-path "/var/lib/agent-mesh/gateway-artifacts"
```

---

## Gateway Configuration

### Base Gateway Template

```yaml
apps:
  - name: my-gateway
    app_module: solace_agent_mesh.gateway.base_gateway.app
    
    # Broker connection
    broker:
      <<: *broker_connection
    
    # Gateway configuration
    app_config:
      namespace: ${NAMESPACE}
      gateway_id: "my-gateway-001"
      
      # System purpose - context for all requests
      system_purpose: |
        You are processing requests from external users.
        Provide helpful, accurate responses.
      
      # Response formatting instructions
      response_format: |
        Format responses as clear, structured text.
        Include relevant details and next steps.
      
      # Artifact service for file handling
      artifact_service: *default_artifact_service
```

---

## Gateway Types and Configuration

### 1. HTTP SSE Gateway (Web UI)

**Use Case:** Real-time web interfaces with streaming responses

**Features:**
- Server-sent events for live updates
- File upload/download
- Agent discovery API
- Session management

**Configuration:**

```yaml
apps:
  - name: webui-gateway
    app_module: solace_agent_mesh.gateway.http_sse_gateway.app
    
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: ${NAMESPACE}
      gateway_id: "webui-gateway"
      
      # System purpose
      system_purpose: |
        You are a helpful AI assistant accessible via web interface.
        Provide clear, user-friendly responses.
      
      # Response format
      response_format: |
        Format responses in markdown for web display.
        Use bullet points and formatting for clarity.
      
      # Web server configuration
      fastapi_host: "0.0.0.0"
      fastapi_port: 8000
      
      # Session configuration
      session_secret_key: ${SESSION_SECRET_KEY}
      
      # Frontend configuration
      frontend_config:
        welcome_message: "Hello! How can I help you today?"
        bot_name: "AI Assistant"
        logo_url: "/static/logo.png"
        collect_feedback: true
      
      # Enable embed resolution
      enable_embed_resolution: true
      
      # Artifact service
      artifact_service: *default_artifact_service
```

**Access:**
```bash
# Start gateway
sam run configs/gateways/webui_gateway.yaml

# Access at http://localhost:8000
```

---

### 2. REST Gateway

**Use Case:** Task submission with polling-based retrieval

**Features:**
- Submit tasks, get task ID
- Poll for results
- Asynchronous processing
- Authentication support

**Configuration:**

```yaml
apps:
  - name: rest-gateway
    app_module: solace_agent_mesh.gateway.rest_gateway.app
    
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: ${NAMESPACE}
      gateway_id: "rest-gateway"
      
      system_purpose: |
        Process API requests and return structured responses.
      
      response_format: |
        Return JSON responses with status and data fields.
      
      # REST server configuration
      fastapi_host: "0.0.0.0"
      fastapi_port: 8080
      
      # Authentication (optional)
      auth_enabled: true
      api_key: ${REST_API_KEY}
      
      artifact_service: *default_artifact_service
```

**API Usage:**

```bash
# Submit task
curl -X POST http://localhost:8080/api/tasks \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"message": "Analyze this data"}'

# Response: {"task_id": "abc123"}

# Poll for result
curl http://localhost:8080/api/tasks/abc123 \
  -H "X-API-Key: your-api-key"
```

---

### 3. Webhook Gateway

**Use Case:** Handle incoming webhook events

**Features:**
- Receive HTTP POST webhooks
- Transform payloads to A2A messages
- Signature verification
- Event filtering

**Configuration:**

```yaml
apps:
  - name: webhook-gateway
    app_module: solace_agent_mesh.gateway.webhook_gateway.app
    
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: ${NAMESPACE}
      gateway_id: "webhook-gateway"
      
      system_purpose: |
        Process incoming webhook events and trigger appropriate actions.
      
      # Webhook configuration
      webhook_path: "/webhook"
      webhook_secret: ${WEBHOOK_SECRET}
      
      # Server configuration
      fastapi_host: "0.0.0.0"
      fastapi_port: 8090
      
      artifact_service: *default_artifact_service
```

**Webhook URL:**
```
http://your-server:8090/webhook
```

---

### 4. Event Mesh Gateway (Plugin)

**Use Case:** Connect external event mesh to Agent Mesh

**Installation:**

```bash
# Install plugin
sam plugin install sam-event-mesh-gateway

# Add gateway instance
sam plugin add my-event-gateway --plugin sam-event-mesh-gateway
```

**Configuration:**

```yaml
apps:
  - name: event-mesh-gateway
    app_module: sam_event_mesh_gateway.app
    
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: ${NAMESPACE}
      gateway_id: "event-mesh-gateway"
      
      # External broker connection
      external_broker:
        broker_url: ${EXTERNAL_BROKER_URL}
        broker_username: ${EXTERNAL_BROKER_USERNAME}
        broker_password: ${EXTERNAL_BROKER_PASSWORD}
        broker_vpn: ${EXTERNAL_BROKER_VPN}
      
      # Topic mapping
      topic_subscriptions:
        - "external/events/>"
      
      # Message transformation
      message_transform:
        extract_payload: true
        add_metadata: true
      
      artifact_service: *default_artifact_service
```

---

### 5. Slack Gateway (Plugin)

**Use Case:** Slack bot integration

**Installation:**

```bash
sam plugin install sam-slack-gateway
sam plugin add slack-bot --plugin sam-slack-gateway
```

**Configuration:**

```yaml
apps:
  - name: slack-gateway
    app_module: sam_slack_gateway.app
    
    broker:
      <<: *broker_connection
    
    app_config:
      namespace: ${NAMESPACE}
      gateway_id: "slack-gateway"
      
      # Slack configuration
      slack_bot_token: ${SLACK_BOT_TOKEN}
      slack_app_token: ${SLACK_APP_TOKEN}
      
      # Bot behavior
      respond_to_mentions: true
      respond_to_dms: true
      
      system_purpose: |
        You are a helpful Slack bot assistant.
        Provide concise, actionable responses.
      
      artifact_service: *default_artifact_service
```

**Setup:**
1. Create Slack app at api.slack.com
2. Enable Socket Mode
3. Add bot token scopes
4. Install app to workspace
5. Configure tokens in .env

---

## Common Gateway Patterns

### Pattern 1: Public Web Interface

**Use Case:** Customer-facing chatbot

```yaml
app_config:
  gateway_id: "public-chatbot"
  
  system_purpose: |
    You are a customer support assistant.
    Help users with product questions and issues.
    Be friendly, professional, and helpful.
  
  response_format: |
    Provide clear, step-by-step guidance.
    Use bullet points for multiple steps.
    Include links to documentation when relevant.
  
  frontend_config:
    welcome_message: "Welcome! How can I help you today?"
    bot_name: "Support Assistant"
    collect_feedback: true
```

---

### Pattern 2: Internal API Gateway

**Use Case:** Internal service integration

```yaml
app_config:
  gateway_id: "internal-api"
  
  system_purpose: |
    Process internal service requests.
    Validate inputs and return structured data.
  
  response_format: |
    Return JSON with:
    - status: success/error
    - data: response data
    - metadata: processing info
  
  auth_enabled: true
  api_key: ${INTERNAL_API_KEY}
```

---

### Pattern 3: Event Processing Gateway

**Use Case:** Process external events

```yaml
app_config:
  gateway_id: "event-processor"
  
  system_purpose: |
    Process incoming events and trigger workflows.
    Extract relevant data and route to appropriate agents.
  
  topic_subscriptions:
    - "orders/created"
    - "users/registered"
    - "payments/completed"
  
  message_transform:
    extract_payload: true
    add_timestamp: true
    add_source: true
```

---

## Authentication and Security

### API Key Authentication

```yaml
app_config:
  auth_enabled: true
  api_key: ${API_KEY}
  
  # Or multiple keys
  api_keys:
    - ${API_KEY_1}
    - ${API_KEY_2}
```

**Usage:**
```bash
curl -H "X-API-Key: your-key" http://localhost:8080/api/endpoint
```

---

### OAuth Integration

```yaml
app_config:
  auth_type: "oauth"
  oauth_provider: "google"
  oauth_client_id: ${OAUTH_CLIENT_ID}
  oauth_client_secret: ${OAUTH_CLIENT_SECRET}
```

---

### Custom Authentication

Create custom auth provider:

```python
# src/my_gateway/auth.py
async def authenticate_request(request):
    """Custom authentication logic."""
    token = request.headers.get("Authorization")
    # Validate token
    return user_info
```

Configure:
```yaml
app_config:
  auth_provider:
    module: "my_gateway.auth"
    function: "authenticate_request"
```

---

## System Purpose and Response Formatting

### System Purpose

The system purpose sets context for all requests through the gateway:

```yaml
system_purpose: |
  You are processing {specific context}.
  
  Your responsibilities:
  1. {Responsibility 1}
  2. {Responsibility 2}
  
  Guidelines:
  - {Guideline 1}
  - {Guideline 2}
```

**Examples:**

**Customer Support:**
```yaml
system_purpose: |
  You are a customer support assistant for TechCorp.
  Help users troubleshoot products and answer questions.
  Be empathetic, patient, and solution-oriented.
```

**Data Analysis:**
```yaml
system_purpose: |
  You are processing data analysis requests.
  Generate insights, visualizations, and reports.
  Ensure accuracy and provide clear explanations.
```

---

### Response Format

Control how responses are structured:

```yaml
response_format: |
  Format responses as {format type}.
  
  Structure:
  - {Element 1}
  - {Element 2}
  
  Style:
  - {Style guideline 1}
  - {Style guideline 2}
```

**Examples:**

**Markdown for Web:**
```yaml
response_format: |
  Format responses in markdown.
  Use headers, bullet points, and code blocks.
  Keep paragraphs concise.
```

**JSON for APIs:**
```yaml
response_format: |
  Return JSON with this structure:
  {
    "status": "success|error",
    "data": {...},
    "message": "Human-readable message"
  }
```

---

## Troubleshooting

### Issue: Gateway won't start

**Symptoms:**
```
Error: Port 8000 already in use
```

**Solutions:**

1. **Change port:**
```yaml
fastapi_port: 8001
```

2. **Kill existing process:**
```bash
lsof -ti:8000 | xargs kill -9
```

3. **Use different gateway:**
```bash
sam run configs/gateways/my_gateway.yaml
```

---

### Issue: Authentication fails

**Symptoms:**
```
401 Unauthorized
```

**Solutions:**

1. **Verify API key:**
```bash
echo $API_KEY
```

2. **Check header format:**
```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8080/api/test
```

3. **Disable auth for testing:**
```yaml
auth_enabled: false
```

---

### Issue: Requests timeout

**Symptoms:**
- Gateway receives request
- No response from agents
- Timeout error

**Solutions:**

1. **Verify agents are running:**
```bash
ps aux | grep "sam run"
```

2. **Check broker connection:**
```bash
# Both gateway and agents must connect to same broker
```

3. **Increase timeout:**
```yaml
request_timeout: 300  # seconds
```

---

## Best Practices

### Design

1. **Clear System Purpose**: Define specific context and guidelines
2. **Appropriate Gateway Type**: Choose based on use case
3. **Response Formatting**: Match external system expectations
4. **Error Handling**: Provide clear error messages

### Security

1. **Enable Authentication**: Always use auth in production
2. **Use HTTPS**: Enable TLS for production deployments
3. **Rate Limiting**: Implement rate limits to prevent abuse
4. **Input Validation**: Validate all incoming data

### Performance

1. **Connection Pooling**: Reuse broker connections
2. **Async Operations**: Use async for I/O operations
3. **Caching**: Cache frequent responses
4. **Load Balancing**: Deploy multiple gateway instances

### Monitoring

1. **Health Checks**: Implement health endpoints
2. **Metrics**: Track request rates, latencies
3. **Logging**: Log all requests and errors
4. **Alerting**: Set up alerts for failures

---

## Validation Checklist

Before deploying a gateway:

- [ ] Gateway type is appropriate for use case
- [ ] System purpose is clear and specific
- [ ] Response format matches requirements
- [ ] Authentication is configured
- [ ] Port is available
- [ ] Broker connection works
- [ ] Agents are accessible
- [ ] Error handling is implemented
- [ ] Logging is configured
- [ ] Security measures are in place

---

## Next Steps

After creating gateways:

1. **Test Gateway**: Send test requests
2. **Monitor Performance**: Track metrics
3. **Add Security**: Implement authentication
4. **Scale**: Deploy multiple instances
5. **Integrate**: Connect external systems

---

## Additional Resources

- [Gateway Documentation](https://docs.cline.bot/components/gateways)
- [REST Gateway Tutorial](https://docs.cline.bot/developing/tutorials/rest-gateway)
- [Slack Integration Guide](https://docs.cline.bot/developing/tutorials/slack-integration)
- [Event Mesh Gateway Tutorial](https://docs.cline.bot/developing/tutorials/event-mesh-gateway)