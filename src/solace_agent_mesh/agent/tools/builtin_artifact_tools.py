"""
Built-in ADK Tools for Artifact Management within the A2A Host.
These tools interact with the ADK ArtifactService via the ToolContext and
use state_delta for signaling artifact return requests to the host component.
Metadata handling is integrated via artifact_helpers.
"""

import logging
import uuid
import json
import re
import fnmatch
from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING
from datetime import datetime, timezone
from google.adk.tools import ToolContext

if TYPE_CHECKING:
    from google.adk.agents.invocation_context import InvocationContext
from google.genai import types as adk_types
from .tool_definition import BuiltinTool
from .registry import tool_registry
from ...agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    decode_and_get_bytes,
    load_artifact_content_or_metadata,
    is_filename_safe,
    METADATA_SUFFIX,
    DEFAULT_SCHEMA_MAX_KEYS,
)
from ...common.utils.embeds import (
    evaluate_embed,
    EMBED_REGEX,
    EMBED_CHAIN_DELIMITER,
)
from ...common.utils.embeds.types import ResolutionMode
from ...agent.utils.context_helpers import get_original_session_id
from ...agent.adk.models.lite_llm import LiteLlm
from google.adk.models import LlmRequest
from google.adk.models.registry import LLMRegistry
from ...common.utils.mime_helpers import is_text_based_file

log = logging.getLogger(__name__)

CATEGORY_NAME = "Artifact Management"
CATEGORY_DESCRIPTION = "List, read, create, update, and delete artifacts."


