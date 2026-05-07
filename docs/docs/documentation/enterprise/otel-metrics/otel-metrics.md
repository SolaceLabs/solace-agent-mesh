---
title: Application Metrics with OpenTelemetry
sidebar_position: 1
---

:::info[Enterprise Only]
This feature is available in the Enterprise Edition only.
:::

Agent Mesh Enterprise provides application metrics instrumentation powered by OpenTelemetry, enabling you to monitor system health, performance trends, and resource utilization through industry-standard observability tools.

## Overview

Application metrics provide aggregated insights into system behavior over time, complementing the request-level visibility you get from the activity viewer, stimulus logs, and broker monitoring. While those tools help you understand individual request flows and debug specific issues, metrics enable you to detect performance degradation, establish service-level objectives (SLOs), define alerts, and integrate Agent Mesh telemetry into your organization's existing observability stack.

For more information about activity viewer, stimulus logs, and broker monitoring, see [Monitoring Your Agent Mesh](../../deploying/observability.md).

Agent Mesh Enterprise instruments critical application domains with latency-based histogram metrics, providing visibility into agent performance, LLM operations, gateway behavior, database interactions, and external dependencies. Agent Mesh exposes these metrics through a standard Prometheus-compatible `/metrics` endpoint and can integrate with observability platforms such as Prometheus, Grafana, Datadog, Dynatrace, Splunk, and other OpenTelemetry-compatible systems.

### Why Use OpenTelemetry Metrics

Metrics-based observability provides several benefits for production deployments:

- **Proactive Health Monitoring**: Establish baseline performance characteristics and detect anomalies before they impact users.
- **Service-Level Objectives**: Define and measure SLOs based on latency percentiles, error rates, and throughput.
- **Capacity Planning**: Understand resource utilization trends over time to make informed scaling decisions.
- **Integration with Existing Stacks**: OpenTelemetry is an industry-standard framework supported by all major observability vendors, allowing you to integrate Agent Mesh metrics without specialized tools.
- **Cost Visibility**: Track LLM token consumption and estimated costs across agents and models.
- **Operational Alerting**: Define alerts based on metric thresholds to enable rapid response to performance degradation.

### Relationship to Other Observability Features

Agent Mesh provides multiple observability capabilities that work together:

| Feature | Purpose |
|---|---|
| **Activity Viewer and Stimulus Logs** | Request-level visibility into how individual queries flow through your agent mesh |
| **Broker Monitoring** | Real-time message flows through the Solace event broker |
| **Application Metrics** (this feature) | Aggregated, time-series data about system performance, health, and resource utilization |

Metrics serve as your high-level health dashboard, while stimulus logs and the activity viewer serve as your diagnostic tools. Metrics tell you that latency increased; stimulus logs and the activity viewer tell you why.

## In This Section

- [Getting Started](./overview.md): Key concepts, prerequisites, enabling metrics, and verifying your setup
- [Configuring OpenTelemetry Metrics](./configuration.md): Complete reference for all metric families, histogram bucket customization, cardinality control, and management server settings
- [Integrating OpenTelemetry Metrics](./integration.md): Integration patterns including a DataDog quick-start walkthrough and OTLP exporter configuration
- [Monitoring and Troubleshooting with Metrics](./monitoring.md): Dashboard examples, alert rules, best practices, and troubleshooting guidance
