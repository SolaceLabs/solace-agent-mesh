---
title: Integrating OpenTelemetry Metrics
sidebar_position: 4
---

:::info[Enterprise Only]
This feature is available in the Enterprise Edition only.
:::

This page describes how to integrate Agent Mesh Enterprise metrics with observability platforms using the OpenTelemetry Protocol (OTLP) or Prometheus-compatible scraping.

For an introduction to application metrics and instructions for enabling them, see [Application Metrics with OpenTelemetry](./otel-metrics.md). For details about available metrics and configuration options, see [Configuring OpenTelemetry Metrics](./configuration.md).

## Integration Patterns

Agent Mesh Enterprise exports metrics using the OpenTelemetry Protocol (OTLP), enabling integration with any OTLP-compatible observability platform. You can send metrics directly to DataDog Cloud, route them through a DataDog Agent, or forward them to an OpenTelemetry Collector for centralized telemetry processing. Agent Mesh also exposes a Prometheus-compatible `/metrics` endpoint for pull-based collection if needed.

## Quick Start: DataDog Integration

This section provides a complete production blueprint for integrating Agent Mesh metrics with DataDog in Kubernetes.

### Prerequisites

- Kubernetes cluster
- DataDog account with API key
- Agent Mesh Enterprise deployed

### Step 1: Deploy the DataDog Agent

Deploy the DataDog agent as a DaemonSet with OTLP receivers enabled:

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

### Step 2: Enable Observability in Agent Mesh

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

### Step 3: Add Environment Tags

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

### Verification

Metrics appear in the DataDog Metrics Explorer under the `sam.*` prefix within five minutes. To verify:

1. Navigate to DataDog Metrics Explorer
2. Search for `sam.operation.duration`
3. Filter by `service:my-service` and `env:production`
4. Create visualizations and dashboards using the queries from [Creating Dashboards and Alerts](./monitoring.md#creating-dashboards-and-alerts)

### Querying Metrics in DataDog

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

## OTLP Exporter Configuration

This section describes how to configure OTLP exporters for sending metrics and logs to observability backends.

### Configuration Parameters

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

**`endpoint`** (required): OTLP endpoint URL. For HTTP protocol, Agent Mesh automatically appends the path `/v1/metrics` or `/v1/logs`. Examples:
- DataDog Agent in Kubernetes: `http://datadog.kube-system.svc.cluster.local:4318`
- DataDog Cloud direct: `https://api.datadoghq.com`
- OpenTelemetry Collector: `http://localhost:4318`

**`protocol`** (required): Transport protocol. Valid values: `http`, `grpc`.

**`metrics`** (optional, default: `false`): Enable metric export to this endpoint. You must explicitly set this to `true` to export metrics.

**`logs`** (optional, default: `false`): Enable log export to this endpoint. You must explicitly set this to `true` to export logs.

**`log_level`** (optional, default: `INFO`): Minimum log level to export. Valid values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

**`headers`** (optional): Custom headers to include in requests. Supports environment variable substitution using `${VAR_NAME}` syntax. Useful for authentication tokens or API keys.

**`compression`** (optional, default: `none`): Compression algorithm. Valid values: `none`, `gzip`, `deflate`.

**`timeout`** (optional, default: `10`): Request timeout in seconds.

**`insecure`** (optional, default: `false`): Skip TLS certificate verification. Only use for development or testing.

**`certificate_file`** (optional): Path to custom CA certificate file for TLS verification.

### Common Integration Patterns

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

### Benefits of OTLP Export

**Vendor Neutrality**: OTLP is an industry-standard protocol supported by all major observability platforms (DataDog, Grafana, Dynatrace, Splunk, New Relic), avoiding vendor lock-in.

**Centralized Telemetry Pipelines**: Route all telemetry through an OpenTelemetry Collector for centralized processing, filtering, sampling, and forwarding to multiple backends.

**Multi-Backend Support**: Send the same telemetry to multiple observability platforms simultaneously without duplication in Agent Mesh configuration.

**Log and Metric Correlation**: Export application logs alongside metrics to the same backend, enabling correlated analysis for troubleshooting.

**Secure Credential Management**: Inject API keys and authentication tokens through environment variables rather than hardcoding credentials in configuration files.

## What's Next

- [Monitoring and Troubleshooting with Metrics](./monitoring.md): Dashboard examples, alert rules, best practices, and troubleshooting guidance
- [Configuring OpenTelemetry Metrics](./configuration.md): Complete reference for metric families, histogram buckets, and cardinality control