async def _internal_create_artifact(
    filename: str,
    content: str,
    mime_type: str,
    tool_context: ToolContext = None,
    description: Optional[str] = None,
    metadata_json: Optional[str] = None,
    schema_max_keys: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Internal helper to create an artifact with its first chunk of content and metadata.
    This function is not intended to be called directly by the LLM.
    It is used by callbacks that process fenced artifact blocks.

    Args:
        filename: The desired name for the artifact.
        content: The first chunk of the artifact content, as a string.
                 If the mime_type suggests binary data, this string is expected
                 to be base64 encoded.
        mime_type: The MIME type of the content.
        tool_context: The ADK ToolContext, required for accessing services.
        description (str, optional): A description for the artifact.
        metadata_json (str, optional): A JSON string of additional metadata.
        schema_max_keys (int, optional): Max keys for schema inference.


    Returns:
        A dictionary indicating the result, returned by save_artifact_with_metadata.
    """
    if not tool_context:
        return {
            "status": "error",
            "filename": filename,
            "message": "ToolContext is missing, cannot save artifact.",
        }

    if not is_filename_safe(filename):
        return {
            "status": "error",
            "filename": filename,
            "message": "Filename is invalid or contains disallowed characters (e.g., '/', '..').",
        }

    log_identifier = f"[BuiltinArtifactTool:_internal_create_artifact:{filename}]"

    final_metadata = {}
    if description:
        final_metadata["description"] = description
    if metadata_json:
        try:
            final_metadata.update(json.loads(metadata_json))
        except (json.JSONDecodeError, TypeError):
            log.warning(
                "%s Invalid JSON in metadata_json attribute: %s",
                log_identifier,
                metadata_json,
            )

            final_metadata["metadata_parsing_error"] = (
                f"Invalid JSON provided: {metadata_json}"
            )

    log.debug("%s Processing request with metadata: %s", log_identifier, final_metadata)

    try:
        inv_context = tool_context._invocation_context
        artifact_bytes, final_mime_type = decode_and_get_bytes(
            content, mime_type, log_identifier
        )
        max_keys_to_use = (
            schema_max_keys if schema_max_keys is not None else DEFAULT_SCHEMA_MAX_KEYS
        )
        if schema_max_keys is not None:
            log.debug(
                "%s Using schema_max_keys provided by LLM: %d",
                log_identifier,
                schema_max_keys,
            )
        else:
            log.debug(
                "%s Using default schema_max_keys: %d",
                log_identifier,
                DEFAULT_SCHEMA_MAX_KEYS,
            )

        artifact_service = inv_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")
        session_last_update_time = inv_context.session.last_update_time
        timestamp_for_artifact: datetime
        if isinstance(session_last_update_time, datetime):
            timestamp_for_artifact = session_last_update_time
        elif isinstance(session_last_update_time, (int, float)):
            log.debug(
                "%s Converting numeric session.last_update_time (%s) to datetime.",
                log_identifier,
                session_last_update_time,
            )
            try:
                timestamp_for_artifact = datetime.fromtimestamp(
                    session_last_update_time, timezone.utc
                )
            except Exception as e:
                log.warning(
                    "%s Failed to convert numeric timestamp %s to datetime: %s. Using current time.",
                    log_identifier,
                    session_last_update_time,
                    e,
                )
                timestamp_for_artifact = datetime.now(timezone.utc)
        else:
            if session_last_update_time is not None:
                log.warning(
                    "%s Unexpected type for session.last_update_time: %s. Using current time.",
                    log_identifier,
                    type(session_last_update_time),
                )
            timestamp_for_artifact = datetime.now(timezone.utc)
        result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=filename,
            content_bytes=artifact_bytes,
            mime_type=final_mime_type,
            metadata_dict=final_metadata,
            timestamp=timestamp_for_artifact,
            schema_max_keys=max_keys_to_use,
            tool_context=tool_context,
        )
        log.info(
            "%s Result from save_artifact_with_metadata: %s", log_identifier, result
        )
        return result
    except Exception as e:
        log.exception(
            "%s Error creating artifact '%s': %s", log_identifier, filename, e
        )
        return {
            "status": "error",
            "filename": filename,
            "message": f"Failed to create artifact: {e}",
        }


async def list_artifacts(tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Lists all available data artifact filenames and their versions for the current session.
    Includes a summary of the latest version's metadata for each artifact.

    Args:
        tool_context: The context provided by the ADK framework.

    Returns:
        A dictionary containing the list of artifacts with metadata summaries or an error.
    """
    if not tool_context:
        return {"status": "error", "message": "ToolContext is missing."}
    log_identifier = "[BuiltinArtifactTool:list_artifacts]"
    log.debug("%s Processing request.", log_identifier)
    try:
        artifact_service = tool_context._invocation_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")
        app_name = tool_context._invocation_context.app_name
        user_id = tool_context._invocation_context.user_id
        session_id = get_original_session_id(tool_context._invocation_context)
        list_keys_method = getattr(artifact_service, "list_artifact_keys")
        all_keys = await list_keys_method(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        response_files = []
        processed_data_files = set()
        for key in all_keys:
            if key.endswith(METADATA_SUFFIX):
                continue  # Skip metadata files initially

            if key in processed_data_files:
                continue  # Already processed this data file

            filename = key
            metadata_summary = None
            versions = []
            try:
                versions = await artifact_service.list_versions(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename,
                )
                if not versions:
                    log.warning(
                        "%s Found artifact key '%s' but no versions listed. Skipping.",
                        log_identifier,
                        filename,
                    )
                    continue
                latest_version = max(versions)
                metadata_filename = f"{filename}{METADATA_SUFFIX}"
                if metadata_filename in all_keys:
                    try:
                        metadata_part = await artifact_service.load_artifact(
                            app_name=app_name,
                            user_id=user_id,
                            session_id=session_id,
                            filename=metadata_filename,
                            version=latest_version,
                        )
                        if metadata_part and metadata_part.inline_data:
                            try:
                                metadata_dict = json.loads(
                                    metadata_part.inline_data.data.decode("utf-8")
                                )
                                schema = metadata_dict.get("schema", {})
                                metadata_summary = {
                                    "description": metadata_dict.get("description"),
                                    "source": metadata_dict.get("source"),
                                    "type": metadata_dict.get("mime_type"),
                                    "size": metadata_dict.get("size_bytes"),
                                    "schema_type": schema.get(
                                        "type", metadata_dict.get("mime_type")
                                    ),
                                    "schema_inferred": schema.get("inferred"),
                                }
                                metadata_summary = {
                                    k: v
                                    for k, v in metadata_summary.items()
                                    if v is not None
                                }
                                log.debug(
                                    "%s Loaded metadata summary for '%s' v%d.",
                                    log_identifier,
                                    filename,
                                    latest_version,
                                )
                            except json.JSONDecodeError as json_err:
                                log.warning(
                                    "%s Failed to parse metadata JSON for '%s' v%d: %s",
                                    log_identifier,
                                    metadata_filename,
                                    latest_version,
                                    json_err,
                                )
                                metadata_summary = {"error": "Failed to parse metadata"}
                            except Exception as fmt_err:
                                log.warning(
                                    "%s Failed to format metadata summary for '%s' v%d: %s",
                                    log_identifier,
                                    metadata_filename,
                                    latest_version,
                                    fmt_err,
                                )
                                metadata_summary = {
                                    "error": "Failed to format metadata"
                                }
                        else:
                            log.warning(
                                "%s Metadata file '%s' v%d found but empty or unreadable.",
                                log_identifier,
                                metadata_filename,
                                latest_version,
                            )
                            metadata_summary = {
                                "error": "Metadata file empty or unreadable"
                            }
                    except Exception as load_err:
                        log.warning(
                            "%s Failed to load metadata file '%s' v%d: %s",
                            log_identifier,
                            metadata_filename,
                            latest_version,
                            load_err,
                        )
                        metadata_summary = {
                            "error": f"Failed to load metadata: {load_err}"
                        }
                else:
                    log.debug(
                        "%s No companion metadata file found for '%s'.",
                        log_identifier,
                        filename,
                    )
                    metadata_summary = {"info": "No metadata file found"}
            except Exception as version_err:
                log.warning(
                    "%s Failed to list versions or process metadata for file '%s': %s. Skipping file.",
                    log_identifier,
                    filename,
                    version_err,
                )
                continue
            response_files.append(
                {
                    "filename": filename,
                    "versions": versions,
                    "metadata_summary": metadata_summary,
                }
            )
            processed_data_files.add(filename)
        log.info(
            "%s Found %d data artifacts for session %s.",
            log_identifier,
            len(response_files),
            session_id,
        )
        return {"status": "success", "artifacts": response_files}
    except Exception as e:
        log.exception("%s Error listing artifacts: %s", log_identifier, e)
        return {"status": "error", "message": f"Failed to list artifacts: {e}"}


async def load_artifact(
    filename: str,
    version: int,
    load_metadata_only: bool = False,
    max_content_length: Optional[int] = None,
    include_line_numbers: bool = False,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Loads the content or metadata of a specific artifact version.
    Early-stage embeds in the filename argument are resolved.

    If load_metadata_only is True, loads the full metadata dictionary.
    Otherwise, loads text content (potentially truncated) or binary metadata summary.

    Args:
        filename: The name of the artifact to load. May contain embeds.
        version: The specific version number to load. Must be explicitly provided. Versions are 0-indexed.
        load_metadata_only (bool): If True, load only the metadata JSON. Default False.
        max_content_length (Optional[int]): Maximum character length for text content.
                                           If None, uses app configuration. Range: 100-100,000.
        include_line_numbers (bool): If True, prefix each line with its 1-based line number
                                    followed by a TAB character for LLM viewing. Line numbers
                                    are not stored in the artifact. Default False.
        tool_context: The context provided by the ADK framework.

    Returns:
        A dictionary containing the artifact details and content/metadata or an error.
    """
    if not tool_context:
        return {
            "status": "error",
            "filename": filename,
            "version": version,
            "message": "ToolContext is missing.",
        }
    log_identifier = f"[BuiltinArtifactTool:load_artifact:{filename}:{version}]"
    log.debug(
        "%s Processing request (load_metadata_only=%s).",
        log_identifier,
        load_metadata_only,
    )
    if version is None:
        version = "latest"
    try:
        artifact_service = tool_context._invocation_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")
        app_name = tool_context._invocation_context.app_name
        user_id = tool_context._invocation_context.user_id
        session_id = get_original_session_id(tool_context._invocation_context)
        agent = getattr(tool_context._invocation_context, "agent", None)
        host_component = getattr(agent, "host_component", None) if agent else None
        result = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            version=version,
            load_metadata_only=load_metadata_only,
            max_content_length=max_content_length,
            include_line_numbers=include_line_numbers,
            component=host_component,
            log_identifier_prefix="[BuiltinArtifactTool:load_artifact]",
        )
        return result
    except FileNotFoundError as fnf_err:
        log.warning(
            "%s Artifact not found (reported by helper): %s", log_identifier, fnf_err
        )
        return {
            "status": "error",
            "filename": filename,
            "version": version,
            "message": str(fnf_err),
        }
    except ValueError as val_err:
        log.warning(
            "%s Value error during load (reported by helper): %s",
            log_identifier,
            val_err,
        )
        return {
            "status": "error",
            "filename": filename,
            "version": version,
            "message": str(val_err),
        }
    except Exception as e:
        log.exception(
            "%s Unexpected error in load_artifact tool: %s", log_identifier, e
        )
        return {
            "status": "error",
            "filename": filename,
            "version": version,
            "message": f"Unexpected error processing load request: {e}",
        }


async def apply_embed_and_create_artifact(
    output_filename: str,
    embed_directive: str,
    output_metadata: Optional[Dict[str, Any]] = None,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Resolves an 'artifact_content' embed directive (including modifiers and formatting)
    and saves the resulting content as a new artifact. The entire embed directive
    must be provided as a string as the embed_directive argument.

    Args:
        output_filename: The desired name for the new artifact.
        embed_directive: The full '«artifact_content:...>>>...>>>format:...»' string.
        output_metadata (dict, optional): Metadata for the new artifact.
        tool_context: The context provided by the ADK framework.

    Returns:
        A dictionary indicating the result, including the new filename and version.
    """
    if not tool_context:
        return {"status": "error", "message": "ToolContext is missing."}

    log_identifier = f"[BuiltinArtifactTool:apply_embed:{output_filename}]"
    log.info(
        "%s Processing request with directive: %s", log_identifier, embed_directive
    )

    match = EMBED_REGEX.fullmatch(embed_directive)
    if not match:
        return {
            "status": "error",
            "message": f"Invalid embed directive format: {embed_directive}",
        }

    embed_type = match.group(1)
    expression = match.group(2)
    format_spec = match.group(3)

    if embed_type != "artifact_content":
        return {
            "status": "error",
            "message": f"This tool only supports 'artifact_content' embeds, got '{embed_type}'.",
        }

    try:
        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService not available.")

        host_component = getattr(inv_context.agent, "host_component", None)
        if not host_component:
            log.warning(
                "%s Could not access host component config for limits. Proceeding without them.",
                log_identifier,
            )
            embed_config = {}
        else:
            embed_config = {
                "gateway_artifact_content_limit_bytes": host_component.get_config(
                    "gateway_artifact_content_limit_bytes", -1
                ),
                "gateway_recursive_embed_depth": host_component.get_config(
                    "gateway_recursive_embed_depth", 3
                ),
            }

        gateway_context = {
            "artifact_service": artifact_service,
            "session_context": {
                "app_name": inv_context.app_name,
                "user_id": inv_context.user_id,
                "session_id": get_original_session_id(inv_context),
            },
        }
    except Exception as ctx_err:
        log.error(
            "%s Failed to prepare context/config for embed evaluation: %s",
            log_identifier,
            ctx_err,
        )
        return {
            "status": "error",
            "message": f"Internal error preparing context: {ctx_err}",
        }

    resolved_content_str, error_msg_from_eval, _ = await evaluate_embed(
        embed_type=embed_type,
        expression=expression,
        format_spec=format_spec,
        context=gateway_context,
        log_identifier=log_identifier,
        resolution_mode=ResolutionMode.TOOL_PARAMETER,
        config=embed_config,
    )

    if error_msg_from_eval or (
        resolved_content_str and resolved_content_str.startswith("[Error:")
    ):
        error_to_report = error_msg_from_eval or resolved_content_str
        log.error("%s Embed resolution failed: %s", log_identifier, error_to_report)
        return {
            "status": "error",
            "message": f"Embed resolution failed: {error_to_report}",
        }

    output_mime_type = "text/plain"
    final_format = None
    chain_parts = expression.split(EMBED_CHAIN_DELIMITER)
    if len(chain_parts) > 1:
        last_part = chain_parts[-1].strip()
        format_match = re.match(r"format:(.*)", last_part, re.DOTALL)
        if format_match:
            final_format = format_match.group(1).strip().lower()
    elif format_spec:
        final_format = format_spec.strip().lower()

    if final_format:
        if final_format == "html":
            output_mime_type = "text/html"
        elif final_format == "json" or final_format == "json_pretty":
            output_mime_type = "application/json"
        elif final_format == "csv":
            output_mime_type = "text/csv"
        elif final_format == "datauri":
            output_mime_type = "text/plain"
            log.warning(
                "%s Embed resolved to data URI; saving new artifact as text/plain.",
                log_identifier,
            )

    log.debug("%s Determined output MIME type as: %s", log_identifier, output_mime_type)

    try:
        resolved_bytes = resolved_content_str.encode("utf-8")
        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")

        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=output_filename,
            content_bytes=resolved_bytes,
            mime_type=output_mime_type,
            metadata_dict=(
                lambda base_meta, user_meta: (
                    base_meta.update(user_meta or {}),
                    base_meta,
                )[1]
            )({"source_directive": embed_directive}, output_metadata),
            timestamp=inv_context.session.last_update_time
            or datetime.now(timezone.utc),
            schema_max_keys=(
                host_component.get_config("schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS)
                if host_component
                else DEFAULT_SCHEMA_MAX_KEYS
            ),
            tool_context=tool_context,
        )

        log.info(
            "%s Successfully applied embed and saved new artifact '%s' (v%s).",
            log_identifier,
            output_filename,
            save_result.get("data_version"),
        )
        return {
            "status": "success",
            "output_filename": output_filename,
            "output_version": save_result.get("data_version"),
            "output_mime_type": output_mime_type,
            "message": f"Successfully created artifact '{output_filename}' v{save_result.get('data_version')} from embed directive.",
        }

    except Exception as save_err:
        log.exception(
            "%s Failed to save resolved content as artifact '%s': %s",
            log_identifier,
            output_filename,
            save_err,
        )
        return {
            "status": "error",
            "message": f"Failed to save new artifact: {save_err}",
        }


async def extract_content_from_artifact(
    filename: str,
    extraction_goal: str,
    version: Optional[str] = "latest",
    output_filename_base: Optional[str] = None,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Loads an existing artifact, uses an internal LLM to process its content
    based on an "extraction_goal," and manages the output by returning it
    or saving it as a new artifact.

    The tool's description for the LLM might dynamically update based on
    the 'supported_binary_mime_types' configuration of the agent, indicating
    which binary types it can attempt to process.

    Args:
        filename (str): Name of the source artifact. May contain embeds.
        extraction_goal (str): Natural language instruction for the LLM on what
                               to extract or how to transform the content.
                               May contain embeds.
        version (Optional[Union[int, str]]): Version of the source artifact.
                                             Can be an integer or "latest".
                                             Defaults to "latest". May contain embeds.
        output_filename_base (Optional[str]): Optional base name for the new
                                              artifact if the extracted content
                                              is saved. May contain embeds.
        tool_context (ToolContext): Provided by the ADK framework.

    Returns:
        Dict[str, Any]: A dictionary containing the status of the operation,
                        a message for the LLM, and potentially the extracted
                        data or details of a newly saved artifact.
                        Refer to the design document for specific response structures.
    """
    log_identifier = f"[BuiltinArtifactTool:extract_content:{filename}:{version}]"
    log.debug(
        "%s Processing request. Goal: '%s', Output base: '%s'",
        log_identifier,
        extraction_goal,
        output_filename_base,
    )

    if not tool_context:
        return {
            "status": "error_tool_context_missing",
            "message_to_llm": "Tool execution failed: ToolContext is missing.",
            "filename": filename,
            "version_requested": str(version),
        }
    if not filename:
        return {
            "status": "error_missing_filename",
            "message_to_llm": "Tool execution failed: 'filename' parameter is required.",
            "version_requested": str(version),
        }
    if not extraction_goal:
        return {
            "status": "error_missing_extraction_goal",
            "message_to_llm": "Tool execution failed: 'extraction_goal' parameter is required.",
            "filename": filename,
            "version_requested": str(version),
        }

    inv_context = tool_context._invocation_context
    host_component = getattr(inv_context.agent, "host_component", None)
    if not host_component:
        log.error(
            "%s Host component not found on agent. Cannot retrieve config.",
            log_identifier,
        )
        return {
            "status": "error_internal_configuration",
            "message_to_llm": "Tool configuration error: Host component not accessible.",
            "filename": filename,
            "version_requested": str(version),
        }

    try:
        save_threshold = host_component.get_config(
            "tool_output_save_threshold_bytes", 2048
        )
        llm_max_bytes = host_component.get_config(
            "tool_output_llm_return_max_bytes", 4096
        )
        extraction_config = host_component.get_config(
            "extract_content_from_artifact_config", {}
        )
        supported_binary_mime_types = extraction_config.get(
            "supported_binary_mime_types", []
        )
        model_config_for_extraction = extraction_config.get("model")
    except Exception as e:
        log.exception("%s Error retrieving tool configuration: %s", log_identifier, e)
        return {
            "status": "error_internal_configuration",
            "message_to_llm": f"Tool configuration error: {e}",
            "filename": filename,
            "version_requested": str(version),
        }

    source_artifact_data = None
    processed_version: Union[int, str]

    if version is None or (
        isinstance(version, str) and version.strip().lower() == "latest"
    ):
        processed_version = "latest"
    else:
        try:
            processed_version = int(version)
        except ValueError:
            log.warning(
                "%s Invalid version string: '%s'. Must be an integer or 'latest'.",
                log_identifier,
                version,
            )
            return {
                "status": "error_invalid_version_format",
                "message_to_llm": f"Invalid version format '{version}'. Version must be an integer or 'latest'.",
                "filename": filename,
                "version_requested": str(version),
            }
    try:
        log.debug(
            "%s Loading source artifact '%s' version '%s' (processed as: %s)",
            log_identifier,
            filename,
            version,
            processed_version,
        )
        source_artifact_data = await load_artifact_content_or_metadata(
            artifact_service=inv_context.artifact_service,
            app_name=inv_context.app_name,
            user_id=inv_context.user_id,
            session_id=get_original_session_id(inv_context),
            filename=filename,
            version=processed_version,
            return_raw_bytes=True,
            log_identifier_prefix=log_identifier,
        )
        if source_artifact_data.get("status") != "success":
            raise FileNotFoundError(
                source_artifact_data.get("message", "Failed to load artifact")
            )
        log.info(
            "%s Successfully loaded source artifact '%s' version %s (actual: v%s)",
            log_identifier,
            filename,
            version,
            source_artifact_data.get("version"),
        )
    except FileNotFoundError as e:
        log.warning("%s Source artifact not found: %s", log_identifier, e)
        return {
            "status": "error_artifact_not_found",
            "message_to_llm": f"Could not extract content. Source artifact '{filename}' (version {version}) was not found: {e}",
            "filename": filename,
            "version_requested": str(version),
        }
    except Exception as e:
        log.exception("%s Error loading source artifact: %s", log_identifier, e)
        return {
            "status": "error_loading_artifact",
            "message_to_llm": f"Error loading source artifact '{filename}': {e}",
            "filename": filename,
            "version_requested": str(version),
        }

    source_artifact_content_bytes = source_artifact_data.get("raw_bytes")
    source_mime_type = source_artifact_data.get("mime_type", "application/octet-stream")
    actual_source_version = source_artifact_data.get("version", "unknown")

    chosen_llm = None
    try:
        if model_config_for_extraction:
            if isinstance(model_config_for_extraction, str):
                chosen_llm = LLMRegistry.new_llm(model_config_for_extraction)
                log.info(
                    "%s Using tool-specific LLM (string): %s",
                    log_identifier,
                    model_config_for_extraction,
                )
            elif isinstance(model_config_for_extraction, dict):
                chosen_llm = LiteLlm(**model_config_for_extraction)
                log.info(
                    "%s Using tool-specific LLM (dict): %s",
                    log_identifier,
                    model_config_for_extraction.get("model"),
                )
            else:
                log.warning(
                    "%s Invalid 'model' config for extraction tool. Falling back to agent default.",
                    log_identifier,
                )
                chosen_llm = inv_context.agent.canonical_model
        else:
            chosen_llm = inv_context.agent.canonical_model
            log.info(
                "%s Using agent's default LLM: %s", log_identifier, chosen_llm.model
            )
    except Exception as e:
        log.exception("%s Error initializing LLM for extraction: %s", log_identifier, e)
        return {
            "status": "error_internal_llm_setup",
            "message_to_llm": f"Failed to set up LLM for extraction: {e}",
            "filename": filename,
            "version_requested": str(version),
        }

    llm_parts = []
    is_binary_supported = False

    normalized_source_mime_type = source_mime_type.lower() if source_mime_type else ""

    is_text_based = is_text_based_file(
        mime_type=normalized_source_mime_type,
        content_bytes=source_artifact_content_bytes,
    )

    if is_text_based:
        try:
            artifact_text_content = source_artifact_content_bytes.decode("utf-8")
            llm_parts.append(
                adk_types.Part(
                    text=f"Artifact Content (MIME type: {source_mime_type}):\n```\n{artifact_text_content}\n```"
                )
            )
            log.debug("%s Prepared text content for LLM.", log_identifier)
        except UnicodeDecodeError as e:
            log.warning(
                "%s Failed to decode text artifact as UTF-8: %s. Treating as opaque binary.",
                log_identifier,
                e,
            )
            llm_parts.append(
                adk_types.Part(
                    text=f"The artifact '{filename}' is a binary file of type '{source_mime_type}' and could not be decoded as text."
                )
            )
    else:  # Binary
        for supported_pattern in supported_binary_mime_types:
            if fnmatch.fnmatch(source_mime_type, supported_pattern):
                is_binary_supported = True
                break
        if is_binary_supported:
            llm_parts.append(
                adk_types.Part(
                    inline_data=adk_types.Blob(
                        mime_type=source_mime_type, data=source_artifact_content_bytes
                    )
                )
            )
            llm_parts.append(
                adk_types.Part(
                    text=f"The above is the content of artifact '{filename}' (MIME type: {source_mime_type})."
                )
            )
            log.debug(
                "%s Prepared supported binary content (MIME: %s) for LLM.",
                log_identifier,
                source_mime_type,
            )
        else:
            llm_parts.append(
                adk_types.Part(
                    text=f"The artifact '{filename}' is a binary file of type '{source_mime_type}'. Direct content processing is not supported by this tool's current configuration. Perform the extraction goal based on its filename and type if possible, or state that the content cannot be analyzed."
                )
            )
            log.debug(
                "%s Prepared message for unsupported binary content (MIME: %s) for LLM.",
                log_identifier,
                source_mime_type,
            )

    internal_llm_contents = [
        adk_types.Content(
            role="user", parts=[adk_types.Part(text=extraction_goal)] + llm_parts
        )
    ]
    internal_llm_request = LlmRequest(
        model=chosen_llm.model,
        contents=internal_llm_contents,
        config=adk_types.GenerateContentConfig(
            temperature=0.1,
        ),
    )

    extracted_content_str = ""
    try:
        log.info(
            "%s Executing internal LLM call for extraction. Goal: %s",
            log_identifier,
            extraction_goal,
        )
        if hasattr(chosen_llm, "generate_content") and not hasattr(
            chosen_llm, "generate_content_async"
        ):
            llm_response = chosen_llm.generate_content(request=internal_llm_request)
            if llm_response.parts:
                extracted_content_str = llm_response.parts[0].text or ""
            else:
                extracted_content_str = ""
        elif hasattr(chosen_llm, "generate_content_async"):
            log.debug(
                "%s Calling LLM's generate_content_async (non-streaming) for extraction.",
                log_identifier,
            )
            try:
                llm_response_obj = None
                async for response_event in chosen_llm.generate_content_async(
                    internal_llm_request
                ):
                    llm_response_obj = response_event
                    break
                if (
                    llm_response_obj
                    and hasattr(llm_response_obj, "text")
                    and llm_response_obj.text
                ):
                    extracted_content_str = llm_response_obj.text
                elif (
                    llm_response_obj
                    and hasattr(llm_response_obj, "parts")
                    and llm_response_obj.parts
                ):
                    extracted_content_str = "".join(
                        [
                            part.text
                            for part in llm_response_obj.parts
                            if hasattr(part, "text") and part.text
                        ]
                    )
                elif (
                    llm_response_obj
                    and hasattr(llm_response_obj, "content")
                    and hasattr(llm_response_obj.content, "parts")
                    and llm_response_obj.content.parts
                ):
                    extracted_content_str = "".join(
                        [
                            part.text
                            for part in llm_response_obj.content.parts
                            if hasattr(part, "text") and part.text
                        ]
                    )
                else:
                    extracted_content_str = ""
                    log.warning(
                        "%s LLM response object or its text/parts were not found or empty after non-streaming call.",
                        log_identifier,
                    )

            except Exception as llm_async_err:
                log.exception(
                    "%s Asynchronous LLM call for extraction failed: %s",
                    log_identifier,
                    llm_async_err,
                )
                extracted_content_str = (
                    f"[ERROR: Asynchronous LLM call failed: {llm_async_err}]"
                )
        else:
            log.error(
                "%s LLM does not have a known generate_content or generate_content_async method. Extraction will be empty.",
                log_identifier,
            )
            extracted_content_str = "[ERROR: LLM method not found]"

        log.info(
            "%s Internal LLM call completed. Extracted content length: %d chars",
            log_identifier,
            len(extracted_content_str),
        )
        if not extracted_content_str.strip():
            log.warning(
                "%s Internal LLM produced empty or whitespace-only content for extraction goal.",
                log_identifier,
            )

    except Exception as e:
        log.exception(
            "%s Internal LLM call for extraction failed: %s", log_identifier, e
        )
        return {
            "status": "error_extraction_failed",
            "message_to_llm": f"The LLM failed to process the artifact content for your goal '{extraction_goal}'. Error: {e}",
            "filename": filename,
            "version_requested": str(version),
        }

    extracted_content_bytes = extracted_content_str.encode("utf-8")
    extracted_content_size_bytes = len(extracted_content_bytes)
    output_mime_type = "text/plain"
    try:
        json.loads(extracted_content_str)
        output_mime_type = "application/json"
        log.debug(
            "%s Extracted content appears to be valid JSON. Setting output MIME to application/json.",
            log_identifier,
        )
    except json.JSONDecodeError:
        log.debug(
            "%s Extracted content is not JSON. Using output MIME text/plain.",
            log_identifier,
        )

    response_for_llm_str = extracted_content_str
    saved_extracted_artifact_details = None
    final_status = "success"
    message_to_llm_parts = [
        f"Successfully extracted content from '{filename}' (v{actual_source_version}) based on your goal: '{extraction_goal}'."
    ]
    was_saved = False
    was_truncated = False

    if extracted_content_size_bytes > save_threshold:
        log.info(
            "%s Extracted content size (%d bytes) exceeds save threshold (%d bytes). Saving as new artifact.",
            log_identifier,
            extracted_content_size_bytes,
            save_threshold,
        )
        saved_extracted_artifact_details = await _save_extracted_artifact(
            tool_context,
            host_component,
            extracted_content_bytes,
            filename,
            actual_source_version,
            extraction_goal,
            output_filename_base,
            output_mime_type,
        )
        if saved_extracted_artifact_details.get("status") == "success":
            was_saved = True
            message_to_llm_parts.append(
                f"The full extracted content was saved as artifact '{saved_extracted_artifact_details.get('data_filename')}' "
                f"(version {saved_extracted_artifact_details.get('data_version')}). "
                f"You can retrieve it using 'load_artifact' or perform further extractions on it using 'extract_content_from_artifact' "
                f"with this new filename and version."
            )
        else:
            message_to_llm_parts.append(
                f"Attempted to save the large extracted content, but failed: {saved_extracted_artifact_details.get('message')}"
            )

    if len(extracted_content_str.encode("utf-8")) > llm_max_bytes:
        was_truncated = True
        log.info(
            "%s Original extracted content (%d bytes) exceeds LLM return max bytes (%d bytes). Truncating for LLM response.",
            log_identifier,
            len(extracted_content_str.encode("utf-8")),
            llm_max_bytes,
        )

        if not was_saved:
            log.info(
                "%s Saving extracted content now because it needs truncation for LLM response and wasn't saved previously.",
                log_identifier,
            )
            saved_extracted_artifact_details = await _save_extracted_artifact(
                tool_context,
                host_component,
                extracted_content_bytes,
                filename,
                actual_source_version,
                extraction_goal,
                output_filename_base,
                output_mime_type,
            )
            if saved_extracted_artifact_details.get("status") == "success":
                was_saved = True
                message_to_llm_parts.append(
                    f"The full extracted content (which is being truncated for this response) was saved as artifact "
                    f"'{saved_extracted_artifact_details.get('data_filename')}' (version {saved_extracted_artifact_details.get('data_version')}). "
                    f"You can retrieve the full content using 'load_artifact' or perform further extractions on it."
                )
            else:
                message_to_llm_parts.append(
                    f"Attempted to save the extracted content before truncation, but failed: {saved_extracted_artifact_details.get('message')}"
                )

        truncation_suffix = "... [Content truncated]"
        adjusted_max_bytes = llm_max_bytes - len(truncation_suffix.encode("utf-8"))
        if adjusted_max_bytes < 0:
            adjusted_max_bytes = 0

        temp_response_bytes = extracted_content_str.encode("utf-8")
        truncated_bytes = temp_response_bytes[:adjusted_max_bytes]
        response_for_llm_str = (
            truncated_bytes.decode("utf-8", "ignore") + truncation_suffix
        )

        message_to_llm_parts.append(
            "The extracted content provided in 'extracted_data_preview' has been truncated due to size limits. "
            "If saved, the full version is available in the specified artifact."
        )

    if was_saved and was_truncated:
        final_status = "success_full_content_saved_preview_returned"
    elif was_saved:
        final_status = "success_full_content_saved_and_returned"
    elif was_truncated:
        final_status = "success_content_returned_truncated_and_saved"
    else:
        final_status = "success_content_returned"

    final_response_dict = {
        "status": final_status,
        "message_to_llm": " ".join(list(dict.fromkeys(message_to_llm_parts))),
        "source_filename": filename,
        "source_version_processed": actual_source_version,
        "extraction_goal_used": extraction_goal,
    }

    if was_truncated:
        final_response_dict["extracted_data_preview"] = response_for_llm_str
    else:
        final_response_dict["extracted_data"] = response_for_llm_str

    if (
        saved_extracted_artifact_details
        and saved_extracted_artifact_details.get("status") == "success"
    ):
        final_response_dict["saved_extracted_artifact_details"] = (
            saved_extracted_artifact_details
        )
    elif saved_extracted_artifact_details:
        final_response_dict["saved_extracted_artifact_attempt_details"] = (
            saved_extracted_artifact_details
        )

    log.info(
        "%s Tool execution finished. Final status: %s. Response preview: %s",
        log_identifier,
        final_status,
        final_response_dict,
    )
    return final_response_dict


async def append_to_artifact(
    filename: str,
    content_chunk: str,
    mime_type: str,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Appends a chunk of content to an existing artifact. This operation will
    create a new version of the artifact. The content_chunk should be a string,
    potentially base64 encoded if it represents binary data (indicated by mime_type).
    The chunk size should be limited (e.g., max 3KB) by the LLM.

    Args:
        filename: The name of the artifact to append to. May contain embeds.
        content_chunk: The chunk of content to append (max approx. 3KB).
                       If mime_type suggests binary, this should be base64 encoded.
                       May contain embeds.
        mime_type: The MIME type of the content_chunk. This helps determine if
                   base64 decoding is needed for the chunk. The overall artifact's
                   MIME type will be preserved from its latest version.
                   May contain embeds.
        tool_context: The context provided by the ADK framework.

    Returns:
        A dictionary indicating the result, including the new version of the artifact.
    """
    if not tool_context:
        return {
            "status": "error",
            "filename": filename,
            "message": "ToolContext is missing, cannot append to artifact.",
        }

    log_identifier = f"[BuiltinArtifactTool:append_to_artifact:{filename}]"
    log.debug("%s Processing request to append chunk.", log_identifier)

    try:
        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")

        app_name = inv_context.app_name
        user_id = inv_context.user_id
        session_id = get_original_session_id(inv_context)
        host_component = getattr(inv_context.agent, "host_component", None)

        log.debug(
            "%s Loading latest version of artifact '%s' content to append to.",
            log_identifier,
            filename,
        )
        content_load_result = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            version="latest",
            load_metadata_only=False,
            return_raw_bytes=True,
            component=host_component,
            log_identifier_prefix=f"{log_identifier}[LoadOriginalContent]",
        )

        if content_load_result.get("status") != "success":
            log.error(
                "%s Failed to load original artifact content '%s': %s",
                log_identifier,
                filename,
                content_load_result.get("message"),
            )
            return {
                "status": "error",
                "filename": filename,
                "message": f"Failed to load original artifact content to append to: {content_load_result.get('message')}",
            }

        original_artifact_bytes = content_load_result.get("raw_bytes", b"")
        original_mime_type = content_load_result.get(
            "mime_type", "application/octet-stream"
        )
        original_version_loaded = content_load_result.get("version", "unknown")
        log.info(
            "%s Loaded original artifact content '%s' v%s, type: %s, size: %d bytes.",
            log_identifier,
            filename,
            original_version_loaded,
            original_mime_type,
            len(original_artifact_bytes),
        )

        log.debug(
            "%s Loading latest version of artifact '%s' metadata.",
            log_identifier,
            filename,
        )
        metadata_load_result = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            version="latest",
            load_metadata_only=True,
            component=host_component,
            log_identifier_prefix=f"{log_identifier}[LoadOriginalMetadata]",
        )
        original_metadata_dict = {}
        if metadata_load_result.get("status") == "success":
            original_metadata_dict = metadata_load_result.get("metadata", {})
            log.info(
                "%s Loaded original artifact metadata for '%s' v%s.",
                log_identifier,
                filename,
                metadata_load_result.get("version", "unknown"),
            )
        else:
            log.warning(
                "%s Failed to load original artifact metadata for '%s': %s. Proceeding with minimal metadata.",
                log_identifier,
                filename,
                metadata_load_result.get("message"),
            )

        chunk_bytes, _ = decode_and_get_bytes(
            content_chunk, mime_type, f"{log_identifier}[DecodeChunk]"
        )
        log.debug(
            "%s Decoded content_chunk (declared type: %s) to %d bytes.",
            log_identifier,
            mime_type,
            len(chunk_bytes),
        )

        combined_bytes = original_artifact_bytes + chunk_bytes
        log.debug(
            "%s Appended chunk. New total size: %d bytes.",
            log_identifier,
            len(combined_bytes),
        )

        new_metadata_for_save = {
            key: value
            for key, value in original_metadata_dict.items()
            if key
            not in [
                "filename",
                "mime_type",
                "size_bytes",
                "timestamp_utc",
                "schema",
                "version",
            ]
        }
        new_metadata_for_save["appended_from_version"] = original_version_loaded
        new_metadata_for_save["appended_chunk_declared_mime_type"] = mime_type

        schema_max_keys = (
            host_component.get_config("schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS)
            if host_component
            else DEFAULT_SCHEMA_MAX_KEYS
        )

        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            content_bytes=combined_bytes,
            mime_type=original_mime_type,
            metadata_dict=new_metadata_for_save,
            timestamp=datetime.now(timezone.utc),
            schema_max_keys=schema_max_keys,
            tool_context=tool_context,
        )

        log.info(
            "%s Result from save_artifact_with_metadata after append: %s",
            log_identifier,
            save_result,
        )

        if save_result.get("status") == "error":
            raise IOError(
                f"Failed to save appended artifact: {save_result.get('message', 'Unknown error')}"
            )

        return {
            "status": "success",
            "filename": filename,
            "new_version": save_result.get("data_version"),
            "total_size_bytes": len(combined_bytes),
            "message": f"Chunk appended to '{filename}'. New version is {save_result.get('data_version')} with total size {len(combined_bytes)} bytes.",
        }

    except FileNotFoundError as e:
        log.warning("%s Original artifact not found for append: %s", log_identifier, e)
        return {
            "status": "error",
            "filename": filename,
            "message": f"Original artifact '{filename}' not found: {e}",
        }
    except ValueError as e:
        log.warning("%s Value error during append: %s", log_identifier, e)
        return {"status": "error", "filename": filename, "message": str(e)}
    except IOError as e:
        log.warning("%s IO error during append: %s", log_identifier, e)
        return {"status": "error", "filename": filename, "message": str(e)}
    except Exception as e:
        log.exception(
            "%s Unexpected error appending to artifact '%s': %s",
            log_identifier,
            filename,
            e,
        )
        return {
            "status": "error",
            "filename": filename,
            "message": f"Failed to append to artifact: {e}",
        }


async def _save_extracted_artifact(
    tool_context: ToolContext,
    host_component: Any,
    extracted_content_bytes: bytes,
    source_artifact_filename: str,
    source_artifact_version: Union[int, str],
    extraction_goal: str,
    output_filename_base: Optional[str],
    output_mime_type: str,
) -> Dict[str, Any]:
    """
    Saves the extracted content as a new artifact with comprehensive metadata.

    Args:
        tool_context: The ADK ToolContext.
        host_component: The A2A_ADK_HostComponent instance for accessing config and services.
        extracted_content_bytes: The raw byte content of the extracted data.
        source_artifact_filename: The filename of the original artifact.
        source_artifact_version: The version of the original artifact.
        extraction_goal: The natural language goal used for extraction.
        output_filename_base: Optional base for the new artifact's filename.
        output_mime_type: The MIME type of the extracted content.

    Returns:
        A dictionary containing details of the saved artifact, as returned by
        `save_artifact_with_metadata`.
    """
    log_identifier = f"[BuiltinArtifactTool:_save_extracted_artifact]"
    log.debug("%s Saving extracted content...", log_identifier)

    try:
        base_name = output_filename_base or f"{source_artifact_filename}_extracted"
        base_name_sanitized = re.sub(r'[<>:"/\\|?*\s]+', "_", base_name)
        base_name_sanitized = base_name_sanitized.strip("_")

        suffix = uuid.uuid4().hex[:8]
        extension_map = {
            "text/plain": ".txt",
            "application/json": ".json",
            "text/csv": ".csv",
            "text/html": ".html",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "application/pdf": ".pdf",
        }
        ext = extension_map.get(output_mime_type.lower(), ".dat")
        filename = f"{base_name_sanitized}_{suffix}{ext}"
        log.debug("%s Generated output filename: %s", log_identifier, filename)

        timestamp = datetime.now(timezone.utc)
        metadata_for_saving = {
            "description": f"Content extracted/transformed from artifact '{source_artifact_filename}' (version {source_artifact_version}) using goal: '{extraction_goal}'.",
            "source_artifact_filename": source_artifact_filename,
            "source_artifact_version": source_artifact_version,
            "extraction_goal_used": extraction_goal,
        }
        log.debug(
            "%s Prepared metadata for saving: %s", log_identifier, metadata_for_saving
        )

        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")

        app_name = inv_context.app_name
        user_id = inv_context.user_id
        session_id = get_original_session_id(inv_context)
        schema_max_keys = host_component.get_config(
            "schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS
        )

        log.debug(
            "%s Calling save_artifact_with_metadata for '%s' (app: %s, user: %s, session: %s, schema_keys: %d)",
            log_identifier,
            filename,
            app_name,
            user_id,
            session_id,
            schema_max_keys,
        )

        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            content_bytes=extracted_content_bytes,
            mime_type=output_mime_type,
            metadata_dict=metadata_for_saving,
            timestamp=timestamp,
            schema_max_keys=schema_max_keys,
            tool_context=tool_context,
        )

        log.info(
            "%s Extracted content saved as artifact '%s' (version %s). Result: %s",
            log_identifier,
            save_result.get("data_filename", filename),
            save_result.get("data_version", "N/A"),
            save_result.get("status"),
        )
        return save_result

    except Exception as e:
        log.exception(
            "%s Error in _save_extracted_artifact for source '%s': %s",
            log_identifier,
            source_artifact_filename,
            e,
        )
        return {
            "status": "error",
            "data_filename": filename if "filename" in locals() else "unknown_filename",
            "message": f"Failed to save extracted content as artifact: {e}",
        }


async def _notify_artifact_save(
    filename: str,
    version: int,
    status: str,
    tool_context: ToolContext = None,  # Keep tool_context for signature consistency
) -> Dict[str, Any]:
    """
    CRITICAL: _notify_artifact_save is automatically invoked by the system as a side-effect when you create artifacts. You should NEVER call this tool yourself. The system will call it for you and provide the results in your next turn. If you manually invoke it, you are making an error."
    """
    return {
        "filename": filename,
        "version": version,
        "status": status,
        "message": "Artifact has been created and provided to the requester",
    }


_notify_artifact_save_tool_def = BuiltinTool(
    name="_notify_artifact_save",
    implementation=_notify_artifact_save,
    description="CRITICAL: _notify_artifact_save is automatically invoked by the system as a side-effect when you create artifacts. You should NEVER call this tool yourself. The system will call it for you and provide the results in your next turn. If you manually invoke it, you are making an error.",
    category="internal",
    required_scopes=[],  # No scopes needed for an internal notification tool
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The name of the artifact that was saved.",
            ),
            "version": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="The version number of the saved artifact.",
            ),
            "status": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The status of the save operation.",
            ),
        },
        required=["filename", "version", "status"],
    ),
    examples=[],
)

append_to_artifact_tool_def = BuiltinTool(
    name="append_to_artifact",
    implementation=append_to_artifact,
    description="Appends a chunk of content to an existing artifact. This operation will create a new version of the artifact. The content_chunk should be a string, potentially base64 encoded if it represents binary data (indicated by mime_type). The chunk size should be limited (e.g., max 3KB) by the LLM.",
    category="artifact_management",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:artifact:append"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The name of the artifact to append to. May contain embeds.",
            ),
            "content_chunk": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The chunk of content to append (max approx. 3KB). If mime_type suggests binary, this should be base64 encoded. May contain embeds.",
            ),
            "mime_type": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The MIME type of the content_chunk. This helps determine if base64 decoding is needed for the chunk. The overall artifact's MIME type will be preserved from its latest version. May contain embeds.",
            ),
        },
        required=["filename", "content_chunk", "mime_type"],
    ),
    examples=[],
)

list_artifacts_tool_def = BuiltinTool(
    name="list_artifacts",
    implementation=list_artifacts,
    description="Lists all available data artifact filenames and their versions for the current session. Includes a summary of the latest version's metadata for each artifact.",
    category="artifact_management",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:artifact:list"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={},
        required=[],
    ),
    examples=[],
)

load_artifact_tool_def = BuiltinTool(
    name="load_artifact",
    implementation=load_artifact,
    description="Loads the content or metadata of a specific artifact version. If load_metadata_only is True, loads the full metadata dictionary. Otherwise, loads text content (potentially truncated) or a summary for binary types. Line numbers can be optionally included for precise line range identification.",
    category="artifact_management",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:artifact:load"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The name of the artifact to load. May contain embeds.",
            ),
            "version": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="The specific version number to load. Must be explicitly provided.",
            ),
            "load_metadata_only": adk_types.Schema(
                type=adk_types.Type.BOOLEAN,
                description="If True, load only the metadata JSON. Default False.",
                nullable=True,
            ),
            "max_content_length": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="Optional. Maximum character length for text content. If None, uses app configuration. Range: 100-100,000.",
                nullable=True,
            ),
            "include_line_numbers": adk_types.Schema(
                type=adk_types.Type.BOOLEAN,
                description="If True, prefix each line with its 1-based line number followed by a TAB character. Line numbers are for LLM viewing only and are not stored in the artifact. Default False.",
                nullable=True,
            ),
        },
        required=["filename", "version"],
    ),
    examples=[],
)

