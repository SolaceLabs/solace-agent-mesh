"""
SandboxRunner - Subprocess management for bubblewrap (bwrap) sandbox execution.

This module provides the SandboxRunner class which manages the lifecycle of
bwrap subprocesses for executing Python tools in a sandboxed environment.

Bubblewrap provides lightweight namespace-based sandboxing. Resource limits
(memory, CPU time, file size, open files) are enforced via Python's
resource.setrlimit() in a preexec_fn, since bwrap itself does not provide
resource control.
"""

import asyncio
import json
import logging
import os
import resource
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .manifest import ManifestEntry
from .protocol import (
    ArtifactReference,
    CreatedArtifact,
    PreloadedArtifact,
    SandboxErrorCodes,
    SandboxInvokeParams,
    SandboxInvokeResult,
    SandboxToolInvocationRequest,
    SandboxToolInvocationResponse,
)

if TYPE_CHECKING:
    from google.adk.artifacts import BaseArtifactService

log = logging.getLogger(__name__)

# Default paths inside the container
DEFAULT_BWRAP_BIN = "/usr/bin/bwrap"
DEFAULT_PYTHON_BIN = "/usr/local/bin/python3"
DEFAULT_WORK_BASE_DIR = "/sandbox/work"
DEFAULT_TOOLS_PYTHON_DIR = "/tools/python"

# Status pipe protocol
STATUS_PIPE_FILENAME = "status.pipe"
RESULT_FILENAME = "result.json"
TOOL_RUNNER_MODULE = "solace_agent_mesh.sandbox.tool_runner"

# Sandbox profiles define resource limits and isolation levels.
# Resource limits are enforced via resource.setrlimit() in preexec_fn.
# Namespace isolation and filesystem mounts are handled in _build_bwrap_command().
#
# All profiles use --ro-bind / / as the base filesystem, then overlay --proc /proc
# (fresh procfs for PID namespace isolation) and --dev /dev (minimal device nodes).
# The container needs CAP_SYS_ADMIN and --security-opt label=disable (to allow
# procfs mounts inside bwrap).
SANDBOX_PROFILES: Dict[str, Dict[str, Any]] = {
    "restrictive": {
        "rlimit_as_mb": 512,
        "rlimit_cpu_sec": 60,
        "rlimit_fsize_mb": 64,
        "rlimit_nofile": 128,
        "network_isolated": True,
        "keep_env": False,
        "writable_var": False,
    },
    "standard": {
        "rlimit_as_mb": 1024,
        "rlimit_cpu_sec": 300,
        "rlimit_fsize_mb": 256,
        "rlimit_nofile": 512,
        "network_isolated": False,
        "keep_env": True,
        "writable_var": False,
    },
    "permissive": {
        "rlimit_as_mb": 4096,
        "rlimit_cpu_sec": 600,
        "rlimit_fsize_mb": 1024,
        "rlimit_nofile": 1024,
        "network_isolated": False,
        "keep_env": True,
        "writable_var": True,
    },
}


@dataclass
class SandboxRunnerConfig:
    """Configuration for sandbox execution.

    Supports two modes:
    - 'bwrap': Full bubblewrap sandboxing with namespace isolation (default)
    - 'direct': Plain subprocess, no isolation (for local dev on any OS)
    """

    mode: str = "bwrap"
    bwrap_bin: str = DEFAULT_BWRAP_BIN
    python_bin: str = DEFAULT_PYTHON_BIN
    work_base_dir: str = DEFAULT_WORK_BASE_DIR
    tools_python_dir: str = DEFAULT_TOOLS_PYTHON_DIR
    default_profile: str = "standard"
    max_concurrent_executions: int = 4


