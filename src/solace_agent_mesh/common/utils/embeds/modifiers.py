"""
Defines modifier implementation functions and their contracts.
"""

import logging
import re
from typing import Any, Callable, Dict, Optional, Tuple, List

from .constants import EARLY_EMBED_TYPES, LATE_EMBED_TYPES

log = logging.getLogger(__name__)

from jsonpath_ng.ext import parse as jsonpath_parse
import pystache

from google.adk.artifacts import BaseArtifactService

from .types import DataFormat, ResolutionMode


def _apply_jsonpath(
    current_data: Any, expression: str, mime_type: Optional[str], log_id: str
) -> Tuple[Any, Optional[str], Optional[str]]:
    """
    Applies a JSONPath expression to parsed JSON data.

    Args:
        current_data: The input data (expected to be dict or list).
        expression: The JSONPath expression string.
        mime_type: The original mime type (passed through).
        log_id: Identifier for logging.

    Returns:
        Tuple: (result_data, original_mime_type, error_string)
               result_data is typically a list of matched values.
    """
    if not isinstance(current_data, (dict, list)):
        return (
            current_data,
            mime_type,
            f"Input data for 'jsonpath' must be a JSON object or list, got {type(current_data).__name__}.",
        )

    try:
        jsonpath_expr = jsonpath_parse(expression)
        matches = [match.value for match in jsonpath_expr.find(current_data)]
        return matches, mime_type, None
    except Exception as e:
        return (
            current_data,
            mime_type,
            f"Error applying JSONPath expression '{expression}': {e}",
        )


def _apply_select_cols(
    current_data: List[Dict], cols_str: str, mime_type: Optional[str], log_id: str
) -> Tuple[Any, Optional[str], Optional[str]]:
    """
    Selects specific columns from data represented as a list of dictionaries.

    Args:
        current_data: The input data (expected List[Dict]).
        cols_str: Comma-separated string of column names to keep.
        mime_type: The original mime type (passed through).
        log_id: Identifier for logging.

    Returns:
        Tuple: (result_data, original_mime_type, error_string)
               result_data is List[Dict] containing only selected columns.
    """
    if not isinstance(current_data, list) or (
        current_data and not isinstance(current_data[0], dict)
    ):
        return (
            current_data,
            mime_type,
            f"Input data for 'select_cols' must be a list of dictionaries, got {type(current_data).__name__}.",
        )

    if not current_data:
        return [], mime_type, None

    try:
        header = list(current_data[0].keys())
        target_cols = [col.strip() for col in cols_str.split(",")]
        output_list = []

        for target_col in target_cols:
            if target_col not in header:
                return (
                    current_data,
                    mime_type,
                    f"Column '{target_col}' not found in data keys: {header}",
                )

        for row_dict in current_data:
            new_row = {col: row_dict.get(col) for col in target_cols}
            output_list.append(new_row)

        return output_list, mime_type, None

    except Exception as e:
        return current_data, mime_type, f"Error selecting columns '{cols_str}': {e}"


def _apply_filter_rows_eq(
    current_data: List[Dict], filter_spec: str, mime_type: Optional[str], log_id: str
) -> Tuple[Any, Optional[str], Optional[str]]:
    """
    Filters a list of dictionaries based on a column's value equality.

    Args:
        current_data: The input data (expected List[Dict]).
        filter_spec: String in the format 'column_name:value'.
        mime_type: The original mime type (passed through).
        log_id: Identifier for logging.

    Returns:
        Tuple: (result_data, original_mime_type, error_string)
               result_data is List[Dict] containing only filtered rows.
    """
    if not isinstance(current_data, list) or (
        current_data and not isinstance(current_data[0], dict)
    ):
        return (
            current_data,
            mime_type,
            f"Input data for 'filter_rows_eq' must be a list of dictionaries, got {type(current_data).__name__}.",
        )

    if not current_data:
        return [], mime_type, None

    try:
        parts = filter_spec.split(":", 1)
        if len(parts) != 2:
            return (
                current_data,
                mime_type,
                f"Invalid filter format '{filter_spec}'. Expected 'column_name:value'.",
            )
        col_name, filter_value = parts[0].strip(), parts[1].strip()

        header = list(current_data[0].keys())
        if col_name not in header:
            return (
                current_data,
                mime_type,
                f"Filter column '{col_name}' not found in data keys: {header}",
            )

        output_list = [
            row for row in current_data if str(row.get(col_name)) == filter_value
        ]

        return output_list, mime_type, None

    except Exception as e:
        return current_data, mime_type, f"Error filtering rows by '{filter_spec}': {e}"