apply_embed_and_create_artifact_tool_def = BuiltinTool(
    name="apply_embed_and_create_artifact",
    implementation=apply_embed_and_create_artifact,
    description="Resolves an 'artifact_content' embed directive (including modifiers and formatting) and saves the resulting content as a new artifact. The entire embed directive must be provided as a string.",
    category="artifact_management",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:artifact:create", "tool:artifact:load"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "output_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The desired name for the new artifact.",
            ),
            "embed_directive": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The full '«artifact_content:...>>>...>>>format:...»' string.",
            ),
            "output_metadata": adk_types.Schema(
                type=adk_types.Type.OBJECT,
                description="Optional metadata for the new artifact.",
                nullable=True,
            ),
        },
        required=["output_filename", "embed_directive"],
    ),
    raw_string_args=["embed_directive"],
    examples=[],
)

extract_content_from_artifact_tool_def = BuiltinTool(
    name="extract_content_from_artifact",
    implementation=extract_content_from_artifact,
    description="Loads an existing artifact, uses an internal LLM to process its content based on an 'extraction_goal,' and manages the output by returning it or saving it as a new artifact.",
    category="artifact_management",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:artifact:load", "tool:artifact:create"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Name of the source artifact. May contain embeds.",
            ),
            "extraction_goal": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Natural language instruction for the LLM on what to extract or how to transform the content. May contain embeds.",
            ),
            "version": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Version of the source artifact. Can be an integer or 'latest'. Defaults to 'latest'. May contain embeds.",
                nullable=True,
            ),
            "output_filename_base": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional base name for the new artifact if the extracted content is saved. May contain embeds.",
                nullable=True,
            ),
        },
        required=["filename", "extraction_goal"],
    ),
    examples=[],
)

