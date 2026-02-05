---
title: Health Checks
sidebar_position: 25
---

# Health Checks

Health checks enable orchestration platforms like Kubernetes to monitor the operational status of your Agent Mesh components. By exposing standardized health endpoints, your agents, gateways, and platform services can signal when they're ready to receive traffic, allowing for graceful deployments, automatic recovery from failures, and intelligent load balancing.

Agent Mesh inherits health check functionality from solace-ai-connector and extends it with broker connectivity checks, database connectivity checks, and custom health check support. For the underlying implementation details, see [solace-ai-connector Health Checks](https://github.com/SolaceLabs/solace-ai-connector/blob/main/docs/health_checks.md).

## Health Check Endpoints

Each Agent Mesh application exposes three HTTP health check endpoints:

| Endpoint | Purpose | Kubernetes Probe |
|----------|---------|------------------|
| `/startup` | One-time gate for initialization - once successful, latches to 200 forever | Startup probe |
| `/readyz` | Validates if the system is ready to process messages | Readiness probe |
| `/healthz` | Confirms the process is alive and responsive | Liveness probe |

All endpoints return:
- **HTTP 200** when healthy
- **HTTP 503** when unhealthy

:::note Understanding the Three Probes
- **Startup probe**: Runs during initialization. Once it succeeds, Kubernetes stops checking it. This prevents liveness probes from killing slow-starting applications.
- **Readiness probe**: Runs continuously. When it fails, Kubernetes removes the pod from service endpoints but keeps it running. When it recovers, traffic resumes.
- **Liveness probe**: Runs continuously. When it fails repeatedly, Kubernetes restarts the container.
:::

## Enabling Health Checks

Add the `health_check` section at the top level of your YAML configuration (outside the `apps:` block). You only need to add this to one configuration file for the health check server to run in the container:

```yaml
health_check:
  enabled: true
  port: 8080  # Default port

apps:
  - name: my-agent-app
    # ... app configuration ...
```

## Built-in Health Checks

### Broker Connection

Agent Mesh automatically monitors the connection to the Solace event broker. The health check returns healthy only when the broker connection status is `CONNECTED`.

When running in **dev mode** (using the DevBroker for local development), broker health checks always return healthy because there's no real broker connection to monitor.

### Database Connectivity

For components using SQL-based session services, Agent Mesh verifies database connectivity against each configured database. The health check fails if any database is unreachable or the query times out (configurable via `database_timeout_seconds`).

You can configure the database health check timeout in your app configuration:

```yaml
apps:
  - name: my-agent-app
    # ... other app config ...
    health_check:
      database_timeout_seconds: 5.0  # Default: 5 seconds
```

:::note
Database health checks only apply to components with SQL-based session services configured. If no databases are configured, this check automatically passes.
:::

## Custom Health Checks

For application-specific health requirements, you can define custom health check functions that run alongside the built-in checks. This is useful for verifying external service availability, checking model readiness, or implementing business-specific health criteria.

### Configuration

Add custom health checks to your application configuration under the app's `health_check` section:

```yaml
apps:
  - name: my-agent-app
    # ... other app config ...
    health_check:
      custom_startup_check: my_agent.health:check_startup
      custom_ready_check: my_agent.health:check_ready
```

The format is `module.path:function_name`, where:

- `module.path` is the Python module path (e.g., `my_agent.health`)
- `function_name` is the function to call (e.g., `check_ready`)

### Writing Custom Health Check Functions

Custom health check functions receive the application instance and must return a boolean:

```python
import logging

log = logging.getLogger(__name__)

def check_startup(app) -> bool:
    """
    Custom startup check - verify external ML service is available.

    Args:
        app: The application instance, providing access to:
             - app.app_info: Application configuration
             - app.flows: All configured flows and components

    Returns:
        True if healthy, False if unhealthy
    """
    try:
        # Example: Check if an external ML service SDK can connect
        from my_ml_service import MLServiceClient
        client = MLServiceClient()
        return client.is_healthy()
    except Exception as e:
        log.warning("ML service health check failed: %s", e)
        return False


def check_ready(app) -> bool:
    """
    Custom readiness check - verify external payment service is reachable.

    Returns:
        True if healthy, False if unhealthy
    """
    try:
        # Example: Check if an external payment service SDK can connect
        from my_payment_service import PaymentClient
        client = PaymentClient()
        return client.ping()
    except Exception as e:
        log.warning("Payment service health check failed: %s", e)
        return False
```

:::warning Return Type
Custom health check functions must return a boolean (`True` or `False`). Non-boolean return values are treated as unhealthy, and exceptions are caught and logged as failures.
:::

## Kubernetes Integration

Configure Kubernetes probes in your deployment manifest to use the health check endpoints:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-agent
spec:
  template:
    spec:
      containers:
        - name: agent
          ports:
            - containerPort: 8080
              name: health
          startupProbe:
            httpGet:
              path: /startup
              port: health
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 30
          readinessProbe:
            httpGet:
              path: /readyz
              port: health
            periodSeconds: 10
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /healthz
              port: health
            periodSeconds: 30
            failureThreshold: 3
```

:::tip Probe Configuration

- **startupProbe**: Use a higher `failureThreshold` to allow time for initial model loading or database migrations
- **readinessProbe**: Use a shorter `periodSeconds` to quickly detect and recover from transient issues
- **livenessProbe**: Use a longer `periodSeconds` and higher `failureThreshold` to avoid unnecessary restarts during temporary issues

:::

## Health Check Flow

The `/healthz` (liveness) endpoint simply returns HTTP 200 if the health check server is running. It does not perform any additional checks.

The `/startup` and `/readyz` endpoints evaluate the following checks:

```text
┌─────────────────────────────────────────────────────────────┐
│              Health Check Request (/startup or /readyz)      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │  Broker Connected?  │
                   │  (or dev_mode?)     │
                   └─────────────────────┘
                        │           │
                       Yes          No ──────► HTTP 503
                        │
                        ▼
                   ┌─────────────────────┐
                   │ Database Connected? │
                   │ (if configured)     │
                   └─────────────────────┘
                        │           │
                       Yes          No ──────► HTTP 503
                        │
                        ▼
                   ┌─────────────────────┐
                   │  Custom Check OK?   │
                   │  (if configured)    │
                   └─────────────────────┘
                        │           │
                       Yes          No ──────► HTTP 503
                        │
                        ▼
                    HTTP 200
```

## Configuration Reference

### Global Health Check Options

Configure the health check server at the top level of your YAML configuration:

```yaml
health_check:
  enabled: true
  port: 8080
  liveness_path: /healthz
  readiness_path: /readyz
  startup_path: /startup
  readiness_check_period_seconds: 5
  startup_check_period_seconds: 5
```

| Option | Type | Default | Description |
| ------ | ---- | ------- | ----------- |
| `enabled` | boolean | `false` | Enable health check endpoints |
| `port` | integer | `8080` | Port for health check HTTP server |
| `liveness_path` | string | `/healthz` | URL path for liveness probe endpoint |
| `readiness_path` | string | `/readyz` | URL path for readiness probe endpoint |
| `startup_path` | string | `/startup` | URL path for startup probe endpoint |
| `readiness_check_period_seconds` | integer | `5` | Interval in seconds for internal readiness monitoring |
| `startup_check_period_seconds` | integer | `5` | Interval in seconds for internal startup monitoring |

:::tip Custom Endpoint Paths
If your infrastructure requires different endpoint paths (e.g., to avoid conflicts with other services), you can customize them using `liveness_path`, `readiness_path`, and `startup_path`. Remember to update your Kubernetes probe configurations to match.
:::

### App-specific Health Check Options

Configure custom health checks per application under each app's `health_check` section:

```yaml
apps:
  - name: my-agent-app
    # ... other app config ...
    health_check:
      database_timeout_seconds: 5.0
      custom_startup_check: my_agent.health:check_startup
      custom_ready_check: my_agent.health:check_ready
```

| Option | Type | Default | Description |
| ------ | ---- | ------- | ----------- |
| `database_timeout_seconds` | float | `5.0` | Timeout for database connectivity checks |
| `custom_startup_check` | string | - | Module path for custom startup check (`module:function`) |
| `custom_ready_check` | string | - | Module path for custom readiness check (`module:function`) |

## Troubleshooting

### Health Check Returns 503

If your health check is returning 503, check the following:

1. **Broker connection**: Verify the Solace broker is reachable and credentials are correct

   ```bash
   # Check agent logs for connection status
   grep -i "connection" /path/to/agent.log
   ```

2. **Database connectivity**: Ensure databases are accessible and responding within the timeout period

3. **Custom health check**: Review logs for custom check failures

   ```bash
   grep -i "custom health check" /path/to/agent.log
   ```

### Health Check Times Out

If health checks are timing out:

1. **Database timeout**: Increase the timeout in your app configuration

   ```yaml
   apps:
     - name: my-agent-app
       health_check:
         database_timeout_seconds: 10.0
   ```

2. **Network issues**: Check network connectivity between the agent and dependent services

3. **Resource constraints**: Ensure the container has adequate CPU and memory

### Dev Mode Always Returns Healthy

When running with `dev_mode: true`, broker health checks always return healthy. This is expected behavior for local development. For production deployments, ensure dev_mode is disabled:

```yaml
broker:
  dev_mode: false
  # ... other broker configuration
```

## Related Documentation

- [solace-ai-connector Health Checks](https://github.com/SolaceLabs/solace-ai-connector/blob/main/docs/health_checks.md) - Underlying health check implementation
- [Kubernetes Deployment Guide](./kubernetes/kubernetes-deployment-guide.md) - Detailed Kubernetes deployment instructions
- [Logging Configuration](./logging.md) - Configure logging for health check debugging
- [Monitoring Your Agent Mesh](./observability.md) - Comprehensive observability features
