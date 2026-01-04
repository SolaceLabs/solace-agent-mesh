"""
Data formatting tools for the data-formatter skill.

These tools provide data transformation capabilities for converting
between different formats like JSON, CSV, and ASCII tables.
"""

import json
from typing import Any, Dict, Optional


def format_as_table(
    data: str,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Formats structured data as an ASCII table.

    Args:
        data: JSON string containing an array of objects to format.
        title: Optional title for the table.

    Returns:
        Dict with status and the formatted table string.
    """
    try:
        records = json.loads(data)

        if not isinstance(records, list):
            records = [records]

        if not records:
            return {"status": "success", "table": "(empty data)"}

        # Get all unique keys for columns
        columns = []
        for record in records:
            for key in record.keys():
                if key not in columns:
                    columns.append(key)

        # Calculate column widths
        widths = {col: len(str(col)) for col in columns}
        for record in records:
            for col in columns:
                val = str(record.get(col, ""))
                widths[col] = max(widths[col], len(val))

        # Build the table
        lines = []

        if title:
            lines.append(f"## {title}")
            lines.append("")

        # Header
        header = "| " + " | ".join(col.ljust(widths[col]) for col in columns) + " |"
        separator = "|-" + "-|-".join("-" * widths[col] for col in columns) + "-|"

        lines.append(header)
        lines.append(separator)

        # Rows
        for record in records:
            row = "| " + " | ".join(
                str(record.get(col, "")).ljust(widths[col]) for col in columns
            ) + " |"
            lines.append(row)

        return {"status": "success", "table": "\n".join(lines)}

    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to format table: {e}"}


def format_as_json(
    data: str,
    indent: Optional[int] = 2,
) -> Dict[str, Any]:
    """
    Formats data as pretty-printed JSON.

    Args:
        data: Data to format (JSON string or other text).
        indent: Number of spaces for indentation.

    Returns:
        Dict with status and the formatted JSON string.
    """
    try:
        # Try to parse as JSON first
        parsed = json.loads(data)
        formatted = json.dumps(parsed, indent=indent or 2, ensure_ascii=False)
        return {"status": "success", "json": formatted}

    except json.JSONDecodeError:
        # If not valid JSON, return error
        return {
            "status": "error",
            "message": "Input is not valid JSON. Please provide valid JSON data.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to format JSON: {e}"}


def format_as_csv(
    data: str,
    include_header: Optional[bool] = True,
) -> Dict[str, Any]:
    """
    Converts structured data to CSV format.

    Args:
        data: JSON string containing an array of objects.
        include_header: Whether to include column headers.

    Returns:
        Dict with status and the CSV string.
    """
    try:
        records = json.loads(data)

        if not isinstance(records, list):
            records = [records]

        if not records:
            return {"status": "success", "csv": ""}

        # Get all unique keys for columns
        columns = []
        for record in records:
            for key in record.keys():
                if key not in columns:
                    columns.append(key)

        lines = []

        # Header row
        if include_header is not False:
            lines.append(",".join(_csv_escape(col) for col in columns))

        # Data rows
        for record in records:
            row = ",".join(
                _csv_escape(str(record.get(col, ""))) for col in columns
            )
            lines.append(row)

        return {"status": "success", "csv": "\n".join(lines)}

    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to format CSV: {e}"}


def _csv_escape(value: str) -> str:
    """Escapes a value for CSV format."""
    if "," in value or '"' in value or "\n" in value:
        return '"' + value.replace('"', '""') + '"'
    return value
