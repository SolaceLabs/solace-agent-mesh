"""
Metrics reporting for stress tests.

Generates console and JSON reports from collected metrics.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, TextIO
import sys

from .collector import MetricsCollector


class MetricsReporter:
    """
    Reporter for stress test metrics.

    Generates human-readable console reports and machine-readable JSON reports.

    Usage:
        reporter = MetricsReporter(collector)
        reporter.print_summary()
        reporter.save_json("stress_report.json")
    """

    def __init__(self, collector: MetricsCollector, test_name: str = "Stress Test"):
        """
        Initialize the reporter.

        Args:
            collector: MetricsCollector with recorded metrics
            test_name: Name of the test for reports
        """
        self.collector = collector
        self.test_name = test_name

    def print_summary(self, file: TextIO = None):
        """
        Print a human-readable summary to console or file.

        Args:
            file: Optional file to write to (defaults to stdout)
        """
        if file is None:
            file = sys.stdout

        summary = self.collector.get_summary()

        file.write("\n")
        file.write("=" * 70 + "\n")
        file.write(f"  STRESS TEST REPORT: {self.test_name}\n")
        file.write("=" * 70 + "\n")
        file.write(f"  Duration: {summary['duration_seconds']:.2f} seconds\n")
        file.write(f"  Total Errors: {summary['total_errors']}\n")
        file.write("=" * 70 + "\n\n")

        # Operations summary
        if summary["operations"]:
            file.write("LATENCY STATISTICS (milliseconds)\n")
            file.write("-" * 70 + "\n")
            file.write(
                f"{'Operation':<25} {'Count':>8} {'P50':>8} {'P95':>8} {'P99':>8} {'Err%':>6}\n"
            )
            file.write("-" * 70 + "\n")

            for op_name, op_data in summary["operations"].items():
                p = op_data["percentiles"]
                file.write(
                    f"{op_name:<25} {p['count']:>8} {p['p50']:>8.1f} "
                    f"{p['p95']:>8.1f} {p['p99']:>8.1f} "
                    f"{op_data['error_rate_percent']:>5.1f}%\n"
                )
            file.write("\n")

        # Throughput summary
        if summary["operations"]:
            file.write("THROUGHPUT (operations/second)\n")
            file.write("-" * 70 + "\n")
            for op_name, op_data in summary["operations"].items():
                file.write(
                    f"  {op_name}: {op_data['throughput_per_sec']:.2f} ops/sec\n"
                )
            file.write("\n")

        # Counters
        if summary["counters"]:
            file.write("COUNTERS\n")
            file.write("-" * 70 + "\n")
            for name, value in sorted(summary["counters"].items()):
                file.write(f"  {name}: {value:,}\n")
            file.write("\n")

        # Memory
        if summary["memory"]["sample_count"] > 0:
            mem = summary["memory"]
            file.write("MEMORY USAGE\n")
            file.write("-" * 70 + "\n")
            file.write(f"  Start:  {mem['start_mb']:.1f} MB\n")
            file.write(f"  End:    {mem['end_mb']:.1f} MB\n")
            file.write(f"  Max:    {mem['max_mb']:.1f} MB\n")
            file.write(f"  Growth: {mem['growth_mb']:+.1f} MB\n")
            file.write("\n")

        # Errors
        if summary["errors"]:
            file.write("ERRORS (first 10)\n")
            file.write("-" * 70 + "\n")
            for err in summary["errors"]:
                file.write(
                    f"  [{err['timestamp']:.2f}s] {err['operation']}: "
                    f"{err['error_type']} - {err['error_message'][:50]}\n"
                )
            file.write("\n")

        file.write("=" * 70 + "\n")

    def get_json_report(self) -> Dict[str, Any]:
        """
        Get metrics as a JSON-serializable dictionary.

        Returns:
            Dictionary with all metrics data plus metadata
        """
        summary = self.collector.get_summary()

        return {
            "metadata": {
                "test_name": self.test_name,
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": summary["duration_seconds"],
            },
            "summary": {
                "total_errors": summary["total_errors"],
                "operations_count": len(summary["operations"]),
            },
            "operations": summary["operations"],
            "counters": summary["counters"],
            "gauges": summary["gauges"],
            "memory": summary["memory"],
            "errors": self.collector.get_errors(limit=100),
        }

    def save_json(self, filepath: str):
        """
        Save metrics report to a JSON file.

        Args:
            filepath: Path to save the JSON file
        """
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        report = self.get_json_report()

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

    def assert_thresholds(
        self,
        max_p99_latency_ms: Optional[Dict[str, float]] = None,
        max_error_rate_percent: Optional[Dict[str, float]] = None,
        max_memory_growth_mb: Optional[float] = None,
    ) -> bool:
        """
        Assert that metrics meet specified thresholds.

        Args:
            max_p99_latency_ms: Maximum p99 latency per operation
            max_error_rate_percent: Maximum error rate per operation
            max_memory_growth_mb: Maximum memory growth allowed

        Returns:
            True if all thresholds are met

        Raises:
            AssertionError: If any threshold is exceeded
        """
        summary = self.collector.get_summary()
        failures = []

        # Check latency thresholds
        if max_p99_latency_ms:
            for op, max_latency in max_p99_latency_ms.items():
                if op in summary["operations"]:
                    actual = summary["operations"][op]["percentiles"]["p99"]
                    if actual > max_latency:
                        failures.append(
                            f"p99 latency for '{op}': {actual:.1f}ms > {max_latency}ms"
                        )

        # Check error rate thresholds
        if max_error_rate_percent:
            for op, max_rate in max_error_rate_percent.items():
                if op in summary["operations"]:
                    actual = summary["operations"][op]["error_rate_percent"]
                    if actual > max_rate:
                        failures.append(
                            f"error rate for '{op}': {actual:.1f}% > {max_rate}%"
                        )

        # Check memory threshold
        if max_memory_growth_mb is not None:
            actual_growth = summary["memory"]["growth_mb"]
            if actual_growth > max_memory_growth_mb:
                failures.append(
                    f"memory growth: {actual_growth:.1f}MB > {max_memory_growth_mb}MB"
                )

        if failures:
            raise AssertionError(
                f"Threshold violations in {self.test_name}:\n  - "
                + "\n  - ".join(failures)
            )

        return True


def create_comparison_report(
    reports: Dict[str, MetricsReporter], file: TextIO = None
):
    """
    Create a comparison report across multiple test runs.

    Args:
        reports: Dictionary of test_name -> MetricsReporter
        file: Optional file to write to (defaults to stdout)
    """
    if file is None:
        file = sys.stdout

    file.write("\n")
    file.write("=" * 80 + "\n")
    file.write("  COMPARISON REPORT\n")
    file.write("=" * 80 + "\n\n")

    # Collect all operations across all reports
    all_operations = set()
    for reporter in reports.values():
        all_operations.update(reporter.collector.get_operations())

    # Header
    test_names = list(reports.keys())
    header = f"{'Operation':<20}"
    for name in test_names:
        header += f" | {name[:15]:>15}"
    file.write(header + "\n")
    file.write("-" * len(header) + "\n")

    # P99 Latencies
    file.write("\nP99 Latency (ms):\n")
    for op in sorted(all_operations):
        row = f"{op:<20}"
        for name in test_names:
            summary = reports[name].collector.get_summary()
            if op in summary["operations"]:
                p99 = summary["operations"][op]["percentiles"]["p99"]
                row += f" | {p99:>15.1f}"
            else:
                row += f" | {'N/A':>15}"
        file.write(row + "\n")

    # Throughput
    file.write("\nThroughput (ops/sec):\n")
    for op in sorted(all_operations):
        row = f"{op:<20}"
        for name in test_names:
            summary = reports[name].collector.get_summary()
            if op in summary["operations"]:
                throughput = summary["operations"][op]["throughput_per_sec"]
                row += f" | {throughput:>15.1f}"
            else:
                row += f" | {'N/A':>15}"
        file.write(row + "\n")

    file.write("\n" + "=" * 80 + "\n")
