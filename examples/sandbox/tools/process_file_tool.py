"""
Artifact test tool for sandbox worker.

Demonstrates receiving an artifact, processing it, and creating
an output artifact. Tests the full artifact pipeline:
  - Worker loads input artifact from shared artifact service
  - Tool receives file path via ctx.load_artifact()
  - Tool processes the content
  - Tool creates output artifact via ctx.save_artifact()
  - Worker saves output artifact to shared artifact service
"""

from typing import Any, Dict


def process_file(ctx: Any, input_file: str) -> Dict[str, Any]:
    """
    Process an input file artifact and produce a summary output artifact.

    Reads the input artifact, computes basic statistics, and saves
    a summary as a new artifact.

    Args:
        ctx: Tool context for status updates and artifact access
        input_file: Filename of the input artifact (loaded by worker)

    Returns:
        Dict with processing results and created artifact info
    """
    ctx.send_status("Loading input artifact...")

    # Load the artifact content via the context facade
    # The parameter name 'input_file' maps to the artifact path
    content = ctx.load_artifact_text("input_file")

    if content is None:
        return {
            "status": "error",
            "error": "Could not load input artifact 'input_file'",
        }

    ctx.send_status("Processing file content...")

    # Compute basic statistics
    lines = content.split("\n")
    words = content.split()
    char_count = len(content)
    line_count = len(lines)
    word_count = len(words)

    # Build a summary report
    summary_lines = [
        "=== File Processing Summary ===",
        f"Characters: {char_count}",
        f"Words:      {word_count}",
        f"Lines:      {line_count}",
        "",
        "--- First 5 lines ---",
    ]
    for line in lines[:5]:
        summary_lines.append(f"  {line}")
    if line_count > 5:
        summary_lines.append(f"  ... ({line_count - 5} more lines)")

    summary_text = "\n".join(summary_lines)

    ctx.send_status("Saving summary artifact...")

    # Save the summary as an output artifact
    ctx.save_artifact(
        "processing_summary.txt",
        summary_text.encode("utf-8"),
    )

    return {
        "status": "success",
        "statistics": {
            "character_count": char_count,
            "word_count": word_count,
            "line_count": line_count,
        },
        "output_artifact": "processing_summary.txt",
    }
