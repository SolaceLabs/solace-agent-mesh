"""
Liquid template rendering with data context preparation.
"""

import logging
import csv
import io
import json
from typing import Any, Dict, Optional, Tuple
from liquid import Environment
from jsonpath_ng.ext import parse as jsonpath_parse
import yaml

log = logging.getLogger(__name__)


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


def _prepare_template_context(
    data: Any,
    data_mime_type: str,
    jsonpath: Optional[str],
    limit: Optional[int],
    log_id: str,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Prepares the template rendering context.
    This involves:
    1. Parsing raw data (e.g., JSON string) into Python objects.
    2. Applying JSONPath filter if provided.
    3. Structuring the data into the final context format (e.g., {"items": ...}).
    4. Applying a limit to the number of items/rows.

    Returns:
        A tuple of (context_dict, error_message).
    """
    # Step 1: Parse raw data into structured data if necessary
    parsed_data = data
    is_csv = data_mime_type in ["text/csv", "application/csv"]
    is_json = "json" in data_mime_type
    is_yaml = "yaml" in data_mime_type or "yml" in data_mime_type

    if isinstance(data, str):
        if is_csv:
            parsed_data = _parse_csv_to_context(data)
        elif is_json:
            try:
                parsed_data = json.loads(data)
            except json.JSONDecodeError as e:
                return {}, f"Failed to parse JSON data: {e}"
        elif is_yaml:
            try:
                parsed_data = yaml.safe_load(data)
            except yaml.YAMLError as e:
                return {}, f"Failed to parse YAML data: {e}"

    # Step 2: Apply JSONPath if provided
    if jsonpath:
        log.info("%s Applying JSONPath: %s", log_id, jsonpath)
        parsed_data, jsonpath_error = _apply_jsonpath_filter(
            parsed_data, jsonpath, log_id
        )
        if jsonpath_error:
            return {}, f"JSONPath filter failed: {jsonpath_error}"

    # Step 3: Structure the data into the final context format
    context: Dict[str, Any]
    if (
        isinstance(parsed_data, dict)
        and "headers" in parsed_data
        and "data_rows" in parsed_data
    ):
        # Already in CSV context format
        context = parsed_data
    elif isinstance(parsed_data, list):
        # Array: available under 'items'
        context = {"items": parsed_data}
    elif isinstance(parsed_data, dict):
        # Dictionary: keys directly available
        context = parsed_data
    elif isinstance(parsed_data, (str, int, float, bool)) or parsed_data is None:
        # Primitives: available under 'value'
        context = {"value": parsed_data}
    else:
        # Fallback: convert to string
        context = {"text": str(parsed_data)}

    # Step 4: Apply limit if provided
    if limit is not None and limit > 0:
        log.info("%s Applying limit: %d", log_id, limit)
        if "data_rows" in context and isinstance(context["data_rows"], list):
            context["data_rows"] = context["data_rows"][:limit]
        elif "items" in context and isinstance(context["items"], list):
            context["items"] = context["items"][:limit]

    return context, None


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
    try:
        # Prepare the template context, including parsing, filtering, and limiting
        context, error = _prepare_template_context(
            data=data_artifact_content,
            data_mime_type=data_mime_type,
            jsonpath=jsonpath,
            limit=limit,
            log_id=log_identifier,
        )
        if error:
            log.error(
                "%s Failed to prepare template context: %s", log_identifier, error
            )
            return f"[Template Error: {error}]", error

        log.debug(
            "%s Template context keys: %s",
            log_identifier,
            list(context.keys()) if isinstance(context, dict) else "non-dict",
        )

        # Render template
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
