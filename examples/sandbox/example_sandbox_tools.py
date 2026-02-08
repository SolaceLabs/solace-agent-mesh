"""
Example sandboxed tools for testing.

These tools are designed to run inside the nsjail sandbox within the
sandbox worker container. They demonstrate various capabilities:
- Simple computation
- Status updates via context
- File/artifact handling
- Error handling

To use these tools, the sandbox worker container must have this module
available (either installed or mounted).
"""

import time
from typing import Any, Dict, List, Optional


def echo_tool(ctx: Any, message: str) -> Dict[str, Any]:
    """
    Simple echo tool that returns the input message.

    This is useful for testing basic sandbox communication.

    Args:
        ctx: Tool context for status updates and services
        message: The message to echo back

    Returns:
        Dict with the echoed message
    """
    ctx.send_status("Processing echo request...")
    time.sleep(0.5)  # Simulate some work

    return {
        "status": "success",
        "echoed_message": message,
        "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def compute_fibonacci(ctx: Any, n: int) -> Dict[str, Any]:
    """
    Compute the nth Fibonacci number.

    Demonstrates CPU-bound computation in the sandbox with status updates.

    Args:
        ctx: Tool context
        n: Which Fibonacci number to compute (0-indexed)

    Returns:
        Dict with the computed value and sequence
    """
    ctx.send_status(f"Computing Fibonacci({n})...")

    if n < 0:
        return {"status": "error", "error": "n must be non-negative"}

    if n <= 1:
        return {"status": "success", "value": n, "sequence": [0, 1][:n + 1]}

    sequence = [0, 1]
    for i in range(2, n + 1):
        sequence.append(sequence[-1] + sequence[-2])
        if i % 10 == 0:
            ctx.send_status(f"Computed {i}/{n} Fibonacci numbers...")

    ctx.send_status("Computation complete!")

    return {
        "status": "success",
        "value": sequence[-1],
        "sequence": sequence[-10:] if len(sequence) > 10 else sequence,
        "total_computed": len(sequence),
    }


def text_analyzer(ctx: Any, text: str) -> Dict[str, Any]:
    """
    Analyze text and return statistics.

    Demonstrates string processing in the sandbox.

    Args:
        ctx: Tool context
        text: The text to analyze

    Returns:
        Dict with text statistics
    """
    ctx.send_status("Analyzing text...")

    words = text.split()
    word_count = len(words)
    char_count = len(text)
    line_count = text.count('\n') + 1

    # Count word frequencies
    word_freq: Dict[str, int] = {}
    for word in words:
        word_lower = word.lower().strip('.,!?;:')
        word_freq[word_lower] = word_freq.get(word_lower, 0) + 1

    # Find top words
    top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]

    ctx.send_status("Analysis complete!")

    return {
        "status": "success",
        "statistics": {
            "word_count": word_count,
            "character_count": char_count,
            "line_count": line_count,
            "average_word_length": char_count / word_count if word_count > 0 else 0,
        },
        "top_words": [{"word": w, "count": c} for w, c in top_words],
    }


def slow_operation(ctx: Any, duration_seconds: int = 5) -> Dict[str, Any]:
    """
    Simulate a slow operation with progress updates.

    Useful for testing timeout handling and status updates.

    Args:
        ctx: Tool context
        duration_seconds: How long to run (default: 5)

    Returns:
        Dict with completion status
    """
    ctx.send_status(f"Starting slow operation ({duration_seconds}s)...")

    for i in range(duration_seconds):
        time.sleep(1)
        progress = (i + 1) / duration_seconds * 100
        ctx.send_status(f"Progress: {progress:.0f}%")

    return {
        "status": "success",
        "duration": duration_seconds,
        "message": "Slow operation completed successfully",
    }


def failing_tool(ctx: Any, error_message: str = "Intentional failure") -> Dict[str, Any]:
    """
    Tool that always fails.

    Useful for testing error handling in the sandbox.

    Args:
        ctx: Tool context
        error_message: The error message to raise

    Raises:
        RuntimeError: Always raises this error
    """
    ctx.send_status("About to fail...")
    raise RuntimeError(error_message)


def execute_python(
    ctx: Any,
    code: str,
    artifacts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Execute arbitrary Python code in the sandbox.

    The code runs in a restricted namespace with access to:
    - All Python builtins
    - Pre-loaded artifacts (available as file paths in the `artifact_files` dict)
    - A `save_artifact(filename, content_bytes)` helper to create output artifacts
    - A `send_status(message)` helper for progress updates

    The code's return value (if any) is captured by assigning to a `result`
    variable.  Anything printed to stdout is also captured.

    Args:
        ctx: Tool context
        code: Python source code to execute
        artifacts: Optional list of artifact parameter names to load

    Returns:
        Dict with execution output, stdout, and any created artifacts
    """
    import io
    import sys
    import traceback as _tb

    ctx.send_status("Executing Python code...")

    # Load requested artifacts into the work directory
    artifact_files: Dict[str, str] = {}
    for name in (artifacts or []):
        path = ctx._artifact_paths.get(name)
        if path:
            artifact_files[name] = path

    # Build the execution namespace
    namespace: Dict[str, Any] = {
        "__builtins__": __builtins__,
        "artifact_files": artifact_files,
        "save_artifact": lambda fn, data: ctx.save_artifact(fn, data if isinstance(data, bytes) else data.encode("utf-8")),
        "send_status": ctx.send_status,
    }

    # Capture stdout
    old_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured

    error = None
    try:
        exec(code, namespace)  # noqa: S102
    except Exception:
        error = _tb.format_exc()
    finally:
        sys.stdout = old_stdout

    stdout_text = captured.getvalue()
    result_value = namespace.get("result")

    output_artifacts = ctx.list_output_artifacts()

    if error:
        return {
            "status": "error",
            "error": error,
            "stdout": stdout_text,
            "created_artifacts": output_artifacts,
        }

    return {
        "status": "success",
        "result": result_value if result_value is not None else stdout_text,
        "stdout": stdout_text,
        "created_artifacts": output_artifacts,
    }
