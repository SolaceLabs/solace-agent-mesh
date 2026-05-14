---
title: Monitoring and Troubleshooting with Metrics
sidebar_position: 5
---

:::info[Enterprise Only]
This feature is available in the Enterprise Edition only.
:::

This page provides practical guidance for monitoring Agent Mesh using OpenTelemetry metrics, including dashboard examples, alert rules, best practices, and troubleshooting.

For an introduction to application metrics and instructions for enabling them, see [Application Metrics with OpenTelemetry](./otel-metrics.md). For details about available metrics and configuration options, see [Configuring OpenTelemetry Metrics](./configuration.md). For integration setup, see [Integrating OpenTelemetry Metrics](./integration.md).

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
2. Enter the query for P95 latency by agent:
   ```promql
   histogram_quantile(0.95, sum(rate(sam_operation_duration_bucket{type="agent"}[5m])) by (component_name, le))
   ```
3. Set the visualization type to "Time series"
4. Configure display:
   - Legend: Show component_name
   - Y-axis: Seconds
   - Add threshold lines at your SLO values (for example, 5s warning, 10s critical)
5. Add a second query for request rate:
   ```promql
   sum(rate(sam_operation_duration_count{type="agent"}[5m])) by (component_name)
   ```

**Visualizing in DataDog:**

1. Navigate to Dashboards and select New Dashboard
2. Add a Timeseries widget
3. Use query: `p95:sam.operation.duration{type:agent} by {component_name}`
4. Set display type to "Line"
5. Add monitor thresholds to visualize SLO boundaries
6. Add a second widget showing request volume: `rate(sam.operation.duration.count{type:agent} by {component_name})`

**Alert Recommendations**: Alert when agent success rate drops below 95% or when latency percentiles exceed established SLO thresholds.

### LLM Cost and Token Tracking

Use the `sam.gen_ai.tokens.used` counter metric to track token consumption and estimate costs:

**Key Insights**:
- Sum token counts by model and token type (input versus output) over time periods
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

Prometheus: Gateway P95 latency by endpoint:
```promql
histogram_quantile(0.95, sum(rate(sam_gateway_duration_bucket[5m])) by (gateway_name, operation_name, le))
```

DataDog: Gateway error rate:
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
- Analyze latency distributions to detect bimodal patterns (for example, cache hits versus misses)

**Alert Recommendations**: Alert when P99 database latency exceeds 100ms or when specific collections show sustained performance degradation.

### Error Rates and Troubleshooting

Use the `error_type` label available on most metrics to analyze failures:

**Key Insights**:
- Calculate overall error rates by dividing failed operations by total operations
- Break down errors by component type, operation, or dependency to identify failure sources
- Track LLM provider errors to detect rate limiting or service degradation
- Monitor dependency errors to identify integration issues with external services

**Alert Recommendations**: Alert when error rates exceed baseline thresholds (typically 1-5%) or when new error types appear that were not previously observed.

## Creating Dashboards and Alerts

After you enable metrics collection and integrate with your observability platform, create dashboards and alerts to monitor Agent Mesh health and performance.

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

#### DataDog

**Agent Performance Dashboard**

1. Create a new dashboard in DataDog
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

#### DataDog Monitors

Create monitors in DataDog using the metric explorer or API:

**High Agent Latency Monitor:**
- Metric: `p95:sam.operation.duration{type:agent}`
- Alert threshold: Above 10 for five minutes
- Group by: `component_name`
- Notification: Alert when any agent exceeds threshold

**Gateway Error Rate Monitor:**
- Metric: Custom query combining error and total request rates
- Alert threshold: Above 5% for five minutes
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

**Monitor cardinality**: Use your observability platform's cardinality analysis tools to understand which metrics and labels contribute most to cardinality. DataDog provides cardinality dashboards that help identify high-cardinality metrics.

