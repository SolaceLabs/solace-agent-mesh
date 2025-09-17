"""
A simple file-based tracker for verifying lifecycle hook execution in tests.
"""
import os
from pathlib import Path
from typing import List
import threading

_lock = threading.Lock()


def track(tracker_file: Path, message: str):
    """Appends a message to the tracker file in a thread-safe manner."""
    with _lock:
        with open(tracker_file, "a", encoding="utf-8") as f:
            f.write(f"{message}\n")


def get_tracked_lines(tracker_file: Path) -> List[str]:
    """Reads all lines from the tracker file."""
    if not tracker_file.exists():
        return []
    with _lock:
        with open(tracker_file, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines()]


def cleanup_tracker(tracker_file: Path):
    """Deletes the tracker file if it exists."""
    with _lock:
        if tracker_file.exists():
            try:
                os.remove(tracker_file)
            except FileNotFoundError:
                pass