tool_registry.register(_notify_artifact_save_tool_def)
tool_registry.register(append_to_artifact_tool_def)
tool_registry.register(list_artifacts_tool_def)
tool_registry.register(load_artifact_tool_def)
tool_registry.register(apply_embed_and_create_artifact_tool_def)
tool_registry.register(extract_content_from_artifact_tool_def)


async def delete_artifact(
    filename: str,
    version: Optional[int] = None,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Deletes a specific version of an artifact, or all versions if no version is specified.

    Args:
        filename: The name of the artifact to delete.
        version: The specific version number to delete. If not provided, all versions will be deleted.
        tool_context: The context provided by the ADK framework.

    Returns:
        A dictionary indicating the result of the deletion.
    """
    if not tool_context:
        return {
            "status": "error",
            "filename": filename,
            "message": "ToolContext is missing, cannot delete artifact.",
        }

    log_identifier = (
        f"[BuiltinArtifactTool:delete_artifact:{filename}:{version or 'all'}]"
    )
    log.debug("%s Processing request.", log_identifier)

    try:
        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")

        app_name = inv_context.app_name
        user_id = inv_context.user_id
        session_id = get_original_session_id(inv_context)

        if not hasattr(artifact_service, "delete_artifact"):
            raise NotImplementedError(
                "ArtifactService does not support deleting artifacts."
            )

        if version is not None:
            log.warning(
                "%s Deleting a specific version (%s) is not supported by the current artifact service interface. "
                "All versions of the artifact will be deleted.",
                log_identifier,
                version,
            )

        await artifact_service.delete_artifact(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
        )

        log.info(
            "%s Successfully deleted artifact '%s' version '%s'.",
            log_identifier,
            filename,
            version or "all",
        )
        return {
            "status": "success",
            "filename": filename,
            "version": version or "all",
            "message": f"Artifact '{filename}' version '{version or 'all'}' deleted successfully.",
        }

    except FileNotFoundError as e:
        log.warning("%s Artifact not found for deletion: %s", log_identifier, e)
        return {
            "status": "error",
            "filename": filename,
            "message": f"Artifact '{filename}' not found.",
        }
    except Exception as e:
        log.exception(
            "%s Error deleting artifact '%s': %s", log_identifier, filename, e
        )
        return {
            "status": "error",
            "filename": filename,
            "message": f"Failed to delete artifact: {e}",
        }


delete_artifact_tool_def = BuiltinTool(
    name="delete_artifact",
    implementation=delete_artifact,
    description="Deletes a specific version of an artifact, or all versions if no version is specified.",
    category="artifact_management",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:artifact:delete"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The name of the artifact to delete.",
            ),
            "version": adk_types.Schema(
                type=adk_types.Type.INTEGER,
                description="The specific version number to delete. If not provided, all versions will be deleted.",
                nullable=True,
            ),
        },
        required=["filename"],
    ),
    examples=[],
)

tool_registry.register(delete_artifact_tool_def)


def _perform_single_replacement(
    content: str,
    search_expr: str,
    replace_expr: str,
    is_regex: bool,
    regex_flags: str,
    log_identifier: str,
    strict_match_validation: bool = False,
) -> Tuple[str, int, Optional[str]]:
    """
    Performs a single search-and-replace operation.

    Args:
        content: The text content to search/replace in
        search_expr: The search pattern (literal or regex)
        replace_expr: The replacement text
        is_regex: If True, search_expr is treated as regex
        regex_flags: Flags for regex behavior ('g', 'i', 'm', 's')
        log_identifier: Logging prefix
        strict_match_validation: If True, error on multiple matches without 'g' flag (for batch mode)

    Returns:
        tuple: (new_content, match_count, error_message)
               error_message is None on success
    """
    match_count = 0
    new_content = content

    if is_regex:
        # Parse regex flags
        flags_value = 0
        global_replace = False

        if regex_flags:
            for flag_char in regex_flags.lower():
                if flag_char == "g":
                    global_replace = True
                elif flag_char == "i":
                    flags_value |= re.IGNORECASE
                elif flag_char == "m":
                    flags_value |= re.MULTILINE
                elif flag_char == "s":
                    flags_value |= re.DOTALL
                else:
                    log.warning(
                        "%s Ignoring unrecognized regexp flag: '%s'",
                        log_identifier,
                        flag_char,
                    )

        # Convert JavaScript-style capture groups ($1, $2) to Python style (\1, \2)
        # Also handle escaped dollar signs ($$) -> literal $
        python_replace_expr = replace_expr
        # First, protect escaped dollars: $$ -> a placeholder
        python_replace_expr = python_replace_expr.replace("$$", "\x00DOLLAR\x00")
        # Convert capture groups: $1 -> \1
        python_replace_expr = re.sub(r"\$(\d+)", r"\\\1", python_replace_expr)
        # Restore escaped dollars: placeholder -> $
        python_replace_expr = python_replace_expr.replace("\x00DOLLAR\x00", "$")

        try:
            # Compile the regex pattern
            pattern = re.compile(search_expr, flags_value)

            # Count matches first
            match_count = len(pattern.findall(content))

            if match_count == 0:
                return content, 0, f"No matches found"

            # Check for multiple matches without global flag (only in strict mode for batch operations)
            if strict_match_validation and match_count > 1 and not global_replace:
                return (
                    content,
                    match_count,
                    f"Multiple matches found ({match_count}) but global flag 'g' not set",
                )

            # Perform replacement
            count_limit = 0 if global_replace else 1
            new_content = pattern.sub(python_replace_expr, content, count=count_limit)

            return new_content, match_count, None

        except re.error as regex_err:
            return content, 0, f"Invalid regular expression: {regex_err}"

    else:
        # Literal string replacement
        match_count = content.count(search_expr)

        if match_count == 0:
            return content, 0, f"No matches found"

        # Replace all occurrences for literal mode
        new_content = content.replace(search_expr, replace_expr)
        return new_content, match_count, None


async def artifact_search_and_replace_regex(
    filename: str,
    search_expression: Optional[str] = None,
    replace_expression: Optional[str] = None,
    is_regexp: bool = False,
    version: Optional[str] = "latest",
    regexp_flags: Optional[str] = "",
    new_filename: Optional[str] = None,
    new_description: Optional[str] = None,
    replacements: Optional[List[Dict[str, Any]]] = None,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Performs search and replace on an artifact's text content using either
    literal string matching or regular expressions. Note that this is run once across the entire artifact.
    If multiple replacements are needed, then set the 'g' flag in regexp_flags.

    Handling Multi-line Search and Replace:

        When searching for or replacing text that spans multiple lines:

        - In literal mode (is_regexp=false): Include actual newline characters directly in your search_expression
        and replace_expression parameters. Do NOT use escape sequences like \n - the tool will search for those
        literal characters. Multi-line parameter values are fully supported in the XML parameter format.

        - In regex mode (is_regexp=true): Use the regex pattern \n to match newline characters in your pattern.

    For multiple independent replacements:

        Use the replacements array parameter to perform all replacements atomically in a single tool call, which is more efficient than multiple sequential calls.

    Args:
        filename: The name of the artifact to search/replace in.
        search_expression: The pattern to search for (regex if is_regexp=true, literal otherwise).
        replace_expression: The replacement text. For regex mode, supports capture groups ($1, $2, etc.). Use $$ to insert a literal dollar sign
        is_regexp: If True, treat search_expression as a regular expression. If False, treat as literal string.
        version: The version of the artifact to operate on. Can be an integer version number as a string or 'latest'. Defaults to 'latest'.
        regexp_flags: Flags for regex behavior (only used when is_regexp=true).
                     String of letters: 'g' (global/replace-all), 'i' (case-insensitive), 'm' (multiline), 's' (dotall).
                     Defaults to empty string (no flags).
        new_filename: Optional. If provided, saves the result as a new artifact with this name.
        new_description: Optional. Description for the new/updated artifact.

    Returns:
        A dictionary containing the result status, filename, version, match count, and any error messages.
    """
    if not tool_context:
        return {
            "status": "error",
            "filename": filename,
            "message": "ToolContext is missing, cannot perform search and replace.",
        }

    log_identifier = (
        f"[BuiltinArtifactTool:artifact_search_and_replace_regex:{filename}:{version}]"
    )
    log.debug("%s Processing request.", log_identifier)

    # Validate parameter combinations
    if replacements is not None and (
        search_expression is not None or replace_expression is not None
    ):
        return {
            "status": "error",
            "filename": filename,
            "message": "Cannot provide both 'replacements' array and individual 'search_expression'/'replace_expression'. Use one or the other.",
        }

    if replacements is None and (
        search_expression is None or replace_expression is None
    ):
        return {
            "status": "error",
            "filename": filename,
            "message": "Must provide either 'replacements' array or both 'search_expression' and 'replace_expression'.",
        }

    if replacements is not None:
        if not isinstance(replacements, list) or len(replacements) == 0:
            return {
                "status": "error",
                "filename": filename,
                "message": "replacements must be a non-empty array.",
            }

        # Validate each replacement entry
        for idx, repl in enumerate(replacements):
            if not isinstance(repl, dict):
                return {
                    "status": "error",
                    "filename": filename,
                    "message": f"Replacement at index {idx} must be a dictionary.",
                }
            if "search" not in repl or "replace" not in repl or "is_regexp" not in repl:
                return {
                    "status": "error",
                    "filename": filename,
                    "message": f"Replacement at index {idx} missing required fields: 'search', 'replace', 'is_regexp'.",
                }

    # Validate inputs for single replacement mode
    if replacements is None and not search_expression:
        return {
            "status": "error",
            "filename": filename,
            "message": "search_expression cannot be empty.",
        }

    # Determine output filename
    output_filename = new_filename if new_filename else filename

    if new_filename and not is_filename_safe(new_filename):
        return {
            "status": "error",
            "filename": filename,
            "message": f"Invalid new_filename: '{new_filename}'. Filename must not contain path separators or traversal sequences.",
        }

    try:
        inv_context = tool_context._invocation_context
        artifact_service = inv_context.artifact_service
        if not artifact_service:
            raise ValueError("ArtifactService is not available in the context.")

        app_name = inv_context.app_name
        user_id = inv_context.user_id
        session_id = get_original_session_id(inv_context)
        host_component = getattr(inv_context.agent, "host_component", None)

        # Load the source artifact
        log.debug(
            "%s Loading artifact '%s' version '%s'.", log_identifier, filename, version
        )
        load_result = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            version=version,
            return_raw_bytes=True,
            component=host_component,
            log_identifier_prefix=log_identifier,
        )

        if load_result.get("status") != "success":
            return {
                "status": "error",
                "filename": filename,
                "version": version,
                "message": f"Failed to load artifact: {load_result.get('message', 'Unknown error')}",
            }

        source_bytes = load_result.get("raw_bytes")
        source_mime_type = load_result.get("mime_type", "application/octet-stream")
        actual_version = load_result.get("version", version)

        # Verify it's a text-based artifact
        if not is_text_based_file(source_mime_type, source_bytes):
            return {
                "status": "error",
                "filename": filename,
                "version": actual_version,
                "message": f"Cannot perform search and replace on binary artifact of type '{source_mime_type}'. This tool only works with text-based content.",
            }

        # Decode the content
        try:
            original_content = source_bytes.decode("utf-8")
        except UnicodeDecodeError as decode_err:
            log.error(
                "%s Failed to decode artifact content as UTF-8: %s",
                log_identifier,
                decode_err,
            )
            return {
                "status": "error",
                "filename": filename,
                "version": actual_version,
                "message": f"Failed to decode artifact content as UTF-8: {decode_err}",
            }

        # Perform the search and replace
        if replacements:
            # Batch mode
            log.info(
                "%s Processing batch of %d replacements.",
                log_identifier,
                len(replacements),
            )

            current_content = original_content
            replacement_results = []
            total_matches = 0

            for idx, repl in enumerate(replacements):
                search_expr = repl["search"]
                replace_expr = repl["replace"]
                is_regex = repl["is_regexp"]
                regex_flags = repl.get("regexp_flags", "")

                # Perform replacement on current state (with strict validation for batch mode)
                new_content, match_count, error_msg = _perform_single_replacement(
                    current_content,
                    search_expr,
                    replace_expr,
                    is_regex,
                    regex_flags,
                    log_identifier,
                    strict_match_validation=True,
                )

                if error_msg:
                    # Rollback - return error with details
                    log.warning(
                        "%s Batch replacement failed at index %d: %s",
                        log_identifier,
                        idx,
                        error_msg,
                    )

                    # Mark all as skipped
                    all_results = replacement_results + [
                        {
                            "search": repl["search"],
                            "match_count": match_count,
                            "status": "error",
                            "error": error_msg,
                        }
                    ]
                    # Add remaining as skipped
                    for i in range(idx + 1, len(replacements)):
                        all_results.append(
                            {
                                "search": replacements[i]["search"],
                                "match_count": 0,
                                "status": "skipped",
                            }
                        )

                    return {
                        "status": "error",
                        "filename": filename,
                        "version": actual_version,
                        "message": f"Batch replacement failed: No changes applied due to error in replacement {idx + 1}",
                        "replacement_results": all_results,
                        "failed_replacement": {
                            "index": idx,
                            "search": search_expr,
                            "error": error_msg,
                        },
                    }

                # Success - update state and continue
                current_content = new_content
                total_matches += match_count
                replacement_results.append(
                    {
                        "search": search_expr,
                        "match_count": match_count,
                        "status": "success",
                    }
                )

                log.debug(
                    "%s Replacement %d/%d succeeded: %d matches",
                    log_identifier,
                    idx + 1,
                    len(replacements),
                    match_count,
                )

            # All replacements succeeded
            final_content = current_content
            total_replacements = len(replacements)

            log.info(
                "%s Batch replacement succeeded: %d operations, %d total matches",
                log_identifier,
                total_replacements,
                total_matches,
            )

        else:
            # Single replacement mode (backward compatible)
            final_content, match_count, error_msg = _perform_single_replacement(
                original_content,
                search_expression,
                replace_expression,
                is_regexp,
                regexp_flags,
                log_identifier,
            )

            if error_msg:
                # Check if it's a "no matches" error specifically
                if match_count == 0 and "No matches found" in error_msg:
                    return {
                        "status": "no_matches",
                        "filename": filename,
                        "version": actual_version,
                        "match_count": 0,
                        "message": f"No matches found for pattern '{search_expression}'. Artifact not modified.",
                    }
                else:
                    return {
                        "status": "error",
                        "filename": filename,
                        "version": actual_version,
                        "message": error_msg,
                    }

            total_replacements = 1
            total_matches = match_count
            replacement_results = None

        # Prepare metadata for the new/updated artifact
        if replacements:
            new_metadata = {
                "source": f"artifact_search_and_replace_regex (batch) from '{filename}' v{actual_version}",
                "total_replacements": total_replacements,
                "total_matches": total_matches,
            }
        else:
            new_metadata = {
                "source": f"artifact_search_and_replace_regex from '{filename}' v{actual_version}",
                "search_expression": search_expression,
                "replace_expression": replace_expression,
                "is_regexp": is_regexp,
                "match_count": match_count,
            }

        if regexp_flags and is_regexp:
            new_metadata["regexp_flags"] = regexp_flags

        if new_description:
            new_metadata["description"] = new_description
        elif not new_filename:
            # If updating the same artifact, preserve original description if available
            try:
                metadata_load_result = await load_artifact_content_or_metadata(
                    artifact_service=artifact_service,
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename,
                    version=actual_version,
                    load_metadata_only=True,
                    component=host_component,
                    log_identifier_prefix=log_identifier,
                )
                if metadata_load_result.get("status") == "success":
                    original_metadata = metadata_load_result.get("metadata", {})
                    if "description" in original_metadata:
                        new_metadata["description"] = original_metadata["description"]
            except Exception as meta_err:
                log.warning(
                    "%s Could not load original metadata to preserve description: %s",
                    log_identifier,
                    meta_err,
                )

        # Save the result
        new_content_bytes = final_content.encode("utf-8")
        schema_max_keys = (
            host_component.get_config("schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS)
            if host_component
            else DEFAULT_SCHEMA_MAX_KEYS
        )

        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=output_filename,
            content_bytes=new_content_bytes,
            mime_type=source_mime_type,
            metadata_dict=new_metadata,
            timestamp=datetime.now(timezone.utc),
            schema_max_keys=schema_max_keys,
            tool_context=tool_context,
        )

        if save_result.get("status") not in ["success", "partial_success"]:
            log.error(
                "%s Failed to save modified artifact: %s",
                log_identifier,
                save_result.get("message"),
            )
            return {
                "status": "error",
                "filename": filename,
                "version": actual_version,
                "message": f"Search and replace succeeded, but failed to save result: {save_result.get('message')}",
            }

        result_version = save_result.get("data_version")
        log.info(
            "%s Successfully saved modified artifact '%s' as version %s.",
            log_identifier,
            output_filename,
            result_version,
        )

        # Return appropriate response based on mode
        if replacements:
            return {
                "status": "success",
                "source_filename": filename,
                "source_version": actual_version,
                "output_filename": output_filename,
                "output_version": result_version,
                "total_replacements": total_replacements,
                "replacement_results": replacement_results,
                "total_matches": total_matches,
                "message": f"Batch replacement completed: {total_replacements} operations, {total_matches} total matches",
            }
        else:
            # Compute replacements_made for backward compatibility
            # For literal replacements, all matches are replaced
            # For regex without 'g' flag, only first match is replaced
            global_replace = "g" in (regexp_flags or "")
            replacements_made = (
                match_count if not is_regexp or global_replace else min(match_count, 1)
            )

            return {
                "status": "success",
                "source_filename": filename,
                "source_version": actual_version,
                "output_filename": output_filename,
                "output_version": result_version,
                "match_count": match_count,
                "replacements_made": replacements_made,
                "message": f"Successfully performed {'regex' if is_regexp else 'literal'} search and replace. "
                f"Found {match_count} match(es), saved result as '{output_filename}' v{result_version}.",
            }

    except FileNotFoundError as fnf_err:
        log.warning("%s Artifact not found: %s", log_identifier, fnf_err)
        return {
            "status": "error",
            "filename": filename,
            "version": version,
            "message": f"Artifact not found: {fnf_err}",
        }
    except Exception as e:
        log.exception(
            "%s Unexpected error during search and replace: %s", log_identifier, e
        )
        return {
            "status": "error",
            "filename": filename,
            "version": version,
            "message": f"Unexpected error: {e}",
        }


