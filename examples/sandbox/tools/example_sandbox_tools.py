"""Example tools for the Secure Tool Runtime sandbox."""

from typing import Any, Dict


def echo_tool(ctx: Any, message: str = "Hello") -> Dict[str, Any]:
    """Echo back a message from the secure sandbox environment."""
    ctx.send_status("Echoing message...")
    return {
        "status": "success",
        "echoed_message": message,
    }


def execute_python(ctx: Any, code: str = "", artifacts: list = None) -> Dict[str, Any]:
    """Execute arbitrary Python code in a sandbox and return the result.

    Supports both expressions and statements. To return a value, assign
    it to a variable called ``result``. Anything printed to stdout is
    also captured.

    The following helpers are available in the code:
    - ``save_artifact(filename, content_bytes)`` — create an output artifact
    - ``send_status(message)`` — send a progress update
    - ``artifact_files`` — dict of input artifact paths (keyed by name)
    - ``load_artifact(name)`` — load artifact content as bytes by name
    """
    import builtins
    import io
    import contextlib

    ctx.send_status("Executing Python code...")
    try:
        # Build artifact_files dict from context facade
        # Keys are like "artifacts[0]", values are local file paths
        raw_artifacts = ctx.list_artifacts() if hasattr(ctx, "list_artifacts") else {}

        # Also provide a simplified mapping: filename -> path
        artifact_files = {}
        for key, path in raw_artifacts.items():
            artifact_files[key] = path
            # Extract just the filename from the path for convenience
            import os
            basename = os.path.basename(path)
            if basename not in artifact_files:
                artifact_files[basename] = path

        # Use a single dict for both globals and locals so that variables
        # assigned at top level are visible inside comprehensions and
        # generator expressions (which create their own scope in Python 3
        # and only see the globals dict, not a separate locals dict).
        exec_ns: Dict[str, Any] = {
            "__builtins__": builtins,
            "save_artifact": ctx.save_artifact,
            "send_status": ctx.send_status,
            "artifact_files": artifact_files,
            "load_artifact": ctx.load_artifact if hasattr(ctx, "load_artifact") else lambda n: None,
        }
        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            exec(code, exec_ns)

        stdout_text = stdout_capture.getvalue()
        result_value = exec_ns.get("result")

        output: Dict[str, Any] = {"status": "success"}
        if result_value is not None:
            output["result"] = str(result_value)
        if stdout_text:
            output["stdout"] = stdout_text
        return output
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }
