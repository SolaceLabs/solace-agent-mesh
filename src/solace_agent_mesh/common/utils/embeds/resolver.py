"""
Contains the main embed resolution functions, including the chain executor.
"""

import logging
import asyncio
import json
import uuid
from typing import Any, Callable, Dict, Optional, Set, Tuple, List, Union
from .constants import (
    EMBED_REGEX,
    EMBED_DELIMITER_OPEN,
    EMBED_DELIMITER_CLOSE,
    EARLY_EMBED_TYPES,
    LATE_EMBED_TYPES,
)
from .evaluators import EMBED_EVALUATORS, _evaluate_artifact_content_embed
from .modifiers import MODIFIER_DEFINITIONS, _parse_modifier_chain
from .converter import (
    convert_data,
    serialize_data,
    _parse_string_to_list_of_dicts,
)
from .types import DataFormat, ResolutionMode
from ..mime_helpers import is_text_based_mime_type

log = logging.getLogger(__name__)

import yaml


def _log_data_state(
    log_id: str,
    step: str,
    data: Any,
    data_format: Optional[DataFormat],
    mime_type: Optional[str],
):
    """Logs the state of the data at a specific step."""
    data_type = type(data).__name__
    data_size = "N/A"
    data_preview = "N/A"

    if isinstance(data, (bytes, str, list)):
        data_size = str(len(data))
    elif isinstance(data, dict):
        data_size = f"{len(data)} keys"

    if isinstance(data, bytes):
        try:
            data_preview = data[:100].decode("utf-8", errors="replace") + (
                "..." if len(data) > 100 else ""
            )
        except Exception:
            data_preview = f"Bytes[{len(data)}]"
    elif isinstance(data, str):
        data_preview = data[:100] + ("..." if len(data) > 100 else "")
    elif isinstance(data, list):
        data_preview = f"List[{len(data)} items]"
        if data and isinstance(data[0], dict):
            data_preview += f" (First item keys: {list(data[0].keys())[:5]}{'...' if len(data[0].keys()) > 5 else ''})"
    elif isinstance(data, dict):
        data_preview = f"Dict[{len(data)} keys: {list(data.keys())[:5]}{'...' if len(data.keys()) > 5 else ''}]"
    else:
        data_preview = str(data)[:100] + ("..." if len(str(data)) > 100 else "")

    log.info(
        "%s [%s] Format: %s, MimeType: %s, Type: %s, Size: %s, Preview: '%s'",
        log_id,
        step,
        data_format.name if data_format else "None",
        mime_type,
        data_type,
        data_size,
        data_preview,
    )


