"""
Thread analysis utilities for stress testing.

Analyzes thread states to detect blocking issues, such as request threads
waiting on database operations or locks.

This is critical for detecting when synchronous operations block request
threads, which caused the 504 timeout issue.
"""

import sys
import threading
import traceback
import time
import statistics
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class ThreadInfo:
    """Information about a single thread."""
    
    thread_id: int
    name: str
    daemon: bool
    stack_trace: List[str]
    is_blocked: bool
    blocked_by: Optional[str] = None
    blocking_patterns: List[str] = field(default_factory=list)


@dataclass
class ThreadDumpSnapshot:
    """Snapshot of all threads at a point in time."""
    
    timestamp: float
    threads: Dict[int, ThreadInfo]
    total_threads: int
    blocked_threads: int
    blocked_thread_ids: List[int]
    
    def get_blocked_summary(self) -> Dict[str, int]:
        """Get summary of blocking patterns."""
        patterns: Dict[str, int] = defaultdict(int)
        for thread in self.threads.values():
            for pattern in thread.blocking_patterns:
                patterns[pattern] += 1
        return dict(patterns)


class ThreadAnalyzer:
    """
    Analyze thread states to detect blocking issues.
    
    Usage:
        analyzer = ThreadAnalyzer()
        
        # Single snapshot
        snapshot = analyzer.capture_thread_dump()
        blocked = analyzer.detect_blocked_patterns(snapshot)
        
        # Continuous monitoring
        with analyzer.monitor_blocking(duration_seconds=10):
            await run_test()
        
        report = analyzer.get_blocking_report()
    """
    
    # Patterns that indicate a thread is blocked on a slow operation
    BLOCKING_PATTERNS = [
        # Database blocking patterns
        ("sqlalchemy", "SQLAlchemy DB operation"),
        ("psycopg2", "PostgreSQL operation"),
        ("sqlite3", "SQLite operation"),
        ("pymysql", "MySQL operation"),
        
        # Lock/synchronization blocking
        ("threading.Lock.acquire", "Waiting on threading.Lock"),
        ("threading.RLock.acquire", "Waiting on threading.RLock"),
        ("threading.Condition.wait", "Waiting on threading.Condition"),
        ("threading.Event.wait", "Waiting on threading.Event"),
        ("queue.Queue.put", "Waiting on queue.put"),
        ("queue.Queue.get", "Waiting on queue.get"),
        
        # Network I/O blocking
        ("socket.recv", "Waiting on socket.recv"),
        ("socket.send", "Waiting on socket.send"),
        ("ssl.read", "Waiting on SSL read"),
        ("ssl.write", "Waiting on SSL write"),
        ("http.client", "HTTP client operation"),
        ("urllib", "urllib operation"),
        ("httpx", "httpx operation"),
        
        # File I/O blocking
        ("io.FileIO", "File I/O operation"),
        ("io.BufferedReader", "Buffered read operation"),
        ("io.BufferedWriter", "Buffered write operation"),
        
        # Note: time.sleep and asyncio.sleep are intentional waits, not blocking
        # They're used in test code. We don't include them as problematic blocking.
    ]
    
    # Patterns that are intentional waits, not problematic blocking
    INTENTIONAL_WAIT_PATTERNS = [
        "time.sleep",
        "asyncio.sleep",
    ]
    
    # Patterns specific to the 504 timeout issue
    REQUEST_THREAD_PATTERNS = [
        "uvicorn",
        "starlette",
        "fastapi",
        "asyncio",
    ]
    
    def __init__(self):
        self._snapshots: List[ThreadDumpSnapshot] = []
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
    
    def capture_thread_dump(self) -> ThreadDumpSnapshot:
        """
        Capture current thread states.
        
        Returns:
            ThreadDumpSnapshot with information about all threads
        """
        threads: Dict[int, ThreadInfo] = {}
        blocked_ids: List[int] = []
        
        # Get all thread frames
        frames = sys._current_frames()
        
        for thread_id, frame in frames.items():
            # Get thread object if available
            thread_obj = None
            for t in threading.enumerate():
                if t.ident == thread_id:
                    thread_obj = t
                    break
            
            # Get stack trace
            stack_lines = traceback.format_stack(frame)
            stack_str = "".join(stack_lines)
            
            # Check for blocking patterns
            is_blocked = False
            blocking_patterns = []
            blocked_by = None
            
            for pattern, description in self.BLOCKING_PATTERNS:
                if pattern in stack_str:
                    is_blocked = True
                    blocking_patterns.append(description)
                    if blocked_by is None:
                        blocked_by = description
            
            thread_info = ThreadInfo(
                thread_id=thread_id,
                name=thread_obj.name if thread_obj else f"Thread-{thread_id}",
                daemon=thread_obj.daemon if thread_obj else False,
                stack_trace=stack_lines,
                is_blocked=is_blocked,
                blocked_by=blocked_by,
                blocking_patterns=blocking_patterns,
            )
            
            threads[thread_id] = thread_info
            if is_blocked:
                blocked_ids.append(thread_id)
        
        snapshot = ThreadDumpSnapshot(
            timestamp=time.monotonic(),
            threads=threads,
            total_threads=len(threads),
            blocked_threads=len(blocked_ids),
            blocked_thread_ids=blocked_ids,
        )
        
        return snapshot
    
    def detect_blocked_patterns(self, snapshot: ThreadDumpSnapshot) -> List[ThreadInfo]:
        """
        Get list of threads that appear to be blocked.
        
        Args:
            snapshot: Thread dump snapshot to analyze
            
        Returns:
            List of ThreadInfo for blocked threads
        """
        return [
            thread for thread in snapshot.threads.values()
            if thread.is_blocked
        ]
    
    def detect_request_thread_blocking(self, snapshot: ThreadDumpSnapshot) -> List[ThreadInfo]:
        """
        Detect specifically if request-handling threads are blocked.
        
        This is the key detection for the 504 timeout issue - when
        request threads are blocked waiting on DB operations.
        
        Args:
            snapshot: Thread dump snapshot to analyze
            
        Returns:
            List of request threads that are blocked
        """
        blocked_request_threads = []
        
        for thread in snapshot.threads.values():
            # Check if this is a request thread
            is_request_thread = any(
                pattern in "".join(thread.stack_trace)
                for pattern in self.REQUEST_THREAD_PATTERNS
            )
            
            if is_request_thread and thread.is_blocked:
                blocked_request_threads.append(thread)
        
        return blocked_request_threads
    
    def start_monitoring(self, interval_seconds: float = 0.5):
        """
        Start continuous thread monitoring.
        
        Args:
            interval_seconds: How often to capture thread dumps
        """
        self._monitoring = True
        self._snapshots = []
        
        def monitor_loop():
            while self._monitoring:
                snapshot = self.capture_thread_dump()
                self._snapshots.append(snapshot)
                time.sleep(interval_seconds)
        
        self._monitor_thread = threading.Thread(
            target=monitor_loop,
            name="ThreadAnalyzer-Monitor",
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info(f"Started thread monitoring (interval: {interval_seconds}s)")
    
    def stop_monitoring(self):
        """Stop continuous monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        logger.info(f"Stopped thread monitoring ({len(self._snapshots)} snapshots)")
    
    def get_monitoring_report(self) -> Dict[str, Any]:
        """
        Get report from monitoring session.
        
        Returns:
            Dictionary with monitoring statistics
        """
        if not self._snapshots:
            return {"error": "No snapshots collected"}
        
        # Calculate statistics
        blocked_counts = [s.blocked_threads for s in self._snapshots]
        total_counts = [s.total_threads for s in self._snapshots]
        
        # Aggregate blocking patterns across all snapshots
        pattern_counts: Dict[str, int] = defaultdict(int)
        for snapshot in self._snapshots:
            for thread in snapshot.threads.values():
                for pattern in thread.blocking_patterns:
                    pattern_counts[pattern] += 1
        
        # Find max blocked threads
        max_blocked_idx = blocked_counts.index(max(blocked_counts))
        max_blocked_snapshot = self._snapshots[max_blocked_idx]
        
        report = {
            "total_snapshots": len(self._snapshots),
            "duration_seconds": (
                self._snapshots[-1].timestamp - self._snapshots[0].timestamp
                if len(self._snapshots) > 1 else 0
            ),
            "blocked_threads": {
                "min": min(blocked_counts),
                "max": max(blocked_counts),
                "mean": statistics.mean(blocked_counts),
                "samples": blocked_counts,
            },
            "total_threads": {
                "min": min(total_counts),
                "max": max(total_counts),
                "mean": statistics.mean(total_counts),
            },
            "blocking_patterns": dict(pattern_counts),
            "max_blocked_snapshot": {
                "timestamp": max_blocked_snapshot.timestamp,
                "blocked_count": max_blocked_snapshot.blocked_threads,
                "blocked_threads": [
                    {
                        "name": max_blocked_snapshot.threads[tid].name,
                        "blocked_by": max_blocked_snapshot.threads[tid].blocked_by,
                    }
                    for tid in max_blocked_snapshot.blocked_thread_ids
                ],
            },
        }
        
        return report
    
    def get_snapshots(self) -> List[ThreadDumpSnapshot]:
        """Get all captured snapshots."""
        return list(self._snapshots)
    
    def clear_snapshots(self):
        """Clear captured snapshots."""
        self._snapshots = []


class RequestLatencyAnalyzer:
    """
    Analyze request completion times to detect blocking.
    
    The key insight: if request threads are blocked, completion times
    will show high variance (some requests fast, others slow waiting
    for the blocked thread).
    
    With the async write queue fix, completion times should be
    consistently fast regardless of background DB operations.
    """
    
    def __init__(self):
        self._completion_times: List[Tuple[str, float]] = []
        self._lock = threading.Lock()
    
    def record_completion(self, request_id: str, duration_ms: float):
        """Record a request completion time."""
        with self._lock:
            self._completion_times.append((request_id, duration_ms))
    
    def analyze_variance(self) -> Dict[str, Any]:
        """
        Analyze completion time variance.
        
        Returns:
            Analysis including variance, which indicates blocking if high
        """
        with self._lock:
            times = [t[1] for t in self._completion_times]
        
        if len(times) < 2:
            return {"error": "Need at least 2 samples"}
        
        mean_time = statistics.mean(times)
        variance = statistics.variance(times)
        stdev = statistics.stdev(times)
        
        # Coefficient of variation - normalized measure of dispersion
        cv = stdev / mean_time if mean_time > 0 else 0
        
        return {
            "sample_count": len(times),
            "mean_ms": mean_time,
            "variance": variance,
            "stdev_ms": stdev,
            "coefficient_of_variation": cv,
            "min_ms": min(times),
            "max_ms": max(times),
            "p50_ms": sorted(times)[len(times) // 2],
            "p99_ms": sorted(times)[int(len(times) * 0.99)] if len(times) >= 100 else max(times),
            # High CV indicates potential thread blocking
            "potential_blocking": cv > 1.0,  # CV > 100% is suspicious
        }
    
    def clear(self):
        """Clear recorded times."""
        with self._lock:
            self._completion_times = []
    
    def get_times(self) -> List[Tuple[str, float]]:
        """Get all recorded completion times."""
        with self._lock:
            return list(self._completion_times)


def format_thread_dump(snapshot: ThreadDumpSnapshot, include_traces: bool = False) -> str:
    """
    Format a thread dump snapshot as a human-readable string.
    
    Args:
        snapshot: The snapshot to format
        include_traces: Whether to include full stack traces
        
    Returns:
        Formatted string
    """
    lines = [
        f"Thread Dump at {snapshot.timestamp:.3f}",
        f"Total threads: {snapshot.total_threads}",
        f"Blocked threads: {snapshot.blocked_threads}",
        "",
        "Blocked Threads:",
        "-" * 40,
    ]
    
    for tid in snapshot.blocked_thread_ids:
        thread = snapshot.threads[tid]
        lines.append(f"  {thread.name} (ID: {tid})")
        lines.append(f"    Blocked by: {thread.blocked_by}")
        
        if include_traces:
            lines.append("    Stack trace:")
            for line in thread.stack_trace[-5:]:  # Last 5 frames
                lines.append(f"      {line.strip()}")
        
        lines.append("")
    
    return "\n".join(lines)
