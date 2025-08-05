"""
Contains the Central Data Converter and Serializer functions.
"""

import json
import csv
import io
import base64
from typing import Any, Tuple, Optional, List, Dict
from solace_ai_connector.common.log import log

from .types import DataFormat
from ..mime_helpers import is_text_based_mime_type

try:
    import yaml

    PYYAML_AVAILABLE = True
except ImportError:
    PYYAML_AVAILABLE = False


def _parse_string_to_list_of_dicts(
    data_string: str, mime_type: Optional[str], log_id: str
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Parses a string into a list of dictionaries based on its MIME type.
    Supports JSON, CSV, and YAML.

    Args:
        data_string: The string to parse.
        mime_type: The MIME type of the string data.
        log_id: Identifier for logging.

    Returns:
        A tuple (parsed_data, error_message).
        parsed_data is List[Dict[str, Any]] on success, None on failure.
        error_message is a string on failure, None on success.
    """
    normalized_mime_type = (mime_type or "").lower()
    log.debug(
        "%s Parsing string to LIST_OF_DICTS, MIME: '%s'", log_id, normalized_mime_type
    )

    try:
        if "json" in normalized_mime_type:
            parsed_json = json.loads(data_string)
            if isinstance(parsed_json, list) and all(
                isinstance(item, dict) for item in parsed_json
            ):
                return parsed_json, None
            elif isinstance(parsed_json, dict):
                return [parsed_json], None
            else:
                return (
                    None,
                    "Parsed JSON is not a list of dictionaries or a single dictionary.",
                )
        elif "csv" in normalized_mime_type:
            string_io = io.StringIO(data_string)
            reader = csv.DictReader(string_io)
            return list(reader), None
        elif "yaml" in normalized_mime_type or "yml" in normalized_mime_type:
            if not PYYAML_AVAILABLE:
                return None, "YAML parsing skipped: 'PyYAML' not installed."
            parsed_yaml = yaml.safe_load(data_string)
            if isinstance(parsed_yaml, list) and all(
                isinstance(item, dict) for item in parsed_yaml
            ):
                return parsed_yaml, None
            elif isinstance(parsed_yaml, dict):
                return [parsed_yaml], None
            else:
                return (
                    None,
                    "Parsed YAML is not a list of dictionaries or a single dictionary.",
                )
        else:
            return (
                None,
                f"Unsupported MIME type '{mime_type}' for direct conversion to LIST_OF_DICTS from string.",
            )
    except json.JSONDecodeError:
        return None, "Failed to parse string as JSON"
    except csv.Error:
        return None, "Failed to parse string as CSV (DictReader)"
    except yaml.YAMLError:
        return None, "Failed to parse string as YAML"
    except Exception as e:
        return (
            None,
            f"Unexpected error parsing string to list of dicts (MIME: {mime_type}): {e}",
        )


def _detect_embedded_csv(text: str) -> bool:
    """
    Detects if a string contains valid CSV content with strict validation.

    Requirements:
    - Must have at least 2 lines (header + at least one data row)
    - Lines should contain comma-separated values

    Args:
        text: The string to check for CSV content

    Returns:
        True if the string appears to contain valid CSV content, False otherwise
    """
    if not isinstance(text, str) or not text.strip():
        return False

    lines = text.strip().split("\n")

    # Must have at least 2 lines (header + data)
    if len(lines) < 2:
        return False

    # Check that lines contain commas (basic CSV indicator)
    for line in lines:
        if "," not in line.strip():
            return False

    # Check that header and first data row have same number of fields
    try:
        header_fields = len(lines[0].split(","))
        first_row_fields = len(lines[1].split(","))
        if header_fields != first_row_fields:
            return False
    except (IndexError, AttributeError):
        return False

    return True


def _parse_embedded_csv(
    text: str, log_id: str
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Attempts to parse a string as CSV content using csv.DictReader.

    Args:
        text: The string to parse as CSV
        log_id: Identifier for logging

    Returns:
        A tuple containing:
        - List of dictionaries representing the CSV data (empty list on failure)
        - Error message string if parsing failed, None on success
    """
    if not text or not isinstance(text, str):
        return [], "Input text is empty or not a string"

    try:
        string_io = io.StringIO(text.strip())
        reader = csv.DictReader(string_io)

        # Convert to list and validate we got actual data
        rows = list(reader)

        if not rows:
            return [], "CSV parsing produced no data rows"

        # Validate that all rows have the same keys as the header and no None keys
        if rows:
            header_keys = set(rows[0].keys())
            for i, row in enumerate(rows):
                # Check for None keys (indicates extra fields)
                if None in row.keys():
                    return [], f"Row {i+1} has more fields than header"
                # Check for missing or extra fields
                if set(row.keys()) != header_keys:
                    return [], f"Row {i+1} has different fields than header"

        log.debug("%s Successfully parsed embedded CSV with %d rows", log_id, len(rows))
        return rows, None

    except csv.Error as e:
        error_msg = f"CSV parsing error: {e}"
        log.debug("%s %s", log_id, error_msg)
        return [], error_msg
    except Exception as e:
        error_msg = f"Unexpected error parsing CSV: {e}"
        log.debug("%s %s", log_id, error_msg)
        return [], error_msg


def _handle_csv_serialization(
    data: Any,
    data_format: Optional[DataFormat],
    original_mime_type: Optional[str],
    log_id: str,
) -> Tuple[str, Optional[str]]:
    """
    Enhanced CSV serialization that can handle embedded CSV strings.

    This function attempts to detect and parse embedded CSV content from:
    - Direct string values
    - Single-element lists containing strings

    Falls back to the original LIST_OF_DICTS conversion logic if no embedded CSV is detected.

    Args:
        data: The data to serialize as CSV
        data_format: The current format of the data
        original_mime_type: The original MIME type
        log_id: Identifier for logging

    Returns:
        A tuple containing:
        - The CSV string representation
        - Error message if serialization failed, None on success
    """
    # Check for single string that might contain embedded CSV
    if isinstance(data, str):
        if _detect_embedded_csv(data):
            log.debug("%s Detected embedded CSV in string data", log_id)
            parsed_data, parse_error = _parse_embedded_csv(data, log_id)
            if parse_error:
                return f"[Serialization Error: {parse_error}]", parse_error

            # Convert parsed data back to CSV format
            return _convert_list_of_dicts_to_csv(parsed_data, log_id)
        else:
            # Single string without CSV content - return error
            error_msg = "Cannot convert single string to CSV format (string does not contain valid CSV content)"
            return f"[Serialization Error: {error_msg}]", error_msg

    # Check for single-element list containing a string
    elif isinstance(data, list) and len(data) == 1 and isinstance(data[0], str):
        csv_string = data[0]
        if _detect_embedded_csv(csv_string):
            log.debug("%s Detected embedded CSV in single-element list", log_id)
            parsed_data, parse_error = _parse_embedded_csv(csv_string, log_id)
            if parse_error:
                return f"[Serialization Error: {parse_error}]", parse_error

            # Convert parsed data back to CSV format
            return _convert_list_of_dicts_to_csv(parsed_data, log_id)

    # Fall back to original logic: convert to LIST_OF_DICTS first
    log.debug(
        "%s Using standard LIST_OF_DICTS conversion for CSV serialization", log_id
    )
    list_of_dicts, _, error1 = convert_data(
        data, data_format, DataFormat.LIST_OF_DICTS, log_id, original_mime_type
    )
    if error1:
        return f"[Serialization Error: {error1}]", error1

    return _convert_list_of_dicts_to_csv(list_of_dicts, log_id)


def _convert_list_of_dicts_to_csv(
    list_of_dicts: List[Dict[str, Any]], log_id: str
) -> Tuple[str, Optional[str]]:
    """
    Converts a list of dictionaries to CSV string format.

    Args:
        list_of_dicts: The data to convert
        log_id: Identifier for logging

    Returns:
        A tuple containing:
        - The CSV string representation
        - Error message if conversion failed, None on success
    """
    try:
        if not list_of_dicts:
            return "", None

        output_io = io.StringIO()
        fieldnames = list(list_of_dicts[0].keys())
        writer = csv.DictWriter(output_io, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(list_of_dicts)
        return output_io.getvalue().strip("\r\n"), None

    except Exception as e:
        error_msg = f"Failed to format list of dicts as CSV string: {e}"
        log.warning("%s %s", log_id, error_msg)
        return f"[Serialization Error: {error_msg}]", error_msg


def convert_data(
    current_data: Any,
    current_format: Optional[DataFormat],
    target_format: DataFormat,
    log_id: str = "[Converter]",
    original_mime_type: Optional[str] = None,
) -> Tuple[Any, DataFormat, Optional[str]]:
    """
    Converts data between different internal DataFormat types, using original
    MIME type as context where necessary (e.g., BYTES -> structured).

    Args:
        current_data: The data to convert.
        current_format: The current DataFormat of the data, or None if unknown/numeric.
        target_format: The desired DataFormat.
        log_id: Identifier for logging.
        original_mime_type: The original MIME type of the data, used as a hint
                            for parsing BYTES or STRING into structured formats.

    Returns:
        A tuple containing:
        - The converted data (or original data if conversion failed).
        - The resulting DataFormat (target_format on success, current_format on failure).
        - An optional error message string if conversion failed.
    """
    current_format_name = current_format.name if current_format else "Unknown/Numeric"
    log.debug(
        "%s Attempting conversion: %s -> %s (Hint: MimeType=%s)",
        log_id,
        current_format_name,
        target_format.name,
        original_mime_type,
    )

    if current_format == target_format:
        log.debug(
            "%s No conversion needed: %s -> %s",
            log_id,
            current_format_name,
            target_format.name,
        )
        return current_data, current_format, None

    normalized_mime_type = (original_mime_type or "").lower()

    try:
        if current_format is None:
            if target_format == DataFormat.STRING:
                try:
                    return str(current_data), DataFormat.STRING, None
                except Exception as e:
                    return (
                        current_data,
                        current_format,
                        f"Failed to convert unknown/numeric type to string: {e}",
                    )
            else:
                return (
                    current_data,
                    current_format,
                    f"Cannot convert from unknown/numeric format to {target_format.name}",
                )

        elif current_format == DataFormat.BYTES:
            if target_format == DataFormat.STRING:
                if original_mime_type and is_text_based_mime_type(original_mime_type):
                    try:
                        return current_data.decode("utf-8"), DataFormat.STRING, None
                    except UnicodeDecodeError as e:
                        return (
                            current_data,
                            current_format,
                            f"Failed to decode bytes (MIME: {original_mime_type}) as UTF-8: {e}",
                        )
                else:
                    error_msg = f"Cannot convert binary data (MIME: {original_mime_type or 'unknown'}) to a general string. This conversion is only supported for text-based MIME types."
                    log.warning("%s %s", log_id, error_msg)
                    return current_data, current_format, error_msg
            elif target_format == DataFormat.JSON_OBJECT:
                if not normalized_mime_type.startswith(
                    "application/json"
                ) and not normalized_mime_type.startswith("text/json"):
                    return (
                        current_data,
                        current_format,
                        f"Cannot convert BYTES to JSON_OBJECT: Original MIME type '{original_mime_type}' is not JSON.",
                    )
                try:
                    string_data = current_data.decode("utf-8")
                    return json.loads(string_data), DataFormat.JSON_OBJECT, None
                except UnicodeDecodeError as e:
                    return (
                        current_data,
                        current_format,
                        f"Failed to decode bytes as UTF-8 before JSON parsing: {e}",
                    )
                except json.JSONDecodeError as e:
                    return (
                        current_data,
                        current_format,
                        f"Failed to parse decoded bytes as JSON: {e}",
                    )
            elif target_format == DataFormat.LIST_OF_DICTS:
                if not normalized_mime_type.startswith("text/csv"):
                    return (
                        current_data,
                        current_format,
                        f"Cannot convert BYTES to LIST_OF_DICTS: Original MIME type '{original_mime_type}' is not CSV.",
                    )
                try:
                    string_data = current_data.decode("utf-8")
                    string_io = io.StringIO(string_data)
                    reader = csv.DictReader(string_io)
                    return list(reader), DataFormat.LIST_OF_DICTS, None
                except UnicodeDecodeError as e:
                    return (
                        current_data,
                        current_format,
                        f"Failed to decode bytes as UTF-8 before CSV parsing: {e}",
                    )
                except csv.Error as e:
                    return (
                        current_data,
                        current_format,
                        f"Failed to parse decoded bytes as CSV (DictReader): {e}",
                    )
                except Exception as e:
                    return (
                        current_data,
                        current_format,
                        f"Unexpected error parsing decoded bytes as CSV: {e}",
                    )

        elif current_format == DataFormat.STRING:
            if target_format == DataFormat.BYTES:
                try:
                    return current_data.encode("utf-8"), DataFormat.BYTES, None
                except Exception as e:
                    return (
                        current_data,
                        current_format,
                        f"Failed to encode string to UTF-8 bytes: {e}",
                    )
            elif target_format == DataFormat.JSON_OBJECT:
                try:
                    return json.loads(current_data), DataFormat.JSON_OBJECT, None
                except json.JSONDecodeError:
                    return (
                        current_data,
                        current_format,
                        "Failed to parse string as JSON",
                    )
            elif target_format == DataFormat.LIST_OF_DICTS:
                parsed_data, error_msg = _parse_string_to_list_of_dicts(
                    data_string=current_data,
                    mime_type=original_mime_type,
                    log_id=log_id,
                )
                if error_msg:
                    return current_data, current_format, error_msg
                return parsed_data, DataFormat.LIST_OF_DICTS, None

        elif current_format == DataFormat.JSON_OBJECT:
            if target_format == DataFormat.STRING:
                try:
                    # Special handling for arrays of strings - convert to newline-separated format
                    # This fixes the issue where jsonpath results need to be processed line-by-line by grep
                    if isinstance(current_data, list) and all(
                        isinstance(item, str) for item in current_data
                    ):
                        result = "\n".join(current_data)
                        log.error(
                            "%s [DEBUG] Converted array of strings to newline-separated format: %s",
                            log_id,
                            result[:100] + ("..." if len(result) > 100 else ""),
                        )
                        return result, DataFormat.STRING, None
                    else:
                        result = json.dumps(current_data, separators=(",", ":"))
                        log.error(
                            "%s [DEBUG] Converted JSON object to JSON string: %s",
                            log_id,
                            result[:100] + ("..." if len(result) > 100 else ""),
                        )
                        return result, DataFormat.STRING, None
                except TypeError as e:
                    return (
                        current_data,
                        current_format,
                        f"Failed to serialize JSON object to string: {e}",
                    )
            elif target_format == DataFormat.LIST_OF_DICTS:
                if isinstance(current_data, list) and all(
                    isinstance(item, dict) for item in current_data
                ):
                    return current_data, DataFormat.LIST_OF_DICTS, None
                else:
                    return (
                        current_data,
                        current_format,
                        "JSON object is not a list of dictionaries",
                    )

        elif current_format == DataFormat.LIST_OF_DICTS:
            if target_format == DataFormat.STRING:
                try:
                    if not current_data:
                        return "", DataFormat.STRING, None
                    output_io = io.StringIO()
                    fieldnames = list(current_data[0].keys())
                    writer = csv.DictWriter(output_io, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(current_data)
                    return output_io.getvalue().strip("\r\n"), DataFormat.STRING, None
                except IndexError:
                    return "", DataFormat.STRING, None
                except Exception as e:
                    return (
                        current_data,
                        current_format,
                        f"Failed to format list of dicts as CSV string: {e}",
                    )
            elif target_format == DataFormat.JSON_OBJECT:
                return current_data, DataFormat.JSON_OBJECT, None

        error_msg = f"Unsupported conversion requested: {current_format_name} -> {target_format.name}"
        log.warning("%s %s", log_id, error_msg)
        return current_data, current_format, error_msg

    except Exception as e:
        error_msg = f"Unexpected error during conversion from {current_format_name} to {target_format.name}: {e}"
        log.exception("%s %s", log_id, error_msg)
        return current_data, current_format, error_msg


def serialize_data(
    data: Any,
    data_format: Optional[DataFormat],
    target_string_format: Optional[str],
    original_mime_type: Optional[str],
    log_id: str = "[Serializer]",
) -> Tuple[str, Optional[str]]:
    """
    Converts data from its internal DataFormat into the target string representation.
    Handles Python format specifiers for numeric types.

    Args:
        data: The data to serialize.
        data_format: The current DataFormat of the data, or None if unknown/numeric.
        target_string_format: The desired final string format (e.g., "text", "json", "datauri", or Python format spec like ".2f").
                              If None or empty, defaults to "text".
        original_mime_type: The original MIME type of the artifact (needed for datauri).
        log_id: Identifier for logging.

    Returns:
        A tuple containing:
        - The final serialized string.
        - An optional error message string if serialization failed.
    """
    target_fmt = (target_string_format or "text").strip()
    log.debug(
        "%s Serializing data from %s to format '%s'",
        log_id,
        data_format.name if data_format else "Unknown/Numeric",
        target_fmt,
    )

    try:
        if isinstance(data, (int, float)) and target_string_format:
            is_format_spec = target_fmt.startswith(".") or any(
                c in target_fmt for c in "defg%"
            )
            if is_format_spec:
                try:
                    formatted_string = format(data, target_fmt)
                    log.debug(
                        "%s Applied Python format specifier '%s' to numeric data.",
                        log_id,
                        target_fmt,
                    )
                    return formatted_string, None
                except ValueError as fmt_err:
                    err_msg = f"Invalid format specifier '{target_fmt}' for numeric data type {type(data).__name__}: {fmt_err}"
                    log.warning("%s %s", log_id, err_msg)
                except Exception as e:
                    err_msg = f"Error applying format specifier '{target_fmt}': {e}"
                    log.warning("%s %s", log_id, err_msg)
        target_fmt_lower = target_fmt.lower()

        if target_fmt_lower == "text":
            string_data, _, error = convert_data(
                data, data_format, DataFormat.STRING, log_id, original_mime_type
            )
            if error:
                return f"[Serialization Error: {error}]", error
            return string_data, None

        elif target_fmt_lower == "json":
            json_obj, _, error = convert_data(
                data, data_format, DataFormat.JSON_OBJECT, log_id, original_mime_type
            )
            if error:
                return f"[Serialization Error: {error}]", error
            try:
                return json.dumps(json_obj, separators=(",", ":")), None
            except TypeError as e:
                err_msg = f"Failed to serialize to JSON string: {e}"
                return f"[Serialization Error: {err_msg}]", err_msg

        elif target_fmt_lower == "json_pretty":
            json_obj, _, error = convert_data(
                data, data_format, DataFormat.JSON_OBJECT, log_id, original_mime_type
            )
            if error:
                return f"[Serialization Error: {error}]", error
            try:
                return json.dumps(json_obj, indent=2), None
            except TypeError as e:
                err_msg = f"Failed to serialize to pretty JSON string: {e}"
                return f"[Serialization Error: {err_msg}]", err_msg

        elif target_fmt_lower == "csv":
            return _handle_csv_serialization(
                data, data_format, original_mime_type, log_id
            )

        elif target_fmt_lower == "datauri":
            byte_data, _, error = convert_data(
                data, data_format, DataFormat.BYTES, log_id, original_mime_type
            )
            if error:
                return f"[Serialization Error: {error}]", error

            if not original_mime_type:
                err_msg = "Original MIME type required for datauri format"
                return f"[Serialization Error: {err_msg}]", err_msg
            try:
                encoded = base64.b64encode(byte_data).decode("utf-8")
                return f"data:{original_mime_type};base64,{encoded}", None
            except Exception as e:
                err_msg = f"Failed to encode datauri: {e}"
                return f"[Serialization Error: {err_msg}]", err_msg

        else:
            log.warning(
                "%s Unknown target format '%s'. Defaulting to 'text'.",
                log_id,
                target_fmt,
            )
            string_data, _, error = convert_data(
                data, data_format, DataFormat.STRING, log_id, original_mime_type
            )  # Pass mime type hint
            if error:
                return f"[Serialization Error: {error}]", error
            return string_data, None

    except Exception as e:
        error_msg = f"Unexpected error during serialization to '{target_fmt}': {e}"
        log.exception("%s %s", log_id, error_msg)
        return f"[Serialization Error: {error_msg}]", error_msg