async def _evaluate_artifact_content_embed_with_chain(
    artifact_spec_from_directive: str,
    modifiers_from_directive: List[Tuple[str, str]],
    output_format_from_directive: Optional[str],
    context: Any,
    log_identifier: str,
    resolution_mode: "ResolutionMode",
    config: Optional[Dict] = None,
    current_depth: int = 0,
    visited_artifacts: Optional[Set[Tuple[str, int]]] = None,
) -> Union[Tuple[str, Optional[str], int], Tuple[None, str, Any]]:
    """
    Loads artifact content, recursively resolves its internal embeds if text-based,
    applies a chain of modifiers, and serializes the final result.
    """
    log.info(
        "%s [Depth:%d] Starting chain execution for artifact directive: %s",
        log_identifier,
        current_depth,
        artifact_spec_from_directive,
    )
    visited_artifacts = visited_artifacts or set()
    parsed_artifact_spec = artifact_spec_from_directive

    loaded_content_bytes, original_mime_type, load_error = (
        await _evaluate_artifact_content_embed(
            parsed_artifact_spec, context, log_identifier, config
        )
    )

    if load_error:
        log.warning(
            "%s [Depth:%d] Error loading initial artifact '%s': %s",
            log_identifier,
            current_depth,
            parsed_artifact_spec,
            load_error,
        )
        err_str = f"[Error loading artifact '{parsed_artifact_spec}': {load_error}]"
        return err_str, load_error, len(err_str.encode("utf-8"))

    if loaded_content_bytes is None:
        err_msg = f"Internal error - Artifact load for '{parsed_artifact_spec}' returned None content without error."
        log.error("%s %s", log_identifier, err_msg)
        return f"[Error: {err_msg}]", err_msg, 0

    current_data: Any = loaded_content_bytes
    current_format: DataFormat = DataFormat.BYTES
    _log_data_state(
        log_identifier,
        f"[Depth:{current_depth}] Initial Load",
        current_data,
        current_format,
        original_mime_type,
    )
    if is_text_based_mime_type(original_mime_type):
        try:
            decoded_content = loaded_content_bytes.decode("utf-8")
            log.debug(
                "%s [Depth:%d] Artifact '%s' is text-based (%s). Attempting recursive embed resolution.",
                log_identifier,
                current_depth,
                parsed_artifact_spec,
                original_mime_type,
            )
            spec_parts = parsed_artifact_spec.split(":", 1)
            filename_for_key = spec_parts[0]
            version_str_for_key = spec_parts[1] if len(spec_parts) > 1 else None
            try:
                version_for_key = (
                    int(version_str_for_key) if version_str_for_key else -1
                )
            except ValueError:
                log.warning(
                    "%s Could not parse version from '%s' for visited_artifacts key. Loop detection might be affected.",
                    log_identifier,
                    parsed_artifact_spec,
                )
                version_for_key = -1

            artifact_key = (filename_for_key, version_for_key)
            new_visited_artifacts = visited_artifacts.copy()
            new_visited_artifacts.add(artifact_key)

            resolved_string_content = await resolve_embeds_recursively_in_string(
                text=decoded_content,
                context=context,
                resolver_func=evaluate_embed,
                types_to_resolve=EARLY_EMBED_TYPES.union(LATE_EMBED_TYPES),
                resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT,
                log_identifier=log_identifier,
                config=config,
                max_depth=config.get("gateway_recursive_embed_depth", 12),
                current_depth=current_depth + 1,
                visited_artifacts=new_visited_artifacts,
                accumulated_size=0,
                max_total_size=config.get(
                    "gateway_max_artifact_resolve_size_bytes", -1
                ),
            )
            current_data = resolved_string_content
            current_format = DataFormat.STRING
            _log_data_state(
                log_identifier,
                f"[Depth:{current_depth}] After Recursive Resolution (including templates)",
                current_data,
                current_format,
                original_mime_type,
            )

        except UnicodeDecodeError as ude:
            err_msg = f"Failed to decode text-based artifact '{parsed_artifact_spec}' for recursion: {ude}"
            log.warning("%s %s", log_identifier, err_msg)
            return f"[Error: {err_msg}]", err_msg, 0
        except Exception as recurse_err:
            err_msg = f"Error during recursive resolution of '{parsed_artifact_spec}': {recurse_err}"
            log.exception("%s %s", log_identifier, err_msg)
            return f"[Error: {err_msg}]", err_msg, 0
    else:
        log.debug(
            "%s [Depth:%d] Artifact '%s' is not text-based (%s). Passing raw bytes to modifier chain.",
            log_identifier,
            current_depth,
            parsed_artifact_spec,
            original_mime_type,
        )

    if current_format == DataFormat.STRING and original_mime_type:
        normalized_mime_type = original_mime_type.lower()
        log.debug(
            "%s [Depth:%d] Pre-parsing string content with MIME type: %s",
            log_identifier,
            current_depth,
            normalized_mime_type,
        )
        if "json" in normalized_mime_type:
            try:
                current_data = json.loads(current_data)
                current_format = DataFormat.JSON_OBJECT
                log.info(
                    "%s [Depth:%d] Pre-parsed string as JSON_OBJECT.",
                    log_identifier,
                    current_depth,
                )
            except json.JSONDecodeError:
                log.warning(
                    "%s [Depth:%d] Failed to pre-parse as JSON despite MIME type '%s'. Content will be treated as STRING.",
                    log_identifier,
                    current_depth,
                    original_mime_type,
                )
        elif "yaml" in normalized_mime_type or "yml" in normalized_mime_type:
            try:
                current_data = yaml.safe_load(current_data)
                current_format = DataFormat.JSON_OBJECT
                log.info(
                    "%s [Depth:%d] Pre-parsed string as YAML (now JSON_OBJECT).",
                    log_identifier,
                    current_depth,
                )
            except yaml.YAMLError:
                log.warning(
                    "%s [Depth:%d] Failed to pre-parse as YAML despite MIME type '%s'. Content will be treated as STRING.",
                    log_identifier,
                    current_depth,
                    original_mime_type,
                )
        elif "csv" in normalized_mime_type:
            parsed_data, error_msg = _parse_string_to_list_of_dicts(
                current_data, original_mime_type, log_identifier
            )
            if error_msg is None and parsed_data is not None:
                current_data = parsed_data
                current_format = DataFormat.LIST_OF_DICTS
                log.info(
                    "%s [Depth:%d] Pre-parsed string as LIST_OF_DICTS from CSV.",
                    log_identifier,
                    current_depth,
                )
            else:
                log.warning(
                    "%s [Depth:%d] Failed to pre-parse as CSV despite MIME type '%s': %s. Content will be treated as STRING.",
                    log_identifier,
                    current_depth,
                    original_mime_type,
                    error_msg,
                )

        _log_data_state(
            log_identifier,
            f"[Depth:{current_depth}] After Pre-parsing",
            current_data,
            current_format,
            original_mime_type,
        )

    modifier_index = 0
    for prefix, value in modifiers_from_directive:
        modifier_index += 1
        modifier_step_id = f"Modifier {modifier_index} ({prefix})"

        modifier_def = MODIFIER_DEFINITIONS.get(prefix)
        if not modifier_def:
            err_msg = f"Unknown modifier prefix: '{prefix}'"
            log.warning("%s %s", log_identifier, err_msg)
            return f"[Error: {err_msg}]", err_msg, 0

        modifier_func = modifier_def["function"]
        accepts_formats: List[DataFormat] = modifier_def["accepts"]
        produces_format: DataFormat = modifier_def["produces"]

        log.info(
            "%s [Depth:%d][%s] Applying modifier: %s:%s (Accepts: %s, Produces: %s)",
            log_identifier,
            current_depth,
            modifier_step_id,
            prefix,
            value[:50] + "...",
            [f.name for f in accepts_formats],
            produces_format.name,
        )

        if current_format not in accepts_formats:
            target_format_for_modifier = accepts_formats[0]
            log.info(
                "%s [Depth:%d][%s] Current format %s not accepted by %s. Converting to %s...",
                log_identifier,
                current_depth,
                modifier_step_id,
                current_format.name,
                prefix,
                target_format_for_modifier.name,
            )
            _log_data_state(
                log_identifier,
                f"[Depth:{current_depth}] {modifier_step_id} - Before Conversion",
                current_data,
                current_format,
                original_mime_type,
            )
            converted_data, new_format, convert_error = convert_data(
                current_data,
                current_format,
                target_format_for_modifier,
                log_identifier,
                original_mime_type,
            )
            if convert_error:
                err_msg = (
                    f"Failed to convert data for modifier '{prefix}': {convert_error}"
                )
                log.warning("%s %s", log_identifier, err_msg)
                return f"[Error: {err_msg}]", err_msg, 0
            current_data = converted_data
            current_format = new_format
            log.info(
                "%s [Depth:%d][%s] Conversion successful. New format: %s",
                log_identifier,
                current_depth,
                modifier_step_id,
                current_format.name,
            )
            _log_data_state(
                log_identifier,
                f"[Depth:{current_depth}] {modifier_step_id} - After Conversion",
                current_data,
                current_format,
                original_mime_type,
            )

        try:
            _log_data_state(
                log_identifier,
                f"[Depth:{current_depth}] {modifier_step_id} - Before Execution",
                current_data,
                current_format,
                original_mime_type,
            )
            if prefix == "apply_to_template":
                result_data, _, exec_error = await modifier_func(
                    current_data, value, original_mime_type, log_identifier, context
                )
            else:
                if asyncio.iscoroutinefunction(modifier_func):
                    result_data, _, exec_error = await modifier_func(
                        current_data, value, original_mime_type, log_identifier
                    )
                else:
                    result_data, _, exec_error = modifier_func(
                        current_data, value, original_mime_type, log_identifier
                    )

            if exec_error:
                err_msg = f"Error applying modifier '{prefix}': {exec_error}"
                log.warning("%s %s", log_identifier, err_msg)
                return f"[Error: {err_msg}]", err_msg, 0

            current_data = result_data
            current_format = produces_format
            log.info(
                "%s [Depth:%d][%s] Modifier '%s' executed. Result format: %s",
                log_identifier,
                current_depth,
                modifier_step_id,
                prefix,
                current_format.name,
            )
            _log_data_state(
                log_identifier,
                f"[Depth:{current_depth}] {modifier_step_id} - After Execution",
                current_data,
                current_format,
                original_mime_type,
            )
            if current_data is None or (
                isinstance(current_data, (list, str, bytes)) and not current_data
            ):
                log.info(
                    "%s [Depth:%d][%s] Modifier '%s' resulted in empty data.",
                    log_identifier,
                    current_depth,
                    modifier_step_id,
                    prefix,
                )

        except Exception as mod_err:
            log.exception(
                "%s [Depth:%d][%s] Unexpected error executing modifier '%s': %s",
                log_identifier,
                current_depth,
                modifier_step_id,
                prefix,
                mod_err,
            )
            err_msg = f"Unexpected error in modifier '{prefix}': {mod_err}"
            return f"[Error: {err_msg}]", err_msg, 0

    if (
        current_format == DataFormat.BYTES
        and resolution_mode == ResolutionMode.A2A_MESSAGE_TO_USER
    ):
        log.info(
            "%s [Depth:%d] Result is binary data in A2A_MESSAGE_TO_USER mode. Signaling for inline binary content.",
            log_identifier,
            current_depth,
        )
        filename_for_signal = artifact_spec_from_directive.split(":", 1)[0]
        return (
            None,
            "SIGNAL_INLINE_BINARY_CONTENT",
            {
                "bytes": current_data,
                "mime_type": original_mime_type,
                "name": filename_for_signal,
            },
        )

    target_string_format = output_format_from_directive
    if target_string_format is None:
        log.warning(
            "%s [Depth:%d] Missing final 'format:' step in chain. Defaulting to 'text'.",
            log_identifier,
            current_depth,
        )
        target_string_format = "text"

    log.info(
        "%s [Depth:%d] [Final Serialization] Serializing final data (Format: %s) to target string format '%s'",
        log_identifier,
        current_depth,
        current_format.name,
        target_string_format,
    )
    _log_data_state(
        log_identifier,
        f"[Depth:{current_depth}] Before Serialization",
        current_data,
        current_format,
        original_mime_type,
    )

    final_serialized_string, serialize_error = serialize_data(
        data=current_data,
        data_format=current_format,
        target_string_format=target_string_format,
        original_mime_type=original_mime_type,
        log_id=log_identifier,
    )

    if serialize_error:
        log.warning("%s [Depth:%d] %s", log_identifier, current_depth, serialize_error)
        return (
            final_serialized_string,
            serialize_error,
            len(final_serialized_string.encode("utf-8")),
        )

    final_size = len(final_serialized_string.encode("utf-8"))
    log.info(
        "%s [Depth:%d] Chain execution completed successfully. Final size: %d bytes.",
        log_identifier,
        current_depth,
        final_size,
    )
    log.info(
        "%s [Depth:%d] [Final Serialization] Result: '%s...'",
        log_identifier,
        current_depth,
        final_serialized_string[:100]
        + ("..." if len(final_serialized_string) > 100 else ""),
    )
    return final_serialized_string, None, final_size