artifact_search_and_replace_regex_tool_def = BuiltinTool(
    name="artifact_search_and_replace_regex",
    implementation=artifact_search_and_replace_regex,
    description="Performs search and replace on an artifact's text content using either literal string matching or regular expressions. Supports both single replacements and atomic batch replacements for efficiency.",
    category="artifact_management",
    category_name=CATEGORY_NAME,
    category_description=CATEGORY_DESCRIPTION,
    required_scopes=["tool:artifact:load", "tool:artifact:create"],
    parameters=adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The name of the artifact to search/replace in.",
            ),
            "search_expression": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The pattern to search for (single replacement mode). If is_regexp is true, this is treated as a regular expression. Otherwise, it's a literal string. Do not use if 'replacements' is provided.",
                nullable=True,
            ),
            "replace_expression": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The replacement text (single replacement mode). For regex mode, supports capture group references using $1, $2, etc. Use $$ to insert a literal dollar sign. Do not use if 'replacements' is provided.",
                nullable=True,
            ),
            "is_regexp": adk_types.Schema(
                type=adk_types.Type.BOOLEAN,
                description="If true, treat search_expression as a regular expression. If false, treat as literal string. Only used in single replacement mode.",
                nullable=True,
            ),
            "version": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="The version of the artifact to operate on. Can be an integer version number or 'latest'. Defaults to 'latest'.",
                nullable=True,
            ),
            "regexp_flags": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Flags for regex behavior (only used when is_regexp=true in single mode). String of letters: 'g' (global/replace all), 'i' (case-insensitive), 'm' (multiline), 's' (dotall). Example: 'gim'. Defaults to empty string.",
                nullable=True,
            ),
            "new_filename": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional. If provided, saves the result as a new artifact with this name instead of creating a new version of the original.",
                nullable=True,
            ),
            "new_description": adk_types.Schema(
                type=adk_types.Type.STRING,
                description="Optional. Description for the new/updated artifact.",
                nullable=True,
            ),
            "replacements": adk_types.Schema(
                type=adk_types.Type.ARRAY,
                items=adk_types.Schema(
                    type=adk_types.Type.OBJECT,
                    properties={
                        "search": adk_types.Schema(
                            type=adk_types.Type.STRING,
                            description="The search pattern (literal string or regex).",
                        ),
                        "replace": adk_types.Schema(
                            type=adk_types.Type.STRING,
                            description="The replacement text. For regex mode, supports $1, $2, etc. Use $$ for literal $.",
                        ),
                        "is_regexp": adk_types.Schema(
                            type=adk_types.Type.BOOLEAN,
                            description="If true, 'search' is a regex pattern. If false, literal string.",
                        ),
                        "regexp_flags": adk_types.Schema(
                            type=adk_types.Type.STRING,
                            description="Flags for regex: 'g' (global), 'i' (case-insensitive), 'm' (multiline), 's' (dotall). Default: ''.",
                            nullable=True,
                        ),
                    },
                    required=["search", "replace", "is_regexp"],
                ),
                description="Optional. Array of replacement operations to perform atomically. Each operation is processed sequentially on the cumulative result. If any operation fails, all changes are rolled back. Do not use with 'search_expression' or 'replace_expression'.",
                nullable=True,
            ),
        },
        required=["filename"],
    ),
    examples=[],
)

tool_registry.register(artifact_search_and_replace_regex_tool_def)
