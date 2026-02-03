"""
Common helper utilities for the HTTP SSE Gateway.
"""

def sanitize_log_input(value: str) -> str:
    """
    Sanitize user input for logging to prevent log injection (CWE-117).

    Removes newlines, carriage returns, and control characters that could
    be used to forge log entries or inject malicious content.

    Args:
        value: User-controlled string (user_id, project_id, etc.)

    Returns:
        Sanitized string safe for logging
    """
    if not value:
        return ""
    # Remove newlines, carriage returns, and other control characters (ASCII 0-31)
    return ''.join(c for c in value if ord(c) >= 32 or c == ' ')
