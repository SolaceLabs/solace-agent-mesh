---
title: Application Metrics with OpenTelemetry
sidebar_position: 25
---

:::info[Enterprise Only]
This feature is available in the Enterprise Edition only.
:::

Agent Mesh Enterprise provides application metrics instrumentation powered by OpenTelemetry, enabling you to monitor system health, performance trends, and resource utilization through industry-standard observability tools. You can shift from reactive log analysis to proactive, metrics-first observability.

## Overview

Application metrics provide aggregated insights into system behavior over time, complementing the request-level visibility you get from the activity viewer, stimulus logs, and broker monitoring. While those tools help you understand individual request flows and debug specific issues, metrics enable you to detect performance degradation, establish service-level objectives (SLOs), define alerts, and integrate Agent Mesh telemetry into your organization's existing observability stack.

For more information about activity viewer, stimulus logs, and broker monitoring, see [Monitoring Your Agent Mesh](../deploying/observability.md).

Agent Mesh Enterprise instruments critical application domains with latency-based histogram metrics, providing visibility into agent performance, LLM operations, gateway behavior, database interactions, and external dependencies. Agent Mesh exposes these metrics through a standard Prometheus-compatible `/metrics` endpoint and can be integrated with observability platforms such as Prometheus, Grafana, Datadog, Dynatrace, Splunk, and other OpenTelemetry-compatible systems.

### Why Use OpenTelemetry Metrics

Metrics-based observability provides several important benefits for production deployments:

**Proactive Health Monitoring**: Establish baseline performance characteristics and detect anomalies before they impact users. Metrics provide early warning signals for degraded performance, resource saturation, or increasing error rates.

**Service-Level Objectives**: Define and measure SLOs based on latency percentiles, error rates, and throughput. Metrics give you the data needed to establish realistic performance targets and track your progress toward them.

**Capacity Planning**: Understand resource utilization trends over time to make informed decisions about scaling, resource allocation, and infrastructure optimization.

**Integration with Existing Stacks**: OpenTelemetry is an industry-standard observability framework supported by all major observability vendors. This vendor-neutral approach allows you to integrate Agent Mesh metrics into your existing monitoring infrastructure without specialized tools or proprietary integrations.

**Cost Visibility**: Track LLM token consumption and estimated costs across agents and models to understand and optimize AI infrastructure spending.

**Operational Alerting**: Define alerts based on metric thresholds or anomaly detection to enable rapid response to performance degradation or system failures.

### Relationship to Other Observability Features

Agent Mesh provides multiple observability capabilities that work together to create a complete picture of system behavior:

**Activity Viewer and Stimulus Logs**: Provide detailed, request-level visibility into how individual queries flow through your agent mesh. These tools excel at understanding specific interactions and debugging complex multi-agent workflows.

**Broker Monitoring**: Shows real-time message flows through the Solace event broker, giving you visibility into communication patterns between components.

**Application Metrics** (this feature): Provide aggregated, time-series data about system performance, health, and resource utilization. Metrics answer questions about trends, capacity, and overall system behavior rather than individual request details.

Think of metrics as your high-level health dashboard, while stimulus logs and the activity viewer serve as your diagnostic tools when you need to understand specific issues. Metrics tell you that latency increased; stimulus logs and the activity viewer tell you why.

## Key Concepts

Before you configure application metrics, you need to understand the core concepts that shape how Agent Mesh collects and exposes telemetry.

### Metric Families

Agent Mesh Enterprise exposes two categories of metrics: histogram-based duration metrics for tracking latency distributions, and counter metrics for tracking resource consumption and request volumes. Each metric family includes a specific set of labels that provide contextual dimensions for filtering and grouping.

**Histogram metrics** capture latency distributions across application domains including outbound requests, LLM operations, gateway handling, database queries, and internal agent operations. These metrics enable you to calculate percentiles (P50, P95, P99) and understand tail latency characteristics.

**Counter metrics** track resource consumption such as LLM token usage and costs, as well as request volumes for gateway endpoints.

