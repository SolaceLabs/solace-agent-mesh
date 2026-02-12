"""
Tool Runner - Executes tools inside the bubblewrap (bwrap) sandbox.

This module is invoked by bwrap to run a Python tool function within
the sandboxed environment. It:
1. Reads invocation parameters from a JSON file
2. Detects special type annotations (ToolContextFacade, Artifact)
3. Sets up context and artifact injection (mirroring DynamicTool behavior)
4. Imports and calls the tool function
5. Extracts output artifacts from ToolResult DataObjects
6. Writes the result to a JSON file

For tools WITH type annotations (portable tools):
    - ToolContextFacade param detected → SandboxToolContextFacade injected by name
    - Artifact params detected → Artifact objects built from preloaded files
    - ToolResult return handled → DataObjects extracted to output dir

For tools WITHOUT type annotations (legacy sandbox-only tools):
    - Context passed as first positional arg
    - Dict return passed through unchanged

Usage:
    python -m solace_agent_mesh.sandbox.tool_runner /path/to/runner_args.json
"""

import asyncio
import importlib
import inspect
import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .context_facade import SandboxToolContextFacade

# Configure logging for sandbox environment
logging.basicConfig(
    level=logging.INFO,
    format="[sandbox] %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lightweight loading of individual modules WITHOUT triggering package __init__
# ---------------------------------------------------------------------------
# The agent.tools.__init__ registers ALL built-in tools (onnxruntime, pydub,
# deep_research, etc.) which takes ~5 seconds in a cold sandbox. We avoid
# this by loading individual module files directly.

def _load_module_file(module_name: str, file_path: str):
    """Load a Python module from a file path without triggering parent __init__.py."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_name} from {file_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _find_agent_module_path(relative_path: str) -> Optional[str]:
    """Find the file path for an agent module relative to solace_agent_mesh."""
    try:
        import solace_agent_mesh
        base = Path(solace_agent_mesh.__file__).parent
        candidate = base / relative_path
        if candidate.exists():
            return str(candidate)
    except (ImportError, AttributeError):
        pass
    return None


# Local lightweight version of ArtifactTypeInfo for detection only.
# Avoids importing from agent.tools which triggers heavy __init__.
class _ArtifactTypeInfo:
    __slots__ = ("is_artifact", "is_list", "is_optional")

    def __init__(self, is_artifact=False, is_list=False, is_optional=False):
        self.is_artifact = is_artifact
        self.is_list = is_list
        self.is_optional = is_optional


# ---------------------------------------------------------------------------
# Type annotation detection (mirrors dynamic_tool.py logic)
# ---------------------------------------------------------------------------

def _is_tool_context_facade_param(annotation) -> bool:
    """Check if an annotation represents a ToolContextFacade parameter.

    Uses string-based checks first to avoid importing heavy modules.
    Falls back to identity comparison only when the class is already loaded.
    """
    if annotation is None:
        return False

    # Check SandboxToolContextFacade itself (tools may annotate with either)
    if annotation is SandboxToolContextFacade:
        return True

    # String annotation check
    if isinstance(annotation, str):
        if "ToolContextFacade" in annotation:
            return True

    # Check class name without importing (avoids pulling in google.adk)
    ann_name = getattr(annotation, "__name__", "") or ""
    ann_qualname = getattr(annotation, "__qualname__", "") or ""
    if ann_name == "ToolContextFacade" or ann_qualname == "ToolContextFacade":
        return True

    return False


def _is_artifact_annotation(annotation) -> bool:
    """Check if an annotation is the Artifact type (by name, not import)."""
    if annotation is None:
        return False
    if isinstance(annotation, str):
        return annotation.strip() == "Artifact"
    return getattr(annotation, "__name__", "") == "Artifact"


def _detect_special_params(func) -> Tuple[Optional[str], Dict[str, Any]]:
    """Detect ToolContextFacade and Artifact parameters from type annotations.

    Uses lightweight string/name checks to avoid importing heavy modules
    like google.adk or the full agent.tools package.

    Returns:
        Tuple of (ctx_param_name, artifact_params_dict)
        - ctx_param_name: Name of the ToolContextFacade parameter, or None
        - artifact_params_dict: Dict of param_name → ArtifactTypeInfo for Artifact params
    """
    from typing import get_origin, get_args, Union

    sig = inspect.signature(func)
    ctx_param_name = None
    artifact_params = {}

    for name, param in sig.parameters.items():
        if name in ("self", "cls", "kwargs"):
            continue
        ann = param.annotation
        if ann is inspect.Parameter.empty:
            continue

        if _is_tool_context_facade_param(ann):
            ctx_param_name = name
            log.debug("Detected ToolContextFacade param: '%s'", name)
        elif _is_artifact_annotation(ann):
            artifact_params[name] = _ArtifactTypeInfo(is_artifact=True)
            log.debug("Detected Artifact param: '%s'", name)
        else:
            # Check for List[Artifact], Optional[Artifact]
            origin = get_origin(ann)
            if origin is not None:
                args = get_args(ann)
                if args:
                    if origin is list and _is_artifact_annotation(args[0]):
                        artifact_params[name] = _ArtifactTypeInfo(
                            is_artifact=True, is_list=True
                        )
                        log.debug("Detected List[Artifact] param: '%s'", name)
                    elif origin is Union:
                        has_none = type(None) in args
                        for arg in args:
                            if arg is not type(None) and _is_artifact_annotation(arg):
                                artifact_params[name] = _ArtifactTypeInfo(
                                    is_artifact=True, is_optional=has_none
                                )
                                log.debug("Detected Optional[Artifact] param: '%s'", name)
                                break

    return ctx_param_name, artifact_params


# ---------------------------------------------------------------------------
# Artifact object construction
# ---------------------------------------------------------------------------

def _build_artifact_objects(
    artifact_params: Dict[str, Any],
    artifact_metadata: Dict[str, Dict[str, Any]],
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """Build Artifact objects from preloaded files for annotated parameters.

    Args:
        artifact_params: Dict of param_name → ArtifactTypeInfo
        artifact_metadata: Dict of param_name → metadata dict from runner_args
        args: The raw tool arguments (for List[Artifact] filename lists)

    Returns:
        Dict of param_name → Artifact (or List[Artifact]) to inject as kwargs
    """
    try:
        # Load artifact_types.py directly from file to avoid triggering
        # agent/tools/__init__.py which imports ALL built-in tools.
        mod_path = _find_agent_module_path("agent/tools/artifact_types.py")
        if not mod_path:
            raise ImportError("artifact_types.py not found")
        _artifact_mod = _load_module_file("_artifact_types_direct", mod_path)
        Artifact = _artifact_mod.Artifact
    except (ImportError, AttributeError) as e:
        log.warning("Could not import Artifact type — skipping artifact injection: %s", e)
        return {}

    injected = {}

    for param_name, type_info in artifact_params.items():
        if type_info.is_list:
            # List[Artifact] — each item is keyed as "param[0]", "param[1]", etc.
            artifacts = []
            filenames = args.get(param_name, [])
            for idx, _fname in enumerate(filenames):
                ref_key = f"{param_name}[{idx}]"
                ref_meta = artifact_metadata.get(ref_key)
                if ref_meta:
                    ref_path = Path(ref_meta["local_path"])
                    if ref_path.exists():
                        artifacts.append(Artifact(
                            content=ref_path.read_bytes(),
                            filename=ref_meta["filename"],
                            version=ref_meta.get("version", 0),
                            mime_type=ref_meta.get("mime_type", "application/octet-stream"),
                        ))
                    else:
                        log.warning("Artifact file missing for %s: %s", ref_key, ref_path)
                else:
                    log.warning("No metadata for list artifact: %s", ref_key)
            injected[param_name] = artifacts
            log.debug("Built %d Artifact objects for list param '%s'", len(artifacts), param_name)
        else:
            # Single Artifact
            meta = artifact_metadata.get(param_name)
            if not meta:
                log.warning("No metadata for artifact param: %s", param_name)
                continue
            path = Path(meta["local_path"])
            if not path.exists():
                log.warning("Artifact file missing for %s: %s", param_name, path)
                continue
            injected[param_name] = Artifact(
                content=path.read_bytes(),
                filename=meta["filename"],
                version=meta.get("version", 0),
                mime_type=meta.get("mime_type", "application/octet-stream"),
            )
            log.debug("Built Artifact object for param '%s': %s", param_name, meta["filename"])

    return injected


# ---------------------------------------------------------------------------
# Output artifact extraction from ToolResult
# ---------------------------------------------------------------------------

def _extract_output_artifacts(result: Any, output_dir: str) -> Any:
    """Extract DataObjects with artifact disposition and write to output dir.

    When a portable tool returns ToolResult with DataObjects, artifacts
    need to be written to the output directory so _collect_output_artifacts()
    in sandbox_runner picks them up.

    Args:
        result: The tool's return value (may be ToolResult, dict, etc.)
        output_dir: Path to the output directory

    Returns:
        The result with artifact DataObjects removed (only inline ones remain)
    """
    if not hasattr(result, "data_objects") or not result.data_objects:
        return result

    try:
        # Load tool_result.py directly from file to avoid triggering
        # agent/tools/__init__.py which imports ALL built-in tools.
        mod_path = _find_agent_module_path("agent/tools/tool_result.py")
        if not mod_path:
            raise ImportError("tool_result.py not found")
        _result_mod = _load_module_file("_tool_result_direct", mod_path)
        DataDisposition = _result_mod.DataDisposition
    except (ImportError, AttributeError):
        log.debug("Could not import DataDisposition — skipping artifact extraction")
        return result

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    remaining = []

    for obj in result.data_objects:
        disposition = getattr(obj, "disposition", None)
        # Write artifact-disposition objects to output dir
        if disposition in (
            DataDisposition.ARTIFACT,
            DataDisposition.AUTO,
            DataDisposition.ARTIFACT_WITH_PREVIEW,
        ):
            content = obj.content
            if isinstance(content, str):
                content = content.encode("utf-8")
            artifact_path = output_path / obj.name
            artifact_path.write_bytes(content)
            log.info("Extracted output artifact: %s (%d bytes)", obj.name, len(content))
        else:
            remaining.append(obj)

    result.data_objects = remaining
    return result


# ---------------------------------------------------------------------------
# Legacy context wrapper for backward compatibility
# ---------------------------------------------------------------------------

class _LegacyContextWrapper:
    """Wraps SandboxToolContextFacade with the old sync API for legacy tools.

    Legacy sandbox tools (no type annotations) call sync methods like:
    - ctx.load_artifact(param_name) → Optional[bytes]
    - ctx.load_artifact_text(param_name) → Optional[str]
    - ctx.list_artifacts() → Dict[str, str]
    - ctx.save_artifact(filename, content) → str
    - ctx.send_status(message) → bool

    The new facade has async versions of load/list. This wrapper provides
    the old sync API by delegating to the legacy methods on the facade.
    """

    def __init__(self, facade: SandboxToolContextFacade):
        self._facade = facade

    @property
    def user_id(self) -> str:
        return self._facade.user_id

    @property
    def session_id(self) -> str:
        return self._facade.session_id

    @property
    def app_name(self) -> str:
        return self._facade.app_name

    def get_config(self, key: str, default: Any = None) -> Any:
        return self._facade.get_config(key, default)

    def send_status(self, message: str) -> bool:
        return self._facade.send_status(message)

    def load_artifact(self, param_name: str) -> Optional[bytes]:
        """Load artifact by parameter name (sync, legacy API)."""
        return self._facade.load_artifact_by_param(param_name)

    def load_artifact_text(self, param_name: str, encoding: str = "utf-8") -> Optional[str]:
        """Load artifact as text by parameter name (sync, legacy API)."""
        content = self._facade.load_artifact_by_param(param_name)
        if content is None:
            return None
        return content.decode(encoding)

    def list_artifacts(self) -> Dict[str, str]:
        """List artifacts as param_name → path dict (sync, legacy API)."""
        return dict(self._facade._artifact_paths)

    def save_artifact(self, filename: str, content: bytes,
                      mime_type: str = "application/octet-stream") -> str:
        return self._facade.save_artifact(filename, content, mime_type)

    def save_artifact_text(self, filename: str, content: str,
                           encoding: str = "utf-8",
                           mime_type: str = "text/plain") -> str:
        return self._facade.save_artifact_text(filename, content, encoding, mime_type)

    def list_output_artifacts(self) -> list:
        return self._facade.list_output_artifacts()


# ---------------------------------------------------------------------------
# Tool loading and result serialization
# ---------------------------------------------------------------------------

def load_tool_function(module_path: str, function_name: str):
    """
    Dynamically import and return a tool function.

    Args:
        module_path: Dot-separated module path (e.g., "mytools.data")
        function_name: Name of the function to call

    Returns:
        The callable function

    Raises:
        ImportError: If module cannot be imported
        AttributeError: If function not found in module
    """
    log.info("Loading tool: %s.%s", module_path, function_name)
    module = importlib.import_module(module_path)
    func = getattr(module, function_name)

    if not callable(func):
        raise TypeError(f"{module_path}.{function_name} is not callable")

    return func


def serialize_result(result: Any) -> Dict[str, Any]:
    """
    Serialize a tool result to a JSON-compatible format.

    Handles ToolResult objects (via to_serializable()), plain dicts, and strings.

    Args:
        result: The tool function's return value

    Returns:
        JSON-serializable dictionary
    """
    # Handle None
    if result is None:
        return {"text": None, "data_objects": []}

    # Handle ToolResult objects (Pydantic model with status + data_objects).
    # Use model_dump() so the dict has exactly the fields ToolResult expects —
    # the agent-side ToolResultProcessor reconstructs via ToolResult(**dict).
    if hasattr(result, "model_dump") and hasattr(result, "data_objects"):
        return result.model_dump()

    # Handle dict directly
    if isinstance(result, dict):
        return result

    # Handle string
    if isinstance(result, str):
        return {"text": result, "data_objects": []}

    # Handle other types - try to convert to string
    try:
        return {"text": str(result), "data_objects": []}
    except Exception:
        return {"text": repr(result), "data_objects": []}


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

async def run_tool_async(
    module_path: str,
    function_name: str,
    args: Dict[str, Any],
    context: SandboxToolContextFacade,
    artifact_metadata: Dict[str, Dict[str, Any]],
    output_dir: str,
) -> Dict[str, Any]:
    """
    Run a tool function (sync or async) with annotation-aware injection.

    For tools with ToolContextFacade/Artifact type annotations:
    - Detects special params from function signature
    - Builds Artifact objects from preloaded files
    - Injects context and artifacts by parameter name

    For tools without annotations (legacy):
    - Passes context as first positional arg, args as kwargs

    Args:
        module_path: Module path to import
        function_name: Function name to call
        args: Arguments to pass to the function
        context: The sandbox context facade
        artifact_metadata: Rich metadata per artifact param
        output_dir: Path for output artifacts

    Returns:
        Serialized result dictionary
    """
    func = load_tool_function(module_path, function_name)

    # Detect special parameters from type annotations
    ctx_param_name, artifact_params = _detect_special_params(func)

    if ctx_param_name or artifact_params:
        # New-style: inject by parameter name (portable tools)
        log.info(
            "Using portable injection: ctx_param=%s, artifact_params=%s",
            ctx_param_name,
            list(artifact_params.keys()),
        )
        kwargs = dict(args)

        # Build and inject Artifact objects
        if artifact_params:
            artifact_objects = _build_artifact_objects(artifact_params, artifact_metadata, args)
            kwargs.update(artifact_objects)

        # Inject context facade by detected parameter name
        if ctx_param_name:
            kwargs[ctx_param_name] = context

        if asyncio.iscoroutinefunction(func):
            result = await func(**kwargs)
        else:
            result = func(**kwargs)
    else:
        # Legacy: context as first positional arg with sync wrapper
        log.info("Using legacy injection: context as first positional arg")
        legacy_ctx = _LegacyContextWrapper(context)
        if asyncio.iscoroutinefunction(func):
            result = await func(legacy_ctx, **args)
        else:
            result = func(legacy_ctx, **args)

    # Extract artifact DataObjects to output dir before serializing
    result = _extract_output_artifacts(result, output_dir)

    return serialize_result(result)


def run_tool(runner_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool with the given arguments.

    Args:
        runner_args: Dictionary containing:
            - module: Module path
            - function: Function name
            - args: Tool arguments
            - tool_config: Tool configuration
            - artifact_paths: Legacy mapping of param names to file paths
            - artifact_metadata: Rich metadata per artifact param
            - status_pipe: Path to status named pipe
            - result_file: Path to write result
            - output_dir: Directory for output artifacts
            - user_id: User ID
            - session_id: Session ID
            - app_name: Application name

    Returns:
        Result dictionary with either 'result' or 'error' key
    """
    module_path = runner_args["module"]
    function_name = runner_args["function"]
    args = runner_args.get("args", {})
    tool_config = runner_args.get("tool_config", {})
    artifact_paths = runner_args.get("artifact_paths", {})
    artifact_metadata = runner_args.get("artifact_metadata", {})
    status_pipe = runner_args.get("status_pipe", "")
    output_dir = runner_args.get("output_dir", "/sandbox/output")
    user_id = runner_args.get("user_id", "unknown")
    session_id = runner_args.get("session_id", "unknown")
    app_name = runner_args.get("app_name", "")

    log.info(
        "Running tool: %s.%s (user=%s, session=%s)",
        module_path,
        function_name,
        user_id,
        session_id,
    )

    # Build filename-keyed artifact dict for the portable API
    artifacts_by_filename: Dict[str, Dict[str, Any]] = {}
    for _param_name, meta in artifact_metadata.items():
        filename = meta.get("filename")
        if filename:
            artifacts_by_filename[filename] = {
                "local_path": meta["local_path"],
                "mime_type": meta.get("mime_type", "application/octet-stream"),
                "version": meta.get("version", 0),
            }

    # Create context facade
    context = SandboxToolContextFacade(
        status_pipe_path=status_pipe,
        tool_config=tool_config,
        artifacts=artifacts_by_filename,
        output_dir=output_dir,
        user_id=user_id,
        session_id=session_id,
        app_name=app_name,
        artifact_paths=artifact_paths,
    )

    try:
        # Run the tool
        result = asyncio.run(
            run_tool_async(
                module_path, function_name, args, context,
                artifact_metadata, output_dir,
            )
        )
        return {"result": result}

    except ImportError as e:
        log.error("Failed to import tool module: %s", e)
        return {"error": f"Import error: {e}"}

    except AttributeError as e:
        log.error("Tool function not found: %s", e)
        return {"error": f"Function not found: {e}"}

    except TypeError as e:
        log.error("Tool function call error: %s", e)
        return {"error": f"Call error: {e}"}

    except Exception as e:
        log.exception("Tool execution failed: %s", e)
        tb = traceback.format_exc()
        return {"error": f"Execution error: {e}\n{tb}"}


def main():
    """
    Main entry point for the tool runner.

    Reads runner arguments from a JSON file and writes result to another JSON file.
    """
    if len(sys.argv) < 2:
        print("Usage: python -m solace_agent_mesh.sandbox.tool_runner <args_file>", file=sys.stderr)
        sys.exit(1)

    args_file = Path(sys.argv[1])

    if not args_file.exists():
        print(f"Error: Arguments file not found: {args_file}", file=sys.stderr)
        sys.exit(1)

    try:
        runner_args = json.loads(args_file.read_text())
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in arguments file: {e}", file=sys.stderr)
        sys.exit(1)

    # Run the tool
    result = run_tool(runner_args)

    # Write result to file
    result_file = runner_args.get("result_file")
    if result_file:
        Path(result_file).write_text(json.dumps(result, default=str))
        log.info("Result written to: %s", result_file)
    else:
        # Fall back to stdout
        print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
