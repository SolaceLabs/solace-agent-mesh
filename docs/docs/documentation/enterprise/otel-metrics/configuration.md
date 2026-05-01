---
title: Configuring OpenTelemetry Metrics
sidebar_position: 3
---

:::info[Enterprise Only]
This feature is available in the Enterprise Edition only.
:::

This page provides a complete reference for configuring application metrics in Agent Mesh Enterprise, including all available metric families, histogram bucket customization, cardinality control, and management server settings.

For an introduction to application metrics and instructions for enabling them, see [Application Metrics with OpenTelemetry](./otel-metrics.md).

## Metric Families Reference

This section provides detailed information about each metric family, including what it measures, the labels it uses, default bucket configurations, and common use cases.

### `sam.outbound.request.duration`

**Description**: Measures the latency of outbound service-to-service requests that Agent Mesh components initiate, including calls to external services, internal APIs, or downstream components.

**Purpose**: Provides visibility into the responsiveness and reliability of dependencies. This metric helps you identify latency introduced by remote services and detect failures in external integrations.

**Labels**:
- `service_peer_name`: Remote service being called (for example, `solace_broker`, `artifact_service`)
- `operation_name`: Operation being performed (for example, `publish`, `list`, `save`, `load`)
- `error_type`: Error classification (`none`, `4xx_error`, `5xx_error`)

**Default Buckets**: `[0.01, 0.025, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0]` (seconds)

**Use Cases**:
- Monitor dependency latency to understand external service performance
- Detect slow or failing external integrations
- Establish SLOs for outbound service calls
- Identify dependencies that contribute most to overall latency