def _apply_slice_rows(
    current_data: List[Dict], slice_spec: str, mime_type: Optional[str], log_id: str
) -> Tuple[Any, Optional[str], Optional[str]]:
    """
    Selects a slice of rows from a list of dictionaries.

    Args:
        current_data: The input data (expected List[Dict]).
        slice_spec: String in Python slice format 'start:end'.
        mime_type: The original mime type (passed through).
        log_id: Identifier for logging.

    Returns:
        Tuple: (result_data, original_mime_type, error_string)
               result_data is List[Dict] containing the sliced rows.
    """
    if not isinstance(current_data, list):
        return (
            current_data,
            mime_type,
            f"Input data for 'slice_rows' must be a list, got {type(current_data).__name__}.",
        )

    try:
        start_str, end_str = None, None
        if ":" in slice_spec:
            parts = slice_spec.split(":", 1)
            start_str, end_str = parts[0].strip(), parts[1].strip()
        else:
            return (
                current_data,
                mime_type,
                f"Invalid slice format '{slice_spec}'. Expected 'start:end'.",
            )

        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else None

        sliced_data = current_data[start:end]

        return sliced_data, mime_type, None

    except (ValueError, TypeError) as e:
        return current_data, mime_type, f"Invalid slice indices in '{slice_spec}': {e}"
    except Exception as e:
        return current_data, mime_type, f"Error slicing rows '{slice_spec}': {e}"


def _apply_slice_lines(
    current_data: str, slice_spec: str, mime_type: Optional[str], log_id: str
) -> Tuple[Any, Optional[str], Optional[str]]:
    """
    Selects a slice of lines from text data.

    Args:
        current_data: The input data (expected str).
        slice_spec: String in Python slice format 'start:end'.
        mime_type: The original mime type (passed through).
        log_id: Identifier for logging.

    Returns:
        Tuple: (result_data, original_mime_type, error_string)
               result_data is str containing the sliced lines.
    """
    if not isinstance(current_data, str):
        return (
            current_data,
            mime_type,
            f"Input data for 'slice_lines' must be a string, got {type(current_data).__name__}.",
        )

    try:
        start_str, end_str = None, None
        if ":" in slice_spec:
            parts = slice_spec.split(":", 1)
            start_str, end_str = parts[0].strip(), parts[1].strip()
        else:
            return (
                current_data,
                mime_type,
                f"Invalid slice format '{slice_spec}'. Expected 'start:end'.",
            )

        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else None

        lines = current_data.splitlines(keepends=True)
        sliced_lines = lines[start:end]

        return "".join(sliced_lines), mime_type, None

    except (ValueError, TypeError) as e:
        return current_data, mime_type, f"Invalid slice indices in '{slice_spec}': {e}"
    except Exception as e:
        return current_data, mime_type, f"Error slicing text lines '{slice_spec}': {e}"


