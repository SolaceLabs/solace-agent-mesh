#!/usr/bin/env python3
"""
Test that the SAME portable tool works in both execution environments:
  1. In-process via _FunctionAsDynamicTool (python executor path)
  2. Sandbox via sandbox tool_runner (sam_remote executor path)

This proves the portability guarantee: a tool with Artifact + ToolContextFacade
annotations produces the same result regardless of where it runs.

Usage:
    python test_portable_both_paths.py
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# ── Locate source repos ──────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_SAM_ROOT = _SCRIPT_DIR.parent.parent
_SAC_ROOT = _SAM_ROOT.parent / "solace-ai-connector"

for _src in [_SAM_ROOT / "src", _SAC_ROOT / "src"]:
    _src_str = str(_src)
    if _src_str not in sys.path:
        sys.path.insert(0, _src_str)

# Also add the tools directory so we can import the portable tool
_TOOLS_DIR = _SCRIPT_DIR / "tools"
sys.path.insert(0, str(_TOOLS_DIR))

# ── Imports ───────────────────────────────────────────────────────────────
from google.adk.tools import ToolContext
from google.genai import types as genai_types

from solace_agent_mesh.agent.tools.dynamic_tool import _FunctionAsDynamicTool
from solace_agent_mesh.agent.tools.artifact_types import Artifact
from solace_agent_mesh.agent.tools.tool_result import ToolResult
from solace_agent_mesh.agent.utils.tool_context_facade import ToolContextFacade
from solace_agent_mesh.agent.adk.artifacts.filesystem_artifact_service import (
    FilesystemArtifactService,
)
from solace_agent_mesh.sandbox.context_facade import SandboxToolContextFacade
from solace_agent_mesh.sandbox.tool_runner import (
    _detect_special_params,
    _build_artifact_objects,
    _extract_output_artifacts,
    _LegacyContextWrapper,
    serialize_result,
)

# Import the portable tool function
from portable_process_file import portable_process_file

# ── ANSI colour helpers ──────────────────────────────────────────────────
_BOLD = "\033[1m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_CYAN = "\033[36m"
_DIM = "\033[2m"
_RESET = "\033[0m"

# ── Test input ────────────────────────────────────────────────────────────
TEST_CONTENT = """\
This is a test file for the portable process_file tool.
It contains multiple lines of text that will be analyzed.
The tool should count characters, words, and lines.
It demonstrates Artifact type annotation injection.
Line five is here.
Line six follows.
And finally, line seven."""

APP_NAME = "test_app"
USER_ID = "test_user"
SESSION_ID = "test_session"


def check(label: str, ok: bool, detail: str = ""):
    symbol = f"{_GREEN}✓{_RESET}" if ok else f"{_RED}✗{_RESET}"
    print(f"  {symbol} {label}", end="")
    if detail:
        print(f"  {_DIM}({detail}){_RESET}", end="")
    print()
    if not ok:
        raise AssertionError(f"FAIL: {label} — {detail}")


# ══════════════════════════════════════════════════════════════════════════
# Path 1: In-process via _FunctionAsDynamicTool
# ══════════════════════════════════════════════════════════════════════════

async def test_inprocess_path() -> dict:
    """Run portable_process_file through the DynamicTool framework path."""
    print(f"\n{_BOLD}{_CYAN}Path 1: In-process (_FunctionAsDynamicTool){_RESET}")

    # -- Step 1: Wrap the function as a DynamicTool and verify detection ----
    tool = _FunctionAsDynamicTool(portable_process_file)

    check(
        "Tool name detected",
        tool.tool_name == "portable_process_file",
        tool.tool_name,
    )
    check(
        "ctx_facade_param_name detected",
        tool.ctx_facade_param_name == "ctx",
        f"found: {tool.ctx_facade_param_name}",
    )
    check(
        "Artifact param detected",
        "input_file" in tool.artifact_params,
        f"found: {list(tool.artifact_params.keys())}",
    )
    check(
        "Artifact is_list=False",
        not tool.artifact_params["input_file"].is_list,
    )

    # -- Step 2: Set up artifact service and seed a test artifact -----------
    with tempfile.TemporaryDirectory() as tmp:
        artifact_service = FilesystemArtifactService(tmp)

        # Save the test file as an artifact
        version = await artifact_service.save_artifact(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=SESSION_ID,
            filename="test_input.txt",
            artifact=genai_types.Part.from_bytes(
                data=TEST_CONTENT.encode("utf-8"),
                mime_type="text/plain",
            ),
        )
        check("Artifact saved", version == 0, f"version={version}")

        # -- Step 3: Build a mock ToolContext with real artifact service ----
        mock_session = Mock()
        mock_session.id = SESSION_ID
        mock_session.app_name = APP_NAME
        mock_session.user_id = USER_ID

        mock_inv_context = Mock()
        mock_inv_context.artifact_service = artifact_service
        mock_inv_context.app_name = APP_NAME
        mock_inv_context.user_id = USER_ID
        mock_inv_context.session = mock_session

        mock_tool_context = Mock(spec=ToolContext)
        mock_tool_context._invocation_context = mock_inv_context
        mock_tool_context.state = {}
        mock_tool_context.actions = Mock()
        mock_tool_context.actions.artifact_delta = {}

        # -- Step 4: Invoke the tool via DynamicTool.run_async() -----------
        result = await tool.run_async(
            args={"input_file": "test_input.txt"},
            tool_context=mock_tool_context,
        )

        check("Result returned", result is not None)
        check(
            "Result is ToolResult",
            isinstance(result, ToolResult),
            type(result).__name__,
        )
        check("Status is success", result.status == "success")
        check(
            "Message contains line/word counts",
            "lines" in result.message and "words" in result.message,
            result.message,
        )
        check(
            "Has data_objects (pre-extraction)",
            len(result.data_objects) == 1,
            f"count={len(result.data_objects)}",
        )
        check(
            "DataObject name",
            result.data_objects[0].name == "processing_summary.txt",
        )

        # Normalize: model_dump for comparison (mirrors what ToolResultProcessor does)
        return result.model_dump()


# ══════════════════════════════════════════════════════════════════════════
# Path 2: Sandbox via tool_runner (same code, sandbox context)
# ══════════════════════════════════════════════════════════════════════════

async def test_sandbox_path() -> dict:
    """Run portable_process_file through the sandbox tool_runner path."""
    print(f"\n{_BOLD}{_CYAN}Path 2: Sandbox (tool_runner){_RESET}")

    # -- Step 1: Annotation detection (same as tool_runner does) ----------
    ctx_param_name, artifact_params = _detect_special_params(portable_process_file)

    check(
        "ctx param detected",
        ctx_param_name == "ctx",
        f"found: {ctx_param_name}",
    )
    check(
        "Artifact param detected",
        "input_file" in artifact_params,
        f"found: {list(artifact_params.keys())}",
    )

    # -- Step 2: Simulate what sandbox_runner does: write artifact to input dir
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        # Write artifact file (simulates _preload_artifacts)
        artifact_file = input_dir / "test_input.txt"
        artifact_file.write_text(TEST_CONTENT)

        # Build metadata (same structure sandbox_runner passes)
        artifact_metadata = {
            "input_file": {
                "filename": "test_input.txt",
                "mime_type": "text/plain",
                "version": 0,
                "local_path": str(artifact_file),
            }
        }

        # -- Step 3: Build Artifact objects (same as tool_runner does) ------
        artifact_objects = _build_artifact_objects(
            artifact_params, artifact_metadata, {"input_file": "test_input.txt"}
        )
        check(
            "Artifact object built",
            "input_file" in artifact_objects,
            f"type={type(artifact_objects.get('input_file')).__name__}",
        )
        art = artifact_objects["input_file"]
        check("Artifact filename correct", art.filename == "test_input.txt")
        check("Artifact content loaded", len(art.as_bytes()) == len(TEST_CONTENT.encode()))

        # -- Step 4: Build SandboxToolContextFacade -------------------------
        # Build filename-keyed artifacts (same as tool_runner.run_tool() does)
        artifacts_by_filename = {}
        for meta in artifact_metadata.values():
            fname = meta.get("filename")
            if fname:
                artifacts_by_filename[fname] = {
                    "local_path": meta["local_path"],
                    "mime_type": meta.get("mime_type", "application/octet-stream"),
                    "version": meta.get("version", 0),
                }

        context = SandboxToolContextFacade(
            status_pipe_path="",  # No pipe in test
            tool_config={},
            artifacts=artifacts_by_filename,
            output_dir=str(output_dir),
            user_id=USER_ID,
            session_id=SESSION_ID,
            app_name=APP_NAME,
        )

        # -- Step 5: Call the function with injected params ------------------
        kwargs = {"input_file": artifact_objects["input_file"]}
        kwargs["ctx"] = context

        result = await portable_process_file(**kwargs)

        check("Result is ToolResult", isinstance(result, ToolResult), type(result).__name__)
        check("Status is success", result.status == "success")

        # -- Step 6: Extract output artifacts (same as tool_runner does) -----
        result = _extract_output_artifacts(result, str(output_dir))

        output_files = list(output_dir.iterdir())
        check(
            "Output artifact written",
            len(output_files) == 1,
            f"files={[f.name for f in output_files]}",
        )
        check(
            "Output artifact name correct",
            output_files[0].name == "processing_summary.txt",
        )

        # -- Step 7: Serialize (same as tool_runner does) --------------------
        serialized = serialize_result(result)
        check("Serialized is dict", isinstance(serialized, dict))

        return serialized


# ══════════════════════════════════════════════════════════════════════════
# Compare results
# ══════════════════════════════════════════════════════════════════════════

def compare_results(inprocess: dict, sandbox: dict):
    """Compare the two results and assert they're equivalent."""
    print(f"\n{_BOLD}{_CYAN}Comparing results{_RESET}")

    # The in-process path returns a ToolResult (from _run_async_impl which
    # returns the raw function return value). DynamicTool doesn't serialize
    # ToolResult to dict — the ToolResultProcessor does that later.
    # For comparison, we need to normalize both results.

    # In-process: DynamicTool._run_async_impl returns the raw ToolResult,
    # but since it's awaited with **kwargs, the result is whatever the
    # async function returned. For _FunctionAsDynamicTool, it returns the
    # raw return value.

    # Extract comparable fields
    ip_status = inprocess.get("status", "")
    sb_status = sandbox.get("status", "")
    check("Status matches", ip_status == sb_status, f"in-process={ip_status}, sandbox={sb_status}")

    ip_message = inprocess.get("message", "")
    sb_message = sandbox.get("message", "")
    check("Message matches", ip_message == sb_message, f"'{ip_message}'")

    ip_data = inprocess.get("data", {})
    sb_data = sandbox.get("data", {})

    ip_stats = (ip_data or {}).get("statistics", {})
    sb_stats = (sb_data or {}).get("statistics", {})
    check(
        "Statistics match",
        ip_stats == sb_stats,
        f"char={ip_stats.get('character_count')}, words={ip_stats.get('word_count')}, lines={ip_stats.get('line_count')}",
    )

    # In-process: DataObjects remain in result (ToolResultProcessor extracts later)
    # Sandbox: DataObjects extracted to output dir by _extract_output_artifacts
    ip_do = inprocess.get("data_objects", [])
    sb_do = sandbox.get("data_objects", [])
    check(
        "In-process has DataObjects (extracted later by ToolResultProcessor)",
        len(ip_do) == 1,
        f"count={len(ip_do)}",
    )
    check(
        "Sandbox DataObjects extracted (empty after _extract_output_artifacts)",
        len(sb_do) == 0,
        f"count={len(sb_do)}",
    )

    # Verify the DataObject content matches the output file
    if ip_do:
        ip_obj_name = ip_do[0].get("name", "")
        check(
            "DataObject name matches output artifact",
            ip_obj_name == "processing_summary.txt",
            ip_obj_name,
        )