**Exclude high-cardinality labels**: If a label creates excessive cardinality without providing operational value, exclude it using the `exclude_labels` configuration. Common culprits include user identifiers, session IDs, or request IDs. For more information, see [Controlling Metric Cardinality](./configuration.md#controlling-metric-cardinality).

**Aggregate at query time**: Instead of creating metrics with high-cardinality labels, store metrics with lower-cardinality labels and perform aggregation or filtering at query time when needed.

### Bucket Configuration for Different Workloads

The default bucket configurations are optimized for typical production workloads, but you may need to adjust them based on your specific performance characteristics:

:::warning[Production Bucket Tuning]
Default bucket configurations are optimized for typical workloads but may not match your specific performance characteristics. Review actual latency distributions before deploying to production and adjust buckets accordingly.
:::

**Low-latency services**: For components with consistently low latency (such as local database operations), use finer-grained buckets in the low-latency range: `[0.001, 0.005, 0.01, 0.025, 0.05, 0.1]`.

**High-latency services**: For components with naturally higher latency (such as LLM inference or complex workflows), use coarser buckets with higher upper bounds: `[1.0, 5.0, 10.0, 30.0, 60.0, 120.0]`.

**Bimodal distributions**: If you observe bimodal latency distributions (for example, cache hits versus cache misses), ensure your bucket configuration has sufficient resolution in both ranges.

**Iterate based on observation**: Start with default buckets and adjust based on actual latency distributions. If most observations fall into a single bucket, you need finer granularity. If many buckets remain empty, you can reduce overhead with coarser granularity.

For more information about customizing buckets, see [Customizing Histogram Buckets](./configuration.md#customizing-histogram-buckets).

## Troubleshooting

This section addresses common issues you might encounter when configuring or using application metrics.

### Metrics Endpoint Not Accessible

**Symptom**: Accessing the `/metrics` endpoint returns a connection error or 404.

**Possible Causes**:
1. Observability is not enabled in configuration
2. The management server is not running or is configured on a different port
3. A firewall or network policy blocks access to the management server port

**Resolution**:
1. Verify that `observability.enabled` is set to `true` in your component configuration
2. Check the management server configuration and verify the port number
3. Use `curl` from the same host to verify local access: `curl http://localhost:8080/metrics`
4. Check firewall rules and Kubernetes network policies to ensure the port is accessible

### No Metrics Appearing

**Symptom**: The `/metrics` endpoint is accessible but returns no metrics or only default process metrics.

**Possible Causes**:
1. No operations have been performed yet to generate metrics
2. All metric families have been disabled by setting `exclude_labels: ['*']`
3. The component has not been restarted after configuration changes

**Resolution**:
1. Trigger some activity (send requests, invoke agents) to generate metric observations
2. Review your `distribution_metrics` configuration to ensure you have not disabled all metrics
3. Restart the component to apply configuration changes
4. Check application logs for errors related to metrics initialization

### High Cardinality Issues

**Symptom**: Your observability platform reports high cardinality or shows query performance degradation.

**Possible Causes**:
1. High-cardinality labels are not excluded (such as `owner.id` or session identifiers)
2. Many unique agents, tools, or components create numerous label combinations
3. Error types proliferate because of diverse failure modes

**Resolution**:
1. Use your observability platform's cardinality analysis tools to identify problematic labels
2. Exclude high-cardinality labels using the `exclude_labels` configuration
3. Consider whether you need per-component granularity or whether aggregating at the type level (`agent`, `tool`) is sufficient
4. Consolidate error types into broader categories if specific error messages create excessive cardinality

### Bucket Configuration Not Applied

**Symptom**: Custom bucket configurations do not appear in the metrics output; Agent Mesh uses default buckets instead.

**Possible Causes**:
1. Configuration syntax errors prevent Agent Mesh from parsing the custom configuration
2. The metric family name is incorrect or does not match the expected format
3. The component has not been restarted after configuration changes

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
3. Label values are empty or null and Agent Mesh omits them from output

**Resolution**:
1. Review your `exclude_labels` configuration to ensure you have not inadvertently excluded required labels
2. Verify that the label applies to the specific metric family and operation you are observing
3. Check application logs for warnings about missing or null label values

## Next Steps

After you configure dashboards and alerts, consider these next steps:

1. **Integrate with incident response**: Connect your metrics-based alerts to your incident management system (PagerDuty, Opsgenie, and similar services)
2. **Optimize cardinality**: Review cardinality in your observability platform and exclude high-cardinality labels that do not provide operational value
3. **Tune bucket configurations**: After collecting baseline metrics, adjust histogram buckets to match your specific latency characteristics
4. **Set up log correlation**: Configure OTLP log export to correlate metrics with application logs for troubleshooting

## Additional Resources

For more information about Agent Mesh observability and related topics, see:

- [Application Metrics with OpenTelemetry](./otel-metrics.md): Overview of application metrics, key concepts, and getting started guide
- [Configuring OpenTelemetry Metrics](./configuration.md): Complete reference for metric families and configuration
- [Integrating OpenTelemetry Metrics](./integration.md): OTLP exporter setup and DataDog quick start
- [Monitoring Agent Mesh](../../installing-and-configuring/observability.md): Overview of runtime observability features including activity viewer, broker monitoring, and stimulus logs
- [Health Checks](../../installing-and-configuring/health-checks.md): Kubernetes-compatible health check endpoints for liveness, readiness, and startup probes
- [Logging Configuration](../../installing-and-configuring/logging.md): Application logging configuration and best practices
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/): Official OpenTelemetry project documentation