
"""
Helper functions for artifact management, including metadata handling and schema inference.
"""

import logging
import base64
import binascii
import json
import csv
import io
import inspect
import os
import yaml
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, List, Union, TYPE_CHECKING
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
from google.adk.artifacts import BaseArtifactService
from google.genai import types as adk_types
from ...common.a2a.types import ArtifactInfo
from ...common.utils.mime_helpers import is_text_based_mime_type, is_text_based_file
from ...common.constants import (
    TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY,
    TEXT_ARTIFACT_CONTEXT_DEFAULT_LENGTH,
)
from ...agent.utils.context_helpers import get_original_session_id

if TYPE_CHECKING:
    from google.adk.tools import ToolContext
    from ...agent.sac.component import SamAgentComponent

log = logging.getLogger(__name__)

METADATA_SUFFIX = ".metadata.json"
DEFAULT_SCHEMA_MAX_KEYS = 20
DEFAULT_SCHEMA_INFERENCE_DEPTH = 4


def is_filename_safe(filename: str) -> bool:
    """
    Checks if a filename is safe for artifact creation.
    - Must not be empty or just whitespace.
    - Must not contain path traversal sequences ('..').
    - Must not contain path separators ('/' or '\\').
    - Must not be a reserved name like '.' or '..'.

    Args:
        filename: The filename to validate.

    Returns:
        True if the filename is safe, False otherwise.
    """
    if not filename or not filename.strip():
        return False

    # Check for path traversal
    if ".." in filename:
        return False

    # Check for path separators
    if "/" in filename or "\\" in filename:
        return False

    # Check for reserved names
    if filename.strip() in [".", ".."]:
        return False

    return True


def sanitize_to_filename(
    text: str,
    max_length: int = 50,
    suffix: str = "",
    replacement_char: str = "_"
) -> str:
    """
    Sanitizes arbitrary text into a safe filename.
    
    Converts text (like a research question or title) into a filesystem-safe
    filename by:
    1. Converting to lowercase
    2. Removing non-word characters (except spaces and hyphens)
    3. Replacing spaces and hyphens with the replacement character
    4. Limiting length to max_length
    5. Optionally appending a suffix
    
    Args:
        text: The text to convert into a filename (e.g., research question, title)
        max_length: Maximum length of the base filename (before suffix). Default: 50
        suffix: Optional suffix to append (e.g., "_report.md"). Default: ""
        replacement_char: Character to replace spaces/hyphens with. Default: "_"
    
    Returns:
        A sanitized filename string safe for filesystem use.
    
    Examples:
        >>> sanitize_to_filename("What is AI?")
        'what_is_ai'
        >>> sanitize_to_filename("Research: Deep Learning!", suffix="_report.md")
        'research_deep_learning_report.md'
        >>> sanitize_to_filename("A very long research question about many topics", max_length=20)
        'a_very_long_research'
    """
    import re
    
    if not text:
        return f"unnamed{suffix}"
    
    # Convert to lowercase and remove non-word characters except spaces and hyphens
    safe_name = re.sub(r'[^\w\s-]', '', text.lower())
    
    # Replace spaces and hyphens with the replacement character
    safe_name = re.sub(r'[-\s]+', replacement_char, safe_name)
    
    # Strip leading/trailing replacement chars
    safe_name = safe_name.strip(replacement_char)
    
    # Limit length
    if max_length > 0:
        safe_name = safe_name[:max_length]
        # Strip trailing replacement char if we cut in the middle
        safe_name = safe_name.rstrip(replacement_char)
    
    # Handle empty result
    if not safe_name:
        safe_name = "unnamed"
    
    return f"{safe_name}{suffix}"


def ensure_correct_extension(filename_from_llm: str, desired_extension: str) -> str:
    """
    Ensures a filename has the correct extension, handling cases where the LLM
    might provide a filename with or without an extension, or with the wrong one.

    Args:
        filename_from_llm: The filename string provided by the LLM.
        desired_extension: The correct extension for the file (e.g., 'png', 'md').
                           Should be provided without a leading dot.

    Returns:
        A string with the correctly formatted filename.
    """
    if not filename_from_llm:
        return f"unnamed.{desired_extension.lower()}"
    filename_stripped = filename_from_llm.strip()
    desired_ext_clean = desired_extension.lower().strip().lstrip(".")
    base_name, current_ext = os.path.splitext(filename_stripped)
    current_ext_clean = current_ext.lower().lstrip(".")
    if current_ext_clean == desired_ext_clean:
        return filename_stripped
    else:
        return f"{base_name}.{desired_ext_clean}"


def format_artifact_uri(
    app_name: str,
    user_id: str,
    session_id: str,
    filename: str,
    version: Union[int, str],
) -> str:
    """Formats the components into a standard artifact:// URI."""
    path = f"/{user_id}/{session_id}/{filename}"
    query = urlencode({"version": str(version)})
    return urlunparse(("artifact", app_name, path, "", query, ""))


def parse_artifact_uri(uri: str) -> Dict[str, Any]:
    """Parses an artifact:// URI into its constituent parts."""
    parsed = urlparse(uri)
    if parsed.scheme != "artifact":
        raise ValueError("Invalid URI scheme, must be 'artifact'.")

    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) != 3:
        raise ValueError("Invalid URI path. Expected /user_id/session_id/filename")

    query_params = parse_qs(parsed.query)
    version = query_params.get("version", [None])[0]
    if not version:
        raise ValueError("Version is missing from URI query parameters.")

    return {
        "app_name": parsed.netloc,
        "user_id": path_parts[0],
        "session_id": path_parts[1],
        "filename": path_parts[2],
        "version": int(version) if version.isdigit() else version,
    }


