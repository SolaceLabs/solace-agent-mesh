"""
Liquid template rendering with data context preparation.
"""

import logging
import csv
import io
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger(__name__)

try:
    from liquid import Environment

    LIQUID_AVAILABLE = True
except ImportError:
    LIQUID_AVAILABLE = False

try:
    from jsonpath_ng.ext import parse as jsonpath_parse

    JSONPATH_NG_AVAILABLE = True
except ImportError:
    JSONPATH_NG_AVAILABLE = False


def _parse_csv_to_context(csv_content: str) -> Dict[str, Any]:
    """
    Parses CSV content into a template context with headers and data_rows.

    Returns:
        Dict with keys: headers (list of strings), data_rows (list of lists)
    """
    try:
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        if not rows:
            return {"headers": [], "data_rows": []}

        headers = rows[0]
        data_rows = rows[1:]

        return {"headers": headers, "data_rows": data_rows}
    except Exception as e:
        log.error("CSV parsing failed: %s", e)
        # Fallback to text
        return {"text": csv_content}


def _apply_jsonpath_filter(
    data: Any, jsonpath_expr: str, log_id: str
) -> Tuple[Any, Optional[str]]:
    """
    Applies JSONPath filter to data.

    Returns:
        Tuple of (filtered_data, error_message)
    """
    if not JSONPATH_NG_AVAILABLE:
        return data, "JSONPath filtering skipped: 'jsonpath-ng' not installed."

    if not isinstance(data, (dict, list)):
        return data, f"JSONPath requires dict or list input, got {type(data).__name__}"

    try:
        expr = jsonpath_parse(jsonpath_expr)
        matches = [match.value for match in expr.find(data)]

        # Special case: if path selects a single array (like $.products), return the array directly
        # But if path uses filters (like $.products[?@.x==y]), return matches as array
        # Heuristic: if we have exactly 1 match and it's a list, return it directly
        # Otherwise, return matches list
        if len(matches) == 1 and isinstance(matches[0], list):
            return matches[0], None
        else:
            return matches, None
    except Exception as e:
        return data, f"JSONPath error: {e}"


def _apply_limit(data: Any, limit: int, log_id: str) -> Any:
    """
    Applies limit to data (arrays or CSV data_rows in context).

    Returns:
        Limited data
    """
    if isinstance(data, dict):
        if "data_rows" in data:
            # CSV context: limit data_rows
            return {
                "headers": data.get("headers", []),
                "data_rows": data["data_rows"][:limit],
            }
        elif "items" in data:
            # JSON/YAML array context: limit items
            return {"items": data["items"][:limit]}
        else:
            # Dict without items or data_rows: no-op
            return data
    elif isinstance(data, list):
        # Raw list (shouldn't happen after context preparation, but handle it)
        return data[:limit]
    else:
        # No-op for other types (primitives, etc.)
        return data


def _prepare_template_context(
    data: Any, data_mime_type: str, log_id: str
) -> Dict[str, Any]:
    """
    Prepares the template rendering context based on data type and MIME type.

    Context structure follows PRD:
    - CSV: {headers: [...], data_rows: [[...]]}
    - JSON/YAML array: {items: [...]}
    - JSON/YAML dict: keys directly available
    - Primitives: {value: ...}
    - String (non-CSV): {text: ...}

    Returns:
        Context dict for Liquid template
    """
    # Determine if this is CSV data
    is_csv = data_mime_type in ["text/csv", "application/csv"]

    # Handle CSV data
    if is_csv:
        if isinstance(data, str):
            return _parse_csv_to_context(data)
        elif isinstance(data, dict) and "headers" in data and "data_rows" in data:
            # Already parsed
            return data
        else:
            log.warning(
                "%s CSV data is not string or parsed dict, wrapping as text", log_id
            )
            return {"text": str(data)}

    # Handle JSON/YAML types
    if isinstance(data, dict):
        # Dictionary: keys directly available
        return data
    elif isinstance(data, list):
        # Array: available under 'items'
        return {"items": data}
    elif isinstance(data, (str, int, float, bool)) or data is None:
        # Primitives: available under 'value'
        return {"value": data}
    else:
        # Fallback: convert to string
        return {"text": str(data)}


def render_liquid_template(
    template_content: str,
    data_artifact_content: Any,
    data_mime_type: str,
    jsonpath: Optional[str] = None,
    limit: Optional[int] = None,
    log_identifier: str = "[LiquidRenderer]",
) -> Tuple[str, Optional[str]]:
    """
    Renders a Liquid template with data from an artifact.

    Args:
        template_content: The Liquid template string
        data_artifact_content: The parsed data (string, dict, list, etc.)
        data_mime_type: MIME type of the data artifact
        jsonpath: Optional JSONPath expression to filter data
        limit: Optional limit on number of items/rows
        log_identifier: Identifier for logging

    Returns:
        Tuple of (rendered_output, error_message)
        If successful, error_message is None
        If failed, rendered_output contains error description
    """
    if not LIQUID_AVAILABLE:
        error = "Liquid templating skipped: 'python-liquid' not installed."
        log.error("%s %s", log_identifier, error)
        return f"[Template Error: {error}]", error

    try:
        # Step 1: Apply JSONPath if provided (before context preparation)
        if jsonpath:
            log.info("%s Applying JSONPath: %s", log_identifier, jsonpath)
            data_artifact_content, jsonpath_error = _apply_jsonpath_filter(
                data_artifact_content, jsonpath, log_identifier
            )
            if jsonpath_error:
                error = f"JSONPath filter failed: {jsonpath_error}"
                log.error("%s %s", log_identifier, error)
                return f"[Template Error: {error}]", error

        # Step 2: Prepare template context (parse CSV, structure data)
        log.info(
            "%s Preparing context. Data type: %s, MIME: %s",
            log_identifier,
            type(data_artifact_content).__name__,
            data_mime_type,
        )
        context = _prepare_template_context(
            data_artifact_content, data_mime_type, log_identifier
        )

        # Step 3: Apply limit if provided (after context preparation)
        if limit is not None and limit > 0:
            log.info("%s Applying limit: %d", log_identifier, limit)
            context = _apply_limit(context, limit, log_identifier)

        log.debug(
            "%s Template context keys: %s",
            log_identifier,
            list(context.keys()) if isinstance(context, dict) else "non-dict",
        )

        # Step 4: Render template
        log.info("%s Rendering Liquid template", log_identifier)
        env = Environment()
        template = env.from_string(template_content)
        rendered_output = template.render(**context)

        log.info(
            "%s Template rendered successfully. Output length: %d",
            log_identifier,
            len(rendered_output),
        )
        return rendered_output, None

    except Exception as e:
        error = f"Template rendering failed: {e}"
        log.exception("%s %s", log_identifier, error)
        return f"[Template Error: {error}]", error
