"""
Generic Memory Monitoring utility for integration and longevity tests.
"""

import gc
import os
import io
from datetime import datetime
from typing import List, Any, Dict, Optional

try:
    import psutil
except ImportError:
    psutil = None

try:
    import objgraph
except ImportError:
    objgraph = None

try:
    from pympler import muppy, summary, asizeof
except ImportError:
    muppy = None
    summary = None
    asizeof = None

from solace_agent_mesh.agent.sac.component import SamAgentComponent
from solace_agent_mesh.agent.tools.peer_agent_tool import PeerAgentTool
from a2a.types import Task, TaskStatusUpdateEvent
from .depth_based_profiler import DepthBasedProfiler, DepthProfilerConfig, MemoryNode
from .diff_generator import MemoryDiffGenerator, MemoryDiffReportGenerator


class MemoryLeakError(AssertionError):
    """Custom exception raised when a memory leak is detected."""

    pass


class MemoryMonitor:
    """
    A class to monitor memory usage during a test, focusing on specific components.
    """

    def _get_object_name(self, obj: Any) -> str:
        """Generates a descriptive name for a tracked object."""
        if hasattr(obj, "agent_name") and getattr(obj, "agent_name"):
            return getattr(obj, "agent_name")
        if hasattr(obj, "gateway_id") and getattr(obj, "gateway_id"):
            return getattr(obj, "gateway_id")
        if hasattr(obj, "name") and getattr(obj, "name"):
            return getattr(obj, "name")
        return type(obj).__name__

    def __init__(
        self,
        test_id: str,
        objects_to_track: List[Any],
        size_threshold_bytes: int = 250 * 1024,  # Default: 250 KB
        process_memory_threshold_mb: Optional[float] = None,
        report_dir: str = "tests/integration/reports",
        force_report: bool = False,
        max_depth: int = 100,
    ):
        if psutil is None or objgraph is None or asizeof is None:
            raise ImportError(
                "psutil, objgraph, and pympler are required for MemoryMonitor."
            )

        self.test_id = test_id
        self.objects_to_track = objects_to_track
        self.size_threshold_bytes = size_threshold_bytes
        self.process_memory_threshold_mb = process_memory_threshold_mb
        self.report_dir = report_dir
        self.force_report = force_report
        self.max_depth = max_depth
        project_root_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
        )
        self.source_code_path = os.path.join(project_root_path, "src")
        self.tests_path = os.path.join(project_root_path, "tests")
        self.process = psutil.Process()
        self.mem_before = 0
        self.tracked_objects_size_before = 0
        self.sum_before = None
        self.component_sizes_before = {}
        self.attribute_sizes_before = {}
        self.memory_tree_before: Optional[MemoryNode] = None
        self.memory_tree_after: Optional[MemoryNode] = None
        self.classes_to_track = [
            SamAgentComponent,
            PeerAgentTool,
            Task,
            TaskStatusUpdateEvent,
        ]
        self.counts_before = {}

    def start(self):
        """Records the initial memory state."""
        gc.collect()
        self.mem_before = self.process.memory_info().rss / (1024 * 1024)
        print(f"\n[{self.test_id}] Process memory before: {self.mem_before:.2f} MB")

        self.tracked_objects_size_before = asizeof.asizeof(self.objects_to_track)
        print(
            f"[{self.test_id}] Tracked objects size before: {self.tracked_objects_size_before / 1024:.2f} KB"
        )

        for c in self.objects_to_track:
            comp_name = self._get_object_name(c)
            self.component_sizes_before[comp_name] = asizeof.asizeof(c)
            self.attribute_sizes_before[comp_name] = self._get_detailed_attribute_sizes(
                c, max_depth=4
            )
        print(f"[{self.test_id}] Component sizes before: {self.component_sizes_before}")

        self.counts_before = {
            cls.__name__: objgraph.count(f"{cls.__module__}.{cls.__name__}")
            for cls in self.classes_to_track
        }
        print(f"[{self.test_id}] Object counts before: {self.counts_before}")
        self.sum_before = summary.summarize(muppy.get_objects())

        profiler_config = DepthProfilerConfig(max_depth=self.max_depth)
        profiler = DepthBasedProfiler(config=profiler_config)
        self.memory_tree_before = profiler.profile(
            self.objects_to_track, name="TrackedObjectsList"
        )

    def stop_and_assert(self):
        """Records final state, generates a report, and asserts memory usage."""
        gc.collect()
        mem_after = self.process.memory_info().rss / (1024 * 1024)
        mem_diff = mem_after - self.mem_before
        print(f"[{self.test_id}] Process memory after: {mem_after:.2f} MB")
        print(f"[{self.test_id}] Process memory difference: {mem_diff:+.2f} MB")

        tracked_objects_size_after = asizeof.asizeof(self.objects_to_track)
        size_diff = tracked_objects_size_after - self.tracked_objects_size_before
        print(
            f"[{self.test_id}] Tracked objects size after: {tracked_objects_size_after / 1024:.2f} KB"
        )
        print(
            f"[{self.test_id}] Tracked objects size difference: {size_diff / 1024:+.2f} KB"
        )

        component_sizes_after = {
            self._get_object_name(c): asizeof.asizeof(c) for c in self.objects_to_track
        }
        print(f"[{self.test_id}] Component sizes after: {component_sizes_after}")

        counts_after = {
            cls.__name__: objgraph.count(f"{cls.__module__}.{cls.__name__}")
            for cls in self.classes_to_track
        }
        print(f"[{self.test_id}] Object counts after: {counts_after}")

        profiler_config = DepthProfilerConfig(max_depth=self.max_depth)
        profiler = DepthBasedProfiler(config=profiler_config)
        self.memory_tree_after = profiler.profile(
            self.objects_to_track, name="TrackedObjectsList"
        )

        size_leak_detected = size_diff >= self.size_threshold_bytes
        process_leak_detected = False
        if self.process_memory_threshold_mb is not None:
            process_leak_detected = mem_diff >= self.process_memory_threshold_mb

        if (
            not size_leak_detected
            and not process_leak_detected
            and not self.force_report
        ):
            print(
                f"[{self.test_id}] Memory usage within all thresholds. No report generated."
            )
            return
        os.makedirs(self.report_dir, exist_ok=True)
        report_buffer = io.StringIO()
        self._generate_report(
            report_buffer, mem_after, component_sizes_after, counts_after
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"{self.test_id.replace('/', '_')}_{timestamp}.md"
        report_path = os.path.join(self.report_dir, report_filename)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_buffer.getvalue())

        if size_leak_detected:
            print(
                f"\nOBJECT SIZE LEAK DETECTED! Detailed report saved to: {report_path}"
            )
            raise MemoryLeakError(
                f"[{self.test_id}] Object size leak detected! "
                f"Increase: {size_diff / 1024:.2f} KB, Threshold: {self.size_threshold_bytes / 1024:.2f} KB. "
                f"Report: {report_path}"
            )
        elif process_leak_detected:
            print(
                f"\nPROCESS MEMORY LEAK DETECTED! Detailed report saved to: {report_path}"
            )
            raise MemoryLeakError(
                f"[{self.test_id}] Process memory leak detected! "
                f"Increase: {mem_diff:.2f} MB, Threshold: {self.process_memory_threshold_mb} MB. "
                f"Report: {report_path}"
            )
        else:
            print(f"\nMEMORY REPORT FORCED. Detailed report saved to: {report_path}")

    def _get_detailed_attribute_sizes(
        self, obj: Any, max_depth: int = 4
    ) -> Dict[str, int]:
        """Recursively gets the size of container attributes up to a certain depth."""
        sizes = {}
        IGNORED_ATTRIBUTES = {"_captured_outputs"}

        def recurse(current_obj, path, depth):
            if depth >= max_depth:
                return

            if isinstance(current_obj, dict):
                for key, value in current_obj.items():
                    try:
                        key_repr = repr(key)
                    except Exception:
                        key_repr = f"<unrepresentable_key_{type(key).__name__}>"
                    new_path = f"{path}[{key_repr}]"
                    sizes[new_path] = asizeof.asizeof(value)
                    recurse(value, new_path, depth + 1)
            elif isinstance(current_obj, list):
                for i, item in enumerate(current_obj):
                    new_path = f"{path}[{i}]"
                    sizes[new_path] = asizeof.asizeof(item)
                    recurse(item, new_path, depth + 1)

        for attr, value in obj.__dict__.items():
            if attr in IGNORED_ATTRIBUTES:
                continue

            if isinstance(value, (dict, list)):
                sizes[attr] = asizeof.asizeof(value)
                recurse(value, attr, 1)

        return sizes

    def _generate_report(
        self, report_buffer, mem_after, component_sizes_after, counts_after
    ):
        """Helper to write the detailed markdown report."""
        mem_diff = mem_after - self.mem_before
        tracked_objects_size_after = asizeof.asizeof(self.objects_to_track)
        size_diff = tracked_objects_size_after - self.tracked_objects_size_before

        report_buffer.write(f"# Memory Leak Report for: `{self.test_id}`\n\n")
        report_buffer.write("## Thresholds\n\n")
        report_buffer.write(
            f"- **Object Size Threshold:** `{self.size_threshold_bytes / 1024:.2f} KB`\n"
        )
        if self.process_memory_threshold_mb is not None:
            report_buffer.write(
                f"- **Process Memory Threshold:** `{self.process_memory_threshold_mb:.2f} MB`\n"
            )
        report_buffer.write("\n")

        report_buffer.write("## Tracked Object Size Summary (asizeof)\n\n")
        report_buffer.write(
            f"- **Before:** {self.tracked_objects_size_before / 1024:.2f} KB\n"
        )
        report_buffer.write(
            f"- **After:** {tracked_objects_size_after / 1024:.2f} KB\n"
        )
        report_buffer.write(f"- **Difference:** {size_diff / 1024:+.2f} KB\n\n")

        report_buffer.write("## Process Memory Summary (RSS)\n\n")
        report_buffer.write(f"- **Before:** {self.mem_before:.2f} MB\n")
        report_buffer.write(f"- **After:** {mem_after:.2f} MB\n")
        report_buffer.write(f"- **Difference:** {mem_diff:+.2f} MB\n\n")

        report_buffer.write("\n## Detailed Memory Diff Report\n\n")
        report_buffer.write(
            "This section shows a hierarchical diff of the tracked objects, highlighting attributes that have grown in size.\n\n"
        )
        if self.memory_tree_before and self.memory_tree_after:
            try:
                diff_generator = MemoryDiffGenerator(
                    self.memory_tree_before, self.memory_tree_after
                )
                diff_tree = diff_generator.generate_diff()

                diff_report_generator = MemoryDiffReportGenerator(
                    diff_tree, threshold_bytes=512
                )
                diff_report = diff_report_generator.generate_report()

                report_buffer.write("```text\n")
                report_buffer.write(diff_report)
                report_buffer.write("\n```\n\n")
            except Exception as e:
                report_buffer.write(
                    f"**Error during generating memory diff report:** `{e}`\n\n"
                )
                import traceback

                traceback.print_exc(file=report_buffer)

        else:
            report_buffer.write(
                "**Could not generate memory diff report: before or after memory tree is missing.**\n\n"
            )

        report_buffer.write("## Global Memory Difference Summary\n\n")
        report_buffer.write(
            "This table shows all object types that increased in memory across the entire application.\n\n"
        )
        report_buffer.write("```text\n")
        from pympler import summary as pympler_summary

        sum_after = pympler_summary.summarize(muppy.get_objects())
        diff = pympler_summary.get_diff(self.sum_before, sum_after)
        positive_diff = sorted(
            [row for row in diff if row[1] > 0], key=lambda r: r[2], reverse=True
        )
        report_buffer.write(f"{'types':<60} | {'# new':>12} | {'total size':>18}\n")
        report_buffer.write(f"{'='*60} | {'='*12} | {'='*18}\n")
        for row in positive_diff[:30]:
            class_name, count, size = row
            size_str = f"{size} B"
            if size > 1024 * 1024:
                size_str = f"{size / (1024*1024):.2f} MB"
            elif size > 1024:
                size_str = f"{size / 1024:.2f} KB"
            report_buffer.write(
                f"{str(class_name):<60} | {count:>+12,d} | {size_str:>18}\n"
            )
        report_buffer.write("```\n\n")

        report_buffer.write("## Component Memory Footprint Analysis\n\n")
        report_buffer.write(
            "| Component Name      | Size Before | Size After  | Delta       |\n"
        )
        report_buffer.write(
            "|---------------------|-------------|-------------|-------------|\n"
        )
        for comp in self.objects_to_track:
            name = self._get_object_name(comp)
            size_before = self.component_sizes_before.get(name, 0)
            size_after = component_sizes_after.get(name, 0)
            delta = size_after - size_before
            report_buffer.write(
                f"| {name:<19} | {size_before:11,d} B | {size_after:11,d} B | {delta:+11,d} B |\n"
            )
        report_buffer.write("\n")