async def main():
    print(f"{_BOLD}Portable Tool Portability Test{_RESET}")
    print(f"Testing: {_CYAN}portable_process_file{_RESET}")
    print(f"Input: {len(TEST_CONTENT)} bytes test file")

    try:
        inprocess_result = await test_inprocess_path()
        sandbox_result = await test_sandbox_path()

        # Normalize in-process result for comparison
        # _FunctionAsDynamicTool._run_async_impl returns the ToolResult directly
        # which is a Pydantic model. We need to convert to dict.
        if isinstance(inprocess_result, ToolResult):
            inprocess_result = inprocess_result.model_dump()
        elif hasattr(inprocess_result, "model_dump"):
            inprocess_result = inprocess_result.model_dump()

        compare_results(inprocess_result, sandbox_result)

        print(f"\n{_BOLD}In-process result:{_RESET}")
        print(f"  {json.dumps(inprocess_result, indent=2, default=str)}")

        print(f"\n{_BOLD}Sandbox result:{_RESET}")
        print(f"  {json.dumps(sandbox_result, indent=2, default=str)}")

        print(f"\n{_GREEN}{_BOLD}ALL CHECKS PASSED{_RESET} — Same tool works in both environments\n")
        return True

    except AssertionError as e:
        print(f"\n{_RED}{_BOLD}TEST FAILED:{_RESET} {e}\n")
        return False
    except Exception as e:
        print(f"\n{_RED}{_BOLD}UNEXPECTED ERROR:{_RESET} {e}\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