For monitoring examples, see [Error Rates and Troubleshooting](./monitoring.md#error-rates-and-troubleshooting).

### `sam.gen_ai.client.operation.duration`

**Description**: Measures total LLM inference latency from request submission to complete response receipt.

**Purpose**: Enables monitoring of overall model performance and responsiveness, which is critical for understanding end-to-end agent execution time and defining AI-related SLOs.

**Labels**:
- `gen_ai_request_model`: Model being used (for example, `openai/gpt-4`, `google/gemini-2.5-flash`)
- `error_type`: Error classification (`none`, `4xx_error`, `5xx_error`)

**Default Buckets**: `[1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]` (seconds)

**Use Cases**:
- Monitor LLM inference latency across different models
- Compare performance characteristics of different model providers
- Establish SLOs for AI-powered operations
- Detect rate limiting or service degradation from LLM providers
- Correlate latency with token counts or request sizes

For monitoring examples, see [LLM Cost and Token Tracking](./monitoring.md#llm-cost-and-token-tracking).

### `sam.gen_ai.client.operation.ttft.duration`

**Description**: Measures time-to-first-token (TTFT) for LLM responses, capturing the time between request submission and the first token being received.

**Purpose**: Provides insight into perceived responsiveness for streaming or interactive AI responses. TTFT helps distinguish model startup latency from total inference time.

**Labels**:
- `gen_ai_request_model`: Model being used
- `error_type`: Error classification

**Default Buckets**: `[0.5, 1.0, 2.0, 3.0, 5.0, 10.0]` (seconds)

**Use Cases**:
- Optimize user experience for streaming responses
- Distinguish between model cold-start latency and processing time
- Compare TTFT across different model providers
- Establish responsiveness SLOs for interactive AI features

### `sam.db.duration`

**Description**: Measures latency of database operations that Agent Mesh components perform, such as queries, reads, writes, or transactions.

**Purpose**: Helps identify slow database interactions and bottlenecks in persistence layers, supporting database performance tuning and reliability monitoring.

**Labels**:
- `db_collection_name`: Collection or table being accessed (for example, `sessions`, `tasks`, `projects`)
- `db_operation_name`: Operation type (`query`, `insert`, `update`, `delete`)
- `error_type`: Error classification

**Default Buckets**: `[0.005, 0.01, 0.025, 0.05, 0.1, 1.0, 5.0]` (seconds)

**Use Cases**:
- Identify slow database queries that require optimization
- Monitor database operation error rates
- Establish database performance SLOs
- Detect database connection pool saturation or resource contention

### `sam.gateway.duration`

**Description**: Measures latency of requests that Agent Mesh gateways handle, from the time the gateway receives an inbound request to the time it returns or forwards a response.

**Purpose**: Provides visibility into gateway-level performance, helping you monitor request handling efficiency and overall entry-point responsiveness of the system.

**Labels**:
- `gateway_name`: Gateway handling the request (for example, `WebUIGateway`, `MCPGateway`)
- `operation_name`: Endpoint or operation being invoked (for example, `/sessions`, `/tasks`, `/message`)
- `error_type`: Error classification

**Default Buckets**: `[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]` (seconds)

**Use Cases**:
- Monitor user-facing API performance
- Establish gateway-level SLOs for responsiveness
- Identify slow endpoints that require optimization
- Detect gateway overload or resource saturation

### `sam.gateway.ttfb.duration`

**Description**: Measures time-to-first-byte latency for gateway requests, capturing the time from request receipt to the first byte of response data.

**Purpose**: Provides visibility into gateway-level responsiveness, helping you distinguish startup latency from total processing time for streaming responses versus the first byte sent into output.

**Labels**:
- `gateway_name`: Gateway handling the request
- `operation_name`: Endpoint or operation being invoked
- `error_type`: Error classification

**Default Buckets**: `[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 1.0]` (seconds)

**Use Cases**:
- Optimize perceived responsiveness for streaming endpoints
- Distinguish between gateway startup latency and data processing time
- Establish TTFB SLOs for interactive user experiences

### `sam.operation.duration`

**Description**: Measures latency of internal Agent Mesh operations, representing the execution time of logical application-level tasks that agents and tools perform.

**Purpose**: Provides insight into the internal performance of Agent Mesh workflows and business logic, enabling you to detect slow operations and define service-level objectives for core system functionality.

**Labels**:
- `component_name`: Component performing the operation (for example, `OrchestratorAgent`, `WebAgent`, tool names)
- `operation_name`: Logical operation being performed (typically `execute`)
- `type`: Component type (`agent`, `tool`, `connector`)
- `error_type`: Error classification

**Default Buckets**: `[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0]` (seconds)

**Use Cases**:
- Monitor agent execution latency
- Compare performance across different agents
- Identify slow tools or operations that require optimization
- Establish agent-level performance SLOs

For monitoring examples, see [Agent Health and Utilization](./monitoring.md#agent-health-and-utilization).

### `sam.gen_ai.tokens.used`

**Description**: Tracks input and output token consumption for LLM requests across components and models.

**Purpose**: Enables cost analysis and budget tracking by monitoring token usage. This metric is essential for understanding and controlling LLM infrastructure costs.

**Labels**:
- `component_name`: Component making the LLM request (for example, `OrchestratorAgent`, `WebAgent`)
- `gen_ai_request_model`: Model being used (for example, `openai/gpt-4`, `google/gemini-2.5-flash`)
- `gen_ai_token_type`: Token type (`input`, `output`)

**Use Cases**:
- Track token consumption by agent to identify high-cost components
- Monitor token usage by model to optimize model selection
- Calculate estimated LLM costs by multiplying token counts by model pricing
- Establish token budgets and alert on budget overruns

For monitoring examples, see [LLM Cost and Token Tracking](./monitoring.md#llm-cost-and-token-tracking).

### `sam.gen_ai.cost.total`

**Description**: Tracks estimated LLM cost per component and model based on token consumption and model pricing.

**Purpose**: Provides direct cost visibility for LLM operations without manual calculation.

**Labels**:
- `component_name`: Component making the LLM request
- `gen_ai_request_model`: Model being used

**Use Cases**:
- Monitor LLM costs in real time
- Track cost trends over time
- Identify cost optimization opportunities

:::note[Pricing Availability]
This metric requires model pricing information to be available in the system. Pricing may not be available for all models, in which case Agent Mesh does not populate this metric. Use `sam.gen_ai.tokens.used` with manual pricing calculations as a fallback.
:::

### `sam.gateway.requests`

**Description**: Tracks HTTP request counts for gateway endpoints, broken down by route, method, and outcome.

**Purpose**: Provides traffic analysis and error rate monitoring for gateway operations.

**Labels**:
- `gateway_name`: Gateway handling the request (for example, `WebUIGateway`, `MCPGateway`)
- `http_method`: HTTP method used (`GET`, `POST`, `PATCH`, `PUT`, `DELETE`)
- `route_template`: Route template being accessed (for example, `/api/v1/sessions`, `/api/v1/tasks`)
- `error_type`: Error classification (`none`, `4xx_error`, `5xx_error`)

**Use Cases**:
- Monitor request volumes by endpoint
- Calculate error rates for gateway operations
- Identify the most frequently accessed endpoints
- Track traffic patterns over time

## Fine-Grained Configuration

The `observability` configuration section controls all aspects of metrics collection. The following example shows all available options:

```yaml
management_server:
  enabled: true
  port: 8080
  observability:
    enabled: true                      # Enable/disable metrics collection (default: false)
    metric_prefix: sam                 # Prefix prepended to all metric names (default: "sam")
        
    # Optional: Customize histogram metrics
    distribution_metrics:
      outbound.request.duration:
        buckets: [0.001, 0.01, 0.1, 0.5, 1.0, 5.0, 10.0]
        exclude_labels: [operation_name]
          
      gen_ai.client.operation.duration:            
        exclude_labels: [tokens]
          
      db.duration:
        buckets: [0.001, 0.01, 0.1, 0.5, 1.0]
        exclude_labels: ['*']           # This metric is effectively disabled
        
    # Optional: Customize counter and gauge metrics
    value_metrics:
      gen_ai.tokens.used:
        exclude_labels: [owner.id]
```

### Configuration Fields

**`enabled`** (boolean, default: `false`): Controls whether metrics collection is active. When set to `false`, Agent Mesh does not expose the metrics endpoint and does not collect telemetry.

**`path`** (string, default: `"/metrics"`): URL path where Agent Mesh exposes the metrics endpoint on the management server.

**`metric_prefix`** (string, default: `"sam"`): Prefix prepended to all metric names. This allows you to namespace Agent Mesh metrics within your broader observability infrastructure. For example, with the default prefix `sam`, Agent Mesh names the outbound request duration metric `sam_outbound_request_duration`.

**`distribution_metrics`** (object, optional): Allows you to customize histogram-based metrics by specifying custom bucket configurations or excluding specific labels. Each key in this object corresponds to a metric family name (without the prefix). If you do not specify this field, Agent Mesh uses default configurations.

**`value_metrics`** (object, optional): Allows you to customize counter and gauge metrics by excluding specific labels to control cardinality. Each key in this object corresponds to a metric family name (without the prefix).

## Customizing Histogram Buckets

Each histogram metric family has default bucket configurations optimized for observed latency characteristics. However, you may want to customize buckets to match your specific performance requirements or to focus on particular latency ranges.

To customize buckets for a metric family, specify the `buckets` array under the metric's configuration:

```yaml
observability:
  enabled: true
  metric_prefix: sam
  distribution_metrics:
    gateway.duration:
      buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
```

Bucket values are specified in seconds. The system automatically adds an `+Inf` bucket to capture all observations regardless of latency.

:::tip[Bucket Configuration Strategy]
Start with default bucket configurations and adjust based on observed latency distributions. If most observations fall into a single bucket, add finer granularity. If many buckets remain empty, use coarser intervals to reduce overhead.
:::

**Choosing Bucket Boundaries**: Effective bucket configurations depend on your specific performance characteristics and monitoring goals:

- **Narrow ranges for critical operations**: If you need fine-grained visibility into low-latency operations (such as database queries), use smaller bucket increments in the relevant range: `[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.5, 1.0]`.

- **Wider ranges for high-latency operations**: For operations with naturally higher latency (such as LLM inference), use larger bucket increments: `[1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]`.

- **Percentile accuracy trade-offs**: More buckets provide more accurate percentile calculations but increase metric cardinality and storage requirements. Fewer buckets reduce overhead but may miss latency characteristics.

**Disabling Metrics**: To disable a specific metric family entirely, set its `exclude_labels` array to `['*']`:

```yaml
observability:
  enabled: true
  distribution_metrics:
    gen_ai.client.operation.ttft.duration:
      exclude_labels: ['*'] # Disables TTFT metric collection
```

## Controlling Metric Cardinality

Metric cardinality refers to the number of unique time series created by combining all label values. High cardinality can lead to increased storage costs and query performance issues in your observability platform. Agent Mesh provides label exclusion capabilities to help you control cardinality.

:::warning[Cardinality Management]
High-cardinality labels can significantly increase storage costs and degrade query performance in your observability platform. Monitor cardinality metrics and exclude labels that do not provide operational value.
:::

To exclude specific labels from a metric, use the `exclude_labels` array:

```yaml
observability:
  enabled: true
  distribution_metrics:
    outbound.request.duration:
      exclude_labels: [operation_name]  # Only track by service and error type

```

When you exclude a label, Agent Mesh does not attach it to metric observations, reducing the number of unique time series.

**When to Exclude Labels**: Consider excluding labels in these scenarios:

- **High-cardinality identifiers**: Labels such as `operation_name`, if the number of operations in your deployment drives the number of unique time series too high.

- **Unused dimensions**: If you do not need to analyze metrics by a particular dimension, excluding the label reduces overhead without losing useful information.

- **Cost optimization**: If your observability platform charges based on the number of unique time series, excluding labels can reduce costs by consolidating metrics.

**Trade-offs**: Excluding labels reduces your ability to filter and group metrics by those dimensions. Only exclude labels that you are confident you do not need for analysis or troubleshooting.

## Management Server Configuration

Agent Mesh exposes the metrics endpoint through the management server, which also provides health check endpoints. The management server configuration controls the port and paths for these operational endpoints.

The following example shows a management server configuration:

```yaml
management_server:
  enabled: true
  port: 8080
  
  health:
    enabled: true
    liveness_path: /healthz
    readiness_path: /readyz
    startup_path: /startup
  
  observability:
    enabled: true
    path: /metrics
    metric_prefix: sam
```

For more information about the management server and health checks, see [Health Checks](../../deploying/health-checks.md).

## What's Next

- [Integrating OpenTelemetry Metrics](./integration.md): Integration patterns including a DataDog quick-start walkthrough and OTLP exporter configuration
- [Monitoring and Troubleshooting with Metrics](./monitoring.md): Dashboard examples, alert rules, best practices, and troubleshooting guidance