def _clean_metadata_for_output(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove null, False, and empty values from metadata to reduce token usage.
    Recursively cleans nested dictionaries.

    Args:
        metadata: The metadata dictionary to clean

    Returns:
        A cleaned dictionary with unnecessary fields removed
    """
    cleaned = {}
    for key, value in metadata.items():
        # Skip None, False, and empty collections
        if value is None or value is False or value == {} or value == []:
            continue

        # Recursively clean nested dictionaries
        if isinstance(value, dict):
            cleaned_nested = _clean_metadata_for_output(value)
            if cleaned_nested:  # Only include if not empty after cleaning
                cleaned[key] = cleaned_nested
        else:
            cleaned[key] = value

    return cleaned


def _inspect_structure(
    data: Any, max_depth: int, max_keys: int, current_depth: int = 0
) -> Any:
    """
    Recursively inspects data structure up to max_depth and max_keys for dictionaries.
    """
    if current_depth >= max_depth:
        return type(data).__name__
    if isinstance(data, dict):
        if not data:
            return {}
        inspected_dict = {}
        keys = list(data.keys())
        keys_to_inspect = keys[:max_keys]
        for key in keys_to_inspect:
            inspected_dict[key] = _inspect_structure(
                data[key], max_depth, max_keys, current_depth + 1
            )
        if len(keys) > max_keys:
            inspected_dict["..."] = f"{len(keys) - max_keys} more keys"
        return inspected_dict
    elif isinstance(data, list):
        if not data:
            return []
        return [_inspect_structure(data[0], max_depth, max_keys, current_depth + 1)]
    else:
        return type(data).__name__


def _infer_schema(
    content_bytes: bytes,
    mime_type: str,
    depth: int = 3,
    max_keys: int = DEFAULT_SCHEMA_MAX_KEYS,
) -> Dict[str, Any]:
    """
    Infers basic schema information for common text-based types.
    Args:
        content_bytes: The raw byte content.
        mime_type: The MIME type.
        depth: Maximum recursion depth for nested structures.
        max_keys: Maximum number of dictionary keys to inspect at each level.
    Returns:
        A dictionary representing the inferred schema, including an 'inferred' flag
        and potential 'error' field.
    """
    schema_info = {"type": mime_type, "inferred": False, "error": None}
    normalized_mime_type = mime_type.lower() if mime_type else ""
    try:
        if normalized_mime_type == "text/csv":
            try:
                text_content = io.TextIOWrapper(
                    io.BytesIO(content_bytes), encoding="utf-8"
                )
                reader = csv.reader(text_content)
                header = next(reader)
                schema_info["columns"] = header
                schema_info["inferred"] = True
            except (StopIteration, csv.Error, UnicodeDecodeError) as e:
                schema_info["error"] = f"CSV header inference failed: {e}"
        elif normalized_mime_type in ["application/json", "text/json"]:
            try:
                data = json.loads(content_bytes.decode("utf-8"))
                schema_info["structure"] = _inspect_structure(data, depth, max_keys)
                schema_info["inferred"] = True
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                schema_info["error"] = f"JSON structure inference failed: {e}"
        elif normalized_mime_type in [
            "application/yaml",
            "text/yaml",
            "application/x-yaml",
            "text/x-yaml",
        ]:
            try:
                data = yaml.safe_load(content_bytes)
                schema_info["structure"] = _inspect_structure(data, depth, max_keys)
                schema_info["inferred"] = True
            except (yaml.YAMLError, UnicodeDecodeError) as e:
                schema_info["error"] = f"YAML structure inference failed: {e}"
    except Exception as e:
        schema_info["error"] = f"Unexpected error during schema inference: {e}"
    if schema_info["error"]:
        log.warning(
            "Schema inference for mime_type '%s' encountered error: %s",
            mime_type,
            schema_info["error"],
        )
    elif not schema_info["inferred"]:
        log.debug(
            "No specific schema inference logic applied for mime_type '%s'.", mime_type
        )
    return schema_info


async def save_artifact_with_metadata(
    artifact_service: BaseArtifactService,
    app_name: str,
    user_id: str,
    session_id: str,
    filename: str,
    content_bytes: bytes,
    mime_type: str,
    metadata_dict: Dict[str, Any],
    timestamp: datetime,
    explicit_schema: Optional[Dict] = None,
    schema_inference_depth: Optional[int] = None,
    schema_max_keys: int = DEFAULT_SCHEMA_MAX_KEYS,
    tool_context: Optional["ToolContext"] = None,
    suppress_visualization_signal: bool = False,
) -> Dict[str, Any]:
    """
    Saves a data artifact and its corresponding metadata artifact using BaseArtifactService.
    """
    log_identifier = f"[ArtifactHelper:save:{filename}]"
    log.debug("%s Saving artifact and metadata (async)...", log_identifier)

    # Resolve schema_inference_depth from artifact service wrapper if not provided
    if schema_inference_depth is None:
        # Use duck typing to check for ScopedArtifactServiceWrapper capability
        # (avoids dynamic class loading issues with isinstance)
        if hasattr(artifact_service, "component") and hasattr(
            artifact_service.component, "get_config"
        ):
            schema_inference_depth = artifact_service.component.get_config(
                "schema_inference_depth", DEFAULT_SCHEMA_INFERENCE_DEPTH
            )
            log.debug(
                "%s Resolved schema_inference_depth from agent config: %d",
                log_identifier,
                schema_inference_depth,
            )
        else:
            schema_inference_depth = DEFAULT_SCHEMA_INFERENCE_DEPTH
            log.debug(
                "%s Using default schema_inference_depth: %d",
                log_identifier,
                schema_inference_depth,
            )

    data_version = None
    metadata_version = None
    metadata_filename = f"{filename}{METADATA_SUFFIX}"
    status = "error"
    status_message = "Initialization error"
    try:
        data_artifact_part = adk_types.Part.from_bytes(
            data=content_bytes, mime_type=mime_type
        )
        log.debug(
            f"{log_identifier} artifact_service object type: {type(artifact_service)}"
        )
        log.debug(
            f"{log_identifier} artifact_service object dir: {dir(artifact_service)}"
        )
        if hasattr(artifact_service, "save_artifact"):
            save_artifact_method = getattr(artifact_service, "save_artifact")
            log.debug(
                f"{log_identifier} type of artifact_service.save_artifact: {type(save_artifact_method)}"
            )
            log.debug(
                f"{log_identifier} Is save_artifact a coroutine function? {inspect.iscoroutinefunction(save_artifact_method)}"
            )
            log.debug(
                f"{log_identifier} Is save_artifact an async generator function? {inspect.isasyncgenfunction(save_artifact_method)}"
            )
            if callable(save_artifact_method):
                try:
                    sig = inspect.signature(save_artifact_method)
                    log.debug(f"{log_identifier} Signature of save_artifact: {sig}")
                except Exception as e_inspect:
                    log.debug(
                        f"{log_identifier} Could not get signature of save_artifact: {e_inspect}"
                    )
        save_data_method = getattr(artifact_service, "save_artifact")
        data_version = await save_data_method(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            artifact=data_artifact_part,
        )
        log.info(
            "%s Saved data artifact '%s' as version %s.",
            log_identifier,
            filename,
            data_version,
        )

        # Populate artifact_delta for ADK callbacks if tool_context is provided
        if (
            tool_context
            and hasattr(tool_context, "actions")
            and hasattr(tool_context.actions, "artifact_delta")
        ):
            tool_context.actions.artifact_delta[filename] = data_version
            log.debug(
                "%s Populated artifact_delta for ADK callbacks: %s -> %s",
                log_identifier,
                filename,
                data_version,
            )

        # Always attempt to publish artifact saved notification for workflow visualization
        # This works independently of artifact_delta and should succeed if we have
        # the necessary context (host_component and a2a_context)
        # Skip if suppress_visualization_signal is True (e.g., when called from fenced block callback)
        if not suppress_visualization_signal:
            try:
                # Try to get context from tool_context if available
                host_component = None
                a2a_context = None
                function_call_id = None

                if tool_context:
                    try:
                        inv_context = tool_context._invocation_context
                        agent = getattr(inv_context, "agent", None)
                        host_component = getattr(agent, "host_component", None)
                        a2a_context = tool_context.state.get("a2a_context")
                        # Get function_call_id if this was created by a tool
                        # Try state first (legacy), then the ADK attribute
                        function_call_id = tool_context.state.get("function_call_id") or getattr(tool_context, "function_call_id", None)
                    except Exception as ctx_err:
                        log.info(
                            "%s Could not extract context from tool_context: %s",
                            log_identifier,
                            ctx_err,
                        )

                # Only proceed if we have both required components
                if host_component and a2a_context:
                    # Create ArtifactInfo object
                    artifact_info = ArtifactInfo(
                        filename=filename,
                        version=data_version,
                        mime_type=mime_type,
                        size=len(content_bytes),
                        description=metadata_dict.get("description") if metadata_dict else None,
                        version_count=None,  # Count not available in save context
                    )

                    # Publish artifact saved notification via component method
                    await host_component.notify_artifact_saved(
                        artifact_info=artifact_info,
                        a2a_context=a2a_context,
                        function_call_id=function_call_id,
                    )
            except Exception as signal_err:
                # Don't fail artifact save if notification publishing fails
                log.warning(
                    "%s Failed to publish artifact saved notification (non-critical): %s",
                    log_identifier,
                    signal_err,
                )

        final_metadata = {
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": len(content_bytes),
            "timestamp_utc": (
                timestamp
                if isinstance(timestamp, (int, float))
                else timestamp.timestamp()
            ),
            **(metadata_dict or {}),
        }
        if explicit_schema:
            final_metadata["schema"] = {
                "type": mime_type,
                "inferred": False,
                **explicit_schema,
            }
            log.debug("%s Using explicit schema provided by caller.", log_identifier)
        else:
            inferred_schema = _infer_schema(
                content_bytes, mime_type, schema_inference_depth, schema_max_keys
            )
            final_metadata["schema"] = inferred_schema
            if inferred_schema.get("inferred"):
                log.debug(
                    "%s Added inferred schema (max_keys=%d).",
                    log_identifier,
                    schema_max_keys,
                )
            elif inferred_schema.get("error"):
                log.warning(
                    "%s Schema inference failed: %s",
                    log_identifier,
                    inferred_schema["error"],
                )
        try:
            metadata_bytes = json.dumps(final_metadata, indent=2).encode("utf-8")
            metadata_artifact_part = adk_types.Part.from_bytes(
                data=metadata_bytes, mime_type="application/json"
            )
            save_metadata_method = getattr(artifact_service, "save_artifact")
            metadata_version = await save_metadata_method(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=metadata_filename,
                artifact=metadata_artifact_part,
            )
            log.info(
                "%s Saved metadata artifact '%s' as version %s.",
                log_identifier,
                metadata_filename,
                metadata_version,
            )
            status = "success"
            status_message = "Artifact and metadata saved successfully."
        except Exception as meta_save_err:
            log.exception(
                "%s Failed to save metadata artifact '%s': %s",
                log_identifier,
                metadata_filename,
                meta_save_err,
            )
            status = "partial_success"
            status_message = f"Data artifact saved (v{data_version}), but failed to save metadata: {meta_save_err}"
    except Exception as data_save_err:
        log.exception(
            "%s Failed to save data artifact '%s': %s",
            log_identifier,
            filename,
            data_save_err,
        )
        status = "error"
        status_message = f"Failed to save data artifact: {data_save_err}"
    return {
        "status": status,
        "data_filename": filename,
        "data_version": data_version,
        "metadata_filename": metadata_filename,
        "metadata_version": metadata_version,
        "message": status_message,
    }


async def process_artifact_upload(
    artifact_service: BaseArtifactService,
    component: Any,
    user_id: str,
    session_id: str,
    filename: str,
    content_bytes: bytes,
    mime_type: str,
    metadata_json: Optional[str] = None,
    log_prefix: str = "[ArtifactUpload]",
) -> Dict[str, Any]:
    """
    Common logic for processing artifact uploads.

    Handles filename validation, metadata parsing, artifact storage, and URI generation.

    Args:
        artifact_service: The artifact service instance to use for storage.
        component: The component instance (agent or gateway) for configuration.
        user_id: The user ID associated with the artifact.
        session_id: The session ID associated with the artifact.
        filename: The name of the artifact file.
        content_bytes: The raw bytes of the artifact content.
        mime_type: The MIME type of the artifact.
        metadata_json: Optional JSON string containing artifact metadata.
        log_prefix: Prefix for log messages.

    Returns:
        Dict with keys:
            - status: "success" or "error"
            - artifact_uri: The URI of the stored artifact (on success)
            - version: The version number of the stored artifact (on success)
            - message: Status message
            - error: Error details (on error)
    """
    log.debug("%s Processing artifact upload for '%s'", log_prefix, filename)

    # Validate filename
    if not is_filename_safe(filename):
        error_msg = f"Invalid filename: '{filename}'. Filename must not contain path separators or traversal sequences."
        log.warning("%s %s", log_prefix, error_msg)
        return {"status": "error", "message": error_msg, "error": "invalid_filename"}

    # Validate content
    if not content_bytes:
        error_msg = "Uploaded file cannot be empty."
        log.warning("%s %s", log_prefix, error_msg)
        return {"status": "error", "message": error_msg, "error": "empty_file"}

    # Parse metadata JSON if provided
    metadata_dict = {}
    if metadata_json and metadata_json.strip():
        try:
            metadata_dict = json.loads(metadata_json.strip())
            if not isinstance(metadata_dict, dict):
                log.warning(
                    "%s Metadata JSON did not parse to a dictionary. Ignoring.",
                    log_prefix,
                )
                metadata_dict = {}
        except json.JSONDecodeError as json_err:
            log.warning(
                "%s Failed to parse metadata_json: %s. Proceeding without it.",
                log_prefix,
                json_err,
            )
            metadata_dict = {}

    # Get app_name from component configuration
    app_name = component.get_config("name", "A2A_WebUI_App")
    current_timestamp = datetime.now(timezone.utc)

    # Save artifact with metadata
    try:
        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            content_bytes=content_bytes,
            mime_type=mime_type,
            metadata_dict=metadata_dict,
            timestamp=current_timestamp,
            schema_max_keys=component.get_config(
                "schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS
            ),
        )

        if save_result["status"] == "success":
            saved_version = save_result.get("data_version")
            artifact_uri = format_artifact_uri(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename,
                version=saved_version,
            )

            log.info(
                "%s Artifact '%s' uploaded successfully. URI: %s, Version: %s",
                log_prefix,
                filename,
                artifact_uri,
                saved_version,
            )

            return {
                "status": "success",
                "artifact_uri": artifact_uri,
                "version": saved_version,
                "message": save_result.get(
                    "message", "Artifact uploaded successfully."
                ),
                "data_version": saved_version,
                "metadata_version": save_result.get("metadata_version"),
            }
        else:
            error_msg = save_result.get("message", "Failed to save artifact.")
            log.error("%s %s", log_prefix, error_msg)
            return {"status": "error", "message": error_msg, "error": "save_failed"}

    except Exception as e:
        error_msg = f"Unexpected error storing artifact: {str(e)}"
        log.exception("%s %s", log_prefix, error_msg)
        return {"status": "error", "message": error_msg, "error": "unexpected_error"}


def format_metadata_for_llm(metadata: Dict[str, Any]) -> str:
    """Formats loaded metadata into an LLM-friendly text block."""
    lines = []
    filename = metadata.get("filename", "Unknown Filename")
    version = metadata.get("version", "N/A")
    lines.append(f"--- Metadata for artifact '{filename}' (v{version}) ---")
    lines.append("**Artifact Metadata:**")
    if "description" in metadata:
        lines.append(f"*   **Description:** {metadata['description']}")
    if "source" in metadata:
        lines.append(f"*   **Source:** {metadata['source']}")
    if "mime_type" in metadata:
        lines.append(f"*   **Type:** {metadata['mime_type']}")
    if "size_bytes" in metadata:
        lines.append(f"*   **Size:** {metadata['size_bytes']} bytes")
    schema = metadata.get("schema", {})
    schema_type = schema.get("type", metadata.get("mime_type", "unknown"))
    schema_details = []
    if schema.get("inferred"):
        schema_details.append("(Inferred)")
    if "columns" in schema:
        schema_details.append(f"Columns: {','.join(schema['columns'])}")
    if "structure" in schema:
        schema_details.append(f"Structure: {json.dumps(schema['structure'])}")
    if schema.get("error"):
        schema_details.append(f"Schema Error: {schema['error']}")
    if schema_details:
        lines.append(f"*   **Schema:** {schema_type} {' '.join(schema_details)}")
    elif schema_type != "unknown":
        lines.append(f"*   **Schema Type:** {schema_type}")
    custom_fields = {
        k: v
        for k, v in metadata.items()
        if k
        not in [
            "filename",
            "mime_type",
            "size_bytes",
            "timestamp_utc",
            "schema",
            "version",
            "description",
            "source",
        ]
    }
    if custom_fields:
        lines.append("*   **Other:**")
        for k, v in custom_fields.items():
            lines.append(f"    *   {k}: {v}")
    lines.append("--- End Metadata ---")
    return "\n".join(lines)


async def generate_artifact_metadata_summary(
    component: "SamAgentComponent",
    artifact_identifiers: List[Dict[str, Any]],
    user_id: str,
    session_id: str,
    app_name: str,
    header_text: Optional[str] = None,
) -> str:
    """
    Loads metadata for a list of artifacts and formats it into a human-readable
    YAML summary string, suitable for LLM context.
    """
    if not artifact_identifiers:
        return ""

    log_identifier = f"{component.log_identifier}[ArtifactSummary]"
    summary_parts = []
    if header_text:
        summary_parts.append(header_text)

    if not (component.artifact_service and user_id and session_id):
        log.warning(
            "%s Cannot load artifact metadata: missing artifact_service or context.",
            log_identifier,
        )
        for artifact_ref in artifact_identifiers:
            filename = artifact_ref.get("filename", "unknown")
            version = artifact_ref.get("version", "latest")
            summary_parts.append(
                f"---\nArtifact: '{filename}' (version: {version})\nError: Could not load metadata. Host component context missing."
            )
        return "\n\n".join(summary_parts)

    for artifact_ref in artifact_identifiers:
        filename = artifact_ref.get("filename")
        version = artifact_ref.get("version", "latest")
        if not filename:
            log.warning(
                "%s Skipping artifact with no filename in identifier: %s",
                log_identifier,
                artifact_ref,
            )
            continue

        try:
            metadata_result = await load_artifact_content_or_metadata(
                artifact_service=component.artifact_service,
                app_name=app_name,
                user_id=user_id,
                session_id=get_original_session_id(session_id),
                filename=filename,
                version=version,
                load_metadata_only=True,
            )
            if metadata_result.get("status") == "success":
                metadata = metadata_result.get("metadata", {})
                resolved_version = metadata_result.get("version", version)
                artifact_header = (
                    f"Artifact: '{filename}' (version: {resolved_version})"
                )

                # Remove redundant fields before dumping to YAML
                metadata.pop("filename", None)
                metadata.pop("version", None)

                # Clean metadata to remove null/false/empty values for token efficiency
                cleaned_metadata = _clean_metadata_for_output(metadata)

                TRUNCATION_LIMIT_BYTES = 1024
                TRUNCATION_MESSAGE = "\n... [truncated] ..."

                try:
                    formatted_metadata_str = yaml.safe_dump(
                        cleaned_metadata,
                        default_flow_style=False,
                        sort_keys=False,
                        allow_unicode=True,
                    )

                    if (
                        len(formatted_metadata_str.encode("utf-8"))
                        > TRUNCATION_LIMIT_BYTES
                    ):
                        cutoff = TRUNCATION_LIMIT_BYTES - len(
                            TRUNCATION_MESSAGE.encode("utf-8")
                        )
                        # Ensure we don't cut in the middle of a multi-byte character
                        encoded_str = formatted_metadata_str.encode("utf-8")
                        if cutoff > 0:
                            truncated_encoded = encoded_str[:cutoff]
                            formatted_metadata_str = (
                                truncated_encoded.decode("utf-8", "ignore")
                                + TRUNCATION_MESSAGE
                            )
                        else:
                            formatted_metadata_str = TRUNCATION_MESSAGE

                    summary_parts.append(
                        f"---\n{artifact_header}\n{formatted_metadata_str}"
                    )
                except Exception as e_format:
                    log.error(
                        "%s Error formatting metadata for %s v%s: %s",
                        log_identifier,
                        filename,
                        version,
                        e_format,
                    )
                    summary_parts.append(
                        f"---\n{artifact_header}\nError: Could not format metadata."
                    )
            else:
                error_message = metadata_result.get(
                    "message", "Could not load metadata."
                )
                log.warning(
                    "%s Failed to load metadata for %s v%s: %s",
                    log_identifier,
                    filename,
                    version,
                    error_message,
                )
                artifact_header = f"Artifact: '{filename}' (version: {version})"
                summary_parts.append(f"---\n{artifact_header}\nError: {error_message}")
        except Exception as e_meta:
            log.error(
                "%s Unexpected error loading metadata for %s v%s: %s",
                log_identifier,
                filename,
                version,
                e_meta,
            )
            artifact_header = f"Artifact: '{filename}' (version: {version})"
            summary_parts.append(
                f"---\n{artifact_header}\nError: An unexpected error occurred while loading metadata."
            )

    return "\n\n".join(summary_parts)


def decode_and_get_bytes(
    content_str: str, mime_type: str, log_identifier: str
) -> Tuple[bytes, str]:
    """
    Decodes content if necessary (based on mime_type) and returns bytes and final mime_type.
    Args:
        content_str: The input content string (potentially base64).
        mime_type: The provided MIME type.
        log_identifier: Identifier for logging.
    Returns:
        A tuple containing (content_bytes, final_mime_type).
    """
    file_bytes: bytes
    final_mime_type = mime_type
    normalized_mime_type = mime_type.lower() if mime_type else ""
    if is_text_based_mime_type(normalized_mime_type):
        file_bytes = content_str.encode("utf-8")
        log.debug(
            "%s Encoded text content for text mimeType '%s'.",
            log_identifier,
            mime_type,
        )
    else:
        try:
            file_bytes = base64.b64decode(content_str, validate=True)
            log.debug(
                "%s Decoded base64 content for non-text mimeType '%s'.",
                log_identifier,
                mime_type,
            )
        except (binascii.Error, ValueError) as decode_error:
            log.warning(
                "%s Failed to base64 decode content for mimeType '%s'. Treating as text/plain. Error: %s",
                log_identifier,
                mime_type,
                decode_error,
            )
            file_bytes = content_str.encode("utf-8")
            final_mime_type = "text/plain"
    return file_bytes, final_mime_type


async def get_latest_artifact_version(
    artifact_service: BaseArtifactService,
    app_name: str,
    user_id: str,
    session_id: str,
    filename: str,
) -> Optional[int]:
    """
    Retrieves the latest version number for a given artifact.

    Args:
        artifact_service: The artifact service instance.
        app_name: The application name.
        user_id: The user ID.
        session_id: The session ID.
        filename: The name of the artifact.

    Returns:
        The latest version number as an integer, or None if no versions exist.
    """
    log_identifier = f"[ArtifactHelper:get_latest_version:{filename}]"
    try:
        if not hasattr(artifact_service, "list_versions"):
            log.warning(
                "%s Artifact service does not support 'list_versions'.", log_identifier
            )
            return None

        versions = await artifact_service.list_versions(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
        )
        if not versions:
            log.debug("%s No versions found for artifact.", log_identifier)
            return None

        latest_version = max(versions)
        log.debug("%s Resolved latest version to %d.", log_identifier, latest_version)
        return latest_version
    except Exception as e:
        log.error("%s Error resolving latest version: %s", log_identifier, e)
        return None


async def get_artifact_counts_batch(
    artifact_service: BaseArtifactService,
    app_name: str,
    user_id: str,
    session_ids: List[str],
) -> Dict[str, int]:
    """
    Get artifact counts for multiple sessions in a batch operation.
    
    Args:
        artifact_service: The artifact service instance.
        app_name: The application name.
        user_id: The user ID.
        session_ids: List of session IDs to get counts for.
    
    Returns:
        Dict mapping session_id to artifact_count (excluding metadata files)
    """
    log_prefix = f"[ArtifactHelper:get_counts_batch] App={app_name}, User={user_id} -"
    counts: Dict[str, int] = {}
    
    try:
        list_keys_method = getattr(artifact_service, "list_artifact_keys")
        
        for session_id in session_ids:
            try:
                keys = await list_keys_method(
                    app_name=app_name, user_id=user_id, session_id=session_id
                )
                # Count only non-metadata files
                count = sum(1 for key in keys if not key.endswith(METADATA_SUFFIX))
                counts[session_id] = count
                log.debug("%s Session %s has %d artifacts", log_prefix, session_id, count)
            except Exception as e:
                log.warning("%s Failed to get count for session %s: %s", log_prefix, session_id, e)
                counts[session_id] = 0
                
    except Exception as e:
        log.exception("%s Error in batch count operation: %s", log_prefix, e)
        # Return 0 for all sessions on error
        return {session_id: 0 for session_id in session_ids}
    
    return counts


async def get_artifact_info_list(
    artifact_service: BaseArtifactService,
    app_name: str,
    user_id: str,
    session_id: str,
) -> List[ArtifactInfo]:
    """
    Retrieves detailed information for all artifacts using the artifact service.

    Args:
        artifact_service: The artifact service instance.
        app_name: The application name.
        user_id: The user ID.
        session_id: The session ID.

    Returns:
        A list of ArtifactInfo objects.
    """
    log_prefix = f"[ArtifactHelper:get_info_list] App={app_name}, User={user_id}, Session={session_id} -"
    artifact_info_list: List[ArtifactInfo] = []

    try:
        list_keys_method = getattr(artifact_service, "list_artifact_keys")
        keys = await list_keys_method(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        log.debug(
            "%s Found %d artifact keys. Fetching details...", log_prefix, len(keys)
        )

        for filename in keys:
            if filename.endswith(METADATA_SUFFIX):
                continue

            log_identifier_item = f"{log_prefix} [{filename}]"
            try:

                version_count: int = 0
                latest_version_num: Optional[int] = await get_latest_artifact_version(
                    artifact_service, app_name, user_id, session_id, filename
                )

                if hasattr(artifact_service, "list_versions"):
                    try:
                        available_versions = await artifact_service.list_versions(
                            app_name=app_name,
                            user_id=user_id,
                            session_id=session_id,
                            filename=filename,
                        )
                        version_count = len(available_versions)
                    except Exception as list_ver_err:
                        log.error(
                            "%s Error listing versions for count: %s.",
                            log_identifier_item,
                            list_ver_err,
                        )

                data = await load_artifact_content_or_metadata(
                    artifact_service=artifact_service,
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename,
                    version="latest",
                    load_metadata_only=True,
                    log_identifier_prefix=log_identifier_item,
                )

                metadata = data.get("metadata", {})
                mime_type = metadata.get("mime_type", "application/data")
                size = metadata.get("size_bytes", 0)
                schema_definition = metadata.get("schema", {})
                description = metadata.get("description", "No description provided")
                loaded_version_num = data.get("version", latest_version_num)

                last_modified_ts = metadata.get("timestamp_utc")
                last_modified_ts = metadata.get("timestamp_utc")
                last_modified_iso = (
                    datetime.fromtimestamp(
                        last_modified_ts, tz=timezone.utc
                    ).isoformat()
                    if last_modified_ts
                    else None
                )

                # Extract source from metadata
                source = metadata.get("source")
                
                artifact_info_list.append(
                    ArtifactInfo(
                        filename=filename,
                        mime_type=mime_type,
                        size=size,
                        last_modified=last_modified_iso,
                        schema_definition=schema_definition,
                        description=description,
                        version=loaded_version_num,
                        version_count=version_count,
                        source=source,
                    )
                )
                log.debug(
                    "%s Successfully processed artifact info.", log_identifier_item
                )

            except FileNotFoundError:
                log.warning(
                    "%s Artifact file not found by service for key '%s'. Skipping.",
                    log_prefix,
                    filename,
                )
            except Exception as detail_e:
                log.error(
                    "%s Error processing details for artifact '%s': %s\n%s",
                    log_prefix,
                    filename,
                    detail_e,
                    traceback.format_exc(),
                )
                artifact_info_list.append(
                    ArtifactInfo(
                        filename=filename,
                        size=0,
                        description=f"Error loading details: {detail_e}",
                        mime_type="application/octet-stream",
                    )
                )

    except Exception as e:
        log.exception(
            "%s Error listing artifact keys or processing list: %s", log_prefix, e
        )
        return []
    return artifact_info_list


async def load_artifact_content_or_metadata(
    artifact_service: BaseArtifactService,
    app_name: str,
    user_id: str,
    session_id: str,
    filename: str,
    version: Union[int, str],
    load_metadata_only: bool = False,
    return_raw_bytes: bool = False,
    max_content_length: Optional[int] = None,
    include_line_numbers: bool = False,
    component: Optional[Any] = None,
    log_identifier_prefix: str = "[ArtifactHelper:load]",
    encoding: str = "utf-8",
    error_handling: str = "strict",
) -> Dict[str, Any]:
    """
    Loads the content or metadata of a specific artifact version using the artifact service.
    """
    log_identifier_req = f"{log_identifier_prefix}:{filename}:{version}"
    log.debug(
        "%s Processing request (load_metadata_only=%s, return_raw_bytes=%s) (async).",
        log_identifier_req,
        load_metadata_only,
        return_raw_bytes,
    )

    if max_content_length is None and component:
        max_content_length = component.get_config("text_artifact_content_max_length")
        if max_content_length is None:
            raise ValueError(
                f"{log_identifier_req} Component config 'text_artifact_content_max_length' is not set."
            )

        if max_content_length < 100:
            log.warning(
                "%s text_artifact_content_max_length too small (%d), using minimum: 100",
                log_identifier_req,
                max_content_length,
            )
            max_content_length = 100
        elif max_content_length > TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY:
            log.warning(
                "%s text_artifact_content_max_length too large (%d), using maximum: %d",
                log_identifier_req,
                max_content_length,
                TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY,
            )
            max_content_length = TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY
    elif max_content_length is None:
        max_content_length = TEXT_ARTIFACT_CONTEXT_DEFAULT_LENGTH

    log.debug(
        "%s Using max_content_length: %d characters (from %s).",
        log_identifier_req,
        max_content_length,
        "app config" if component else "default",
    )

    try:
        actual_version: int
        if isinstance(version, str) and version.lower() == "latest":
            log.debug(
                "%s Requested version is 'latest', resolving...", log_identifier_req
            )
            try:
                list_versions_method = getattr(artifact_service, "list_versions")
                # Use metadata filename when loading metadata, content filename otherwise
                version_check_filename = f"{filename}{METADATA_SUFFIX}" if load_metadata_only else filename
                available_versions = await list_versions_method(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=version_check_filename,
                )
                if not available_versions:
                    raise FileNotFoundError(
                        f"Artifact '{filename}' has no versions available to determine 'latest'."
                    )
                actual_version = max(available_versions)
                log.info(
                    "%s Resolved 'latest' to version %d.",
                    log_identifier_req,
                    actual_version,
                )
            except Exception as list_err:
                log.error(
                    "%s Failed to list versions for '%s' to resolve 'latest': %s",
                    log_identifier_req,
                    filename,
                    list_err,
                )
                raise FileNotFoundError(
                    f"Could not determine latest version for '{filename}': {list_err}"
                ) from list_err
        elif isinstance(version, int):
            actual_version = version
        elif isinstance(version, str):
            try:
                actual_version = int(version)
            except ValueError:
                raise ValueError(
                    f"Invalid version specified: '{version}'. Must be a positive integer string or 'latest'."
                )
        else:
            raise ValueError(
                f"Invalid version type: '{type(version).__name__}'. Must be an integer or 'latest'."
            )

        if actual_version < 0:
            raise ValueError(
                f"Version number must be a positive integer. Got: {actual_version}"
            )

        target_filename = (
            f"{filename}{METADATA_SUFFIX}" if load_metadata_only else filename
        )
        version_to_load = actual_version

        log_identifier = f"{log_identifier_prefix}:{filename}:v{version_to_load}"

        log.debug(
            "%s Attempting to load '%s' v%d (async)",
            log_identifier,
            target_filename,
            version_to_load,
        )

        load_artifact_method = getattr(artifact_service, "load_artifact")
        artifact_part = await load_artifact_method(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=target_filename,
            version=version_to_load,
        )

        if not artifact_part or not artifact_part.inline_data:
            raise FileNotFoundError(
                f"Artifact '{target_filename}' version {version_to_load} not found or has no data."
            )

        mime_type = artifact_part.inline_data.mime_type
        data_bytes = artifact_part.inline_data.data
        size_bytes = len(data_bytes)

        if load_metadata_only:
            if mime_type != "application/json":
                log.warning(
                    "%s Expected metadata file '%s' v%d to be application/json, but got '%s'. Attempting parse anyway.",
                    log_identifier,
                    target_filename,
                    version_to_load,
                    mime_type,
                )
            try:
                metadata_dict = json.loads(data_bytes.decode("utf-8"))
                log.info(
                    "%s Successfully loaded and parsed metadata for '%s' v%d.",
                    log_identifier,
                    filename,
                    version_to_load,
                )
                return {
                    "status": "success",
                    "filename": filename,
                    "version": version_to_load,
                    "metadata": metadata_dict,
                }

            except (json.JSONDecodeError, UnicodeDecodeError) as parse_err:
                raise ValueError(
                    f"Failed to parse metadata file '{target_filename}' v{version_to_load}: {parse_err}"
                ) from parse_err

        else:
            if return_raw_bytes:
                log.info(
                    "%s Loaded artifact '%s' v%d (%d bytes, type: %s). Returning raw_bytes.",
                    log_identifier,
                    filename,
                    version_to_load,
                    size_bytes,
                    mime_type,
                )
                return {
                    "status": "success",
                    "filename": filename,
                    "version": version_to_load,
                    "mime_type": mime_type,
                    "raw_bytes": data_bytes,
                    "size_bytes": size_bytes,
                }
            else:
                is_text = is_text_based_file(mime_type, data_bytes)

                if is_text:
                    # Try multiple encodings with fallback for Windows-exported files
                    # Common case: CSV files exported from Excel on Windows use CP1252
                    content_str = None
                    used_encoding = None
                    encodings_to_try = [encoding, "utf-16", "cp1252", "latin-1"]
                    decode_errors = []
                    
                    for enc in encodings_to_try:
                        try:
                            content_str = data_bytes.decode(enc, errors=error_handling)
                            used_encoding = enc
                            if enc != encoding:
                                log.info(
                                    "%s Successfully decoded text artifact '%s' v%d using fallback encoding '%s' (primary '%s' failed)",
                                    log_identifier,
                                    filename,
                                    version_to_load,
                                    enc,
                                    encoding,
                                )
                            break
                        except UnicodeDecodeError as e:
                            decode_errors.append(f"{enc}: {e}")
                            continue
                    
                    if content_str is None:
                        # All encodings failed
                        log.error(
                            "%s Failed to decode text artifact '%s' v%d with any encoding. Errors: %s",
                            log_identifier,
                            filename,
                            version_to_load,
                            "; ".join(decode_errors),
                        )
                        raise ValueError(
                            f"Failed to decode artifact '{filename}' v{version_to_load}. Tried encodings: {', '.join(encodings_to_try)}"
                        )
                    
                    original_content_str = content_str  # Save for line count calculation

                    # Add line numbers if requested (before truncation)
                    if include_line_numbers:
                        lines = content_str.split('\n')
                        numbered_lines = [f"{i+1}\t{line}" for i, line in enumerate(lines)]
                        content_str = '\n'.join(numbered_lines)
                        log.debug(
                            "%s Added line numbers to %d lines.",
                            log_identifier,
                            len(lines)
                        )

                    message_to_llm = ""
                    if len(content_str) > max_content_length:
                        truncated_content = content_str[:max_content_length] + "..."

                        # Calculate line range if line numbers are included
                        line_range_msg = ""
                        if include_line_numbers:
                            visible_line_count = truncated_content.count('\n') + 1
                            total_line_count = original_content_str.count('\n') + 1
                            line_range_msg = f" Lines 1-{visible_line_count} of {total_line_count} total."

                        if (
                            max_content_length
                            < TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY
                        ):
                            message_to_llm = f"""This artifact content has been truncated to {max_content_length} characters.{line_range_msg}
                                            The artifact is larger ({len(content_str)} characters).
                                            Please request again with larger max size up to {TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY} for the full artifact."""
                        else:
                            message_to_llm = f"""This artifact content has been truncated to {max_content_length} characters.{line_range_msg}
                                            The artifact content met the maximum allowed size of {TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY} characters.
                                            Please continue with this truncated content as the full artifact cannot be provided."""
                        log.info(
                            "%s Loaded and decoded text artifact '%s' v%d. Returning truncated content (%d chars, limit: %d).%s",
                            log_identifier,
                            filename,
                            version_to_load,
                            len(truncated_content),
                            max_content_length,
                            line_range_msg,
                        )
                    else:
                        truncated_content = content_str
                        log.info(
                            "%s Loaded and decoded text artifact '%s' v%d. Returning full content (%d chars).",
                            log_identifier,
                            filename,
                            version_to_load,
                            len(content_str),
                        )
                    return {
                        "status": "success",
                        "filename": filename,
                        "version": version_to_load,
                        "mime_type": mime_type,
                        "content": truncated_content,
                        "message_to_llm": message_to_llm,
                        "size_bytes": size_bytes,
                    }
                else:
                    log.info(
                        "%s Loaded binary/unknown artifact '%s' v%d. Returning metadata summary.",
                        log_identifier,
                        filename,
                        version_to_load,
                    )

                    metadata_for_binary = {}
                    if not filename.endswith(METADATA_SUFFIX):
                        try:
                            metadata_filename_for_binary = (
                                f"{filename}{METADATA_SUFFIX}"
                            )
                            log.debug(
                                "%s Attempting to load linked metadata file '%s' for binary artifact '%s' v%d.",
                                log_identifier,
                                metadata_filename_for_binary,
                                filename,
                                version_to_load,
                            )
                            metadata_data = await load_artifact_content_or_metadata(
                                artifact_service=artifact_service,
                                app_name=app_name,
                                user_id=user_id,
                                session_id=session_id,
                                filename=f"{filename}{METADATA_SUFFIX}",
                                version=version,
                                load_metadata_only=True,
                                log_identifier_prefix=f"{log_identifier}[meta_for_binary]",
                            )
                            if metadata_data.get("status") == "success":
                                metadata_for_binary = metadata_data.get("metadata", {})
                        except Exception as e_meta_bin:
                            log.warning(
                                f"{log_identifier} Could not load metadata for binary artifact {filename}: {e_meta_bin}"
                            )
                            metadata_for_binary = {
                                "error": f"Could not load metadata: {e_meta_bin}"
                            }

                    return {
                        "status": "success",
                        "filename": filename,
                        "version": version_to_load,
                        "mime_type": mime_type,
                        "size_bytes": size_bytes,
                        "metadata": metadata_for_binary,
                        "content": f"Binary data of type {mime_type}. Content not displayed.",
                    }

    except FileNotFoundError as fnf_err:
        log.warning("%s Artifact not found: %s", log_identifier_req, fnf_err)
        return {"status": "not_found", "message": str(fnf_err)}
    except ValueError as val_err:
        log.error(
            "%s Value error during artifact load: %s", log_identifier_req, val_err
        )
        return {"status": "error", "message": str(val_err)}
    except Exception as e:
        log.exception(
            "%s Unexpected error loading artifact '%s' version '%s': %s",
            log_identifier_req,
            filename,
            version,
            e,
        )
        return {
            "status": "error",
            "message": f"Unexpected error loading artifact: {e}",
        }