def _apply_grep(
    current_data: str, pattern: str, mime_type: Optional[str], log_id: str
) -> Tuple[Any, Optional[str], Optional[str]]:
    """
    Filters lines matching a regex pattern from text data.

    Args:
        current_data: The input data (expected str).
        pattern: The regex pattern string.
        mime_type: The original mime type (passed through).
        log_id: Identifier for logging.

    Returns:
        Tuple: (result_data, original_mime_type, error_string)
               result_data is str containing only matching lines.
    """
    if not isinstance(current_data, str):
        return (
            current_data,
            mime_type,
            f"Input data for 'grep' must be a string, got {type(current_data).__name__}.",
        )

    try:
        regex = re.compile(pattern)
        lines = current_data.splitlines(keepends=True)
        filtered_lines = [line for line in lines if regex.search(line)]
        return "".join(filtered_lines), mime_type, None
    except re.error as e:
        return current_data, mime_type, f"Invalid regex pattern '{pattern}': {e}"
    except Exception as e:
        return current_data, mime_type, f"Error applying grep pattern '{pattern}': {e}"


def _apply_head(
    current_data: str, n_str: str, mime_type: Optional[str], log_id: str
) -> Tuple[Any, Optional[str], Optional[str]]:
    """
    Returns the first N lines of text data.

    Args:
        current_data: The input data (expected str).
        n_str: String representing the number of lines (N).
        mime_type: The original mime type (passed through).
        log_id: Identifier for logging.

    Returns:
        Tuple: (result_data, original_mime_type, error_string)
               result_data is str containing the first N lines.
    """
    if not isinstance(current_data, str):
        return (
            current_data,
            mime_type,
            f"Input data for 'head' must be a string, got {type(current_data).__name__}.",
        )

    try:
        n = int(n_str.strip())
        if n < 0:
            return current_data, mime_type, "Head count N cannot be negative."

        lines = current_data.splitlines(keepends=True)
        head_lines = lines[:n]
        return "".join(head_lines), mime_type, None
    except (ValueError, TypeError) as e:
        return current_data, mime_type, f"Invalid head count N '{n_str}': {e}"
    except Exception as e:
        return current_data, mime_type, f"Error applying head '{n_str}': {e}"


def _apply_tail(
    current_data: str, n_str: str, mime_type: Optional[str], log_id: str
) -> Tuple[Any, Optional[str], Optional[str]]:
    """
    Returns the last N lines of text data.

    Args:
        current_data: The input data (expected str).
        n_str: String representing the number of lines (N).
        mime_type: The original mime type (passed through).
        log_id: Identifier for logging.

    Returns:
        Tuple: (result_data, original_mime_type, error_string)
               result_data is str containing the last N lines.
    """
    if not isinstance(current_data, str):
        return (
            current_data,
            mime_type,
            f"Input data for 'tail' must be a string, got {type(current_data).__name__}.",
        )

    try:
        n = int(n_str.strip())
        if n < 0:
            return current_data, mime_type, "Tail count N cannot be negative."
        if n == 0:
            return "", mime_type, None

        lines = current_data.splitlines(keepends=True)
        tail_lines = lines[-n:]
        return "".join(tail_lines), mime_type, None
    except (ValueError, TypeError) as e:
        return current_data, mime_type, f"Invalid tail count N '{n_str}': {e}"
    except Exception as e:
        return current_data, mime_type, f"Error applying tail '{n_str}': {e}"


def _apply_select_fields(
    current_data: List[Dict], fields_str: str, mime_type: Optional[str], log_id: str
) -> Tuple[Any, Optional[str], Optional[str]]:
    """
    Selects specific fields from a list of dictionaries.

    Args:
        current_data: The input data (expected List[Dict]).
        fields_str: Comma-separated string of field names to keep.
        mime_type: The original mime type (passed through).
        log_id: Identifier for logging.

    Returns:
        Tuple: (result_data, original_mime_type, error_string)
               result_data is List[Dict] containing only selected fields.
    """
    if not isinstance(current_data, list) or (
        current_data and not isinstance(current_data[0], dict)
    ):
        return (
            current_data,
            mime_type,
            f"Input data for 'select_fields' must be a list of dictionaries, got {type(current_data).__name__}.",
        )

    target_fields = [field.strip() for field in fields_str.split(",")]
    if not target_fields:
        return current_data, mime_type, "No fields specified for 'select_fields'."

    output_list = []
    try:
        for item in current_data:
            if isinstance(item, dict):
                new_item = {
                    field: item.get(field) for field in target_fields if field in item
                }
                output_list.append(new_item)
            else:
                log.warning(
                    "%s Skipping non-dictionary item in list during select_fields.",
                    log_id,
                )
                continue
        return output_list, mime_type, None
    except Exception as e:
        return current_data, mime_type, f"Error selecting fields '{fields_str}': {e}"


