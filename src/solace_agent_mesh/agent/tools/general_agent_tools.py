"""
Collection of Python tools that can be configured for general purpose agents.
"""

import logging
import asyncio
import inspect
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from playwright.async_api import async_playwright

from google.adk.tools import ToolContext

from markitdown import MarkItDown, UnsupportedFormatException
from mermaid_cli import render_mermaid

from ...agent.utils.artifact_helpers import (
    ensure_correct_extension,
    save_artifact_with_metadata,
    METADATA_SUFFIX,
    DEFAULT_SCHEMA_MAX_KEYS,
)
from ...agent.utils.context_helpers import get_original_session_id

from google.genai import types as adk_types
from .tool_definition import BuiltinTool
from .registry import tool_registry

log = logging.getLogger(__name__)

def _simple_truncate_text(text: str, max_bytes: int = 2048) -> Tuple[str, bool]:
    """Truncates text to a maximum number of bytes for preview."""
    truncated = False
    preview_text = text
    if not isinstance(text, str):
        return "", False
    if len(text.encode("utf-8")) > max_bytes:
        encoded = text.encode("utf-8")
        preview_text = encoded[:max_bytes].decode("utf-8", errors="ignore") + "..."
        truncated = True
    return preview_text, truncated


async def convert_file_to_markdown(
    input_filename: str,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Converts an input file artifact to Markdown using the MarkItDown library.
    The supported input types are those supported by MarkItDown (e.g., PDF, DOCX, XLSX, HTML, CSV, PPTX, ZIP).
    The output is a new Markdown artifact.

    Args:
        input_filename: The filename (and optional :version) of the input artifact.
        tool_context: The context provided by the ADK framework.
        tool_config: Optional dictionary for tool-specific configuration (unused by this tool).

    Returns:
        A dictionary with status, output artifact details, and a preview of the result.
    """
    if not tool_context:
        return {"status": "error", "message": "ToolContext is missing."}

    log_identifier = f"[GeneralTool:convert_to_markdown:{input_filename}]"
    log.info("%s Processing request.", log_identifier)

    temp_input_file = None
    original_input_basename = "unknown_input"

    try:
        inv_context = tool_context._invocation_context
        app_name = inv_context.app_name
        user_id = inv_context.user_id
        session_id = get_original_session_id(inv_context)
        artifact_service = inv_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")

        parts = input_filename.split(":", 1)
        filename_base_for_load = parts[0]
        version_str = parts[1] if len(parts) > 1 else None
        version_to_load = int(version_str) if version_str else None

        if version_to_load is None:
            list_versions_method = getattr(artifact_service, "list_versions")
            if inspect.iscoroutinefunction(list_versions_method):
                versions = await list_versions_method(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename_base_for_load,
                )
            else:
                versions = await asyncio.to_thread(
                    list_versions_method,
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename_base_for_load,
                )
            if not versions:
                raise FileNotFoundError(
                    f"Artifact '{filename_base_for_load}' not found."
                )
            version_to_load = max(versions)
            log.debug(
                "%s Using latest version for input: %d", log_identifier, version_to_load
            )

        metadata_filename_to_load = f"{filename_base_for_load}{METADATA_SUFFIX}"
        try:
            load_meta_method = getattr(artifact_service, "load_artifact")
            if inspect.iscoroutinefunction(load_meta_method):
                metadata_part = await load_meta_method(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=metadata_filename_to_load,
                    version=version_to_load,
                )
            else:
                metadata_part = await asyncio.to_thread(
                    load_meta_method,
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=metadata_filename_to_load,
                    version=version_to_load,
                )
            if not metadata_part or not metadata_part.inline_data:
                raise FileNotFoundError(
                    f"Metadata for '{filename_base_for_load}' v{version_to_load} not found."
                )
            input_metadata = json.loads(metadata_part.inline_data.data.decode("utf-8"))
            original_input_filename_from_meta = input_metadata.get(
                "filename", filename_base_for_load
            )
            original_input_basename, original_input_ext = os.path.splitext(
                original_input_filename_from_meta
            )
        except Exception as meta_err:
            log.warning(
                "%s Could not load metadata for '%s' v%s: %s. Using input filename for naming.",
                log_identifier,
                filename_base_for_load,
                version_to_load,
                meta_err,
            )
            original_input_basename, original_input_ext = os.path.splitext(
                filename_base_for_load
            )

        load_artifact_method = getattr(artifact_service, "load_artifact")
        if inspect.iscoroutinefunction(load_artifact_method):
            input_artifact_part = await load_artifact_method(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename_base_for_load,
                version=version_to_load,
            )
        else:
            input_artifact_part = await asyncio.to_thread(
                load_artifact_method,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename_base_for_load,
                version=version_to_load,
            )

        if not input_artifact_part or not input_artifact_part.inline_data:
            raise FileNotFoundError(
                f"Content for artifact '{filename_base_for_load}' v{version_to_load} not found."
            )
        input_bytes = input_artifact_part.inline_data.data

        temp_suffix = original_input_ext if original_input_ext else None
        temp_input_file = tempfile.NamedTemporaryFile(delete=False, suffix=temp_suffix)
        temp_input_file.write(input_bytes)
        temp_input_file.close()
        log.debug(
            "%s Input artifact content written to temporary file: %s",
            log_identifier,
            temp_input_file.name,
        )

        md_converter = MarkItDown()
        log.debug(
            "%s Calling MarkItDown.convert() on %s",
            log_identifier,
            temp_input_file.name,
        )
        conversion_result = await asyncio.to_thread(
            md_converter.convert, temp_input_file.name
        )

        markdown_text_content = (
            conversion_result.text_content
            if conversion_result and conversion_result.text_content
            else ""
        )
        if not markdown_text_content:
            log.warning(
                "%s MarkItDown conversion resulted in empty content for %s.",
                log_identifier,
                input_filename,
            )

        markdown_content_bytes = markdown_text_content.encode("utf-8")

        output_filename = f"{original_input_basename}_converted.md"
        output_mime_type = "text/markdown"

        host_component = getattr(inv_context.agent, "host_component", None)
        schema_max_keys = DEFAULT_SCHEMA_MAX_KEYS

        save_metadata_dict = {
            "description": f"Markdown conversion of '{original_input_basename}{original_input_ext}'",
            "source_artifact": input_filename,
            "source_artifact_version": version_to_load,
            "conversion_tool": "MarkItDown",
        }
        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=output_filename,
            content_bytes=markdown_content_bytes,
            mime_type=output_mime_type,
            metadata_dict=save_metadata_dict,
            timestamp=datetime.now(timezone.utc),
            schema_max_keys=schema_max_keys,
            tool_context=tool_context,
        )
        if save_result["status"] == "error":
            raise IOError(
                f"Failed to save Markdown artifact: {save_result.get('message', 'Unknown error')}"
            )

        preview_data, truncated = _simple_truncate_text(markdown_text_content)
        preview_message = f"File converted to Markdown successfully. Full result saved as '{output_filename}' v{save_result['data_version']}."
        if truncated:
            preview_message += f" Preview shows first portion."

        return {
            "status": "success",
            "message": preview_message,
            "output_filename": output_filename,
            "output_version": save_result["data_version"],
            "result_preview": preview_data,
            "result_truncated": truncated,
        }

    except FileNotFoundError as e:
        log.warning("%s File not found error: %s", log_identifier, e)
        return {"status": "error", "message": str(e)}
    except UnsupportedFormatException as e:
        log.warning("%s MarkItDown unsupported format: %s", log_identifier, e)
        return {
            "status": "error",
            "message": f"Unsupported file format for MarkItDown: {e}",
        }
    except ValueError as e:
        log.warning("%s Value error: %s", log_identifier, e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        log.exception(
            "%s Unexpected error in convert_file_to_markdown: %s", log_identifier, e
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}
    finally:
        if (
            temp_input_file
            and temp_input_file.name
            and os.path.exists(temp_input_file.name)
        ):
            try:
                os.remove(temp_input_file.name)
                log.debug(
                    "%s Removed temporary input file: %s",
                    log_identifier,
                    temp_input_file.name,
                )
            except OSError as e_remove:
                log.error(
                    "%s Failed to remove temporary input file %s: %s",
                    log_identifier,
                    temp_input_file.name,
                    e_remove,
                )

async def _convert_svg_to_png_with_playwright(svg_data: str, scale: int = 2) -> bytes:
    """
    Converts SVG data to a PNG image using Playwright.

    Args:
        svg_data (str): The SVG data to be converted.
        scale (int, optional): The scale factor for the PNG image. Defaults to 2.

    Returns:
        bytes: The PNG image data as a byte array.

    Raises:
        ValueError: If the SVG bounding box cannot be determined.

    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(device_scale_factor=scale)
        page = await context.new_page()

        html_content = f"""
        <html>
        <body style="margin: 0; padding: 0; background: white;">
        <div id="container">{svg_data}</div>
        </body>
        </html>
        """
        await page.set_content(html_content, wait_until="load")
        await page.wait_for_timeout(50)

        svg = page.locator("svg")
        box = await svg.bounding_box()
        if not box:
            raise ValueError("Could not determine SVG bounding box.")

        width = int(box["width"])
        height = int(box["height"])

        await page.set_viewport_size({"width": width, "height": height})

        image_data = await svg.screenshot(type="png")

        await browser.close()
        return image_data

async def mermaid_diagram_generator(
    mermaid_syntax: str,
    output_filename: Optional[str] = None,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generates a PNG image from Mermaid diagram syntax and saves it as an artifact.
    The diagram must be detailed.

    Args:
        mermaid_syntax: The Mermaid diagram syntax (string).
        output_filename: Optional desired name for the output PNG file.
                         If not provided, a unique name will be generated.
        tool_context: The context provided by the ADK framework.
        tool_config: Optional dictionary for tool-specific configuration (unused by this tool).

    Returns:
        A dictionary with status, output artifact details, and a preview message.
    """
    if not tool_context:
        return {"status": "error", "message": "ToolContext is missing."}

    log_identifier = f"[GeneralTool:mermaid_diagram_generator]"
    if output_filename:
        log_identifier += f":{output_filename}"
    log.info("%s Processing request.", log_identifier)

    try:
        inv_context = tool_context._invocation_context
        app_name = inv_context.app_name
        user_id = inv_context.user_id
        session_id = get_original_session_id(inv_context)
        artifact_service = inv_context.artifact_service

        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")

        log.debug(
            "%s Calling render_mermaid for syntax: %s",
            log_identifier,
            mermaid_syntax[:100] + "...",
        )
        title, desc, svg_image_data = await render_mermaid(
            mermaid_syntax, output_format="svg", background_color="white"
        )

        if not svg_image_data:
            log.error(
                "%s Failed to render Mermaid diagram. No image data returned.",
                log_identifier,
            )
            return {
                "status": "error",
                "message": "Failed to render Mermaid diagram. No image data returned.",
            }
        try:
            scale = max(2, len(mermaid_syntax.splitlines()) // 10)
            image_data = await _convert_svg_to_png_with_playwright(svg_image_data.decode("utf-8"), scale)
        except Exception as e:
            log.error(
                "%s Failed to convert SVG to PNG with Playwright: %s",
                log_identifier,
                e,
            )
            return {
                "status": "error",
                "message": f"Failed to convert SVG to PNG: {e}",
            }

        log.debug(
            "%s Mermaid diagram rendered successfully with scale %d, image_data length: %d bytes",
            log_identifier,
            scale,
            len(image_data),
        )

        if output_filename:
            final_output_filename = ensure_correct_extension(output_filename, "png")
        else:
            final_output_filename = f"mermaid_diagram_{uuid.uuid4()}.png"

        log.debug(
            "%s Determined final output filename: %s",
            log_identifier,
            final_output_filename,
        )

        output_mime_type = "image/png"
        schema_max_keys = DEFAULT_SCHEMA_MAX_KEYS

        save_metadata_dict = {
            "description": f"PNG image generated from Mermaid syntax. Original requested filename: {output_filename if output_filename else 'N/A'}",
            "source_format": "mermaid_syntax",
            "generation_tool": "mermaid_diagram_generator (mermaid-cli)",
            "mermaid_title": title if title else "N/A",
            "mermaid_description": desc if desc else "N/A",
        }

        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=final_output_filename,
            content_bytes=image_data,
            mime_type=output_mime_type,
            metadata_dict=save_metadata_dict,
            timestamp=datetime.now(timezone.utc),
            schema_max_keys=schema_max_keys,
            tool_context=tool_context,
        )

        if save_result["status"] == "error":
            log.error(
                "%s Failed to save PNG artifact: %s",
                log_identifier,
                save_result.get("message", "Unknown error"),
            )
            raise IOError(
                f"Failed to save PNG artifact: {save_result.get('message', 'Unknown error')}"
            )

        log.info(
            "%s PNG artifact saved successfully: %s v%d",
            log_identifier,
            final_output_filename,
            save_result["data_version"],
        )

        preview_message = f"Mermaid diagram rendered and saved as artifact '{final_output_filename}' v{save_result['data_version']}."

        return {
            "status": "success",
            "message": preview_message,
            "output_filename": final_output_filename,
            "output_version": save_result["data_version"],
            "result_preview": f"Artifact '{final_output_filename}' (v{save_result['data_version']}) created successfully.",
        }

    except ValueError as e:
        log.warning(
            "%s Value error in mermaid_diagram_generator: %s", log_identifier, e
        )
        return {"status": "error", "message": str(e)}
    except IOError as e:
        log.warning("%s IO error in mermaid_diagram_generator: %s", log_identifier, e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        log.exception(
            "%s Unexpected error in mermaid_diagram_generator: %s", log_identifier, e
        )
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


async def _continue_generation() -> Dict[str, Any]:
    """
    Internal tool to signal the LLM to continue a response that was interrupted.
    This tool is not intended to be called directly by the LLM.
    """
    return {
        "status": "continue",
        "message": "You were interrupted due to a token limit. Please review your last output and continue *exactly where you left off with no other commentary*. \nTake care with newlines. If the last output did not finish with a newline, should the next character be a newline? This is especially important for files like csv or yaml files, where a missing newline will break the parser. \nFrom the user's point of view, this continuation needs to be seamless. This function (_continue_generation()) is an internal function that you must not call - it is just here to facilitate providing this message to you.\nIn the unlikely case you have nothing additional to output, then just return nothing.",
    }


# --- Tool Definitions ---

_continue_generation_tool_def = BuiltinTool(
    name="_continue_generation",
    implementation=_continue_generation,
    description="INTERNAL TOOL. This tool is used by the system to continue a response that was interrupted. You MUST NOT call this tool directly.",
    category="internal",
    required_scopes=[],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={},
        required=[],
    ),
    examples=[],
)

convert_file_to_markdown_tool_def = BuiltinTool(
    name="convert_file_to_markdown",
    implementation=convert_file_to_markdown,
    description="Converts an input file artifact to Markdown using the MarkItDown library. The supported input types are those supported by MarkItDown (e.g., PDF, DOCX, XLSX, HTML, CSV, PPTX, ZIP). The output is a new Markdown artifact.",
    category="general",
    required_scopes=["tool:general:convert_file"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "input_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The filename (and optional :version) of the input artifact.",
            ),
        },
        required=["input_filename"],
    ),
    examples=[],
)

mermaid_diagram_generator_tool_def = BuiltinTool(
    name="mermaid_diagram_generator",
    implementation=mermaid_diagram_generator,
    description="Generates a PNG image from Mermaid diagram syntax and saves it as an artifact.",
    category="general",
    required_scopes=["tool:general:mermaid"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "mermaid_syntax": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The Mermaid diagram syntax (string).",
            ),
            "output_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional desired name for the output PNG file. If not provided, a unique name will be generated.",
                nullable=True,
            ),
        },
        required=["mermaid_syntax"],
    ),
    examples=[],
)


tool_registry.register(_continue_generation_tool_def)
tool_registry.register(convert_file_to_markdown_tool_def)
tool_registry.register(mermaid_diagram_generator_tool_def)