For complete details about all available metrics, including labels, default bucket configurations, and use cases, see [Metric Families Reference](#metric-families-reference).

### Histogram Buckets

Agent Mesh uses histogram instrumentation to record latency observations. When Agent Mesh records a latency measurement, it places the observation into predefined buckets, where each bucket represents an upper latency boundary. For example, a histogram might contain buckets such as `≤10ms`, `≤25ms`, `≤50ms`, `≤100ms`, `≤250ms`, `≤500ms`, `≤1s`, `≤2s`, `≤5s`.

Every time Agent Mesh records a latency value, it increments the counter of each bucket whose upper bound is greater than or equal to the observation. Over time, this produces a distribution that reflects how latency values are spread across the system. Observability platforms can use these bucket counts to calculate percentiles dynamically without requiring raw data storage.

Histograms provide several important advantages:

**Distribution Preservation**: Unlike simple averages, histograms preserve the full latency distribution, allowing you to understand outliers, tail latency, and the shape of performance characteristics.

**Dynamic Percentile Calculation**: Observability platforms can derive percentiles (P50, P95, P99) from histogram data without requiring additional storage or computation in Agent Mesh.

**Flexible Analysis**: You can analyze the same histogram data in different ways over time, calculating different percentiles or aggregating across different dimensions as your monitoring needs evolve.

**OpenTelemetry Standard**: Histograms are the standard latency instrument in OpenTelemetry, ensuring compatibility with observability platforms and avoiding vendor lock-in.

Agent Mesh provides default bucket configurations optimized for each metric family based on observed latency characteristics in production workloads. You can customize bucket configurations to match your specific performance requirements. For more information, see [Customizing Histogram Buckets](#customizing-histogram-buckets).

### Integration Patterns

Agent Mesh supports two primary patterns for integrating metrics with observability platforms:

**Pull-Based Integration**: Agent Mesh components expose a `/metrics` endpoint in Prometheus-compatible format. Your observability platform periodically scrapes this endpoint to collect metrics. This pattern works with Datadog, Prometheus, Grafana, and other compatible collectors. It is simple to configure and requires no additional infrastructure beyond what you already use for monitoring.

**Push-Based Integration (OpenTelemetry Collector)**: Agent Mesh supports pushing metrics to an OpenTelemetry Collector using the OpenTelemetry Protocol (OTLP). This pattern allows you to send telemetry to a colocated collector (such as a sidecar or node-level daemon) or directly to remote observability services.

## Getting Started

This section walks you through the basic steps to enable metrics and verify that telemetry is being collected correctly.

### Prerequisites

Before you enable application metrics, ensure you have the following:

- **Agent Mesh Enterprise**: Application metrics with OpenTelemetry is an enterprise-only feature. For information about installing Agent Mesh Enterprise, see [Enterprise Installation](./installation.md).

- **Agent Mesh Version**: Ensure you are running a version of Agent Mesh Enterprise that includes OpenTelemetry metrics support (version 1.20.0 or later).

- **Observability Platform** (optional at this stage): Although not required for initial testing, you will eventually need an observability platform such as Prometheus, Grafana, Datadog, or another compatible system to collect and visualize metrics.

### Enabling Metrics

You control application metrics through the `observability` configuration section in your component configuration files. By default, observability is disabled and must be explicitly enabled.

To enable metrics, add the following configuration to your component configuration file (for example, your agent or gateway configuration):

```yaml
management_server:
  enabled: true
  port: 8080

  observability:
    enabled: true
    metric_prefix: sam
```

The `enabled` field controls whether metrics collection is active. The `metric_prefix` field specifies the prefix prepended to all metric names, allowing you to namespace Agent Mesh metrics within your broader observability infrastructure. The default prefix is `sam`.

With this minimal configuration, your component will begin collecting metrics using default bucket configurations and label sets. The metrics endpoint will be exposed at `/metrics` on the component's management server.

### Accessing the Metrics Endpoint

Once observability is enabled, your component exposes a Prometheus-compatible metrics endpoint. The endpoint location depends on your component's management server configuration, which is typically defined in the `management_server` section of your configuration.

By default, the management server runs on port `8080` and exposes the metrics endpoint at:

```
http://<component-host>:8080/metrics
```

To verify that metrics are being collected, you can access this endpoint directly using a web browser or command-line tools such as `curl`:

```bash
curl http://localhost:8080/metrics
```

You should see output in Prometheus text format, with lines such as:

```
# HELP sam_outbound_request_duration Outbound request latency
# TYPE sam_outbound_request_duration histogram
sam_outbound_request_duration_bucket{service_peer_name="solace_broker",operation_name="publish",error_type="none",le="0.01"} 45
sam_outbound_request_duration_bucket{service_peer_name="solace_broker",operation_name="publish",error_type="none",le="0.025"} 102
sam_outbound_request_duration_bucket{service_peer_name="solace_broker",operation_name="publish",error_type="none",le="0.1"} 215
...
```

This output confirms that metrics are being collected and exposed correctly. Each line represents a histogram bucket with its associated labels and count.

:::note[Metrics Endpoint Security]
The `/metrics` endpoint exposes operational telemetry without authentication by default. In production environments, use network policies, firewall rules, or reverse proxy authentication to restrict access to authorized scraping services only.
:::

### Quick Verification

To verify that metrics are being collected for active operations, perform a simple test:

1. **Trigger some activity**: Send a request through your agent mesh, such as asking a question through the web UI or invoking an agent directly.

2. **Check the metrics endpoint**: Access the `/metrics` endpoint again and look for metrics with labels matching your test activity. For example, if you invoked the `OrchestratorAgent`, look for lines containing `component_name="OrchestratorAgent"` in the `sam_operation_duration` metric.

3. **Observe bucket counts increasing**: As you perform more operations, the bucket counts in the histogram metrics should increase, reflecting the latency distribution of your requests.

If you see metrics appearing and bucket counts increasing, your observability configuration is working correctly and you are ready to integrate with an observability platform.

## Configuration Reference

This section provides detailed information about configuring application metrics. It starts with a complete reference of all available metrics and their labels, then covers how to enable, disable, and customize metric collection.

### Metric Families Reference

This section provides detailed information about each metric family, including what it measures, the labels it uses, default bucket configurations, and common use cases.

#### `sam.outbound.request.duration`

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

For monitoring examples, see [Error Rates and Troubleshooting](#error-rates-and-troubleshooting).

#### `sam.gen_ai.client.operation.duration`

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

For monitoring examples, see [LLM Cost and Token Tracking](#llm-cost-and-token-tracking).

#### `sam.gen_ai.client.operation.ttft.duration`

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

#### `sam.db.duration`

**Description**: Measures latency of database operations that Agent Mesh components perform, such as queries, reads, writes, or transactions.

**Purpose**: Helps identify slow database interactions and bottlenecks in persistence layers, supporting database performance tuning and reliability monitoring.

**Labels**:
- `db_collection_name`: Collection or table being accessed (for example, `sessions`, `tasks`, `projects`)
- `db_operation_name`: Operation type (`query`, `insert`, `update`, `delete`)
- `error_type`: Error classification

**Default Buckets**: `[0.005, 0.01, 0.025, 0.05, 0.1, 1.0, 5.0]` (seconds)

**Use Cases**:
- Identify slow database queries requiring optimization
- Monitor database operation error rates
- Establish database performance SLOs
- Detect database connection pool saturation or resource contention

#### `sam.gateway.duration`

**Description**: Measures latency of requests that Agent Mesh gateways handle, from the time the gateway receives an inbound request to the time a response is returned or forwarded for processing.

**Purpose**: Provides visibility into gateway-level performance, helping monitor request handling efficiency and overall entry-point responsiveness of the system.

**Labels**:
- `gateway_name`: Gateway handling the request (for example, `WebUIGateway`, `MCPGateway`)
- `operation_name`: Endpoint or operation being invoked (for example, `/sessions`, `/tasks`, `/message`)
- `error_type`: Error classification

**Default Buckets**: `[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]` (seconds)

**Use Cases**:
- Monitor user-facing API performance
- Establish gateway-level SLOs for responsiveness
- Identify slow endpoints requiring optimization
- Detect gateway overload or resource saturation

#### `sam.gateway.ttfb.duration`

**Description**: Measures time-to-first-byte latency for gateway requests, capturing the time from request receipt to the first byte of response data.

**Purpose**: Provides visibility into gateway-level responsiveness, helping distinguish startup latency from total processing time for streaming responses versus first byte sent into output.

**Labels**:
- `gateway_name`: Gateway handling the request
- `operation_name`: Endpoint or operation being invoked
- `error_type`: Error classification

**Default Buckets**: `[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 1.0]` (seconds)

**Use Cases**:
- Optimize perceived responsiveness for streaming endpoints
- Distinguish between gateway startup latency and data processing time
- Establish TTFB SLOs for interactive user experiences

#### `sam.operation.duration`

**Description**: Measures latency of internal Agent Mesh operations, representing the execution time of logical application-level tasks performed by agents and tools.

**Purpose**: Provides insight into the internal performance of Agent Mesh workflows and business logic, enabling operators to detect slow operations and define service-level objectives for core system functionality.

**Labels**:
- `component_name`: Component performing the operation (for example, `OrchestratorAgent`, `WebAgent`, tool names)
- `operation_name`: Logical operation being performed (typically `execute`)
- `type`: Component type (`agent`, `tool`, `connector`)
- `error_type`: Error classification

**Default Buckets**: `[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0]` (seconds)

**Use Cases**:
- Monitor agent execution latency
- Compare performance across different agents
- Identify slow tools or operations requiring optimization
- Establish agent-level performance SLOs

For monitoring examples, see [Agent Health and Utilization](#agent-health-and-utilization).

#### `sam.gen_ai.tokens.used`

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

For monitoring examples, see [LLM Cost and Token Tracking](#llm-cost-and-token-tracking).

#### `sam.gen_ai.cost.total`

**Description**: Tracks estimated LLM cost per component and model based on token consumption and model pricing.

**Purpose**: Provides direct cost visibility for LLM operations without manual calculation.

**Labels**:
- `component_name`: Component making the LLM request
- `gen_ai_request_model`: Model being used

**Use Cases**:
- Monitor LLM costs in real-time
- Track cost trends over time
- Identify cost optimization opportunities

:::note[Pricing Availability]
This metric requires model pricing information to be available in the system. Pricing may not be available for all models, in which case this metric will not be populated. Use `sam.gen_ai.tokens.used` with manual pricing calculations as a fallback.
:::

#### `sam.gateway.requests`

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
- Identify most frequently accessed endpoints
- Track traffic patterns over time

### Fine-Grained Configuration

The `observability` configuration section controls all aspects of metrics collection. Here is a complete example showing all available options:

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
        exclude_labels: [*]           # This metric is effectively disabled
        
    # Optional: Customize counter and gauge metrics
    value_metrics:
      gen_ai.tokens.used:
        exclude_labels: [owner.id]
```

### Configuration Fields

**`enabled`** (boolean, default: `false`): Controls whether metrics collection is active. When set to `false`, the metrics endpoint is not exposed and no telemetry is collected.

**`metric_prefix`** (string, default: `"sam"`): Prefix prepended to all metric names. This allows you to namespace Agent Mesh metrics within your broader observability infrastructure. For example, with the default prefix `sam`, the outbound request duration metric is named `sam_outbound_request_duration`.

**`distribution_metrics`** (object, optional): Allows you to customize histogram-based metrics by specifying custom bucket configurations or excluding specific labels. Each key in this object corresponds to a metric family name (without the prefix). If not specified, default configurations are used.

**`value_metrics`** (object, optional): Allows you to customize counter and gauge metrics by excluding specific labels to control cardinality. Each key in this object corresponds to a metric family name (without the prefix).

### Customizing Histogram Buckets

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

- **Percentile accuracy trade-offs**: More buckets provide more accurate percentile calculations but increase metric cardinality and storage requirements. Fewer buckets reduce overhead but may miss important latency characteristics.

**Disabling Metrics**: To disable a specific metric family entirely, set its `exclude_labels` array to [*]:

```yaml
observability:
  enabled: true
  distribution_metrics:
    gen_ai.client.operation.ttft.duration:
      exclude_labels: [*] # Disables TTFT metric collection
```

### Controlling Metric Cardinality

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

When a label is excluded, it is not attached to metric observations, reducing the number of unique time series.

**When to Exclude Labels**: Consider excluding labels in these scenarios:

- **High-cardinality identifiers**: Labels such as `operation_name` - in case if number of operations in your deployment drive numbers of unique time series too high.

- **Unused dimensions**: If you do not need to analyze metrics by a particular dimension, excluding the label reduces overhead without losing useful information.

- **Cost optimization**: If your observability platform charges based on the number of unique time series, excluding labels can reduce costs by consolidating metrics.

**Trade-offs**: Excluding labels reduces your ability to filter and group metrics by those dimensions. Only exclude labels that you are confident you will not need for analysis or troubleshooting.

### Management Server Configuration

The metrics endpoint is exposed through the management server, which also provides health check endpoints. The management server configuration controls the port and paths used for these operational endpoints.

Here is an example management server configuration:

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

The `observability.path` field specifies the endpoint path for metrics (default: `/metrics`). The `observability.metric_prefix` field duplicates the top-level `metric_prefix` setting for convenience; both fields have the same effect.

For more information about the management server and health checks, see [Health Checks](../deploying/health-checks.md).

## Integration Patterns

Agent Mesh Enterprise exports metrics using the OpenTelemetry Protocol (OTLP), enabling integration with any OTLP-compatible observability platform. You can send metrics directly to DataDog Cloud, route them through a DataDog Agent, or forward them to an OpenTelemetry Collector for centralized telemetry processing. Agent Mesh also exposes a Prometheus-compatible `/metrics` endpoint for pull-based collection if needed.

### Quick Start: DataDog Integration

This section provides a complete production blueprint for integrating Agent Mesh metrics with DataDog in Kubernetes.

#### Prerequisites

- Kubernetes cluster
- DataDog account with API key
- Agent Mesh Enterprise deployed

#### Step 1: Deploy DataDog Agent

Deploy the DataDog agent as a DaemonSet with OTLP receivers enabled (one-time setup, approximately 5 minutes):

**Create the DataDog API key secret:**

```bash
kubectl create secret generic datadog-secret \
  --namespace kube-system \
  --from-literal=api-key=${DD_API_KEY}
```

**Create a manifest file `datadog-agent.yaml`:**

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: datadog
  namespace: kube-system
spec:
  selector:
    matchLabels:
      app: datadog
  template:
    metadata:
      labels:
        app: datadog
    spec:
      containers:
      - name: agent
        image: gcr.io/datadoghq/agent:7
        env:
          - name: DD_API_KEY
            valueFrom:
              secretKeyRef:
                name: datadog-secret
                key: api-key
          - name: DD_SITE
            value: datadoghq.com
          - name: DD_OTLP_CONFIG_RECEIVER_PROTOCOLS_HTTP_ENDPOINT
            value: "0.0.0.0:4318"
          - name: DD_OTLP_CONFIG_RECEIVER_PROTOCOLS_GRPC_ENDPOINT
            value: "0.0.0.0:4317"
        ports:
          - containerPort: 4318
            name: otlp-http
          - containerPort: 4317
            name: otlp-grpc
---
apiVersion: v1
kind: Service
metadata:
  name: datadog
  namespace: kube-system
spec:
  internalTrafficPolicy: Local
  selector:
    app: datadog
  ports:
    - name: otlp-http
      port: 4318
      targetPort: 4318
    - name: otlp-grpc
      port: 4317
      targetPort: 4317
```

**Apply the manifest:**

```bash
kubectl apply -f datadog-agent.yaml
```

This deploys a DaemonSet with one agent per node that receives OTLP telemetry and forwards it to DataDog Cloud.

#### Step 2: Enable Observability in Agent Mesh

Create a management server configuration file (for example, `configs/management_server.yaml`):

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

  exporters:
    - type: otlp
      endpoint: http://datadog.kube-system.svc.cluster.local:4318
      protocol: http
      metrics: true
      logs: false
      compression: gzip
      timeout: 10
```

Include this configuration file when starting Agent Mesh:

```bash
solace-agent-mesh run configs/my_agent.yaml configs/management_server.yaml
```

#### Step 3: Add Environment Tags

Add environment variables to your container deployment to enable automatic service and environment tagging in DataDog:

```yaml
env:
  - name: OTEL_SERVICE_NAME
    value: my-service
  - name: OTEL_RESOURCE_ATTRIBUTES
    value: "deployment.environment=production"
```

DataDog automatically creates the following tags from these variables:
- `service:my-service`
- `env:production`

#### Verification

Metrics appear in the DataDog Metrics Explorer under the `sam.*` prefix within 5 minutes. To verify:

1. Navigate to DataDog Metrics Explorer
2. Search for `sam.operation.duration`
3. Filter by `service:my-service` and `env:production`
4. Create visualizations and dashboards using the queries from [Creating Dashboards and Alerts](#creating-dashboards-and-alerts)

#### Querying Metrics in DataDog

DataDog automatically converts OpenTelemetry histogram metrics to native DataDog distributions, allowing you to use DataDog's query language:

```
# P95 latency by agent
p95:sam.operation.duration{type:agent} by {component_name}

# Total token usage (24 hours)
sum:sam.gen_ai.tokens.used.rollup(sum, 86400) by {gen_ai_request_model}

# Gateway error rate
sum:sam.gateway.requests{error_type:4xx_error OR error_type:5xx_error}.as_rate() / 
sum:sam.gateway.requests{*}.as_rate()
```

### OTLP Exporter Configuration

This section describes how to configure OTLP exporters for sending metrics and logs to observability backends.

#### Configuration Parameters

Add exporter configuration to your component's `management_server` section. You can configure multiple exporters to send telemetry to different backends simultaneously.

```yaml
management_server:
  enabled: true
  port: 8080
  
  observability:
    enabled: true
    metric_prefix: sam
  
  exporters:
    - type: otlp
      endpoint: http://datadog.kube-system.svc.cluster.local:4318
      protocol: http
      metrics: true
      logs: false
      compression: gzip
      timeout: 10
```

**`type`** (required): Exporter type. Currently only `otlp` is supported.

**`endpoint`** (required): OTLP endpoint URL. For HTTP protocol, the path `/v1/metrics` or `/v1/logs` is automatically appended. Examples:
- DataDog Agent in Kubernetes: `http://datadog.kube-system.svc.cluster.local:4318`
- DataDog Cloud direct: `https://api.datadoghq.com`
- OpenTelemetry Collector: `http://localhost:4318`

**`protocol`** (required): Transport protocol. Valid values: `http`, `grpc`.

**`metrics`** (optional, default: `false`): Enable metric export to this endpoint. Must explicitly set to `true` to export metrics.

**`logs`** (optional, default: `false`): Enable log export to this endpoint. Must explicitly set to `true` to export logs.

**`log_level`** (optional, default: `INFO`): Minimum log level to export. Valid values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

**`headers`** (optional): Custom headers to include in requests. Supports environment variable substitution using `${VAR_NAME}` syntax. Useful for authentication tokens or API keys.

**`compression`** (optional, default: `none`): Compression algorithm. Valid values: `none`, `gzip`, `deflate`.

**`timeout`** (optional, default: `10`): Request timeout in seconds.

**`insecure`** (optional, default: `false`): Skip TLS certificate verification. Only use for development or testing.

**`certificate_file`** (optional): Path to custom CA certificate file for TLS verification.

#### Common Integration Patterns

**DataDog Agent (Recommended for Kubernetes)**: Deploy the DataDog agent as a DaemonSet and send telemetry to the agent, which forwards to DataDog Cloud:

```yaml
exporters:
  - type: otlp
    endpoint: http://datadog.kube-system.svc.cluster.local:4318
    protocol: http
    metrics: true
    logs: false
    compression: gzip
```

**DataDog Cloud Direct**: Send metrics directly to DataDog's OTLP ingestion endpoint without an intermediate agent:

```yaml
exporters:
  - type: otlp
    endpoint: https://api.datadoghq.com
    protocol: http
    headers:
      DD-API-KEY: ${DD_API_KEY}
    metrics: true
    logs: false
```

**OpenTelemetry Collector**: Deploy an OpenTelemetry Collector as a sidecar or DaemonSet for centralized telemetry processing:

```yaml
exporters:
  - type: otlp
    endpoint: http://localhost:4318
    protocol: http
    metrics: true
    logs: true
    log_level: INFO
```

**Multiple Backends**: Configure multiple exporters to send different telemetry to different backends:

```yaml
exporters:
  # Send all metrics to DataDog
  - type: otlp
    endpoint: https://api.datadoghq.com
    protocol: http
    headers:
      DD-API-KEY: ${DD_API_KEY}
    metrics: true
    logs: false
  
  # Send only ERROR logs to New Relic
  - type: otlp
    endpoint: https://otlp.nr-data.net:4317
    protocol: grpc
    headers:
      api-key: ${NR_LICENSE_KEY}
    metrics: false
    logs: true
    log_level: ERROR
```

#### Benefits of OTLP Export

**Vendor Neutrality**: OTLP is an industry-standard protocol supported by all major observability platforms (DataDog, Grafana, Dynatrace, Splunk, New Relic), avoiding vendor lock-in.

**Centralized Telemetry Pipelines**: Route all telemetry through an OpenTelemetry Collector for centralized processing, filtering, sampling, and forwarding to multiple backends.

**Multi-Backend Support**: Send the same telemetry to multiple observability platforms simultaneously without duplication in Agent Mesh configuration.

**Log and Metric Correlation**: Export application logs alongside metrics to the same backend, enabling correlated analysis for troubleshooting.

**Secure Credential Management**: Securely inject API keys and authentication tokens through environment variables rather than hardcoding credentials in configuration files.

## Common Monitoring Scenarios

This section provides practical guidance for common monitoring scenarios using the available metrics.

### Agent Health and Utilization

Use the `sam.operation.duration` metric to monitor agent health and performance:

**Key Insights**:
- Monitor request rates per agent to identify busy or underutilized agents
- Track latency percentiles (P50, P95, P99) to understand agent response time characteristics
- Calculate success rates by comparing successful requests (`error_type="none"`) to total requests
- Identify agents with degraded performance by comparing current latency to historical baselines

**Visualizing in Grafana:**

1. Create a new panel and select your Prometheus datasource
2. Enter query for P95 latency by agent:
   ```promql
   histogram_quantile(0.95, sum(rate(sam_operation_duration_bucket{type="agent"}[5m])) by (component_name, le))
   ```
3. Set visualization type to "Time series"
4. Configure display:
   - Legend: Show component_name
   - Y-axis: Seconds
   - Add threshold lines at your SLO values (for example, 5s warning, 10s critical)
5. Add a second query for request rate:
   ```promql
   sum(rate(sam_operation_duration_count{type="agent"}[5m])) by (component_name)
   ```

**Visualizing in Datadog:**

1. Navigate to Dashboards → New Dashboard
2. Add a Timeseries widget
3. Use query: `p95:sam.operation.duration{type:agent} by {component_name}`
4. Set display type to "Line"
5. Add monitor thresholds to visualize SLO boundaries
6. Add a second widget showing request volume: `rate(sam.operation.duration.count{type:agent} by {component_name})`

**Alert Recommendations**: Alert when agent success rate drops below 95% or when latency percentiles exceed established SLO thresholds.

### LLM Cost and Token Tracking

Use the `sam.gen_ai.tokens.used` counter metric to track token consumption and estimate costs:

**Key Insights**:
- Sum token counts by model and token type (input vs. output) over time periods
- Calculate estimated costs by multiplying token counts by model pricing (pricing varies by provider and model)
- Identify high-cost agents or models by grouping token usage by `component_name` and `gen_ai_request_model`
- Track token usage trends over time to forecast budgets and identify usage spikes

**Alert Recommendations**: Set budget alerts based on daily or monthly token consumption thresholds. Alert when costs exceed expected values or when usage patterns change unexpectedly.

### Gateway Performance

Use `sam.gateway.duration` and `sam.gateway.ttfb.duration` metrics to monitor gateway performance:

**Key Insights**:
- Monitor latency percentiles by endpoint to identify slow operations
- Track request rates by endpoint to understand traffic patterns
- Analyze time-to-first-byte (TTFB) for streaming endpoints to optimize perceived responsiveness
- Calculate error rates by comparing failed requests to total requests

**Example Queries:**

Prometheus - Gateway P95 latency by endpoint:
```promql
histogram_quantile(0.95, sum(rate(sam_gateway_duration_bucket[5m])) by (gateway_name, operation_name, le))
```

Datadog - Gateway error rate:
```
sum:sam.gateway.requests{error_type:4xx_error OR error_type:5xx_error}.as_rate() / sum:sam.gateway.requests{*}.as_rate()
```

**Alert Recommendations**: Alert when gateway latency exceeds SLOs (for example, P95 > 500ms) or when error rates exceed acceptable thresholds (typically 1-5%).

### Database Performance

Use the `sam.db.duration` metric to monitor database operations:

**Key Insights**:
- Monitor latency percentiles by collection and operation type to identify slow queries
- Track query volume by collection to understand database load patterns
- Identify collections with degraded performance by comparing current latency to historical baselines
- Analyze latency distributions to detect bimodal patterns (for example, cache hits vs. misses)

**Alert Recommendations**: Alert when P99 database latency exceeds 100ms or when specific collections show sustained performance degradation.

### Error Rates and Troubleshooting

Use the `error_type` label available on most metrics to analyze failures:

**Key Insights**:
- Calculate overall error rates by dividing failed operations by total operations
- Break down errors by component type, operation, or dependency to identify failure sources
- Track LLM provider errors to detect rate limiting or service degradation
- Monitor dependency errors to identify integration issues with external services

**Alert Recommendations**: Alert when error rates exceed baseline thresholds (typically 1-5%) or when new error types appear that weren't previously observed.

## Creating Dashboards and Alerts

After you enable metrics collection and integrate with your observability platform, you need to create dashboards and alerts to monitor Agent Mesh health and performance.

### Example Dashboard Panels

This section provides examples for creating dashboard panels in common observability platforms.

#### Grafana with Prometheus

**Panel 1: Agent Latency Percentiles by Component**

Query:
```promql
histogram_quantile(0.95, sum(rate(sam_operation_duration_bucket{type="agent"}[5m])) by (component_name, le))
```

Visualization type: Time series  
Display: Multiple lines (one per agent)  
Threshold markers: Warning at 5s, Critical at 10s

**Panel 2: LLM Token Consumption Rate**

Query:
```promql
sum(rate(sam_gen_ai_tokens_used[5m])) by (gen_ai_request_model, gen_ai_token_type)
```

Visualization type: Stacked area chart  
Legend: Show model and token type

**Panel 3: Gateway Error Rate**

Query:
```promql
sum(rate(sam_gateway_requests{error_type!="none"}[5m])) / sum(rate(sam_gateway_requests[5m]))
```

Visualization type: Time series  
Format: Percentage  
Threshold markers: Warning at 1%, Critical at 5%

**Panel 4: Database Operation Latency by Collection**

Query:
```promql
histogram_quantile(0.99, sum(rate(sam_db_duration_bucket[5m])) by (db_collection_name, le))
```

Visualization type: Bar gauge  
Display: Current value per collection

#### Datadog

**Agent Performance Dashboard**

1. Create a new dashboard in Datadog
2. Add a Timeseries widget with query:
   ```
   p95:sam.operation.duration{type:agent} by {component_name}
   ```
3. Set visualization to Line graph
4. Add monitor threshold overlay at your SLO value

**Cost Tracking Dashboard**

1. Add a Query Value widget with query:
   ```
   sum:sam.gen_ai.cost.total{*}.rollup(sum, 86400)
   ```
2. Format as currency
3. Add a Timeseries widget showing cost trends over 30 days

### Defining Alert Rules

#### Prometheus Alert Rules

Add these rules to your Prometheus configuration:

```yaml
groups:
  - name: agent_mesh_alerts
    interval: 30s
    rules:
      # Alert when agent P95 latency exceeds 10 seconds
      - alert: HighAgentLatency
        expr: histogram_quantile(0.95, sum(rate(sam_operation_duration_bucket{type="agent"}[5m])) by (component_name, le)) > 10
        for: 5m
        labels:
          severity: warning
          component: agent_mesh
        annotations:
          summary: "Agent {{ $labels.component_name }} P95 latency exceeds 10s"
          description: "Agent {{ $labels.component_name }} has P95 latency of {{ $value }}s, exceeding the 10s threshold."
      
      # Alert when gateway error rate exceeds 5%
      - alert: HighGatewayErrorRate
        expr: |
          sum(rate(sam_gateway_requests{error_type!="none"}[5m])) by (gateway_name) 
          / 
          sum(rate(sam_gateway_requests[5m])) by (gateway_name) 
          > 0.05
        for: 5m
        labels:
          severity: critical
          component: agent_mesh
        annotations:
          summary: "Gateway {{ $labels.gateway_name }} error rate exceeds 5%"
          description: "Gateway {{ $labels.gateway_name }} has {{ $value | humanizePercentage }} error rate."
      
      # Alert when LLM latency is abnormally high
      - alert: HighLLMLatency
        expr: histogram_quantile(0.95, sum(rate(sam_gen_ai_client_operation_duration_bucket[5m])) by (gen_ai_request_model, le)) > 30
        for: 10m
        labels:
          severity: warning
          component: agent_mesh
        annotations:
          summary: "LLM {{ $labels.gen_ai_request_model }} P95 latency exceeds 30s"
          description: "Model {{ $labels.gen_ai_request_model }} has P95 latency of {{ $value }}s."
      
      # Alert when database operations are slow
      - alert: SlowDatabaseOperations
        expr: histogram_quantile(0.99, sum(rate(sam_db_duration_bucket[5m])) by (db_collection_name, le)) > 1.0
        for: 5m
        labels:
          severity: warning
          component: agent_mesh
        annotations:
          summary: "Database collection {{ $labels.db_collection_name }} P99 latency exceeds 1s"
          description: "Collection {{ $labels.db_collection_name }} has P99 latency of {{ $value }}s."
      
      # Alert when daily LLM costs exceed budget
      - alert: LLMCostBudgetExceeded
        expr: sum(increase(sam_gen_ai_cost_total[24h])) > 100
        labels:
          severity: info
          component: agent_mesh
        annotations:
          summary: "Daily LLM costs exceed $100"
          description: "Total LLM costs in the last 24 hours: ${{ $value }}."
```

#### Datadog Monitors

Create monitors in Datadog using the metric explorer or API:

**High Agent Latency Monitor:**
- Metric: `p95:sam.operation.duration{type:agent}`
- Alert threshold: Above 10 for 5 minutes
- Group by: `component_name`
- Notification: Alert when any agent exceeds threshold

**Gateway Error Rate Monitor:**
- Metric: Custom query combining error and total request rates
- Alert threshold: Above 5% for 5 minutes
- Group by: `gateway_name`

**Cost Budget Monitor:**
- Metric: `sum:sam.gen_ai.cost.total{*}.rollup(sum, 86400)`
- Alert threshold: Above daily budget value
- Notification: Warning when approaching budget, critical when exceeded

### Choosing Alert Thresholds

When defining alert thresholds, consider these factors:

**Baseline Performance**: Establish baseline metrics from normal operation before setting thresholds. What is typical P95 latency for your agents? What is your normal error rate?

**SLO Alignment**: Align alert thresholds with your service-level objectives. If you commit to 99.9% uptime, alert before you risk breaching that SLO.

**Alert Fatigue**: Set thresholds that indicate genuine problems, not normal variance. Use the `for:` clause in Prometheus rules to require sustained threshold violations before alerting.

**Severity Levels**: Use multiple severity levels (info, warning, critical) to distinguish between "awareness needed" and "immediate action required."

## Best Practices

This section provides guidance on operating Agent Mesh observability in production environments.

### Metric Cardinality Management

High cardinality is one of the most common challenges in metrics-based observability. Every unique combination of label values creates a separate time series, and excessive cardinality can lead to increased storage costs and query performance degradation.

**Monitor cardinality**: Use your observability platform's cardinality analysis tools to understand which metrics and labels contribute most to cardinality. Datadog provides cardinality dashboards that help identify high-cardinality metrics.

**Exclude high-cardinality labels**: If a label creates excessive cardinality without providing operational value, exclude it using the `exclude_labels` configuration. Common culprits include user identifiers, session IDs, or request IDs.

**Aggregate at query time**: Instead of creating metrics with high-cardinality labels, store metrics with lower-cardinality labels and perform aggregation or filtering at query time when needed.

### Bucket Configuration for Different Workloads

The default bucket configurations are optimized for typical production workloads, but you may need to adjust them based on your specific performance characteristics:

:::warning[Production Bucket Tuning]
Default bucket configurations are optimized for typical workloads but may not match your specific performance characteristics. Review actual latency distributions before deploying to production and adjust buckets accordingly.
:::

**Low-latency services**: For components with consistently low latency (such as local database operations), use finer-grained buckets in the low-latency range: `[0.001, 0.005, 0.01, 0.025, 0.05, 0.1]`.

**High-latency services**: For components with naturally higher latency (such as LLM inference or complex workflows), use coarser buckets with higher upper bounds: `[1.0, 5.0, 10.0, 30.0, 60.0, 120.0]`.

**Bimodal distributions**: If you observe bimodal latency distributions (for example, cache hits vs. cache misses), ensure your bucket configuration has sufficient resolution in both ranges.

**Iterate based on observation**: Start with default buckets and adjust based on actual latency distributions. If most observations fall into a single bucket, you may need finer granularity. If many buckets remain empty, you may be able to reduce overhead with coarser granularity.

## Troubleshooting

This section addresses common issues you might encounter when configuring or using application metrics.

### Metrics Endpoint Not Accessible

**Symptom**: Accessing the `/metrics` endpoint returns a connection error or 404.

**Possible Causes**:
1. Observability is not enabled in configuration
2. Management server is not running or is configured on a different port
3. Firewall or network policy blocks access to the management server port

**Resolution**:
1. Verify that `observability.enabled` is set to `true` in your component configuration
2. Check the management server configuration and verify the port number
3. Use `curl` from the same host to verify local access: `curl http://localhost:8080/metrics`
4. Check firewall rules and Kubernetes network policies to ensure the port is accessible

### No Metrics Appearing

**Symptom**: The `/metrics` endpoint is accessible but returns no metrics or only default process metrics.

**Possible Causes**:
1. No operations have been performed yet to generate metrics
2. All metric families have been disabled by setting `exclude_labels: [*]`
3. Component has not been restarted after configuration changes

**Resolution**:
1. Trigger some activity (send requests, invoke agents) to generate metric observations
2. Review your `distribution_metrics` configuration to ensure you have not disabled all metrics
3. Restart the component to apply configuration changes
4. Check application logs for errors related to metrics initialization

### High Cardinality Issues

**Symptom**: Observability platform reports high cardinality or shows query performance degradation.

**Possible Causes**:
1. High-cardinality labels are not excluded (such as `owner.id` or session identifiers)
2. Many unique agents, tools, or components create numerous label combinations
3. Error types proliferate due to diverse failure modes

**Resolution**:
1. Use your observability platform's cardinality analysis tools to identify problematic labels
2. Exclude high-cardinality labels using the `exclude_labels` configuration
3. Consider whether you need per-component granularity or whether aggregating at the type level (`agent`, `tool`) is sufficient
4. Consolidate error types into broader categories if specific error messages create excessive cardinality

### Bucket Configuration Not Applied

**Symptom**: Custom bucket configurations do not appear in the metrics output; default buckets are used instead.

**Possible Causes**:
1. Configuration syntax errors prevent the custom configuration from being parsed
2. Metric family name is incorrect or does not match expected format
3. Component has not been restarted after configuration changes

**Resolution**:
1. Verify that the metric family name in your configuration matches the documented name (without the `sam_` prefix)
2. Check application logs for configuration parsing errors
3. Restart the component to apply configuration changes
4. Use the `/metrics` endpoint to verify that the expected bucket boundaries appear in the histogram metrics

### Missing Labels in Metrics

**Symptom**: Expected labels are missing from metric output.

**Possible Causes**:
1. Labels have been excluded in the `exclude_labels` configuration
2. The component or operation does not provide that label (for example, not all operations have a `db_collection_name`)
3. Label values are empty or null and are omitted from output

**Resolution**:
1. Review your `exclude_labels` configuration to ensure you have not inadvertently excluded required labels
2. Verify that the label is applicable to the specific metric family and operation you are observing
3. Check application logs for warnings about missing or null label values

## Next Steps

After enabling and configuring OpenTelemetry metrics, consider these next steps:

1. **Create dashboards**: Use the examples in [Creating Dashboards and Alerts](#creating-dashboards-and-alerts) to build monitoring dashboards in your observability platform
2. **Define alerts**: Set up alert rules for critical metrics like agent latency, gateway error rates, and LLM costs
3. **Integrate with incident response**: Connect your metrics-based alerts to your incident management system (PagerDuty, Opsgenie, etc.)
4. **Optimize cardinality**: Review cardinality in your observability platform and exclude high-cardinality labels that do not provide operational value
5. **Tune bucket configurations**: After collecting baseline metrics, adjust histogram buckets to match your specific latency characteristics
6. **Set up log correlation**: Configure OTLP log export to correlate metrics with application logs for troubleshooting

## Additional Resources

For more information about Agent Mesh observability and related topics, see:

- [Monitoring Your Agent Mesh](../deploying/observability.md): Overview of runtime observability features including activity viewer, broker monitoring, and stimulus logs
- [Health Checks](../deploying/health-checks.md): Kubernetes-compatible health check endpoints for liveness, readiness, and startup probes
- [Logging Configuration](../deploying/logging.md): Application logging configuration and best practices
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/): Official OpenTelemetry project documentation