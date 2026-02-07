"""
NsjailRunner - Subprocess management for nsjail execution.

This module provides the NsjailRunner class which manages the lifecycle of
nsjail subprocesses for executing Python tools in a sandboxed environment.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

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
DEFAULT_NSJAIL_BIN = "/usr/bin/nsjail"
DEFAULT_NSJAIL_CONFIG_DIR = "/etc/nsjail"
DEFAULT_PYTHON_BIN = "/usr/local/bin/python3"
DEFAULT_WORK_BASE_DIR = "/sandbox/work"

# Status pipe protocol
STATUS_PIPE_FILENAME = "status.pipe"
RESULT_FILENAME = "result.json"
TOOL_RUNNER_MODULE = "solace_agent_mesh.sandbox.tool_runner"


@dataclass
class NsjailConfig:
    """Configuration for nsjail execution."""

    nsjail_bin: str = DEFAULT_NSJAIL_BIN
    config_dir: str = DEFAULT_NSJAIL_CONFIG_DIR
    python_bin: str = DEFAULT_PYTHON_BIN
    work_base_dir: str = DEFAULT_WORK_BASE_DIR
    default_profile: str = "standard"
    max_concurrent_executions: int = 4
    # Additional mounts to pass to nsjail
    extra_mounts: List[Dict[str, str]] = field(default_factory=list)


class NsjailRunner:
    """
    Manages nsjail subprocess execution for sandboxed Python tools.

    This class handles:
    - Setting up work directories for each invocation
    - Creating named pipes for status message forwarding
    - Spawning nsjail with appropriate configuration
    - Enforcing timeouts at multiple levels
    - Collecting results and cleaning up
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the NsjailRunner.

        Args:
            config: Optional configuration dictionary with nsjail settings
        """
        config = config or {}
        self._config = NsjailConfig(
            nsjail_bin=config.get("nsjail_bin", DEFAULT_NSJAIL_BIN),
            config_dir=config.get("config_dir", DEFAULT_NSJAIL_CONFIG_DIR),
            python_bin=config.get("python_bin", DEFAULT_PYTHON_BIN),
            work_base_dir=config.get("work_base_dir", DEFAULT_WORK_BASE_DIR),
            default_profile=config.get("default_profile", "standard"),
            max_concurrent_executions=config.get("max_concurrent_executions", 4),
            extra_mounts=config.get("extra_mounts", []),
        )

        # Semaphore to limit concurrent executions
        self._execution_semaphore = asyncio.Semaphore(
            self._config.max_concurrent_executions
        )

        log.info(
            "NsjailRunner initialized: config_dir=%s, max_concurrent=%d",
            self._config.config_dir,
            self._config.max_concurrent_executions,
        )

    def _get_nsjail_config_path(self, profile: str) -> str:
        """Get the path to an nsjail configuration file."""
        return os.path.join(self._config.config_dir, f"{profile}.cfg")

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
    ) -> Dict[str, str]:
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
            Dict mapping parameter names to local file paths
        """
        input_dir = work_dir / "input"
        artifact_paths: Dict[str, str] = {}

        # Write preloaded artifacts
        for param_name, artifact in preloaded_artifacts.items():
            file_path = input_dir / artifact.filename
            content = (
                artifact.content.encode()
                if isinstance(artifact.content, str)
                else artifact.content
            )
            file_path.write_bytes(content)
            artifact_paths[param_name] = str(file_path)
            log.debug("Wrote preloaded artifact: %s -> %s", param_name, file_path)

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

        return artifact_paths

    async def _collect_output_artifacts(
        self,
        work_dir: Path,
        artifact_service: Optional["BaseArtifactService"],
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> List[CreatedArtifact]:
        """
        Collect artifacts created by the tool and save to artifact service.

        Args:
            work_dir: The work directory path
            artifact_service: The artifact service for saving artifacts
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
                        # Import Part for creating artifact
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
                        log.debug(
                            "Saved output artifact: %s (version=%s)", filename, version
                        )
                    else:
                        # No artifact service - just report the file
                        created_artifacts.append(
                            CreatedArtifact(
                                filename=filename,
                                version=0,
                                mime_type=mime_type,
                                size_bytes=len(content),
                            )
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

    def _build_nsjail_command(
        self,
        work_dir: Path,
        params: SandboxInvokeParams,
        artifact_paths: Dict[str, str],
    ) -> List[str]:
        """
        Build the nsjail command line.

        Args:
            work_dir: The work directory path
            params: The invocation parameters
            artifact_paths: Mapping of param names to artifact file paths

        Returns:
            Command line as list of strings
        """
        profile = params.sandbox_profile or self._config.default_profile
        config_path = self._get_nsjail_config_path(profile)

        # Build the tool runner command that runs inside nsjail
        tool_runner_args = {
            "module": params.module,
            "function": params.function,
            "args": params.args,
            "tool_config": params.tool_config,
            "artifact_paths": artifact_paths,
            "status_pipe": str(work_dir / STATUS_PIPE_FILENAME),
            "result_file": str(work_dir / RESULT_FILENAME),
            "output_dir": str(work_dir / "output"),
            "user_id": params.user_id,
            "session_id": params.session_id,
        }

        # Write tool runner args to work dir
        args_file = work_dir / "runner_args.json"
        args_file.write_text(json.dumps(tool_runner_args))

        cmd = [
            self._config.nsjail_bin,
            "--config",
            config_path,
            # Time limit in seconds
            "--time_limit",
            str(params.timeout_seconds),
            # Mount the work directory
            "--bindmount",
            f"{work_dir}:{work_dir}:rw",
            # Run Python with the tool runner module
            "--",
            self._config.python_bin,
            "-m",
            TOOL_RUNNER_MODULE,
            str(args_file),
        ]

        return cmd

    async def execute_tool(
        self,
        request: SandboxToolInvocationRequest,
        artifact_service: Optional["BaseArtifactService"] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> SandboxToolInvocationResponse:
        """
        Execute a tool invocation in the nsjail sandbox.

        Args:
            request: The tool invocation request
            artifact_service: Optional artifact service for loading/saving artifacts
            status_callback: Optional callback for status messages

        Returns:
            The tool invocation response
        """
        params = request.params
        task_id = params.task_id
        log_id = f"[NsjailRunner:{task_id}]"
        start_time = time.time()

        log.info(
            "%s Starting execution: tool=%s, timeout=%ds",
            log_id,
            params.tool_name,
            params.timeout_seconds,
        )

        # Acquire semaphore to limit concurrent executions
        async with self._execution_semaphore:
            work_dir = None
            stop_event = threading.Event()
            status_thread = None

            try:
                # Set up work directory
                work_dir = self._setup_work_directory(task_id)

                # Preload artifacts
                artifact_paths = await self._preload_artifacts(
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

                # Build and execute nsjail command
                cmd = self._build_nsjail_command(work_dir, params, artifact_paths)
                log.debug("%s Running command: %s", log_id, " ".join(cmd))

                # Run nsjail subprocess
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(work_dir),
                )

                try:
                    # Wait with timeout (add buffer for nsjail overhead)
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
                        "%s Execution timed out after %ds", log_id, params.timeout_seconds
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
                        "%s nsjail failed with code %d: %s",
                        log_id,
                        process.returncode,
                        stderr_text,
                    )

                    return SandboxToolInvocationResponse(
                        id=request.id,
                        error={
                            "code": SandboxErrorCodes.EXECUTION_ERROR,
                            "message": f"nsjail execution failed: {stderr_text[:500]}",
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

                # Collect output artifacts
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
