"""Centralized error handlers for Solace Agent Mesh."""

from typing import Tuple
from litellm.exceptions import BadRequestError


# User-facing error messages
CONTEXT_LIMIT_ERROR_MESSAGE = (
    "The conversation history has become too long for the AI model to process. "
    "This can happen after extended conversations. "
    "To continue, please start a new conversation."
)

DEFAULT_BAD_REQUEST_MESSAGE = (
    "An unexpected error occurred during tool execution. "
    "Please try your request again. If the problem persists, "
    "contact an administrator."
)


def _is_context_limit_error(exception: Exception) -> bool:
    """
    Detects if an exception is a context/token limit error from LiteLLM.
    
    Args:
        exception: The exception to check
        
    Returns:
        True if the exception indicates a context limit error
    """
    if not isinstance(exception, BadRequestError):
        return False
    
    error_str = str(exception).lower()
    
    # Context limit error patterns from various LLM providers
    context_limit_patterns = [
        "too many tokens",
        "expected maxlength:",
        "input is too long",
        "prompt is too long",
        "prompt: length: 1..",
        "too many input tokens",
    ]
    
    return any(pattern in error_str for pattern in context_limit_patterns)


def _get_user_friendly_error_message(exception: Exception) -> str:
    """
    Returns a user-friendly error message for the given exception.
    
    Args:
        exception: The exception to get a message for
        
    Returns:
        User-friendly error message string
    """
    if _is_context_limit_error(exception):
        return CONTEXT_LIMIT_ERROR_MESSAGE
    
    if isinstance(exception, BadRequestError):
        return f"Bad request: {exception}"
    
    return DEFAULT_BAD_REQUEST_MESSAGE


def get_error_message(
    exception: BadRequestError,
) -> Tuple[str, bool]:
    """
    Handles BadRequestError and returns error information.
    
    Args:
        exception: The BadRequestError to handle
        
    Returns:
        Tuple of (error_message, is_context_limit_error)
    """
    is_context_limit = _is_context_limit_error(exception)
    error_message = _get_user_friendly_error_message(exception)
    
    return error_message, is_context_limit