async def _apply_template(
    current_data: Any,
    template_spec: str,
    mime_type: Optional[str],
    log_id: str,
    context: Any,
) -> Tuple[Any, Optional[str], Optional[str]]:
    """
    Applies a Mustache template loaded from an artifact to the input data.
    This version first renders the template, then resolves embeds on the result.

    Args:
        current_data: The input data (expected dict, list, or str).
        template_spec: String 'template_filename[:version]'.
        mime_type: The original mime type (passed through).
        log_id: Identifier for logging.
        context: The Gateway context dictionary containing artifact_service and session_context.

    Returns:
        Tuple: (result_data, original_mime_type, error_string)
               result_data is the rendered and resolved string.
    """
    from .resolver import resolve_embeds_recursively_in_string, evaluate_embed

    if not isinstance(current_data, (dict, list, str)):
        return (
            current_data,
            mime_type,
            f"Input data for 'apply_to_template' must be dict, list, or string, got {type(current_data).__name__}.",
        )

    parts = template_spec.strip().split(":", 1)
    template_filename = parts[0]
    template_version_str = parts[1] if len(parts) > 1 else None
    template_version = None

    if not template_filename:
        return current_data, mime_type, "Template filename cannot be empty."

    if not isinstance(context, dict):
        return current_data, mime_type, "Invalid context for template loading."
    artifact_service: Optional[BaseArtifactService] = context.get("artifact_service")
    session_context = context.get("session_context")
    if not artifact_service or not session_context:
        return (
            current_data,
            mime_type,
            "ArtifactService or session context not available for template loading.",
        )

    app_name = session_context.get("app_name")
    user_id = session_context.get("user_id")
    session_id = session_context.get("session_id")
    if not all([app_name, user_id, session_id]):
        return (
            current_data,
            mime_type,
            "Missing required session identifiers in context for template loading.",
        )

    try:
        if template_version_str:
            template_version = int(template_version_str)
        else:
            versions = await artifact_service.list_versions(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=template_filename,
            )
            if not versions:
                return (
                    current_data,
                    mime_type,
                    f"Template artifact '{template_filename}' (latest) not found.",
                )
            template_version = max(versions)

        template_part = await artifact_service.load_artifact(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=template_filename,
            version=template_version,
        )

        if not template_part or not template_part.inline_data:
            return (
                current_data,
                mime_type,
                f"Template artifact '{template_filename}' v{template_version} not found or empty.",
            )

        template_bytes = template_part.inline_data.data
        try:
            raw_template_string = template_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return (
                current_data,
                mime_type,
                f"Cannot render non-UTF-8 decodable binary template '{template_filename}' v{template_version}.",
            )

    except FileNotFoundError:
        return (
            current_data,
            mime_type,
            f"Template artifact '{template_filename}' v{template_version_str or 'latest'} not found.",
        )
    except ValueError as e:
        return (
            current_data,
            mime_type,
            f"Invalid version specified for template: '{template_version_str}' or other value error: {e}",
        )
    except Exception as e:
        return (
            current_data,
            mime_type,
            f"Error loading template artifact '{template_filename}' v{template_version_str or 'latest'}: {e}",
        )

    try:
        log.info(
            "%s [apply_to_template] Preparing render context. Input data type: %s, Original MIME: %s",
            log_id,
            type(current_data).__name__,
            mime_type,
        )
        render_context: Dict[str, Any]

        if isinstance(current_data, list):
            if mime_type and "csv" in mime_type.lower():
                log.info(
                    "%s [apply_to_template] Input is a list and original MIME is CSV. Structuring context with 'headers' and 'data_rows'.",
                    log_id,
                )
                if not current_data:
                    render_context = {"headers": [], "data_rows": []}
                else:
                    if all(isinstance(item, dict) for item in current_data):
                        headers = list(current_data[0].keys()) if current_data else []
                        data_rows = [list(row.values()) for row in current_data]
                        render_context = {"headers": headers, "data_rows": data_rows}
                    else:
                        log.warning(
                            "%s [apply_to_template] Input is list from CSV, but items are not all dictionaries. Falling back to 'items' context.",
                            log_id,
                        )
                        render_context = {"items": current_data}
            else:
                log.info(
                    "%s [apply_to_template] Input is a list (from JSON/YAML). Data available under 'items' key.",
                    log_id,
                )
                render_context = {"items": current_data}
        elif isinstance(current_data, dict):
            render_context = current_data
            log.info(
                "%s [apply_to_template] Input is dict. Keys directly available in template.",
                log_id,
            )
        elif isinstance(current_data, str):
            render_context = {"text": current_data}
            log.info(
                "%s [apply_to_template] Input is string. Data available under 'text' key.",
                log_id,
            )
        else:
            log.warning(
                "%s [apply_to_template] Input is unexpected type %s. Converting to string and placing under 'value' key.",
                log_id,
                type(current_data).__name__,
            )
            render_context = {"value": str(current_data)}

        log.info(
            "%s [apply_to_template] Render context keys: %s",
            log_id,
            list(render_context.keys()),
        )
        if "items" in render_context and isinstance(render_context["items"], list):
            log.info(
                "%s [apply_to_template] Render context 'items' length: %d",
                log_id,
                len(render_context["items"]),
            )

        intermediate_rendered_string = pystache.render(
            raw_template_string, render_context
        )
        log.debug(
            "%s [apply_to_template] Intermediate rendered string: %s",
            log_id,
            intermediate_rendered_string[:200] + "...",
        )

    except Exception as e:
        return (
            current_data,
            mime_type,
            f"Error preparing context or rendering template '{template_filename}' v{template_version}: {e}",
        )

    try:
        log.debug(
            "%s [apply_to_template] Resolving embeds on rendered template output.",
            log_id,
        )
        resolver_config = context.get("config", {})
        if not resolver_config:
            log.warning(
                "%s 'config' not found in context for template embed resolution. Using defaults.",
                log_id,
            )

        final_rendered_string = await resolve_embeds_recursively_in_string(
            text=intermediate_rendered_string,
            context=context,
            resolver_func=evaluate_embed,
            types_to_resolve=EARLY_EMBED_TYPES.union(LATE_EMBED_TYPES),
            resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT,
            log_identifier=f"{log_id}[TemplateEmbeds]",
            config=resolver_config,
            max_depth=resolver_config.get("gateway_recursive_embed_depth", 12),
            current_depth=0,
            visited_artifacts=set(),
            accumulated_size=0,
            max_total_size=resolver_config.get(
                "gateway_max_artifact_resolve_size_bytes", -1
            ),
        )
        log.debug(
            "%s [apply_to_template] Final rendered string after embed resolution: %s",
            log_id,
            final_rendered_string[:200] + "...",
        )
    except Exception as recurse_err:
        log.exception(
            "%s Error during recursive resolution of rendered template: %s",
            log_id,
            recurse_err,
        )
        return (
            current_data,
            mime_type,
            f"Error resolving embeds within rendered template: {recurse_err}",
        )

    return final_rendered_string, mime_type, None