class SandboxRunner:
    """
    Manages bubblewrap (bwrap) subprocess execution for sandboxed Python tools.

    This class handles:
    - Setting up work directories for each invocation
    - Creating named pipes for status message forwarding
    - Spawning bwrap with appropriate namespace isolation and mounts
    - Enforcing resource limits via setrlimit() in preexec_fn
    - Enforcing timeouts via asyncio.wait_for()
    - Collecting results and cleaning up
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self._config = SandboxRunnerConfig(
            mode=config.get("mode", "bwrap"),
            bwrap_bin=config.get("bwrap_bin", DEFAULT_BWRAP_BIN),
            python_bin=config.get("python_bin", DEFAULT_PYTHON_BIN),
            work_base_dir=config.get("work_base_dir", DEFAULT_WORK_BASE_DIR),
            tools_python_dir=config.get("tools_python_dir", DEFAULT_TOOLS_PYTHON_DIR),
            default_profile=config.get("default_profile", "standard"),
            max_concurrent_executions=config.get("max_concurrent_executions", 4),
        )

        # Semaphore to limit concurrent executions
        self._execution_semaphore = asyncio.Semaphore(
            self._config.max_concurrent_executions
        )

        log.info(
            "SandboxRunner initialized: mode=%s, max_concurrent=%d",
            self._config.mode,
            self._config.max_concurrent_executions,
        )

    def _get_profile(self, profile_name: str) -> Dict[str, Any]:
        """Get a sandbox profile by name, falling back to standard."""
        profile = SANDBOX_PROFILES.get(profile_name)
        if not profile:
            log.warning(
                "Unknown sandbox profile '%s', falling back to 'standard'",
                profile_name,
            )
            profile = SANDBOX_PROFILES["standard"]
        return profile

    def _setup_work_directory(self, task_id: str) -> Path:
        """
        Create a work directory for a tool invocation.

        Structure:
            /sandbox/work/{task_id}/
                input/          # Input artifacts
                output/         # Tool output artifacts
                status.pipe     # Named pipe for status messages
                result.json     # Tool execution result

        Args:
            task_id: Unique identifier for this invocation

        Returns:
            Path to the work directory
        """
        work_dir = Path(self._config.work_base_dir) / task_id
        work_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (work_dir / "input").mkdir(exist_ok=True)
        (work_dir / "output").mkdir(exist_ok=True)

        # Create named pipe for status messages
        status_pipe = work_dir / STATUS_PIPE_FILENAME
        if not status_pipe.exists():
            os.mkfifo(status_pipe)

        log.debug("Created work directory: %s", work_dir)
        return work_dir

    def _cleanup_work_directory(self, work_dir: Path) -> None:
        """Remove a work directory and all its contents."""
        try:
            if work_dir.exists():
                shutil.rmtree(work_dir)
                log.debug("Cleaned up work directory: %s", work_dir)
        except Exception as e:
            log.warning("Failed to clean up work directory %s: %s", work_dir, e)

    async def _preload_artifacts(
        self,
        work_dir: Path,
        preloaded_artifacts: Dict[str, PreloadedArtifact],
        artifact_references: Dict[str, ArtifactReference],
        artifact_service: Optional["BaseArtifactService"],
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> tuple:
        """
        Load artifacts into the work directory's input folder.

        Args:
            work_dir: The work directory path
            preloaded_artifacts: Artifacts with content already provided
            artifact_references: References to artifacts that need to be loaded
            artifact_service: The artifact service for loading references
            app_name: App name for artifact scoping
            user_id: User ID for artifact scoping
            session_id: Session ID for artifact scoping

        Returns:
            Tuple of:
            - artifact_paths: Dict mapping parameter names to local file paths (legacy)
            - artifact_metadata: Dict mapping parameter names to rich metadata dicts
              containing {"filename", "mime_type", "version", "local_path"}
        """
        input_dir = work_dir / "input"
        artifact_paths: Dict[str, str] = {}
        artifact_metadata: Dict[str, Dict[str, Any]] = {}

        # Write preloaded artifacts (content is base64-encoded)
        import base64

        for param_name, artifact in preloaded_artifacts.items():
            file_path = input_dir / artifact.filename
            content = base64.b64decode(artifact.content)
            file_path.write_bytes(content)
            artifact_paths[param_name] = str(file_path)
            artifact_metadata[param_name] = {
                "filename": artifact.filename,
                "mime_type": getattr(artifact, "mime_type", "application/octet-stream"),
                "version": getattr(artifact, "version", 0),
                "local_path": str(file_path),
            }
            log.debug(
                "Wrote preloaded artifact: %s -> %s (%d bytes)",
                param_name,
                file_path,
                len(content),
            )

        # Load referenced artifacts via artifact service
        if artifact_service and artifact_references:
            for param_name, ref in artifact_references.items():
                try:
                    artifact = await artifact_service.load_artifact(
                        app_name=app_name,
                        user_id=user_id,
                        session_id=session_id,
                        filename=ref.filename,
                        version=ref.version,
                    )
                    if artifact:
                        file_path = input_dir / ref.filename
                        # artifact.inline_data contains the bytes
                        file_path.write_bytes(artifact.inline_data)
                        artifact_paths[param_name] = str(file_path)
                        artifact_metadata[param_name] = {
                            "filename": ref.filename,
                            "mime_type": getattr(artifact, "mime_type", "application/octet-stream"),
                            "version": ref.version if ref.version is not None else 0,
                            "local_path": str(file_path),
                        }
                        log.debug(
                            "Loaded artifact reference: %s -> %s", param_name, file_path
                        )
                    else:
                        log.warning(
                            "Artifact not found: %s (version=%s)",
                            ref.filename,
                            ref.version,
                        )
                except Exception as e:
                    log.error("Failed to load artifact %s: %s", ref.filename, e)

        return artifact_paths, artifact_metadata

    async def _collect_output_artifacts(
        self,
        work_dir: Path,
        artifact_service: Optional["BaseArtifactService"],
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> List[CreatedArtifact]:
        """
        Collect artifacts created by the tool and save to the shared artifact service.

        Args:
            work_dir: The work directory path
            artifact_service: The shared artifact service for saving artifacts
            app_name: App name for artifact scoping
            user_id: User ID for artifact scoping
            session_id: Session ID for artifact scoping

        Returns:
            List of CreatedArtifact metadata
        """
        output_dir = work_dir / "output"
        created_artifacts: List[CreatedArtifact] = []

        if not output_dir.exists():
            return created_artifacts

        for file_path in output_dir.iterdir():
            if file_path.is_file():
                try:
                    content = file_path.read_bytes()
                    filename = file_path.name

                    # Determine mime type (basic detection)
                    mime_type = "application/octet-stream"
                    if filename.endswith(".json"):
                        mime_type = "application/json"
                    elif filename.endswith(".txt"):
                        mime_type = "text/plain"
                    elif filename.endswith(".csv"):
                        mime_type = "text/csv"
                    elif filename.endswith(".png"):
                        mime_type = "image/png"
                    elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
                        mime_type = "image/jpeg"

                    if artifact_service:
                        from google.genai import types as genai_types

                        version = await artifact_service.save_artifact(
                            app_name=app_name,
                            user_id=user_id,
                            session_id=session_id,
                            filename=filename,
                            artifact=genai_types.Part.from_bytes(
                                data=content, mime_type=mime_type
                            ),
                        )

                        created_artifacts.append(
                            CreatedArtifact(
                                filename=filename,
                                version=version,
                                mime_type=mime_type,
                                size_bytes=len(content),
                            )
                        )
                        log.info(
                            "Saved output artifact: %s (version=%d, %d bytes)",
                            filename,
                            version,
                            len(content),
                        )
                    else:
                        log.warning(
                            "No artifact service configured — cannot save output artifact: %s",
                            filename,
                        )
                except Exception as e:
                    log.error("Failed to save output artifact %s: %s", file_path.name, e)

        return created_artifacts

    def _start_status_reader(
        self,
        status_pipe_path: Path,
        callback: Callable[[str], None],
        stop_event: threading.Event,
    ) -> threading.Thread:
        """
        Start a thread that reads status messages from the named pipe.

        Args:
            status_pipe_path: Path to the named pipe
            callback: Function to call with each status message
            stop_event: Event to signal thread shutdown

        Returns:
            The reader thread
        """

        def reader_thread():
            try:
                # Open in non-blocking mode with select
                fd = os.open(str(status_pipe_path), os.O_RDONLY | os.O_NONBLOCK)
                buffer = ""

                while not stop_event.is_set():
                    try:
                        # Try to read from pipe
                        data = os.read(fd, 4096)
                        if data:
                            buffer += data.decode("utf-8", errors="replace")
                            # Process complete lines
                            while "\n" in buffer:
                                line, buffer = buffer.split("\n", 1)
                                if line.strip():
                                    try:
                                        msg = json.loads(line)
                                        if "status" in msg:
                                            callback(msg["status"])
                                    except json.JSONDecodeError:
                                        log.warning(
                                            "Invalid status message format: %s", line
                                        )
                        else:
                            # No data available, brief sleep
                            time.sleep(0.1)
                    except BlockingIOError:
                        # No data available
                        time.sleep(0.1)
                    except Exception as e:
                        log.debug("Status reader error: %s", e)
                        time.sleep(0.1)

                os.close(fd)
            except Exception as e:
                log.warning("Status reader thread failed: %s", e)

        thread = threading.Thread(target=reader_thread, daemon=True)
        thread.start()
        return thread

    @staticmethod
    def _make_preexec_fn(profile: Dict[str, Any]) -> Callable[[], None]:
        """
        Return a preexec_fn that sets resource limits before exec.

        This runs in the child process after fork() but before exec(), so
        limits are inherited by bwrap and the sandboxed tool process.
        """

        def _set_limits():
            if profile.get("rlimit_as_mb"):
                limit = profile["rlimit_as_mb"] * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
            if profile.get("rlimit_cpu_sec"):
                limit = profile["rlimit_cpu_sec"]
                resource.setrlimit(resource.RLIMIT_CPU, (limit, limit))
            if profile.get("rlimit_fsize_mb"):
                limit = profile["rlimit_fsize_mb"] * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
            if profile.get("rlimit_nofile"):
                limit = profile["rlimit_nofile"]
                resource.setrlimit(resource.RLIMIT_NOFILE, (limit, limit))
            # No core dumps
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

        return _set_limits

    def _write_runner_args(
        self,
        work_dir: Path,
        params: SandboxInvokeParams,
        manifest_entry: ManifestEntry,
        artifact_paths: Dict[str, str],
        artifact_metadata: Dict[str, Dict[str, Any]],
    ) -> Path:
        """
        Write the tool_runner args JSON file to the work directory.

        This is shared by both bwrap and direct execution modes — the IPC
        contract (args file, result file, status pipe, artifact dirs) is
        identical regardless of how the subprocess is launched.

        Returns:
            Path to the written args file
        """
        tool_runner_args = {
            "module": manifest_entry.module,
            "function": manifest_entry.function,
            "args": params.args,
            "tool_config": params.tool_config,
            "artifact_paths": artifact_paths,
            "artifact_metadata": artifact_metadata,
            "status_pipe": str(work_dir / STATUS_PIPE_FILENAME),
            "result_file": str(work_dir / RESULT_FILENAME),
            "output_dir": str(work_dir / "output"),
            "user_id": params.user_id,
            "session_id": params.session_id,
            "app_name": params.app_name,
        }

        args_file = work_dir / "runner_args.json"
        args_file.write_text(json.dumps(tool_runner_args))
        return args_file

    def _build_bwrap_command(
        self,
        work_dir: Path,
        params: SandboxInvokeParams,
        manifest_entry: ManifestEntry,
        artifact_paths: Dict[str, str],
        artifact_metadata: Dict[str, Dict[str, Any]],
        profile: Dict[str, Any],
    ) -> List[str]:
        """
        Build the bubblewrap command line.

        Uses --ro-bind / / as the base filesystem, then overlays:
        - --proc /proc  — fresh procfs scoped to the new PID namespace
        - --dev /dev    — minimal device nodes (null, zero, urandom, etc.)
        - --tmpfs /tmp  — writable temp directory
        - --bind work_dir — writable work directory for tool I/O

        The --proc /proc mount provides proper PID namespace isolation: the
        sandboxed process can only see its own PIDs, cannot read environment
        variables of container processes, and tools like ``ps`` work correctly.

        The container must be started with:
        - --cap-add=SYS_ADMIN (for user namespace creation)
        - --security-opt label=disable (to allow procfs mounts)

        Module and function are resolved from the manifest entry (not from the
        request params), so the agent doesn't need to know implementation details.

        Args:
            work_dir: The work directory path
            params: The invocation parameters
            manifest_entry: The manifest entry for the tool being invoked
            artifact_paths: Mapping of param names to artifact file paths
            artifact_metadata: Rich metadata per artifact param (filename, mime_type, etc.)
            profile: The resolved sandbox profile dict

        Returns:
            Command line as list of strings
        """
        tools_python_dir = self._config.tools_python_dir

        args_file = self._write_runner_args(
            work_dir, params, manifest_entry, artifact_paths, artifact_metadata,
        )

        # Start building the bwrap command
        cmd: List[str] = [self._config.bwrap_bin]

        # Namespace isolation
        cmd.extend([
            "--die-with-parent",
            "--new-session",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
        ])

        if profile.get("network_isolated"):
            cmd.append("--unshare-net")

        # Base filesystem: bind entire root read-only, then overlay proc/dev.
        # Order matters: --ro-bind / / first, then --proc and --dev overlay
        # the bind-mounted /proc and /dev with fresh isolated mounts.
        cmd.extend(["--ro-bind", "/", "/"])

        # Fresh procfs scoped to new PID namespace — sandboxed process can only
        # see its own PIDs and cannot read /proc/<pid>/environ of other processes.
        # Requires --security-opt label=disable on the container.
        cmd.extend(["--proc", "/proc"])

        # Minimal /dev with only essential device nodes
        cmd.extend(["--dev", "/dev"])

        # Writable overlays
        cmd.extend(["--tmpfs", "/tmp"])
        cmd.extend(["--bind", str(work_dir), str(work_dir)])

        if profile.get("writable_var"):
            cmd.extend(["--tmpfs", "/var"])

        # Working directory inside the sandbox
        cmd.extend(["--chdir", str(work_dir)])

        # Environment variables — bwrap always uses --clearenv + explicit --setenv
        # to prevent any env vars from leaking into the sandbox. The bwrap process
        # itself is also started with a minimal env (see execute_tool) so that
        # /proc/1/environ inside the PID namespace doesn't expose secrets.
        cmd.append("--clearenv")
        cmd.extend(["--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin"])
        cmd.extend(["--setenv", "HOME", "/tmp"])
        cmd.extend(["--setenv", "TMPDIR", "/tmp"])
        cmd.extend(["--setenv", "LANG", "C.UTF-8"])
        cmd.extend(["--setenv", "PYTHONPATH", tools_python_dir])
        # Skip heavy built-in tool registration inside the sandbox
        cmd.extend(["--setenv", "_SAM_SANDBOX_LIGHT", "1"])

        if profile.get("keep_env"):
            # For standard/permissive profiles, forward specific safe env vars
            # that the tool may need (e.g., API keys set via tool_config).
            # Note: container secrets like SOLACE_PASSWORD are NOT forwarded.
            for key in ("PYTHONDONTWRITEBYTECODE", "PYTHONUNBUFFERED"):
                val = os.environ.get(key)
                if val:
                    cmd.extend(["--setenv", key, val])

        # Separator and Python command
        cmd.append("--")
        cmd.extend([
            self._config.python_bin,
            "-m",
            TOOL_RUNNER_MODULE,
            str(args_file),
        ])

        return cmd

    def _build_direct_command(
        self,
        work_dir: Path,
        params: SandboxInvokeParams,
        manifest_entry: ManifestEntry,
        artifact_paths: Dict[str, str],
        artifact_metadata: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        """
        Build command for direct execution (no bwrap).

        Uses the same IPC contract (args file, result file, status pipe,
        artifact dirs) but runs as a plain subprocess. Suitable for local
        development on any OS including macOS.

        Args:
            work_dir: The work directory path
            params: The invocation parameters
            manifest_entry: The manifest entry for the tool being invoked
            artifact_paths: Mapping of param names to artifact file paths
            artifact_metadata: Rich metadata per artifact param

        Returns:
            Command line as list of strings
        """
        args_file = self._write_runner_args(
            work_dir, params, manifest_entry, artifact_paths, artifact_metadata,
        )

        return [
            self._config.python_bin,
            "-m",
            TOOL_RUNNER_MODULE,
            str(args_file),
        ]

    async def execute_tool(
        self,
        request: SandboxToolInvocationRequest,
        manifest_entry: ManifestEntry,
        artifact_service: Optional["BaseArtifactService"] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> SandboxToolInvocationResponse:
        """
        Execute a tool invocation in the bwrap sandbox.

        Args:
            request: The tool invocation request
            manifest_entry: The manifest entry for the tool (provides module/function)
            artifact_service: Optional artifact service for loading/saving artifacts
            status_callback: Optional callback for status messages

        Returns:
            The tool invocation response
        """
        params = request.params
        task_id = params.task_id
        log_id = f"[SandboxRunner:{task_id}]"
        start_time = time.time()

        log.info(
            "%s Starting execution: tool=%s, timeout=%ds",
            log_id,
            params.tool_name,
            params.timeout_seconds,
        )

        # Resolve profile
        profile_name = (
            manifest_entry.sandbox_profile
            or params.sandbox_profile
            or self._config.default_profile
        )
        profile = self._get_profile(profile_name)

        # Acquire semaphore to limit concurrent executions
        async with self._execution_semaphore:
            work_dir = None
            stop_event = threading.Event()
            status_thread = None

            try:
                # Set up work directory
                work_dir = self._setup_work_directory(task_id)

                # Preload artifacts
                artifact_paths, artifact_metadata = await self._preload_artifacts(
                    work_dir=work_dir,
                    preloaded_artifacts=params.preloaded_artifacts,
                    artifact_references=params.artifact_references,
                    artifact_service=artifact_service,
                    app_name=params.app_name,
                    user_id=params.user_id,
                    session_id=params.session_id,
                )

                # Start status reader thread
                if status_callback:
                    status_pipe_path = work_dir / STATUS_PIPE_FILENAME
                    status_thread = self._start_status_reader(
                        status_pipe_path, status_callback, stop_event
                    )

                # Build and execute command (bwrap or direct mode)
                if self._config.mode == "direct":
                    cmd = self._build_direct_command(
                        work_dir, params, manifest_entry, artifact_paths,
                        artifact_metadata,
                    )
                    log.debug("%s Running direct command: %s", log_id, " ".join(cmd))

                    # Inherit environment but add PYTHONPATH and sandbox light flag
                    direct_env = os.environ.copy()
                    tools_pp = str(Path(self._config.tools_python_dir).resolve())
                    existing_pp = direct_env.get("PYTHONPATH", "")
                    direct_env["PYTHONPATH"] = (
                        tools_pp + os.pathsep + existing_pp if existing_pp else tools_pp
                    )
                    direct_env["_SAM_SANDBOX_LIGHT"] = "1"

                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(work_dir),
                        env=direct_env,
                    )
                else:
                    cmd = self._build_bwrap_command(
                        work_dir, params, manifest_entry, artifact_paths,
                        artifact_metadata, profile,
                    )
                    log.debug("%s Running bwrap command: %s", log_id, " ".join(cmd))

                    # Run bwrap subprocess with resource limits applied via preexec_fn.
                    # Pass a minimal env so that /proc/1/environ inside the PID
                    # namespace (which is bwrap's own process) doesn't expose
                    # container secrets like SOLACE_PASSWORD.
                    bwrap_env = {
                        "PATH": "/usr/local/bin:/usr/bin:/bin",
                    }
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(work_dir),
                        env=bwrap_env,
                        preexec_fn=self._make_preexec_fn(profile),
                    )

                try:
                    # Wait with timeout (add buffer for bwrap overhead)
                    timeout = params.timeout_seconds + 5
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=timeout
                    )
                except asyncio.TimeoutError:
                    # Kill the process
                    process.kill()
                    await process.wait()
                    execution_time_ms = int((time.time() - start_time) * 1000)

                    log.warning(
                        "%s Execution timed out after %ds",
                        log_id,
                        params.timeout_seconds,
                    )

                    return SandboxToolInvocationResponse(
                        id=request.id,
                        result=SandboxInvokeResult(
                            tool_result={},
                            execution_time_ms=execution_time_ms,
                            timed_out=True,
                            created_artifacts=[],
                        ),
                    )

                # Stop status reader
                stop_event.set()
                if status_thread:
                    status_thread.join(timeout=1.0)

                execution_time_ms = int((time.time() - start_time) * 1000)

                # Check for errors
                if process.returncode != 0:
                    stderr_text = stderr.decode("utf-8", errors="replace")
                    log.error(
                        "%s Sandbox execution failed with code %d: %s",
                        log_id,
                        process.returncode,
                        stderr_text,
                    )

                    return SandboxToolInvocationResponse(
                        id=request.id,
                        error={
                            "code": SandboxErrorCodes.EXECUTION_ERROR,
                            "message": f"Sandbox execution failed: {stderr_text[:500]}",
                        },
                    )

                # Read result file
                result_file = work_dir / RESULT_FILENAME
                if not result_file.exists():
                    log.error("%s Result file not found", log_id)
                    return SandboxToolInvocationResponse(
                        id=request.id,
                        error={
                            "code": SandboxErrorCodes.INTERNAL_ERROR,
                            "message": "Tool execution completed but no result file found",
                        },
                    )

                try:
                    result_data = json.loads(result_file.read_text())
                except json.JSONDecodeError as e:
                    log.error("%s Invalid result JSON: %s", log_id, e)
                    return SandboxToolInvocationResponse(
                        id=request.id,
                        error={
                            "code": SandboxErrorCodes.INTERNAL_ERROR,
                            "message": f"Invalid result format: {e}",
                        },
                    )

                # Check for tool-level error
                if result_data.get("error"):
                    return SandboxToolInvocationResponse(
                        id=request.id,
                        error={
                            "code": SandboxErrorCodes.TOOL_ERROR,
                            "message": result_data["error"],
                        },
                    )

                # Collect output artifacts and save to shared artifact service
                created_artifacts = await self._collect_output_artifacts(
                    work_dir=work_dir,
                    artifact_service=artifact_service,
                    app_name=params.app_name,
                    user_id=params.user_id,
                    session_id=params.session_id,
                )

                log.info(
                    "%s Execution completed in %dms, %d artifacts created",
                    log_id,
                    execution_time_ms,
                    len(created_artifacts),
                )

                return SandboxToolInvocationResponse(
                    id=request.id,
                    result=SandboxInvokeResult(
                        tool_result=result_data.get("result", {}),
                        execution_time_ms=execution_time_ms,
                        timed_out=False,
                        created_artifacts=created_artifacts,
                    ),
                )

            except Exception as e:
                execution_time_ms = int((time.time() - start_time) * 1000)
                log.exception("%s Execution failed: %s", log_id, e)

                return SandboxToolInvocationResponse(
                    id=request.id,
                    error={
                        "code": SandboxErrorCodes.INTERNAL_ERROR,
                        "message": f"Sandbox execution failed: {str(e)}",
                    },
                )

            finally:
                # Clean up
                stop_event.set()
                if status_thread and status_thread.is_alive():
                    status_thread.join(timeout=1.0)
                if work_dir:
                    self._cleanup_work_directory(work_dir)
