---
title: Getting Started with OpenTelemetry Metrics
sidebar_position: 2
---

:::info[Enterprise Only]
This feature is available in the Enterprise Edition only.
:::

This page introduces the core concepts behind Agent Mesh application metrics and walks you through enabling and verifying metrics collection.

For an overview of application metrics and how they fit into the Agent Mesh observability stack, see [Application Metrics with OpenTelemetry](./otel-metrics.md).

## Key Concepts

Before you configure application metrics, you need to understand the core concepts that shape how Agent Mesh collects and exposes telemetry.

### Metric Families

Agent Mesh Enterprise exposes two categories of metrics: histogram-based duration metrics for tracking latency distributions, and counter metrics for tracking resource consumption and request volumes. Each metric family includes a specific set of labels that provide contextual dimensions for filtering and grouping.

**Histogram metrics** capture latency distributions across application domains including outbound requests, LLM operations, gateway handling, database queries, and internal agent operations. These metrics enable you to calculate percentiles (P50, P95, P99) and understand tail latency characteristics.

**Counter metrics** track resource consumption such as LLM token usage and costs, as well as request volumes for gateway endpoints.

For complete details about all available metrics, including labels, default bucket configurations, and use cases, see [Metric Families Reference](./configuration.md#metric-families-reference).

### Histogram Buckets

Agent Mesh uses histogram instrumentation to record latency observations. When Agent Mesh records a latency measurement, it places the observation into predefined buckets, where each bucket represents an upper latency boundary. For example, a histogram might contain buckets such as `≤10ms`, `≤25ms`, `≤50ms`, `≤100ms`, `≤250ms`, `≤500ms`, `≤1s`, `≤2s`, `≤5s`.

Every time Agent Mesh records a latency value, it increments the counter of each bucket whose upper bound is greater than or equal to the observation. Over time, this produces a distribution that reflects how latency values spread across the system. Observability platforms can use these bucket counts to calculate percentiles dynamically without requiring raw data storage.

Histograms provide several advantages:

- **Distribution Preservation**: Unlike simple averages, histograms preserve the full latency distribution, allowing you to understand outliers and tail latency.
- **Dynamic Percentile Calculation**: Observability platforms can derive percentiles (P50, P95, P99) from histogram data without requiring additional storage or computation in Agent Mesh.
- **Flexible Analysis**: You can analyze the same histogram data in different ways over time, calculating different percentiles or aggregating across different dimensions.
- **OpenTelemetry Standard**: Histograms are the standard latency instrument in OpenTelemetry, ensuring compatibility with observability platforms and avoiding vendor lock-in.

Agent Mesh provides default bucket configurations optimized for each metric family based on observed latency characteristics in production workloads. You can customize bucket configurations to match your specific performance requirements. For more information, see [Customizing Histogram Buckets](./configuration.md#customizing-histogram-buckets).

### Integration Patterns

Agent Mesh supports two primary patterns for integrating metrics with observability platforms:

**Pull-Based Integration**: Agent Mesh components expose a `/metrics` endpoint in Prometheus-compatible format. Your observability platform periodically scrapes this endpoint to collect metrics. This pattern works with Datadog, Prometheus, Grafana, and other compatible collectors. It requires no additional infrastructure beyond what you already use for monitoring.

**Push-Based Integration (OpenTelemetry Collector)**: Agent Mesh supports pushing metrics to an OpenTelemetry Collector using the OpenTelemetry Protocol (OTLP). This pattern allows you to send telemetry to a colocated collector (such as a sidecar or node-level daemon) or directly to remote observability services.

For detailed integration setup instructions, see [Integrating OpenTelemetry Metrics](./integration.md).

## Prerequisites

Before you enable application metrics, ensure you have the following:

- **Agent Mesh Enterprise**: Application metrics with OpenTelemetry is an enterprise-only feature. For information about installing Agent Mesh Enterprise, see [Enterprise Installation](../installation.md).

- **Observability Platform** (optional at this stage): Although not required for initial testing, you need an observability platform such as Prometheus, Grafana, Datadog, or another compatible system to collect and visualize metrics in production.

## Enabling Metrics

You control application metrics through the `observability` configuration section in your component configuration files. By default, observability is disabled and you must explicitly enable it.

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

With this minimal configuration, your component begins collecting metrics using default bucket configurations and label sets. The component exposes the metrics endpoint at `/metrics` on its management server.

## Accessing the Metrics Endpoint

After you enable observability, your component exposes a Prometheus-compatible metrics endpoint. The endpoint location depends on your component's management server configuration, which is typically defined in the `management_server` section of your configuration.

By default, the management server runs on port `8080` and exposes the metrics endpoint at:

```
http://<component-host>:8080/metrics
```

To verify that Agent Mesh collects metrics, access this endpoint directly using a web browser or command-line tools such as `curl`:

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

This output confirms that Agent Mesh collects and exposes metrics correctly. Each line represents a histogram bucket with its associated labels and count.

:::note[Metrics Endpoint Security]
The `/metrics` endpoint exposes operational telemetry without authentication by default. In production environments, use network policies, firewall rules, or reverse proxy authentication to restrict access to authorized scraping services only.
:::

## Quick Verification

To verify that Agent Mesh collects metrics for active operations, perform a test:

1. **Trigger some activity**: Send a request through your agent mesh, such as asking a question through the web UI or invoking an agent directly.

2. **Check the metrics endpoint**: Access the `/metrics` endpoint again and look for metrics with labels matching your test activity. For example, if you invoked the `OrchestratorAgent`, look for lines containing `component_name="OrchestratorAgent"` in the `sam_operation_duration` metric.

3. **Observe bucket counts increasing**: As you perform more operations, the bucket counts in the histogram metrics increase, reflecting the latency distribution of your requests.

If you see metrics appearing and bucket counts increasing, your observability configuration works correctly and you are ready to integrate with an observability platform.

## What's Next

- [Configuring OpenTelemetry Metrics](./configuration.md): Customize metric families, histogram buckets, and cardinality settings
- [Integrating OpenTelemetry Metrics](./integration.md): Connect to DataDog, Prometheus, Grafana, or other observability platforms
- [Monitoring and Troubleshooting with Metrics](./monitoring.md): Build dashboards, define alerts, and diagnose common issues
