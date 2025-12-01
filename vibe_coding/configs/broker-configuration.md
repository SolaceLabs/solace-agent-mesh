# Broker Configuration

Configures connection to Solace PubSub+ Event Broker for Agent-to-Agent (A2A) communication. The broker serves as the event mesh backbone enabling asynchronous, event-driven communication between all agents and gateways.

## Overview

The Solace broker configuration establishes:
- **Connection Settings** - URL, credentials, and VPN
- **Queue Management** - Message queuing and delivery
- **Topic Subscriptions** - Event routing patterns
- **Communication Protocol** - A2A protocol over Solace

## Configuration Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `broker_type` | String | Yes | - | Type of broker. Must be `"solace"` |
| `broker_url` | String | Yes | - | Broker connection URL |
| `broker_username` | String | Yes | - | Username for authentication |
| `broker_password` | String | Yes | - | Password for authentication |
| `broker_vpn` | String | Yes | - | Virtual Private Network (VPN) name |
| `broker_queue_name` | String | No | Auto-generated | Queue name for receiving messages |
| `broker_subscriptions` | List | No | Auto-generated | Topic subscriptions |

## Basic Configuration

### Minimal Configuration

```yaml
broker:
  broker_type: "solace"
  broker_url: "${SOLACE_BROKER_URL}"
  broker_username: "${SOLACE_BROKER_USERNAME}"
  broker_password: "${SOLACE_BROKER_PASSWORD}"
  broker_vpn: "${SOLACE_BROKER_VPN}"
```

### With Environment Variables

```bash
# .env file
SOLACE_BROKER_URL="tcp://localhost:55555"
SOLACE_BROKER_USERNAME="default"
SOLACE_BROKER_PASSWORD="default"
SOLACE_BROKER_VPN="default"
```

## Connection URLs

### URL Formats

| Protocol | Format | Use Case |
|----------|--------|----------|
| TCP | `tcp://host:port` | Standard connection |
| TLS/SSL | `tcps://host:port` | Encrypted connection |
| WebSocket | `ws://host:port` | Web-based connection |
| Secure WebSocket | `wss://host:port` | Encrypted web connection |

### Examples

```yaml
# Local development
broker_url: "tcp://localhost:55555"

# Solace Cloud
broker_url: "tcps://mr-connection-abc123.messaging.solace.cloud:55443"

# On-premises with TLS
broker_url: "tcps://broker.example.com:55443"

# WebSocket
broker_url: "ws://localhost:8008"
```

## Queue Configuration

### Auto-Generated Queues

By default, Agent Mesh automatically generates queue names:

```yaml
broker:
  broker_type: "solace"
  broker_url: "${SOLACE_BROKER_URL}"
  # Queue name auto-generated as: {namespace}q/a2a/{component-name}
```

### Custom Queue Names

Specify a custom queue name:

```yaml
broker:
  broker_type: "solace"
  broker_url: "${SOLACE_BROKER_URL}"
  broker_username: "${SOLACE_BROKER_USERNAME}"
  broker_password: "${SOLACE_BROKER_PASSWORD}"
  broker_vpn: "${SOLACE_BROKER_VPN}"
  broker_queue_name: "my-custom-queue"
```

### Queue Naming Convention

Default queue naming pattern:
```
{namespace}q/a2a/{component-name}
```

Example:
- Namespace: `myorg/prod`
- Component: `calculator-agent`
- Queue: `myorg/prodq/a2a/calculator-agent`

## Topic Subscriptions

### Auto-Generated Subscriptions

Agent Mesh automatically subscribes to relevant topics based on:
- Agent name
- Namespace
- Component type

### Custom Subscriptions

Add custom topic subscriptions:

```yaml
broker:
  broker_type: "solace"
  broker_url: "${SOLACE_BROKER_URL}"
  broker_username: "${SOLACE_BROKER_USERNAME}"
  broker_password: "${SOLACE_BROKER_PASSWORD}"
  broker_vpn: "${SOLACE_BROKER_VPN}"
  broker_subscriptions:
    - "myorg/prod/events/>"
    - "myorg/prod/notifications/agent/*"
```