async def resolve_embeds_in_string(
    text: str,
    context: Any,
    resolver_func: Callable[
        ..., Union[Tuple[str, Optional[str], int], Tuple[None, str, Any]]
    ],
    types_to_resolve: Set[str],
    resolution_mode: "ResolutionMode",
    log_identifier: str = "[EmbedUtil]",
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[str, int, List[Tuple[int, Any, str]]]:
    """
    Resolves specified embed types within a string using a provided resolver function.
    This is the TOP-LEVEL resolver called by gateways. It handles signals and buffering.
    It does NOT perform recursion itself but calls `evaluate_embed` which might trigger recursion.

    Processes the string iteratively, resolving one embed at a time.
    Includes buffering logic: stops processing if a partial embed delimiter is found
    at the end, returning the processed part and the index where processing stopped.
    Can now return special signals from the resolver function.

    Args:
        text: The input string potentially containing embeds.
        context: The context object passed to the resolver function (now a Dict).
        resolver_func: The function to call for evaluating each embed.
                       Signature: (type, expression, format, context, log_id, config, ...) -> Any
                       Can return a string for replacement, or a tuple like (None, "SIGNAL_TYPE", data)
                       to indicate a signal instead of text replacement.
        types_to_resolve: A set of embed types (strings) to resolve in this pass.
        log_identifier: Identifier for logging.
        config: Optional configuration dictionary passed to the resolver.

    Returns:
        A tuple containing:
        - The string with specified embeds resolved (or removed if signaled).
        - The index in the *original* string representing the end of the
          successfully processed portion (useful for buffering). This will be
          len(text) if the whole string was processed.
        - A list of signals encountered during resolution, as tuples (index, signal_data).
          The index corresponds to the start index of the embed directive in the original string.
    """
    resolved_parts = []
    signals_found: List[Tuple[int, Any, str]] = []
    last_end = 0
    original_length = len(text)

    log.debug(
        "%s Checking for embeds in text: '%s'", log_identifier, text[:200] + "..."
    )

    for match in EMBED_REGEX.finditer(text):
        start, end = match.span()
        embed_type = match.group(1)
        expression = match.group(2)
        format_spec = match.group(3)

        resolved_parts.append(text[last_end:start])

        if embed_type in types_to_resolve:
            log.info(
                "%s Found embed type '%s' to resolve: expr='%s', fmt='%s'",
                log_identifier,
                embed_type,
                expression,
                format_spec,
            )
            resolved_value = await resolver_func(
                embed_type,
                expression,
                format_spec,
                context,
                log_identifier,
                resolution_mode,
                config,
            )

            if (
                isinstance(resolved_value, tuple)
                and len(resolved_value) == 3
                and resolved_value[0] is None
                and isinstance(resolved_value[1], str)
            ):
                signal_type = resolved_value[1]
                log.info(
                    "%s Received signal '%s' from resolver for embed at index %d.",
                    log_identifier,
                    signal_type,
                    start,
                )
                placeholder = f"__EMBED_SIGNAL_{uuid.uuid4().hex}__"
                resolved_parts.append(placeholder)
                signals_found.append(
                    (
                        start,
                        resolved_value,
                        placeholder,
                    )
                )
            elif (
                isinstance(resolved_value, tuple)
                and len(resolved_value) == 3
                and isinstance(resolved_value[0], str)
                and isinstance(resolved_value[2], int)
            ):
                text_content, error_message, _ = resolved_value
                if error_message:
                    log.warning(
                        "%s Embed resolution for '%s:%s' resulted in error: %s. Using error string as content.",
                        log_identifier,
                        embed_type,
                        expression,
                        error_message,
                    )
                resolved_parts.append(text_content)
            else:
                log.warning(
                    "%s Resolver for type '%s' returned unexpected structure %s. Treating as error string.",
                    log_identifier,
                    embed_type,
                    type(resolved_value),
                )

        else:
            log.debug(
                "%s Skipping embed type '%s' (not in types_to_resolve)",
                log_identifier,
                embed_type,
            )
            resolved_parts.append(match.group(0))

        last_end = end

    remaining_text = text[last_end:]
    resolved_parts.append(remaining_text)

    potential_partial_embed = False
    partial_embed_start_index = -1

    last_open_delimiter_index = remaining_text.rfind(EMBED_DELIMITER_OPEN)

    if last_open_delimiter_index != -1:
        closing_delimiter_index = remaining_text.find(
            EMBED_DELIMITER_CLOSE, last_open_delimiter_index
        )
        if closing_delimiter_index == -1:
            potential_partial_embed = True
            partial_embed_start_index = last_open_delimiter_index
            log.debug(
                "%s Potential unclosed embed detected starting at index %d within remaining text: '%s...'",
                log_identifier,
                partial_embed_start_index,
                remaining_text[
                    partial_embed_start_index : partial_embed_start_index + 10
                ],
            )

    if potential_partial_embed:
        processed_until_index = last_end + partial_embed_start_index
        final_text = (
            "".join(resolved_parts[:-1]) + remaining_text[:partial_embed_start_index]
        )
        log.debug(
            "%s Returning processed text up to index %d due to potential partial embed.",
            log_identifier,
            processed_until_index,
        )
    else:
        final_text = "".join(resolved_parts)
        processed_until_index = original_length
        log.debug(
            "%s Returning fully processed text (length %d).",
            log_identifier,
            len(final_text),
        )

    # If resolving late embeds, also resolve template blocks
    # Templates are considered late embeds since they need artifact service access
    if LATE_EMBED_TYPES.intersection(types_to_resolve):
        try:
            from ..templates import resolve_template_blocks_in_string

            artifact_service = context.get("artifact_service")
            session_context = context.get("session_context")

            if artifact_service and session_context:
                log.debug(
                    "%s Resolving template blocks after late embed resolution.",
                    log_identifier,
                )
                final_text = await resolve_template_blocks_in_string(
                    text=final_text,
                    artifact_service=artifact_service,
                    session_context=session_context,
                    log_identifier=f"{log_identifier}[TemplateResolve]",
                )
        except Exception as template_err:
            log.warning(
                "%s Failed to resolve template blocks: %s",
                log_identifier,
                template_err,
            )
            # Continue with final_text as-is

    return final_text, processed_until_index, signals_found


async def resolve_embeds_recursively_in_string(
    text: str,
    context: Any,
    resolver_func: Callable[..., Tuple[str, Optional[str], int]],
    types_to_resolve: Set[str],
    resolution_mode: "ResolutionMode",
    log_identifier: str,
    config: Optional[Dict],
    max_depth: int,
    current_depth: int = 0,
    visited_artifacts: Optional[Set[Tuple[str, int]]] = None,
    accumulated_size: int = 0,
    max_total_size: int = -1,
) -> str:
    """
    Recursively resolves specified embed types within a string, respecting depth,
    loop detection (via visited_artifacts passed down), and accumulated size limits.
    """
    if current_depth >= max_depth:
        log.warning(
            "%s Max embed recursion depth (%d) reached for current processing string.",
            log_identifier,
            max_depth,
        )
        return "[Error: Max embed depth exceeded]"

    visited_artifacts = visited_artifacts or set()
    resolved_parts = []
    last_end = 0

    for match in EMBED_REGEX.finditer(text):
        start, end = match.span()
        embed_type = match.group(1)
        expression = match.group(2)
        format_spec = match.group(3)

        resolved_parts.append(text[last_end:start])

        if embed_type not in types_to_resolve:
            resolved_parts.append(match.group(0))
            last_end = end
            continue

        log.debug(
            "%s [Depth:%d] Found embed '%s' to resolve: expr='%s', fmt='%s'",
            log_identifier,
            current_depth,
            embed_type,
            expression,
            format_spec,
        )

        resolved_value = await resolver_func(
            embed_type,
            expression,
            format_spec,
            context,
            log_identifier,
            resolution_mode,
            config,
            current_depth,
            visited_artifacts,
        )

        if (
            isinstance(resolved_value, tuple)
            and len(resolved_value) == 3
            and isinstance(resolved_value[0], str)
            and isinstance(resolved_value[2], int)
        ):
            resolved_string_for_embed, error_msg_from_chain, size_of_this_embed = (
                resolved_value
            )
        else:
            log.error(
                "%s [Depth:%d] Recursive call to resolver for '%s:%s' returned unexpected signal or format. Treating as error.",
                log_identifier,
                current_depth,
                embed_type,
                expression,
            )
            error_msg_from_chain = "Recursive resolution returned unexpected signal."
            resolved_string_for_embed = f"[Error: {error_msg_from_chain}]"
            size_of_this_embed = len(resolved_string_for_embed.encode("utf-8"))

        if error_msg_from_chain:
            log.warning(
                "%s [Depth:%d] Embed '%s:%s' resulted in error from chain: %s",
                log_identifier,
                current_depth,
                embed_type,
                expression,
                error_msg_from_chain,
            )
            resolved_parts.append(resolved_string_for_embed)
        else:
            if (
                max_total_size >= 0
                and accumulated_size + size_of_this_embed > max_total_size
            ):
                error_str = f"[Error: Embedding '{expression}' exceeds total size limit for parent content ({accumulated_size + size_of_this_embed} > {max_total_size})]"
                log.warning("%s %s", log_identifier, error_str)
                resolved_parts.append(error_str)
            else:
                resolved_parts.append(resolved_string_for_embed)
                accumulated_size += size_of_this_embed
                log.debug(
                    "%s [Depth:%d] Appended resolved embed (size: %d). Current accumulated_size: %d",
                    log_identifier,
                    current_depth,
                    size_of_this_embed,
                    accumulated_size,
                )

        last_end = end

    resolved_parts.append(text[last_end:])
    result_text = "".join(resolved_parts)

    # If resolving late embeds, also resolve template blocks
    # Templates are considered late embeds since they need artifact service access
    if LATE_EMBED_TYPES.intersection(types_to_resolve):
        try:
            from ..templates import resolve_template_blocks_in_string

            artifact_service = context.get("artifact_service")
            session_context = context.get("session_context")

            if artifact_service and session_context:
                log.debug(
                    "%s [Depth:%d] Resolving template blocks after late embed resolution.",
                    log_identifier,
                    current_depth,
                )
                result_text = await resolve_template_blocks_in_string(
                    text=result_text,
                    artifact_service=artifact_service,
                    session_context=session_context,
                    log_identifier=f"{log_identifier}[TemplateResolve]",
                )
        except Exception as template_err:
            log.warning(
                "%s [Depth:%d] Failed to resolve template blocks: %s",
                log_identifier,
                current_depth,
                template_err,
            )
            # Continue with result_text as-is

    return result_text


async def evaluate_embed(
    embed_type: str,
    expression: str,
    format_spec: Optional[str],
    context: Dict[str, Any],
    log_identifier: str,
    resolution_mode: "ResolutionMode",
    config: Optional[Dict] = None,
    current_depth: int = 0,
    visited_artifacts: Optional[Set[Tuple[str, int]]] = None,
) -> Union[Tuple[str, Optional[str], int], Tuple[None, str, Any]]:
    """
    Evaluates a single embed directive.
    For 'artifact_content', it handles the modifier chain and potential internal recursion.
    For other types, it evaluates directly and returns a 3-tuple (text, error, size).
    For 'status_update', it returns a signal tuple (None, "SIGNAL_STATUS_UPDATE", data).

    Args:
        embed_type: The type of the embed.
        expression: The expression part of the embed.
        format_spec: The optional format specifier.
        context: The dictionary-based context (containing artifact_service, session_context, config).
        log_identifier: Identifier for logging.
        config: Optional configuration dictionary (now part of context or passed if needed by evaluators).
        current_depth: Current recursion depth (for artifact_content).
        visited_artifacts: Set of visited artifacts (for artifact_content).

    Returns:
        A 3-tuple (text_content, error_message, size) or a signal tuple (None, signal_type, data).
    """
    log.debug(
        "%s Evaluating embed: type='%s', expr='%s', fmt='%s'",
        log_identifier,
        embed_type,
        expression[:50] + "...",
        format_spec,
    )

    if embed_type == "status_update":
        status_text = expression.strip()
        log.info("%s Detected 'status_update' embed. Signaling.", log_identifier)
        return (None, "SIGNAL_STATUS_UPDATE", status_text)

    elif embed_type == "artifact_return":
        if resolution_mode == ResolutionMode.A2A_MESSAGE_TO_USER:
            parts = expression.strip().split(":", 1)
            filename = parts[0]
            version = parts[1] if len(parts) > 1 else "latest"
            log.info("%s Detected 'artifact_return' embed. Signaling.", log_identifier)
            return (
                None,
                "SIGNAL_ARTIFACT_RETURN",
                {"filename": filename, "version": version},
            )
        else:
            log.warning(
                "%s Ignoring 'artifact_return' embed in unsupported context: %s",
                log_identifier,
                resolution_mode.name,
            )
            original_embed_text = f"«{embed_type}:{expression}»"
            return original_embed_text, None, len(original_embed_text.encode("utf-8"))

    elif embed_type == "artifact_content":
        artifact_spec, modifiers, output_format = _parse_modifier_chain(expression)
        if output_format is None and format_spec is not None:
            log.warning(
                "%s Using format specifier '| %s' for artifact_content as chain format step was missing.",
                log_identifier,
                format_spec,
            )
            output_format = format_spec

        # Check if this is a deep research report artifact
        # Deep research reports should be rendered by the frontend component, not resolved inline
        filename_part = artifact_spec.split(":")[0] if ":" in artifact_spec else artifact_spec
        is_deep_research_report = filename_part.lower().endswith("_report.md")
        
        if is_deep_research_report and resolution_mode == ResolutionMode.A2A_MESSAGE_TO_USER:
            # Parse version from artifact_spec
            parts = artifact_spec.strip().split(":", 1)
            filename = parts[0]
            version = parts[1] if len(parts) > 1 else "latest"
            log.info(
                "%s Detected deep research report artifact '%s'. Signaling for frontend rendering instead of inline resolution.",
                log_identifier,
                filename,
            )
            return (
                None,
                "SIGNAL_DEEP_RESEARCH_REPORT",
                {"filename": filename, "version": version},
            )

        result = await _evaluate_artifact_content_embed_with_chain(
            artifact_spec_from_directive=artifact_spec,
            modifiers_from_directive=modifiers,
            output_format_from_directive=output_format,
            context=context,
            log_identifier=log_identifier,
            resolution_mode=resolution_mode,
            config=config,
            current_depth=current_depth,
            visited_artifacts=visited_artifacts or set(),
        )
        return result

    else:
        evaluator = EMBED_EVALUATORS.get(embed_type)
        if not evaluator:
            err_msg = f"Unknown embed type: '{embed_type}'"
            log.warning("%s %s", log_identifier, err_msg)
            err_str = f"[Error: {err_msg}]"
            return err_str, err_msg, len(err_str.encode("utf-8"))

        try:
            if asyncio.iscoroutinefunction(evaluator):
                str_value, eval_error, size = await evaluator(
                    expression, context, log_identifier, format_spec
                )
            else:
                str_value, eval_error, size = evaluator(
                    expression, context, log_identifier, format_spec
                )

            return str_value, eval_error, size

        except Exception as e:
            log.exception(
                "%s Unexpected error evaluating %s embed '%s': %s",
                log_identifier,
                embed_type,
                expression,
                e,
            )
            err_msg = f"Unexpected evaluation error: {e}"
            err_str = f"[Error: {err_msg}]"
            return err_str, err_msg, len(err_str.encode("utf-8"))
