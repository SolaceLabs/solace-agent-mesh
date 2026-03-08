"""
Metrics collection for stress tests.

Collects latencies, throughput, errors, and memory usage with thread-safe operations.
"""

import asyncio
import threading
import time
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import defaultdict


@dataclass
class MetricSample:
    """Single metric sample with timestamp."""

    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ErrorRecord:
    """Record of an error occurrence."""

    timestamp: float
    operation: str
    error_type: str
    error_message: str
    context: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """
    Thread-safe metrics collector for stress tests.

    Collects:
    - Latencies by operation (with percentile calculations)
    - Counters for events and errors
    - Gauges for point-in-time values
    - Memory samples over time
    - Error details

    Usage:
        collector = MetricsCollector()
        await collector.start()

        # Record metrics
        await collector.record_latency("sse_connect", 45.2)
        await collector.increment_counter("connections")
        await collector.record_error("sse_connect", exc, {"task_id": "123"})

        # Get summary
        summary = collector.get_summary()
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._latencies: Dict[str, List[float]] = defaultdict(list)
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._errors: List[ErrorRecord] = []
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._memory_samples: List[MetricSample] = []
        self._custom_metrics: Dict[str, List[MetricSample]] = defaultdict(list)

    async def start(self):
        """Start metrics collection."""
        with self._lock:
            self._start_time = time.monotonic()
            self._end_time = None

    async def stop(self):
        """Stop metrics collection."""
        with self._lock:
            self._end_time = time.monotonic()

    def start_sync(self):
        """Synchronous version of start for non-async contexts."""
        with self._lock:
            self._start_time = time.monotonic()
            self._end_time = None

    def stop_sync(self):
        """Synchronous version of stop for non-async contexts."""
        with self._lock:
            self._end_time = time.monotonic()

    async def record_latency(self, operation: str, latency_ms: float):
        """
        Record a latency measurement in milliseconds.

        Args:
            operation: Name of the operation (e.g., "sse_connect", "http_request")
            latency_ms: Latency in milliseconds
        """
        with self._lock:
            self._latencies[operation].append(latency_ms)

    def record_latency_sync(self, operation: str, latency_ms: float):
        """Synchronous version of record_latency."""
        with self._lock:
            self._latencies[operation].append(latency_ms)

    async def increment_counter(self, name: str, amount: int = 1):
        """
        Increment a counter.

        Args:
            name: Counter name
            amount: Amount to increment by (default 1)
        """
        with self._lock:
            self._counters[name] += amount

    def increment_counter_sync(self, name: str, amount: int = 1):
        """Synchronous version of increment_counter."""
        with self._lock:
            self._counters[name] += amount

    async def set_gauge(self, name: str, value: float):
        """
        Set a gauge value (point-in-time measurement).

        Args:
            name: Gauge name
            value: Current value
        """
        with self._lock:
            self._gauges[name] = value

    def set_gauge_sync(self, name: str, value: float):
        """Synchronous version of set_gauge."""
        with self._lock:
            self._gauges[name] = value

    async def record_error(
        self,
        operation: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Record an error occurrence.

        Args:
            operation: Operation that failed
            error: The exception that occurred
            context: Additional context about the error
        """
        with self._lock:
            elapsed = time.monotonic() - (self._start_time or time.monotonic())
            self._errors.append(
                ErrorRecord(
                    timestamp=elapsed,
                    operation=operation,
                    error_type=type(error).__name__,
                    error_message=str(error),
                    context=context or {},
                )
            )
            self._counters[f"errors_{operation}"] += 1
            self._counters["total_errors"] += 1

    def record_error_sync(
        self,
        operation: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Synchronous version of record_error."""
        with self._lock:
            elapsed = time.monotonic() - (self._start_time or time.monotonic())
            self._errors.append(
                ErrorRecord(
                    timestamp=elapsed,
                    operation=operation,
                    error_type=type(error).__name__,
                    error_message=str(error),
                    context=context or {},
                )
            )
            self._counters[f"errors_{operation}"] += 1
            self._counters["total_errors"] += 1

    async def record_memory(self, rss_mb: float, tracked_kb: float = 0):
        """
        Record memory usage sample.

        Args:
            rss_mb: Process RSS memory in megabytes
            tracked_kb: Tracked objects size in kilobytes
        """
        with self._lock:
            elapsed = time.monotonic() - (self._start_time or time.monotonic())
            self._memory_samples.append(
                MetricSample(
                    timestamp=elapsed,
                    value=rss_mb,
                    labels={"tracked_kb": str(tracked_kb)},
                )
            )

    async def record_custom_metric(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ):
        """
        Record a custom metric sample.

        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels for the metric
        """
        with self._lock:
            elapsed = time.monotonic() - (self._start_time or time.monotonic())
            self._custom_metrics[name].append(
                MetricSample(
                    timestamp=elapsed,
                    value=value,
                    labels=labels or {},
                )
            )

    def calculate_percentiles(self, operation: str) -> Dict[str, float]:
        """
        Calculate percentile statistics for an operation's latencies.

        Args:
            operation: Operation name

        Returns:
            Dictionary with p50, p95, p99, min, max, mean, stddev, count
        """
        with self._lock:
            latencies = self._latencies.get(operation, [])

        if not latencies:
            return {
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "min": 0.0,
                "max": 0.0,
                "mean": 0.0,
                "stddev": 0.0,
                "count": 0,
            }

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        def percentile(p: float) -> float:
            idx = int(n * p)
            return sorted_latencies[min(idx, n - 1)]

        result = {
            "p50": percentile(0.50),
            "p95": percentile(0.95),
            "p99": percentile(0.99),
            "min": min(sorted_latencies),
            "max": max(sorted_latencies),
            "mean": statistics.mean(sorted_latencies),
            "count": n,
        }

        if n > 1:
            result["stddev"] = statistics.stdev(sorted_latencies)
        else:
            result["stddev"] = 0.0

        return result

    def get_throughput(self, operation: str) -> float:
        """
        Get operations per second for an operation.

        Args:
            operation: Operation name

        Returns:
            Operations per second
        """
        with self._lock:
            if not self._start_time:
                return 0.0
            end = self._end_time or time.monotonic()
            elapsed = end - self._start_time
            count = len(self._latencies.get(operation, []))

        return count / elapsed if elapsed > 0 else 0.0

    def get_error_rate(self, operation: str) -> float:
        """
        Get error rate as percentage for an operation.

        Args:
            operation: Operation name

        Returns:
            Error rate as percentage (0-100)
        """
        with self._lock:
            total = len(self._latencies.get(operation, []))
            errors = self._counters.get(f"errors_{operation}", 0)

        if total == 0 and errors == 0:
            return 0.0
        return (errors / (total + errors)) * 100

    def get_counter(self, name: str) -> int:
        """Get current value of a counter."""
        with self._lock:
            return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        """Get current value of a gauge."""
        with self._lock:
            return self._gauges.get(name, 0.0)

    def get_duration_seconds(self) -> float:
        """Get total duration of metrics collection in seconds."""
        with self._lock:
            if not self._start_time:
                return 0.0
            end = self._end_time or time.monotonic()
            return end - self._start_time

    def get_operations(self) -> List[str]:
        """Get list of all operations that have recorded latencies."""
        with self._lock:
            return list(self._latencies.keys())

    def get_memory_trend(self) -> Dict[str, Any]:
        """
        Analyze memory usage trend over time.

        Returns:
            Dictionary with start_mb, end_mb, max_mb, min_mb, growth_mb, samples
        """
        with self._lock:
            samples = self._memory_samples.copy()

        if not samples:
            return {
                "start_mb": 0.0,
                "end_mb": 0.0,
                "max_mb": 0.0,
                "min_mb": 0.0,
                "growth_mb": 0.0,
                "sample_count": 0,
            }

        values = [s.value for s in samples]
        return {
            "start_mb": values[0],
            "end_mb": values[-1],
            "max_mb": max(values),
            "min_mb": min(values),
            "growth_mb": values[-1] - values[0],
            "sample_count": len(values),
        }

    def get_errors(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recorded errors.

        Args:
            limit: Maximum number of errors to return

        Returns:
            List of error dictionaries
        """
        with self._lock:
            errors = self._errors[:limit]

        return [
            {
                "timestamp": e.timestamp,
                "operation": e.operation,
                "error_type": e.error_type,
                "error_message": e.error_message,
                "context": e.context,
            }
            for e in errors
        ]

    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics summary.

        Returns:
            Dictionary containing all metrics data
        """
        with self._lock:
            operations = list(self._latencies.keys())
            counters = dict(self._counters)
            gauges = dict(self._gauges)
            total_errors = len(self._errors)
            errors_preview = self._errors[:10]

        summary = {
            "duration_seconds": self.get_duration_seconds(),
            "operations": {},
            "counters": counters,
            "gauges": gauges,
            "total_errors": total_errors,
            "errors": [
                {
                    "timestamp": e.timestamp,
                    "operation": e.operation,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                }
                for e in errors_preview
            ],
            "memory": self.get_memory_trend(),
        }

        for op in operations:
            summary["operations"][op] = {
                "percentiles": self.calculate_percentiles(op),
                "throughput_per_sec": self.get_throughput(op),
                "error_rate_percent": self.get_error_rate(op),
            }

        return summary

    def reset(self):
        """Reset all metrics to initial state."""
        with self._lock:
            self._latencies.clear()
            self._counters.clear()
            self._gauges.clear()
            self._errors.clear()
            self._memory_samples.clear()
            self._custom_metrics.clear()
            self._start_time = None
            self._end_time = None