MODIFIER_IMPLEMENTATIONS: Dict[
    str, Callable[..., Tuple[Any, Optional[str], Optional[str]]]
] = {
    "jsonpath": _apply_jsonpath,
    "select_cols": _apply_select_cols,
    "filter_rows_eq": _apply_filter_rows_eq,
    "slice_rows": _apply_slice_rows,
    "slice_lines": _apply_slice_lines,
    "grep": _apply_grep,
    "head": _apply_head,
    "tail": _apply_tail,
    "select_fields": _apply_select_fields,
    "apply_to_template": _apply_template,
}

MODIFIER_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "jsonpath": {
        "function": _apply_jsonpath,
        "accepts": [DataFormat.JSON_OBJECT],
        "produces": DataFormat.JSON_OBJECT,
    },
    "select_cols": {
        "function": _apply_select_cols,
        "accepts": [DataFormat.LIST_OF_DICTS],
        "produces": DataFormat.LIST_OF_DICTS,
    },
    "filter_rows_eq": {
        "function": _apply_filter_rows_eq,
        "accepts": [DataFormat.LIST_OF_DICTS],
        "produces": DataFormat.LIST_OF_DICTS,
    },
    "slice_rows": {
        "function": _apply_slice_rows,
        "accepts": [DataFormat.LIST_OF_DICTS],
        "produces": DataFormat.LIST_OF_DICTS,
    },
    "slice_lines": {
        "function": _apply_slice_lines,
        "accepts": [DataFormat.STRING],
        "produces": DataFormat.STRING,
    },
    "grep": {
        "function": _apply_grep,
        "accepts": [DataFormat.STRING],
        "produces": DataFormat.STRING,
    },
    "head": {
        "function": _apply_head,
        "accepts": [DataFormat.STRING],
        "produces": DataFormat.STRING,
    },
    "tail": {
        "function": _apply_tail,
        "accepts": [DataFormat.STRING],
        "produces": DataFormat.STRING,
    },
    "select_fields": {
        "function": _apply_select_fields,
        "accepts": [DataFormat.LIST_OF_DICTS],
        "produces": DataFormat.LIST_OF_DICTS,
    },
    "apply_to_template": {
        "function": _apply_template,
        "accepts": [
            DataFormat.JSON_OBJECT,
            DataFormat.LIST_OF_DICTS,
            DataFormat.STRING,
        ],
        "produces": DataFormat.STRING,
    },
}


