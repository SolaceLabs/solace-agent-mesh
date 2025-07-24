"""
Provides debugging utilities for the declarative test framework,
including a pretty-printer for A2A event history.
"""

import json
from datetime import datetime
from typing import List, Dict, Any


def _truncate(s: str, max_len: int) -> str:
    """Truncates a string if it exceeds max_len, appending '...'."""
    if not isinstance(s, str):
        s = str(s)
    if max_len <= 0 or len(s) <= max_len:
        return s
    if max_len <= 3:
        return s[:max_len]
    return s[: max_len - 3] + "..."


def _format_a2a_parts(parts: List[Dict], max_string_length: int) -> str:
    """Helper to format A2A message parts into a readable string."""
    if not parts:
        return "[No Parts]"

    formatted_parts = []
    for part in parts:
        part_type = part.get("type", "unknown")
        if part_type == "text":
            text = part.get("text", "")
            formatted_parts.append(
                f"  - [Text]: '{_truncate(text, max_string_length)}'"
            )
        elif part_type == "data":
            data_content = json.dumps(part.get("data", {}))
            formatted_parts.append(
                f"  - [Data]: {_truncate(data_content, max_string_length)}"
            )
        elif part_type == "file":
            file_info = part.get("file", {})
            name = file_info.get("name", "N/A")
            mime = file_info.get("mimeType", "N/A")
            formatted_parts.append(
                f"  - [File]: {_truncate(name, max_string_length)} ({mime})"
            )
        else:
            part_str = json.dumps(part)
            formatted_parts.append(
                f"  - [Unknown Part]: {_truncate(part_str, max_string_length)}"
            )
    return "\n".join(formatted_parts)


def _truncate_dict_strings(data: Any, max_len: int) -> Any:
    """Recursively traverses a dict/list and truncates all string values."""
    if max_len <= 0:
        return data
    if isinstance(data, dict):
        return {k: _truncate_dict_strings(v, max_len) for k, v in data.items()}
    elif isinstance(data, list):
        return [_truncate_dict_strings(item, max_len) for item in data]
    elif isinstance(data, str):
        return _truncate(data, max_len)
    else:
        return data


def pretty_print_event_history(
    event_history: List[Dict[str, Any]], max_string_length: int = 200
):
    """
    Formats and prints a list of A2A event payloads for debugging.
    """
    if not event_history:
        print("\n" + "=" * 25 + " NO EVENTS RECORDED " + "=" * 25)
        print("--- The test failed before any events were received from the agent. ---")
        print("=" * 70 + "\n")
        return

    print("\n" + "=" * 25 + " TASK EVENT HISTORY " + "=" * 25)
    for i, event_payload in enumerate(event_history):
        print(f"\n--- Event {i+1} ---")

        event_type = "Unknown Event"
        details = ""

        result = event_payload.get("result", {})
        error = event_payload.get("error")

        if error:
            event_type = "Error Response"
            details += f"  Error Code: {error.get('code')}\n"
            details += f"  Error Message: {_truncate(error.get('message'), max_string_length)}\n"

        elif result.get("status") and result.get("final") is not None:
            event_type = "Task Status Update"
            status = result.get("status", {})
            state = status.get("state", "UNKNOWN")
            message = status.get("message", {})
            parts = message.get("parts", [])
            details += f"  State: {state}\n"
            details += f"  Parts:\n{_format_a2a_parts(parts, max_string_length)}\n"

        elif result.get("status") and result.get("sessionId"):
            event_type = "Final Task Response"
            status = result.get("status", {})
            state = status.get("state", "UNKNOWN")
            message = status.get("message", {})
            parts = message.get("parts", [])
            details += f"  Final State: {state}\n"
            details += (
                f"  Final Parts:\n{_format_a2a_parts(parts, max_string_length)}\n"
            )
            if result.get("artifacts"):
                artifacts_str = json.dumps(result.get("artifacts"))
                details += (
                    f"  Artifacts: {_truncate(artifacts_str, max_string_length)}\n"
                )

        elif result.get("artifact"):
            event_type = "Task Artifact Update"
            artifact = result.get("artifact", {})
            details += f"  Artifact Name: {_truncate(artifact.get('name'), max_string_length)}\n"
            details += f"  Artifact Parts:\n{_format_a2a_parts(artifact.get('parts', []), max_string_length)}\n"

        print(f"Type: {event_type}")
        if details:
            print(details, end="")

        print("Raw Payload:")
        truncated_payload = _truncate_dict_strings(event_payload, max_string_length)
        print(json.dumps(truncated_payload, indent=2))

    print("=" * 70 + "\n")