### Topic Wildcards

Solace supports hierarchical topic wildcards:

| Wildcard | Matches | Example |
|----------|---------|---------|
| `*` | Single level | `myorg/*/events` matches `myorg/prod/events` |
| `>` | Multiple levels | `myorg/>` matches `myorg/prod/events/user` |

## Deployment Scenarios

### Local Development

```yaml
broker:
  broker_type: "solace"
  broker_url: "tcp://localhost:55555"
  broker_username: "default"
  broker_password: "default"
  broker_vpn: "default"
```

Start local broker with Docker:
```bash
docker run -d -p 8080:8080 -p 55555:55555 \
  --name solace \
  solace/solace-pubsub-standard:latest
```

### Solace Cloud

```yaml
broker:
  broker_type: "solace"
  broker_url: "${SOLACE_CLOUD_URL}"
  broker_username: "${SOLACE_CLOUD_USERNAME}"
  broker_password: "${SOLACE_CLOUD_PASSWORD}"
  broker_vpn: "${SOLACE_CLOUD_VPN}"
```

Environment variables:
```bash
export SOLACE_CLOUD_URL="tcps://mr-connection-abc123.messaging.solace.cloud:55443"
export SOLACE_CLOUD_USERNAME="solace-cloud-client"
export SOLACE_CLOUD_PASSWORD="your-password"
export SOLACE_CLOUD_VPN="your-vpn-name"
```

### On-Premises with TLS

```yaml
broker:
  broker_type: "solace"
  broker_url: "tcps://broker.example.com:55443"
  broker_username: "${BROKER_USERNAME}"
  broker_password: "${BROKER_PASSWORD}"
  broker_vpn: "production"
```

## Shared Configuration

### Define in shared_config.yaml

```yaml
shared_config:
  - broker_connection: &broker_connection
      broker_type: "solace"
      broker_url: "${SOLACE_BROKER_URL}"
      broker_username: "${SOLACE_BROKER_USERNAME}"
      broker_password: "${SOLACE_BROKER_PASSWORD}"
      broker_vpn: "${SOLACE_BROKER_VPN}"
```

### Reference in Components

```yaml
!include shared_config.yaml

components:
  - name: my-agent
    broker:
      <<: *broker_connection
```

### Override Specific Fields

```yaml
!include shared_config.yaml

components:
  - name: my-agent
    broker:
      <<: *broker_connection
      broker_queue_name: "custom-queue"  # Override queue name
```

## Multiple Brokers

Configure different brokers for different components:

```yaml
shared_config:
  # Production broker
  - broker_connection_prod: &broker_connection_prod
      broker_type: "solace"
      broker_url: "${PROD_BROKER_URL}"
      broker_username: "${PROD_BROKER_USERNAME}"
      broker_password: "${PROD_BROKER_PASSWORD}"
      broker_vpn: "production"
  
  # Development broker
  - broker_connection_dev: &broker_connection_dev
      broker_type: "solace"
      broker_url: "tcp://localhost:55555"
      broker_username: "default"
      broker_password: "default"
      broker_vpn: "default"
```

Use in components:
```yaml
components:
  - name: prod-agent
    broker:
      <<: *broker_connection_prod
  
  - name: dev-agent
    broker:
      <<: *broker_connection_dev
```

## Queue Templates (Production)

For production deployments with multiple instances, configure queue templates in Solace:

### Queue Template Settings

1. **Access Type**: Exclusive or Non-Exclusive
   - **Exclusive**: Single consumer (default)
   - **Non-Exclusive**: Multiple consumers (load balancing)

2. **Queue Name Pattern**:
   ```
   {NAMESPACE}q/a2a/>
   ```
   Replace `{NAMESPACE}` with your configured namespace (e.g., `myorg/prod`)

3. **Respect TTL**: Enable to honor message time-to-live