def _parse_modifier_chain(
    expression: str,
) -> Tuple[str, List[Tuple[str, str]], Optional[str]]:
    """
    Parses the expression part of an artifact_content embed.

    Separates the artifact specifier, modifier chain, and final format specifier.

    Args:
        expression: The full expression string after 'artifact_content:'.

    Returns:
        A tuple containing:
        - artifact_spec (str): The filename and optional version (e.g., "data.csv:1").
        - modifiers (List[Tuple[str, str]]): A list of (prefix, value) tuples for modifiers.
        - output_format (Optional[str]): The final output format string (e.g., "text", "json").
                                          Returns None if the format step is missing or invalid.
    """
    from .constants import EMBED_CHAIN_DELIMITER

    parts = expression.split(EMBED_CHAIN_DELIMITER)
    if not parts:
        return expression, [], None

    artifact_spec = parts[0].strip()
    modifiers = []
    output_format = None

    for i in range(1, len(parts)):
        part = parts[i].strip()
        if not part:
            continue

        if i == len(parts) - 1:
            format_match = re.match(r"format:(.*)", part, re.DOTALL)
            if format_match:
                output_format = format_match.group(1).strip()
                continue

        modifier_parts = part.split(":", 1)
        if len(modifier_parts) == 2:
            prefix = modifier_parts[0].strip()
            value = modifier_parts[1].strip()
            if prefix and value:
                modifiers.append((prefix, value))
            else:
                log.warning("Ignoring invalid modifier step format: '%s'", part)
        else:
            log.warning("Ignoring invalid modifier step format: '%s'", part)

    return artifact_spec, modifiers, output_format
