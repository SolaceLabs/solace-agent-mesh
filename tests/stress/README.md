# HTTP SSE Gateway Stress Tests

Stress test harness for validating the SAM HTTP SSE gateway under load.

> **Note:** Stress tests are excluded from normal CI/CD runs. They must be run explicitly using the commands below.

## Quick Start

```bash
# Run all stress tests with smoke profile (~6 min)
.venv/bin/python -m pytest tests/stress/scenarios/ -v --stress-scale=smoke

# Run with JSON reports
.venv/bin/python -m pytest tests/stress/scenarios/ -v --stress-scale=smoke \
    --stress-report=/path/to/report.json
```

> Stress tests are excluded from `pytest tests/` by default via `--ignore=tests/stress` in `pyproject.toml`.

## Scale Profiles

| Profile | SSE Connections | Sessions | Duration | Use Case |
|---------|-----------------|----------|----------|----------|
| `smoke` | 3 | 2 | 5s | Quick validation |
| `small` | 5 | 3 | 10s | Development testing |
| `medium` | 25 | 10 | 30s | CI/CD integration |
| `large` | 100 | 50 | 60s | Pre-release validation |
| `soak` | 10 | 5 | 300s | Memory leak detection |

```bash
# Examples
--stress-scale=smoke   # Quick CI check
--stress-scale=medium  # Standard testing
--stress-scale=large   # Load testing
--stress-scale=soak    # Long-running stability
```

## Test Scenarios

### Concurrent SSE Connections (`test_sse_concurrent.py`)

Tests SSEManager's ability to handle multiple simultaneous connections.

```bash
.venv/bin/python -m pytest tests/stress/scenarios/test_sse_concurrent.py -v --stress-scale=smoke
```

**Tests:**
- `test_concurrent_sse_connections[N]` - N concurrent SSE connections receiving events
- `test_sse_connection_churn` - Rapid connect/disconnect cycles
- `test_concurrent_task_submission_burst` - Burst of simultaneous task submissions

### WebUI/A2A Isolation (`test_webui_a2a_isolation.py`)

Validates that WebUI REST endpoints don't affect A2A streaming and vice versa.

```bash
.venv/bin/python -m pytest tests/stress/scenarios/test_webui_a2a_isolation.py -v --stress-scale=smoke
```

**Tests:**
- `test_webui_load_doesnt_affect_a2a_streaming` - Heavy WebUI load during A2A streaming
- `test_a2a_streaming_doesnt_affect_webui_response_time` - A2A load during WebUI requests
- `test_mixed_workload_stability` - Sustained mixed workload

### Large Artifacts (`test_large_artifacts.py`)

Tests artifact upload/download during SSE streaming.

```bash
.venv/bin/python -m pytest tests/stress/scenarios/test_large_artifacts.py -v --stress-scale=smoke
```

**Tests:**
- `test_large_upload_during_streaming[N]` - Upload N MB artifact during streaming
- `test_concurrent_uploads_and_downloads` - Multiple concurrent artifact operations
- `test_large_download_during_streaming` - Download large artifact during streaming
- `test_artifact_size_limits` - Various artifact sizes (1KB to 5MB)

### Session Scalability (`test_session_scalability.py`)

Tests session management under load.

```bash
.venv/bin/python -m pytest tests/stress/scenarios/test_session_scalability.py -v --stress-scale=smoke
```

**Tests:**
- `test_many_concurrent_sessions[N]` - N concurrent sessions with A2A tasks
- `test_session_isolation` - Sessions receive only their own responses
- `test_sustained_session_load` - Continuous session creation over time

### Soak Tests (`test_soak.py`)

Long-running stability and memory leak detection.

```bash
.venv/bin/python -m pytest tests/stress/scenarios/test_soak.py -v --stress-scale=soak
```

**Tests:**
- `test_extended_streaming_soak` - Extended streaming with memory monitoring
- `test_connection_leak_detection` - Detect connection leaks over 100 cycles
- `test_cache_growth_monitoring` - Monitor SSEManager cache growth
- `test_queue_overflow_handling` - Handle queue overflow gracefully

## CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--stress-scale=PROFILE` | Scale profile (smoke/small/medium/large/soak) | `small` |
| `--stress-report=PATH` | Save JSON reports to path | None |
| `--stress-duration=SECONDS` | Override test duration | Profile default |

## Environment Variables

Override configuration via environment:

```bash
export STRESS_CONCURRENT_SSE=50
export STRESS_CONCURRENT_SESSIONS=20
export STRESS_DURATION=60
export STRESS_SOAK_DURATION=600
export STRESS_MAX_P99_LATENCY=1000
export STRESS_MAX_ERROR_RATE=5
```

## Test Markers

Run specific test categories:

```bash
# All stress tests
pytest -m stress

# Long-running soak tests only
pytest -m long_soak

# Isolation tests only
pytest -m isolation

# Artifact tests only
pytest -m artifacts

# Scalability tests only
pytest -m scalability
```

## JSON Reports

When using `--stress-report`, individual JSON reports are generated per test:

```
stress_report_test_concurrent_sse_connections[25].json
stress_report_test_webui_load_doesnt_affect_a2a_streaming.json
stress_report_test_large_upload_during_streaming[10].json
```

Report structure:

```json
{
  "metadata": {
    "test_name": "test_concurrent_sse_connections[25]",
    "timestamp": "2026-01-31T10:13:35.150264",
    "duration_seconds": 0.406
  },
  "summary": {
    "total_errors": 0,
    "operations_count": 2
  },
  "operations": {
    "task_submit": {
      "percentiles": {
        "p50": 0.034,
        "p95": 0.540,
        "p99": 0.643,
        "min": 0.027,
        "max": 0.643,
        "mean": 0.104,
        "count": 25
      },
      "throughput_per_sec": 61.5,
      "error_rate_percent": 0.0
    }
  },
  "counters": {
    "tasks_submitted": 25,
    "events_received": 100
  },
  "gauges": {
    "successful_connections": 25,
    "failed_connections": 0
  },
  "memory": {
    "start_mb": 0.0,
    "end_mb": 0.0,
    "growth_mb": 0.0
  },
  "errors": []
}
```

## Directory Structure

```
tests/stress/
├── README.md                         # This file
├── conftest.py                       # Fixtures and configuration
├── metrics/
│   ├── collector.py                  # Latency, throughput, error collection
│   └── reporter.py                   # Console/JSON report generation
├── harness/
│   ├── sse_client.py                 # Async SSE client with metrics
│   ├── http_client.py                # Async HTTP client with metrics
│   └── artifact_generator.py         # Large artifact generation
└── scenarios/
    ├── test_sse_concurrent.py        # Concurrent SSE connections
    ├── test_webui_a2a_isolation.py   # WebUI vs A2A isolation
    ├── test_large_artifacts.py       # Artifact handling during streaming
    ├── test_session_scalability.py   # Many simultaneous sessions
    └── test_soak.py                  # Long-running memory leak tests
```

## Thresholds

Default pass/fail thresholds (configurable via scale profiles):

| Metric | Threshold |
|--------|-----------|
| Task submit p99 latency | < 500ms (smoke: 1000ms) |
| SSE event p99 latency | < 500ms |
| Error rate | < 1% |
| Memory growth (soak) | < 50MB |
| Success rate | > 95% |

## Troubleshooting

### Tests timeout

Increase the scale profile timeout or use `--stress-duration`:

```bash
--stress-duration=120
```

### Memory tests show 0 MB

Install `psutil` for memory monitoring:

```bash
pip install psutil
```

### Flaky tests

Some tests may be sensitive to system load. Try:
- Running with fewer parallel tests: `-n 1`
- Using a smaller scale profile
- Ensuring no other resource-intensive processes are running

## Integration with CI/CD

Example GitHub Actions workflow:

```yaml
- name: Run stress tests
  run: |
    .venv/bin/python -m pytest tests/stress/scenarios/ \
      -m stress \
      --stress-scale=smoke \
      --stress-report=stress_report.json \
      -v \
      --timeout=600
```