### Example Configuration

In Solace Cloud or PubSub+ Manager:
- **Queue Template Name**: `sam-agent-queues`
- **Queue Name Filter**: `myorg/prodq/a2a/>`
- **Access Type**: `Non-Exclusive` (for multiple instances)
- **Respect TTL**: `true`

## Security Best Practices

### 1. Use Environment Variables

Never hardcode credentials:

```yaml
# Good
broker_password: "${SOLACE_BROKER_PASSWORD}"

# Bad - Never do this
broker_password: "my-secret-password"
```

### 2. Use TLS/SSL in Production

```yaml
# Production
broker_url: "tcps://broker.example.com:55443"

# Not for production
broker_url: "tcp://broker.example.com:55555"
```

### 3. Restrict VPN Access

Use dedicated VPNs for different environments:
- `production` - Production workloads
- `staging` - Staging environment
- `development` - Development/testing

### 4. Rotate Credentials

Regularly rotate broker credentials and update environment variables.

### 5. Use Service Accounts

Create dedicated service accounts for Agent Mesh with minimal required permissions.

## Troubleshooting

### Connection Refused

**Error**: `Connection refused` or `Unable to connect to broker`

**Solutions**:
1. Verify broker is running and accessible
2. Check firewall rules allow connection to broker port
3. Verify broker URL is correct
4. Test connection with telnet: `telnet broker-host 55555`

### Authentication Failed

**Error**: `Authentication failed` or `Invalid credentials`

**Solutions**:
1. Verify username and password are correct
2. Check VPN name matches broker configuration
3. Ensure credentials have not expired
4. Verify environment variables are set correctly

### Queue Creation Failed

**Error**: `Failed to create queue` or `Queue already exists`

**Solutions**:
1. Check queue naming doesn't conflict with existing queues
2. Verify user has permission to create queues
3. Use custom queue name if auto-generation fails
4. Check queue template configuration in Solace

### Topic Subscription Failed

**Error**: `Failed to subscribe to topic`

**Solutions**:
1. Verify topic syntax is correct
2. Check user has permission to subscribe to topics
3. Ensure topic matches configured namespace
4. Review Solace ACL (Access Control List) settings

### Message Not Received

**Issue**: Agent not receiving messages

**Solutions**:
1. Verify queue subscriptions are correct
2. Check namespace matches across all components
3. Ensure broker connection is active
4. Review Solace message logs
5. Verify topic hierarchy matches expected pattern

## Performance Tuning

### Connection Pooling

For high-throughput scenarios, consider:
- Using persistent connections
- Configuring connection retry settings
- Monitoring connection health

### Queue Configuration

Optimize queue settings:
- Set appropriate message TTL
- Configure max message size
- Set queue depth limits
- Enable message spooling for persistence

### Topic Design

Design efficient topic hierarchies:
- Use specific topics over wildcards when possible
- Avoid excessive topic depth
- Group related events under common prefixes

## Monitoring

### Connection Health

Monitor broker connection status:
- Connection state (connected/disconnected)
- Reconnection attempts
- Message delivery rates

### Queue Metrics

Track queue performance:
- Queue depth
- Message rates (in/out)
- Consumer count
- Message acknowledgments

### Topic Metrics

Monitor topic activity:
- Subscription count
- Message publish rates
- Topic match rates

## Related Documentation

- [Shared Configuration](./shared-configuration.md) - Using broker config in shared settings
- [Agent Configuration](./agent-configuration.md) - Agent-specific broker usage
- [Gateway Configuration](./gateway-configuration.md) - Gateway broker configuration
- [Environment Variables](./environment-variables.md) - Broker environment variables
- [Best Practices](./best-practices.md) - Broker configuration best practices

## External Resources

- [Solace PubSub+ Documentation](https://docs.solace.com/)
- [Solace Cloud](https://solace.com/products/event-broker/cloud/)
- [Solace Docker Images](https://hub.docker.com/r/solace/solace-pubsub-standard)