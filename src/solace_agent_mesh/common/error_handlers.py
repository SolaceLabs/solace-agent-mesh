"""Centralized error handlers for Solace Agent Mesh."""

from typing import Tuple

from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    BudgetExceededError,
    ContentPolicyViolationError,
    ContextWindowExceededError,
    APIConnectionError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)


# Tuple of all recognized litellm exception types, for use in except clauses
LITELLM_EXCEPTIONS = (
    AuthenticationError,
    BadRequestError,
    BudgetExceededError,
    ContentPolicyViolationError,
    ContextWindowExceededError,
    APIConnectionError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)


# User-facing error messages
CONTEXT_LIMIT_ERROR_MESSAGE = (
    "The conversation history has become too long for the AI model to process. "
    "This can happen after extended conversations. "
    "To continue, please start a new conversation."
)

DEFAULT_BAD_REQUEST_MESSAGE = (
    "The LLM service rejected the request. "
    "Please try rephrasing your message. If the problem persists, "
    "contact an administrator."
)

AUTHENTICATION_ERROR_MESSAGE = (
    "The LLM service rejected the authentication credentials. "
    "Please contact an administrator to verify the API key or authentication configuration."
)

RATE_LIMIT_ERROR_MESSAGE = (
    "The LLM service rate limit has been exceeded. "
    "Please wait a moment and try again. If this persists, "
    "contact an administrator to review rate limits or upgrade the plan."
)

SERVICE_UNAVAILABLE_ERROR_MESSAGE = (
    "The LLM service is temporarily unavailable. "
    "Please try again in a few minutes. If the problem persists, "
    "contact an administrator to check the service status."
)

API_CONNECTION_ERROR_MESSAGE = (
    "Unable to connect to the LLM service. "
    "This may be due to a network issue or incorrect endpoint configuration. "
    "Please contact an administrator to verify the connection settings."
)

TIMEOUT_ERROR_MESSAGE = (
    "The request to the LLM service timed out. "
    "This may be due to high load or a complex request. "
    "Please try again. If this persists, contact an administrator."
)

CONTENT_POLICY_VIOLATION_MESSAGE = (
    "The request was blocked by the LLM provider's content safety filters. "
    "Please rephrase your request and try again."
)

NOT_FOUND_ERROR_MESSAGE = (
    "The configured LLM model was not found. "
    "Please contact an administrator to verify the model name and provider configuration."
)

PERMISSION_DENIED_ERROR_MESSAGE = (
    "Access to the LLM model was denied. "
    "Please contact an administrator to verify the API permissions and access configuration."
)

INTERNAL_SERVER_ERROR_MESSAGE = (
    "The LLM service encountered an internal error. "
    "This is a temporary issue on the provider's side. "
    "Please try again. If this persists, contact an administrator."
)

BUDGET_EXCEEDED_ERROR_MESSAGE = (
    "The LLM usage budget has been exceeded. "
    "Please contact an administrator to review and adjust the budget limits."
)

DEFAULT_LLM_ERROR_MESSAGE = (
    "An error occurred while communicating with the LLM service. "
    "Please try again. If the problem persists, contact an administrator."
)


def is_llm_exception(exception: Exception) -> bool:
    """Check if the exception is a known litellm exception type."""
    return isinstance(exception, LITELLM_EXCEPTIONS)


def _is_context_limit_error(exception: Exception) -> bool:
    """
    Detects if an exception is a context/token limit error from LiteLLM.

    Args:
        exception: The exception to check

    Returns:
        True if the exception indicates a context limit error
    """
    if isinstance(exception, ContextWindowExceededError):
        return True

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

    # Check subclasses before BadRequestError base class
    if isinstance(exception, ContentPolicyViolationError):
        return CONTENT_POLICY_VIOLATION_MESSAGE

    if isinstance(exception, BadRequestError):
        return DEFAULT_BAD_REQUEST_MESSAGE

    if isinstance(exception, AuthenticationError):
        return AUTHENTICATION_ERROR_MESSAGE

    if isinstance(exception, RateLimitError):
        return RATE_LIMIT_ERROR_MESSAGE

    if isinstance(exception, ServiceUnavailableError):
        return SERVICE_UNAVAILABLE_ERROR_MESSAGE

    if isinstance(exception, APIConnectionError):
        return API_CONNECTION_ERROR_MESSAGE

    if isinstance(exception, Timeout):
        return TIMEOUT_ERROR_MESSAGE

    if isinstance(exception, NotFoundError):
        return NOT_FOUND_ERROR_MESSAGE

    if isinstance(exception, PermissionDeniedError):
        return PERMISSION_DENIED_ERROR_MESSAGE

    if isinstance(exception, InternalServerError):
        return INTERNAL_SERVER_ERROR_MESSAGE

    if isinstance(exception, BudgetExceededError):
        return BUDGET_EXCEEDED_ERROR_MESSAGE

    return DEFAULT_LLM_ERROR_MESSAGE


def get_error_message(
    exception: Exception,
) -> Tuple[str, bool]:
    """
    Handles LLM-related exceptions and returns error information.

    Args:
        exception: The exception to handle

    Returns:
        Tuple of (error_message, is_context_limit_error)
    """
    is_context_limit = _is_context_limit_error(exception)
    error_message = _get_user_friendly_error_message(exception)

    return error_message, is_context_limit
